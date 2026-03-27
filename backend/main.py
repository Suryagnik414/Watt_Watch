from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
import tempfile
import os
import base64
import numpy as np
import cv2
import torch

# Import YOLO after torch to avoid DLL issues
try:
    from ultralytics import YOLO
except ImportError as e:
    print(f"[ERROR] Failed to import YOLO: {e}")
    print("Try running: pip uninstall torch -y && pip install torch --index-url https://download.pytorch.org/whl/cu130")
    raise

from pose_utils import (
    COCO_SKELETON_MAP, KEYPOINT_CONFIDENCE_THRESHOLD, MODEL_CONFIDENCE_THRESHOLD,
    draw_skeleton_on_image, load_image_safe
)

# PHASE 0: Import canonical schemas and state machine
from schemas import RoomEvent, ApplianceDetection, AuditResponse
from state_machine import RoomStateMachine
from datetime import datetime
import time

# PHASE 3: Import event logger
from event_logger import get_event_logger

# PHASE 1: Import camera sampler and state tracker
from camera_sampler import CameraFrameSampler, CameraConfig, FrameProcessor, get_camera_sampler, stop_all_samplers
from state_machine import StateTracker

app = FastAPI(title="Watt Watch API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create annotated_images directory at startup (avoid per-request file I/O)
ANNOTATED_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "annotated_images")
os.makedirs(ANNOTATED_IMAGES_DIR, exist_ok=True)

# GPU/Device Configuration
try:
    DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    CUDA_AVAILABLE = torch.cuda.is_available()
except Exception as e:
    print(f"[WARN] Error checking CUDA availability: {e}")
    DEVICE = "cpu"
    CUDA_AVAILABLE = False

@app.on_event("startup")
async def startup_event():
    """Initialize on startup: ensure output directory and log device info."""
    os.makedirs(ANNOTATED_IMAGES_DIR, exist_ok=True)

    # Log GPU info
    if CUDA_AVAILABLE:
        print(f"✓ CUDA GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f}GB")
        print(f"  CUDA Version: {torch.version.cuda}")
    else:
        print("⚠ No CUDA GPU available, using CPU (slower inference)")
    print(f"  Device: {DEVICE}")

# Model weight names
YOLO_POSE_MODEL = "yolov8x-pose-p6.pt"
YOLO_DETECT_MODEL = "yolov8x.pt"

# Appliance detection settings
APPLIANCE_CLASSES = {
    62: "Projector/TV",
    63: "Laptop"
}
SKELETON_MAP = [(16,14),(14,12),(17,15),(15,13),(12,13),(6,12),(7,13),
                (6,7),(6,8),(7,9),(8,10),(9,11),(2,3),(1,2),(1,3),(2,4),(3,5)]


def _load_yolo_model(weight_name: str, device: str = DEVICE):
    """Load YOLO model on specified device (GPU or CPU)."""
    try:
        model = YOLO(weight_name)
        model.to(device)  # Move model to GPU/CPU
        return model
    except FileNotFoundError:
        raise RuntimeError(f"Model weight '{weight_name}' not found locally. Please ensure {weight_name} is in the backend directory.")


# Load both models once at startup on GPU
pose_model = _load_yolo_model(YOLO_POSE_MODEL, DEVICE)
detect_model = _load_yolo_model(YOLO_DETECT_MODEL, DEVICE)


class BoundingBox(BaseModel):
    class_id: int
    class_name: Optional[str]
    confidence: float
    xyxy: List[float]  # [x_min, y_min, x_max, y_max]


class Keypoint(BaseModel):
    x: float
    y: float
    confidence: float


class PoseDetection(BaseModel):
    class_id: int
    class_name: Optional[str]
    confidence: float
    xyxy: List[float]  # [x_min, y_min, x_max, y_max]
    keypoints: List[Keypoint]  # 17 COCO keypoints


class DetectionResult(BaseModel):
    file_name: str
    height: Optional[int]
    width: Optional[int]
    detections: Optional[List[PoseDetection]]


class InferenceResponse(BaseModel):
    results: List[DetectionResult]


# Use canonical ApplianceDetection from schemas.py to keep PHASE 0 contract stable


class AuditResult(BaseModel):
    file_name: str
    height: Optional[int]
    width: Optional[int]
    person_count: int
    appliances: List[ApplianceDetection]
    energy_waste_detected: bool
    energy_saved_kwh: float
    pose_detections: Optional[List[PoseDetection]]
    annotated_image_path: Optional[str] = None


class DashboardAuditResponse(BaseModel):
    file_name: str
    person_count: int
    active_appliances: int
    energy_waste_detected: bool
    l_thresh: int
    s_thresh: int
    ghost_image_base64: Optional[str] = None
    annotated_image_path: Optional[str] = None


def _parse_pose_detections(result, classes: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    detections_out = []
    if result.boxes is None or len(result.boxes) == 0:
        return detections_out

    for idx, box in enumerate(result.boxes):
        class_id = int(box.cls[0].item())
        if classes is not None and len(classes) > 0 and class_id not in classes:
            continue

        xyxy = box.xyxy[0].tolist()
        conf = float(box.conf[0].item())

        # Extract keypoints for this person
        keypoints_list = []
        if result.keypoints is not None and idx < len(result.keypoints.data):
            kpts = result.keypoints.data[idx].cpu().numpy()  # [17, 3] -> (x, y, confidence)
            for x, y, conf_kpt in kpts:
                keypoints_list.append({
                    "x": round(float(x), 4),
                    "y": round(float(y), 4),
                    "confidence": round(float(conf_kpt), 4)
                })

        detections_out.append({
            "class_id": class_id,
            "class_name": result.names.get(class_id, None) if hasattr(result, "names") else None,
            "confidence": round(conf, 4),
            "xyxy": [round(x, 4) for x in xyxy],
            "keypoints": keypoints_list if keypoints_list else None
        })

    return detections_out


def draw_detection_boxes(image: np.ndarray, detection_json: Dict[str, Any]) -> np.ndarray:
    """
    Draw detection boxes with keypoint skeleton on image.

    Args:
        image: Image array (cv2 format, BGR)
        detection_json: Detection result JSON containing pose detections

    Returns:
        Modified image with annotations drawn
    """
    detections = detection_json.get("detections", [])

    # Draw bounding boxes and pose skeletons
    for detection in detections:
        xyxy = detection.get("xyxy", [])
        x_min, y_min, x_max, y_max = map(int, xyxy)
        confidence = detection.get("confidence", 0.0)
        keypoints = detection.get("keypoints", [])

        # Draw bounding box (cyan)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (255, 255, 0), 2)

        # Draw skeleton using shared utility
        if keypoints:
            draw_skeleton_on_image(image, keypoints, COCO_SKELETON_MAP, KEYPOINT_CONFIDENCE_THRESHOLD)

        # Add label with confidence
        label = f"Person: {confidence:.2f}"
        (label_width, label_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(image, (x_min, y_min - label_height - baseline - 5),
                     (x_min + label_width, y_min), (255, 255, 0), -1)
        cv2.putText(image, label, (x_min, y_min - baseline - 2),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return image


def analyze_appliance_status(image: np.ndarray, bbox: List[float], sensitivity: int = 160) -> Tuple[str, int]:
    """
    Analyze appliance status based on brightness within bounding box.

    Args:
        image: Input image (BGR format)
        bbox: Bounding box coordinates [x_min, y_min, x_max, y_max]
        sensitivity: Brightness threshold (0-255, default 160)

    Returns:
        Tuple of (status, brightness) where status is "ON" or "OFF"
    """
    x1, y1, x2, y2 = map(int, bbox)

    # Ensure coordinates are within image bounds
    h, w = image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x1 >= x2 or y1 >= y2:
        return "OFF", 0

    crop = image[y1:y2, x1:x2]
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    brightness = int(np.mean(gray_crop))
    status = "ON" if brightness > sensitivity else "OFF"

    return status, brightness


def detect_appliances(image: np.ndarray, sensitivity: int = 160) -> List[Dict]:
    """
    Detect appliances (projectors/TVs and laptops) in the image.

    Args:
        image: Input image (BGR format)
        sensitivity: Brightness threshold for ON/OFF detection

    Returns:
        List of appliance detections with status information
    """
    appliances = []

    # Run appliance detection
    detect_results = detect_model.predict(
        source=image, imgsz=1280, conf=0.15, device=DEVICE, verbose=False
    )[0]

    if detect_results.boxes is not None:
        for box in detect_results.boxes:
            class_id = int(box.cls[0])
            if class_id in APPLIANCE_CLASSES:
                xyxy = box.xyxy[0].tolist()
                confidence = float(box.conf[0])

                # Analyze appliance status based on brightness
                status, brightness = analyze_appliance_status(image, xyxy, sensitivity)

                appliances.append({
                    "name": APPLIANCE_CLASSES[class_id],
                    "status": status,
                    "brightness": brightness,
                    "confidence": round(confidence, 4),
                    "xyxy": [round(x, 4) for x in xyxy]
                })

    return appliances


def detect_appliances_optimized(image: np.ndarray, sensitivity: int = 160) -> List[Dict]:
    """
    OPTIMIZED: Detect appliances with reduced resolution for real-time performance.

    Args:
        image: Input image (BGR format)
        sensitivity: Brightness threshold for ON/OFF detection

    Returns:
        List of appliance detections with status information
    """
    appliances = []

    try:
        # Run appliance detection with OPTIMIZED settings
        detect_results = detect_model.predict(
            source=image, imgsz=640, conf=0.25, device=DEVICE, verbose=False  # Reduced from 1280 to 640, higher conf
        )[0]

        if detect_results.boxes is not None:
            for box in detect_results.boxes:
                class_id = int(box.cls[0])
                if class_id in APPLIANCE_CLASSES:
                    xyxy = box.xyxy[0].tolist()
                    confidence = float(box.conf[0])

                    # Analyze appliance status based on brightness
                    status, brightness = analyze_appliance_status(image, xyxy, sensitivity)

                    appliances.append({
                        "name": APPLIANCE_CLASSES[class_id],
                        "status": status,
                        "brightness": brightness,
                        "confidence": round(confidence, 4),
                        "xyxy": [round(x, 4) for x in xyxy]
                    })

    except Exception as e:
        print(f"[WARN] Optimized appliance detection failed: {e}")
        # Return empty list to prevent system crash

    return appliances


def check_energy_waste(person_count: int, appliances: List[Dict]) -> Tuple[bool, float]:
    """
    Check if energy waste is detected based on occupancy and appliance status.

    Args:
        person_count: Number of people detected
        appliances: List of appliance detections with status

    Returns:
        Tuple of (waste_detected, energy_saved_kwh)
    """
    waste_detected = False

    # Check if any appliances are ON when no people are present
    if person_count == 0:
        for appliance in appliances:
            if appliance["status"] == "ON":
                waste_detected = True
                break

    # Calculate energy saved (simple estimation)
    energy_saved = 0.45 if not waste_detected else 0.00

    return waste_detected, energy_saved


def run_audit(frame: np.ndarray, l_thresh: int = 235, s_thresh: int = 165) -> Tuple[np.ndarray, int, bool, int]:
    """
    Run a lightweight audit flow for dashboard-style live analysis.

    Args:
        frame: Input image frame (BGR)
        l_thresh: Light threshold for ceiling lamp detection (0-255)
        s_thresh: Screen brightness threshold for appliance active state

    Returns:
        ghost: Privacy-preserving blurred frame with skeleton + boxes
        person_count: Number of detected people in the frame
        energy_waste_detected: True when room has no people but lights/screens are on
        active_appliance_count: Count of detected lighting/screen structures
    """
    h, w = frame.shape[:2]

    # Start with privacy blur
    ghost = cv2.GaussianBlur(frame.copy(), (99, 99), 30)

    # Pose detection
    pose_res = pose_model.predict(source=frame, imgsz=1280, conf=0.15, device=DEVICE, verbose=False)[0]
    person_count = len(pose_res.boxes) if pose_res.boxes is not None else 0

    # Draw skeleton on ghost view
    if pose_res.keypoints is not None:
        for kpts_obj in pose_res.keypoints.data:
            kpts = kpts_obj.cpu().numpy()
            for start, end in SKELETON_MAP:
                pt1, pt2 = kpts[start-1], kpts[end-1]
                if pt1[2] > 0.3 and pt2[2] > 0.3:
                    cv2.line(ghost,
                             (int(pt1[0]), int(pt1[1])),
                             (int(pt2[0]), int(pt2[1])),
                             (0, 255, 255), 2)

    # Light detection (ceiling region)
    ceiling = frame[0:int(h*0.45), 0:w]
    gray = cv2.cvtColor(ceiling, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, l_thresh, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lights = sum(1 for c in contours if cv2.contourArea(c) > 60)

    # Appliance/screen detection using object detector
    det_res = detect_model.predict(source=frame, imgsz=1280, conf=0.5, device=DEVICE, verbose=False)[0]
    screens = 0
    if det_res.boxes is not None:
        for box in det_res.boxes:
            class_id = int(box.cls[0])
            if class_id in APPLIANCE_CLASSES:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                if (x2 - x1) <= 0 or (y2 - y1) <= 0:
                    continue
                if (x2 - x1) * (y2 - y1) < 8000:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                mean_brightness = float(np.mean(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)))
                if mean_brightness > s_thresh:
                    screens += 1
                    cv2.rectangle(ghost, (x1, y1), (x2, y2), (0, 255, 0), 3)

    active_appliances = lights + screens
    energy_waste_detected = (person_count == 0 and active_appliances > 0)

    return ghost, person_count, energy_waste_detected, active_appliances


def create_ghost_view(image: np.ndarray, pose_results) -> np.ndarray:
    """
    Create a privacy-enabled "ghost" view with heavy blur and pose skeletons.

    Args:
        image: Input image (BGR format)
        pose_results: YOLO pose detection results

    Returns:
        Blurred image with pose skeletons drawn
    """
    # Apply heavy Gaussian blur for privacy
    ghost_view = cv2.GaussianBlur(image.copy(), (99, 99), 30)

    # Draw pose skeletons
    if pose_results.keypoints is not None:
        for kpts_obj in pose_results.keypoints.data:
            kpts = kpts_obj.cpu().numpy()
            for start, end in SKELETON_MAP:
                if start <= len(kpts) and end <= len(kpts):
                    pt1, pt2 = kpts[start-1], kpts[end-1]
                    # Check both confidence and that points are not at origin (0,0)
                    if (pt1[2] > 0.15 and pt2[2] > 0.15 and
                        pt1[0] > 0 and pt1[1] > 0 and
                        pt2[0] > 0 and pt2[1] > 0):
                        cv2.line(ghost_view,
                               (int(pt1[0]), int(pt1[1])),
                               (int(pt2[0]), int(pt2[1])),
                               (0, 255, 255), 2)

    return ghost_view


def draw_audit_annotations(image: np.ndarray, pose_detections: List[Dict], appliances: List[Dict]) -> np.ndarray:
    """
    Draw both pose and appliance annotations on the image.

    Args:
        image: Input image (BGR format)
        pose_detections: List of pose detection results
        appliances: List of appliance detection results

    Returns:
        Annotated image
    """
    annotated_img = image.copy()

    # Draw pose detections (reuse existing logic)
    detection_data = {"detections": pose_detections}
    annotated_img = draw_detection_boxes(annotated_img, detection_data)

    # Draw appliance detections
    for appliance in appliances:
        xyxy = appliance["xyxy"]
        x1, y1, x2, y2 = map(int, xyxy)
        status = appliance["status"]
        brightness = appliance["brightness"]
        name = appliance["name"]

        # Color based on status
        color = (0, 255, 0) if status == "ON" else (0, 0, 255)

        # Draw bounding box
        cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 4)

        # Add status label
        label = f"{name}: {status} (B:{brightness})"
        (label_width, label_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(annotated_img, (x1, y1 - label_height - baseline - 5),
                     (x1 + label_width, y1), color, -1)
        cv2.putText(annotated_img, label, (x1, y1 - baseline - 2),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return annotated_img


def _process_single_image(image: np.ndarray, filename: str, classes: Optional[List[int]] = None) -> Dict[str, Any]:
    """Process image with YOLOv8x-Pose on GPU and return pose detection results.

    Args:
        image: Image array (cv2 format, BGR) - already loaded from disk
        filename: Original filename for the result record
        classes: Optional class filter (person=0)

    Returns:
        Dict with detection results {file_name, height, width, detections}
    """
    # Run inference on pre-loaded image array on GPU (avoids redundant disk read)
    pose_results = pose_model.predict(source=image, classes=classes, verbose=False, device=DEVICE)

    final_result = {
        "file_name": filename,
        "height": image.shape[0],
        "width": image.shape[1],
        "detections": [],
    }

    if pose_results is not None and len(pose_results) > 0:
        res = pose_results[0]
        final_result["detections"] = _parse_pose_detections(res, classes)

    return final_result


@app.get("/")
async def root():
    return {"message": "Welcome to Watt Watch API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/device")
async def get_device_info():
    """Get information about the device being used (GPU or CPU)."""
    if CUDA_AVAILABLE:
        return {
            "device": DEVICE,
            "cuda_available": True,
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2),
            "cuda_version": torch.version.cuda,
        }
    else:
        return {
            "device": DEVICE,
            "cuda_available": False,
            "message": "Running on CPU (slower inference)"
        }


@app.post("/detect", response_model=InferenceResponse)
async def detect_image(
    file: UploadFile = File(...),
    classes: Optional[List[int]] = Query([0], description="Class IDs to keep (person=0)"),
    save_annotated: Optional[bool] = Query(False, description="Save annotated image with pose skeleton"),
):
    """
    Single image pose detection endpoint.
    Upload an image to detect humans and their pose keypoints.
    """
    if file.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=415, detail="Uploaded file is not an image")

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tmp_path = tf.name
        contents = await file.read()
        tf.write(contents)

    try:
        # Load image once, reuse for both inference and annotation
        img = cv2.imread(tmp_path)
        if img is None:
            raise HTTPException(status_code=400, detail="Could not read image file")

        final_result = _process_single_image(img, file.filename, classes)

        # Optionally save annotated image (reuses already-loaded image array)
        if save_annotated and final_result.get("detections"):
            try:
                # Draw annotations on the already-loaded image (no redundant read)
                annotated_img = draw_detection_boxes(img.copy(), final_result)
                output_path = os.path.join(ANNOTATED_IMAGES_DIR, f"annotated_{file.filename}")
                cv2.imwrite(output_path, annotated_img)
                final_result["annotated_image_path"] = output_path
            except Exception as e:
                final_result["annotation_error"] = str(e)

        return JSONResponse(status_code=200, content={"results": [final_result]})
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.post("/detect/batch", response_model=InferenceResponse)
async def detect_batch(
    files: List[UploadFile] = File(...),
    classes: Optional[List[int]] = Query([0], description="Class IDs to keep (person=0)"),
    save_annotated: Optional[bool] = Query(False, description="Save annotated images with pose skeleton"),
):
    """
    Batch processing endpoint.
    Upload multiple images to detect humans and pose keypoints in all of them.
    """
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results = []
    temp_files = []
    loaded_images = []  # Store (image_array, filename, tmp_path)

    try:
        # Phase 1: Load all images
        for file in files:
            # Validate content type (handle None case)
            content_type = file.content_type or ""
            if not content_type.startswith("image/"):
                results.append({
                    "file_name": file.filename,
                    "height": None,
                    "width": None,
                    "detections": [],
                    "error": "Not an image file"
                })
                continue

            suffix = os.path.splitext(file.filename)[1] or ".jpg"
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                    tmp_path = tf.name
                    temp_files.append(tmp_path)
                    contents = await file.read()
                    tf.write(contents)

                img = cv2.imread(tmp_path)
                if img is None:
                    results.append({
                        "file_name": file.filename,
                        "height": None,
                        "width": None,
                        "detections": [],
                        "error": "Could not read image"
                    })
                else:
                    loaded_images.append((img, file.filename, tmp_path))
            except Exception as e:
                results.append({
                    "file_name": file.filename,
                    "height": None,
                    "width": None,
                    "detections": [],
                    "error": f"Failed to load image: {str(e)}"
                })

        # Phase 2: Process loaded images
        for img, filename, tmp_path in loaded_images:
            try:
                final_result = _process_single_image(img, filename, classes)

                # Optionally save annotated image (save even without detections to show processed image)
                if save_annotated:
                    try:
                        annotated_img = draw_detection_boxes(img.copy(), final_result)
                        output_path = os.path.join(ANNOTATED_IMAGES_DIR, f"annotated_{filename}")
                        success = cv2.imwrite(output_path, annotated_img)
                        if success:
                            final_result["annotated_image_path"] = output_path
                        else:
                            final_result["annotation_error"] = "Failed to save annotated image"
                    except Exception as e:
                        final_result["annotation_error"] = str(e)

                results.append(final_result)
            except Exception as e:
                results.append({
                    "file_name": filename,
                    "height": None,
                    "width": None,
                    "detections": [],
                    "error": str(e)
                })

        return JSONResponse(status_code=200, content={"results": results})
    finally:
        # Clean up all temporary files
        for tmp_path in temp_files:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.post("/audit", response_model=AuditResponse)
async def comprehensive_audit(
    file: UploadFile = File(...),
    room_id: Optional[str] = Query("default_room", description="Unique identifier for the room/camera"),
    sensitivity: Optional[int] = Query(160, description="Brightness threshold for appliance ON/OFF detection (0-255)"),
    save_annotated: Optional[bool] = Query(False, description="Save annotated image with pose and appliance detection"),
    privacy_mode: Optional[bool] = Query(False, description="Use privacy-enabled ghost view for annotations")
):
    """
    PHASE 0: Comprehensive energy audit endpoint with canonical RoomEvent schema.

    Features:
    - Human pose detection and counting
    - Appliance detection (projectors/TVs and laptops) with ON/OFF status inference
    - FSM-based room state evaluation (OCCUPIED, EMPTY_SAFE, EMPTY_WASTING)
    - Energy waste detection with kWh estimation
    - Privacy mode with blurred view and skeleton overlay
    - Canonical event schema output (FROZEN)

    Returns:
        AuditResponse with RoomEvent following PHASE 0 contract
    """
    start_time = time.time()

    if file.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=415, detail="Uploaded file is not an image")

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tmp_path = tf.name
        contents = await file.read()
        tf.write(contents)

    try:
        # Load image
        img = cv2.imread(tmp_path)
        if img is None:
            raise HTTPException(status_code=400, detail="Could not read image file")

        # 1. Human pose detection
        pose_results = pose_model.predict(
            source=img, imgsz=1280, conf=0.1, iou=0.65,
            device=DEVICE, verbose=False
        )[0]

        person_count = len(pose_results.boxes) if pose_results.boxes is not None else 0
        pose_detections = _parse_pose_detections(pose_results, classes=[0])  # Only person class

        # Calculate overall pose detection confidence
        pose_confidences = [d.get("confidence", 0.0) for d in pose_detections]
        avg_pose_confidence = sum(pose_confidences) / len(pose_confidences) if pose_confidences else 1.0

        # 2. Appliance detection with status analysis
        appliances_raw = detect_appliances(img, sensitivity)

        # Convert to canonical ApplianceDetection schema
        appliances: List[ApplianceDetection] = []
        for app in appliances_raw:
            appliances.append(ApplianceDetection(
                name=app["name"],
                state=app["status"],  # "ON", "OFF", or "UNKNOWN"
                confidence=app.get("confidence", 0.9),
                bbox=app.get("xyxy"),
                brightness=app.get("brightness")
            ))

        # 3. PHASE 0: Use state machine to evaluate room state
        room_state, energy_waste_detected = RoomStateMachine.evaluate_state(
            people_count=person_count,
            appliances=appliances
        )

        # 4. Calculate energy savings estimate
        # For single-frame audit, duration is 0 (could be extended with state tracking)
        duration_sec = 0
        energy_saved_kwh = RoomStateMachine.estimate_energy_savings(
            room_state=room_state,
            appliances=appliances,
            duration_sec=duration_sec
        )

        # 5. Calculate overall confidence (weighted average)
        appliance_confidences = [a.confidence for a in appliances]
        avg_appliance_confidence = sum(appliance_confidences) / len(appliance_confidences) if appliance_confidences else 1.0
        overall_confidence = (avg_pose_confidence + avg_appliance_confidence) / 2.0

        # 6. Optionally save annotated image
        image_path = None
        if save_annotated:
            try:
                if privacy_mode:
                    # Use privacy-enabled ghost view
                    annotated_img = create_ghost_view(img, pose_results)
                    # Add appliance annotations to ghost view
                    for appliance in appliances:
                        if appliance.bbox:
                            xyxy = appliance.bbox
                            x1, y1, x2, y2 = map(int, xyxy)
                            status = appliance.state
                            brightness = appliance.brightness or 0
                            name = appliance.name

                            color = (0, 255, 0) if status == "ON" else (0, 0, 255)
                            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 4)
                            cv2.putText(annotated_img, f"{name}: {status} (B:{brightness:.0f})",
                                      (x1, y1-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                    output_path = os.path.join(ANNOTATED_IMAGES_DIR, f"ghost_{file.filename}")
                else:
                    # Use regular view with full annotations
                    annotated_img = draw_audit_annotations(img.copy(), pose_detections, appliances_raw)
                    output_path = os.path.join(ANNOTATED_IMAGES_DIR, f"audit_{file.filename}")

                cv2.imwrite(output_path, annotated_img)
                image_path = output_path
            except Exception as e:
                # Log error but don't fail the request
                print(f"[WARN] Failed to save annotated image: {e}")

        # 7. PHASE 0: Construct canonical RoomEvent
        event = RoomEvent(
            room_id=room_id,
            timestamp=datetime.utcnow(),
            people_count=person_count,
            room_state=room_state,
            appliances=appliances,
            energy_waste_detected=energy_waste_detected,
            energy_saved_kwh=energy_saved_kwh,
            duration_sec=duration_sec,
            confidence=overall_confidence,
            image_path=image_path,
            privacy_mode=privacy_mode
        )

        # PHASE 3: Log event to local JSONL stream
        try:
            logger = get_event_logger()
            logger.log_event(event)
        except Exception as e:
            print(f"[WARN] Failed to log event: {e}")

        # 8. Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # 9. Return canonical response
        response = AuditResponse(
            event=event,
            processing_time_ms=processing_time_ms,
            model_versions={
                "pose_model": "yolov8x-pose",
                "detection_model": "yolov8x",
                "schema_version": "PHASE_0_FROZEN"
            }
        )

        return response

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.post("/audit/dashboard", response_model=DashboardAuditResponse)
async def dashboard_audit(
    file: UploadFile = File(...),
    l_thresh: int = Query(235, description="Light threshold for ceiling region"),
    s_thresh: int = Query(165, description="Screen brightness threshold"),
    save_annotated: Optional[bool] = Query(False, description="Save annotated ghost image to disk")
):
    """Lightweight dashboard audit mimicking `dashboard.py` run_audit behavior."""
    if file.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=415, detail="Uploaded file is not an image")

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tmp_path = tf.name
        contents = await file.read()
        tf.write(contents)

    ghost_b64 = None
    annotated_path = None
    try:
        img = cv2.imread(tmp_path)
        if img is None:
            raise HTTPException(status_code=400, detail="Could not read image file")

        ghost, person_count, energy_waste_detected, active_appliances = run_audit(img, l_thresh, s_thresh)

        # Encode ghost image for easy frontend embedding
        _, buffer = cv2.imencode('.jpg', cv2.cvtColor(ghost, cv2.COLOR_BGR2RGB))
        ghost_b64 = base64.b64encode(buffer).decode('utf-8')

        if save_annotated:
            annotated_path = os.path.join(ANNOTATED_IMAGES_DIR, f"dashboard_{file.filename}")
            cv2.imwrite(annotated_path, ghost)

        return DashboardAuditResponse(
            file_name=file.filename,
            person_count=person_count,
            active_appliances=active_appliances,
            energy_waste_detected=energy_waste_detected,
            l_thresh=l_thresh,
            s_thresh=s_thresh,
            ghost_image_base64=ghost_b64,
            annotated_image_path=annotated_path
        )

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ============================================================================
# PHASE 1: CONTINUOUS MONITORING ENDPOINTS
# ============================================================================

# Global state trackers for each room
_room_state_trackers: Dict[str, StateTracker] = {}
_frame_processors: Dict[str, FrameProcessor] = {}  # Store processors to get performance stats


def get_state_tracker(room_id: str) -> StateTracker:
    """Get or create state tracker for a room."""
    if room_id not in _room_state_trackers:
        _room_state_trackers[room_id] = StateTracker()
    return _room_state_trackers[room_id]


def process_frame_for_monitoring(frame: np.ndarray, room_id: str) -> RoomEvent:
    """
    OPTIMIZED: Process a camera frame for continuous monitoring with performance optimizations.

    This is the audit function used by the camera sampler.
    Uses reduced resolution and optimized processing for real-time performance.
    """
    try:
        # OPTIMIZATION 1: Use smaller resolution for real-time processing
        # Reduce from 1280 to 640 for much faster inference

        # 1. Human pose detection (OPTIMIZED)
        pose_results = pose_model.predict(
            source=frame, imgsz=640, conf=0.2, iou=0.65,  # Reduced resolution from 1280 to 640
            device=DEVICE, verbose=False
        )[0]

        person_count = len(pose_results.boxes) if pose_results.boxes is not None else 0
        pose_detections = _parse_pose_detections(pose_results, classes=[0])

        # Calculate pose confidence
        pose_confidences = [d.get("confidence", 0.0) for d in pose_detections]
        avg_pose_confidence = sum(pose_confidences) / len(pose_confidences) if pose_confidences else 1.0

        # 2. Appliance detection (OPTIMIZED)
        appliances_raw = detect_appliances_optimized(frame, sensitivity=160)

        # Convert to schema
        appliances: List[ApplianceDetection] = []
        for app in appliances_raw:
            appliances.append(ApplianceDetection(
                name=app["name"],
                state=app["status"],
                confidence=app.get("confidence", 0.9),
                bbox=app.get("xyxy"),
                brightness=app.get("brightness")
            ))

        # 3. Get state tracker and update temporal state
        tracker = get_state_tracker(room_id)
        current_time = time.time()

        room_state, duration_sec, state_changed = tracker.update(
            people_count=person_count,
            appliances=appliances,
            current_time=current_time
        )

        # 4. Energy calculations
        energy_waste_detected = RoomStateMachine.should_alert(room_state, duration_sec)
        energy_saved_kwh = RoomStateMachine.estimate_energy_savings(
            room_state=room_state,
            appliances=appliances,
            duration_sec=duration_sec
        )

        # 5. Overall confidence
        appliance_confidences = [a.confidence for a in appliances]
        avg_appliance_confidence = sum(appliance_confidences) / len(appliance_confidences) if appliance_confidences else 1.0
        overall_confidence = (avg_pose_confidence + avg_appliance_confidence) / 2.0

        # 6. Create event
        event = RoomEvent(
            room_id=room_id,
            timestamp=datetime.utcnow(),
            people_count=person_count,
            room_state=room_state,
            appliances=appliances,
            energy_waste_detected=energy_waste_detected,
            energy_saved_kwh=energy_saved_kwh,
            duration_sec=duration_sec,
            confidence=overall_confidence,
            privacy_mode=False  # Live monitoring uses standard processing
        )

        # 7. Log event (ASYNC - don't block on logging)
        try:
            logger = get_event_logger()
            # Only log significant events to reduce I/O overhead
            if energy_waste_detected or state_changed:
                logger.log_event(event)
        except Exception as e:
            print(f"[WARN] Failed to log monitoring event: {e}")

        return event

    except Exception as e:
        print(f"[ERROR] Frame processing failed for room {room_id}: {e}")
        # Return fallback event to prevent system crash
        return RoomEvent(
            room_id=room_id,
            timestamp=datetime.utcnow(),
            people_count=0,
            room_state="EMPTY_SAFE",
            appliances=[],
            energy_waste_detected=False,
            energy_saved_kwh=0.0,
            duration_sec=0,
            confidence=0.0,
            privacy_mode=False
        )


@app.post("/monitor/start")
async def start_monitoring(
    room_id: str = Query("default_room", description="Unique identifier for the room"),
    camera_id: int = Query(0, description="Camera device ID (0 = default)"),
    fps: float = Query(0.5, description="Processing frames per second (OPTIMIZED: default 0.5 for stability)"),
    resolution_width: int = Query(640, description="Camera width"),
    resolution_height: int = Query(480, description="Camera height"),
    save_frames: bool = Query(False, description="Save captured frames to disk")
):
    """
    PHASE 1: Start continuous monitoring for a room.

    Begins live camera capture and real-time energy audit processing.
    OPTIMIZED: Uses conservative defaults for stability.
    """
    try:
        # Check if already monitoring this room
        sampler = get_camera_sampler(room_id, config=None)
        if sampler.is_running:
            return {
                "message": f"Monitoring already active for room {room_id}",
                "room_id": room_id,
                "status": "already_running"
            }

        # Create camera config with OPTIMIZED defaults
        config = CameraConfig(
            camera_id=camera_id,
            fps=max(0.1, min(1.0, fps)),  # Clamp FPS between 0.1 and 1.0 for stability
            resolution=(resolution_width, resolution_height),
            room_id=room_id,
            save_frames=save_frames
        )

        print(f"[INFO] Starting monitoring with FPS: {config.fps}, Resolution: {config.resolution}")

        # Create sampler
        new_sampler = CameraFrameSampler(config)

        # Create frame processor with timeout protection
        processor = FrameProcessor(process_frame_for_monitoring, max_processing_time=5.0)

        # Start monitoring
        new_sampler.start(frame_callback=processor)

        # Update global registries
        global _active_samplers, _frame_processors
        from camera_sampler import _active_samplers
        _active_samplers[room_id] = new_sampler
        _frame_processors[room_id] = processor

        return {
            "message": f"Monitoring started for room {room_id}",
            "room_id": room_id,
            "camera_id": camera_id,
            "fps": config.fps,
            "resolution": [resolution_width, resolution_height],
            "status": "started",
            "optimizations": "Using reduced FPS and resolution for stability"
        }

    except Exception as e:
        print(f"[ERROR] Failed to start monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")


@app.post("/monitor/stop")
async def stop_monitoring(room_id: str = Query("default_room")):
    """Stop continuous monitoring for a room."""
    try:
        sampler = get_camera_sampler(room_id, config=None)

        if not sampler.is_running:
            return {
                "message": f"No active monitoring for room {room_id}",
                "room_id": room_id,
                "status": "not_running"
            }

        sampler.stop()

        # Remove from global registry
        global _active_samplers
        from camera_sampler import _active_samplers
        _active_samplers.pop(room_id, None)

        return {
            "message": f"Monitoring stopped for room {room_id}",
            "room_id": room_id,
            "status": "stopped"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")


@app.get("/monitor/status")
async def get_monitoring_status(room_id: Optional[str] = Query(None, description="Room ID (omit for all rooms)")):
    """Get monitoring status for one or all rooms."""
    try:
        global _active_samplers
        from camera_sampler import _active_samplers

        if room_id:
            # Single room status
            if room_id not in _active_samplers:
                return {
                    "room_id": room_id,
                    "status": "not_configured"
                }

            sampler = _active_samplers[room_id]
            stats = sampler.get_stats()

            # Add state tracker info
            if room_id in _room_state_trackers:
                tracker = _room_state_trackers[room_id]
                stats["current_state"] = tracker.current_state
                stats["state_transition_count"] = tracker.transition_count

            # Add processor performance stats (OPTIMIZED)
            if room_id in _frame_processors:
                processor = _frame_processors[room_id]
                processor_stats = processor.get_stats()
                stats["processor_performance"] = processor_stats

            return {
                "room_id": room_id,
                "status": "running" if stats["is_running"] else "stopped",
                **stats
            }
        else:
            # All rooms status
            all_status = {}
            for rid, sampler in _active_samplers.items():
                stats = sampler.get_stats()

                if rid in _room_state_trackers:
                    tracker = _room_state_trackers[rid]
                    stats["current_state"] = tracker.current_state
                    stats["state_transition_count"] = tracker.transition_count

                # Add processor performance stats (OPTIMIZED)
                if rid in _frame_processors:
                    processor = _frame_processors[rid]
                    processor_stats = processor.get_stats()
                    stats["processor_performance"] = processor_stats

                all_status[rid] = {
                    "status": "running" if stats["is_running"] else "stopped",
                    **stats
                }

            return {
                "total_rooms": len(all_status),
                "active_rooms": sum(1 for s in all_status.values() if s["status"] == "running"),
                "rooms": all_status
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.post("/monitor/stop-all")
async def stop_all_monitoring():
    """Stop monitoring for all rooms."""
    try:
        stop_all_samplers()
        _room_state_trackers.clear()

        return {
            "message": "All monitoring stopped",
            "status": "stopped"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop all monitoring: {str(e)}")


# Cleanup on app shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown: stop all camera samplers."""
    print("[INFO] Shutting down - stopping all camera samplers")
    stop_all_samplers()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
