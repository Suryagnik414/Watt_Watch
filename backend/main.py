from fastapi import FastAPI, File, UploadFile, HTTPException, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple, Set
import tempfile
import os
import base64
import numpy as np
import cv2
import torch
import asyncio
import json
import requests
import threading
from dotenv import load_dotenv

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

# Load environment variables
load_dotenv()

# Application Mode Configuration
APP_MODE = os.getenv("APP_MODE", "dev").lower()  # 'dev' or 'prod'
VIDEO_STREAM_FPS = int(os.getenv("VIDEO_STREAM_FPS", "5"))
VIDEO_STREAM_QUALITY = int(os.getenv("VIDEO_STREAM_QUALITY", "75"))

class AppConfig:
    """Application configuration."""
    mode: str = APP_MODE
    is_dev_mode: bool = APP_MODE == "dev"
    is_prod_mode: bool = APP_MODE == "prod"
    video_stream_fps: int = VIDEO_STREAM_FPS
    video_stream_quality: int = VIDEO_STREAM_QUALITY
    
    @classmethod
    def validate_dev_mode(cls):
        """Raise exception if not in dev mode."""
        if not cls.is_dev_mode:
            raise HTTPException(
                status_code=403,
                detail="This endpoint is only available in development mode. Set APP_MODE=dev"
            )

# PHASE 4: AWS REST API Gateway Configuration
AWS_INGEST_URL = os.getenv("AWS_INGEST_URL", "https://zwgua3w3sb.execute-api.ap-south-1.amazonaws.com/prod/ingest")

def send_event_to_aws(event_dict: dict):
    """Background task to send event to AWS REST API Gateway"""
    try:
        # Convert datetime to string for JSON serialization
        if 'timestamp' in event_dict and not isinstance(event_dict['timestamp'], str):
            event_dict['timestamp'] = event_dict['timestamp'].isoformat()

        response = requests.post(AWS_INGEST_URL, json=event_dict, timeout=5)
        if response.status_code != 200:
            print(f"[AWS SYNC ERROR] {response.text}")
        else:
            print(f"[AWS SYNC SUCCESS] Event logged to REST API for {event_dict.get('room_id')}")
    except Exception as e:
        print(f"[AWS SYNC FAILED] Could not connect to AWS: {e}")

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
    
    # Log application mode
    print(f"\n{'='*60}")
    print(f"  APPLICATION MODE: {APP_MODE.upper()}")
    if AppConfig.is_dev_mode:
        print(f"  ✓ Video streaming: ENABLED")
        print(f"  ✓ Visualization controls: ENABLED")
        print(f"  ✓ Video FPS: {VIDEO_STREAM_FPS}")
    else:
        print(f"  ✗ Video streaming: DISABLED")
        print(f"  ✗ Visualization controls: DISABLED")
        print(f"  ✓ Processing only mode")
    print(f"{'='*60}\n")
    
    # Auto-initialize default RTSP streams
    await auto_initialize_default_streams()


async def auto_initialize_default_streams():
    """Auto-initialize default RTSP camera streams at startup."""
    # Default RTSP streams configuration
    default_streams = [
        {"room_id": "room_1", "camera_source": "rtsp://64.227.185.144:8554/feed1"},
        {"room_id": "room_2", "camera_source": "rtsp://64.227.185.144:8554/feed2"},
        {"room_id": "room_3", "camera_source": "rtsp://64.227.185.144:8554/feed3"},
        {"room_id": "room_4", "camera_source": "rtsp://64.227.185.144:8554/feed4"},
        {"room_id": "room_5", "camera_source": "rtsp://64.227.185.144:8554/feed5"},
        {"room_id": "room_6", "camera_source": "rtsp://64.227.185.144:8554/feed6"},
    ]
    
    # Check if auto-initialization is enabled
    auto_init = os.getenv("AUTO_INIT_STREAMS", "true").lower() == "true"
    if not auto_init:
        print("[INFO] Auto-initialization disabled (AUTO_INIT_STREAMS=false)")
        return
    
    print(f"\n{'='*60}")
    print(f"  AUTO-INITIALIZING {len(default_streams)} RTSP STREAMS")
    print(f"{'='*60}")
    
    from camera_sampler import _active_samplers
    
    # Initialize streams in parallel using threads
    def init_stream(stream_config):
        room_id = stream_config["room_id"]
        camera_source = stream_config["camera_source"]
        
        try:
            print(f"[INIT] Starting {room_id}: {camera_source}")
            
            # Create camera config
            config = CameraConfig(
                camera_source=camera_source,
                fps=0.5,  # Conservative FPS for stability
                resolution=(640, 480),
                room_id=room_id,
                save_frames=False,
                rtsp_timeout=10
            )
            
            # Create sampler
            sampler = CameraFrameSampler(config)
            
            # Create frame processor
            processor = FrameProcessor(process_frame_for_monitoring, max_processing_time=5.0)
            
            # Start monitoring
            sampler.start(frame_callback=processor)
            
            # Update global registries
            _active_samplers[room_id] = sampler
            _frame_processors[room_id] = processor
            
            # Initialize visualization options
            if room_id not in _visualization_options:
                _visualization_options[room_id] = VisualizationOptions()
            
            print(f"[INIT] ✓ {room_id} started successfully")
            return True
            
        except Exception as e:
            print(f"[INIT] ✗ {room_id} failed: {e}")
            return False
    
    # Initialize all streams in parallel threads
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(init_stream, stream): stream for stream in default_streams}
        
        success_count = 0
        for future in as_completed(futures):
            if future.result():
                success_count += 1
    
    print(f"\n[INIT] Initialization complete: {success_count}/{len(default_streams)} streams active")
    print(f"{'='*60}\n")

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

# Global tracking dictionaries
_room_state_trackers: Dict[str, StateTracker] = {}
_frame_processors: Dict[str, Any] = {}
_visualization_options: Dict[str, Any] = {}  # Per-room visualization settings (VisualizationOptions)



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


class VisualizationOptions(BaseModel):
    """Visualization options for video streaming (dev mode only)."""
    show_skeleton: bool = True
    show_bounding_boxes: bool = True
    show_keypoints: bool = True
    apply_blur: bool = False
    privacy_mode: bool = False
    show_appliance_labels: bool = True
    show_energy_info: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "show_skeleton": True,
                "show_bounding_boxes": True,
                "show_keypoints": True,
                "apply_blur": False,
                "privacy_mode": False,
                "show_appliance_labels": True,
                "show_energy_info": True
            }
        }


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
    background_tasks: BackgroundTasks,
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

        # PHASE 4: Send to AWS REST API (Non-blocking)
        background_tasks.add_task(send_event_to_aws, event.model_dump(mode="json"))

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

# Global state trackers for each room (already defined at startup, removing duplicate)


def get_state_tracker(room_id: str) -> StateTracker:
    """Get or create state tracker for a room."""
    if room_id not in _room_state_trackers:
        _room_state_trackers[room_id] = StateTracker()
    return _room_state_trackers[room_id]


def get_visualization_options(room_id: str) -> VisualizationOptions:
    """Get or create visualization options for a room."""
    if room_id not in _visualization_options:
        _visualization_options[room_id] = VisualizationOptions()
    return _visualization_options[room_id]


# Cache for latest processed frames (for video streaming in dev mode)
_latest_frames: Dict[str, Tuple[np.ndarray, RoomEvent, float]] = {}  # room_id -> (frame, event, timestamp)


def render_visualizations(frame: np.ndarray, event: RoomEvent, viz_options: VisualizationOptions) -> np.ndarray:
    """
    Render visualization overlays on a frame based on options (DEV MODE ONLY).
    
    Args:
        frame: Original camera frame
        event: Processed RoomEvent with detection data
        viz_options: Visualization options for this room
        
    Returns:
        Annotated frame with requested visualizations
    """
    annotated = frame.copy()
    
    # Privacy mode: full blur
    if viz_options.privacy_mode:
        annotated = cv2.GaussianBlur(annotated, (99, 99), 30)
        return annotated
    
    # Apply background blur if requested
    if viz_options.apply_blur:
        annotated = cv2.GaussianBlur(annotated, (21, 21), 0)
    
    # Draw bounding boxes for persons and appliances
    if viz_options.show_bounding_boxes and event.appliances:
        for appliance in event.appliances:
            # Different colors for different appliances
            color = (0, 255, 0) if appliance.appliance_type == "Projector/TV" else (255, 165, 0)
            
            # Draw bounding box
            x1, y1, x2, y2 = map(int, [appliance.x_min, appliance.y_min, appliance.x_max, appliance.y_max])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Show appliance labels if enabled
            if viz_options.show_appliance_labels:
                label = f"{appliance.appliance_type} ({appliance.confidence:.2f})"
                cv2.putText(annotated, label, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # Draw skeleton and keypoints (simplified - using pose_utils if available)
    if (viz_options.show_skeleton or viz_options.show_keypoints) and hasattr(event, 'pose_detections'):
        try:
            # Use existing draw_skeleton_on_image if available
            from pose_utils import draw_skeleton_on_image
            # This is a simplified approach - you may want to extract keypoints from event
            # For now, we'll skip skeleton drawing to avoid complexity
            pass
        except Exception:
            pass
    
    # Show energy information overlay
    if viz_options.show_energy_info:
        # Create info panel at top
        info_text = [
            f"Persons: {event.person_count}",
            f"Appliances: {len(event.appliances)}",
            f"Waste: {'YES' if event.energy_waste_detected else 'NO'}",
            f"Saved: {event.energy_saved_kwh:.2f} kWh"
        ]
        
        y_offset = 30
        for i, text in enumerate(info_text):
            color = (0, 0, 255) if event.energy_waste_detected and i == 2 else (255, 255, 255)
            cv2.putText(annotated, text, (10, y_offset + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    return annotated


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

        # --- INTELLIGENT EDGE FILTER ---
        # Define what makes an event "Significant" enough to send to AWS
        is_significant = False

        # Reason A: State just changed (e.g., Someone left the room, TV is still on)
        if state_changed:
            is_significant = True

        # Reason B: Escalation intervals crossed (e.g., Every 5 minutes of continuous waste)
        # Assuming fps is roughly 1 frame per sec. 300 sec = 5 mins.
        if energy_waste_detected and (duration_sec > 0 and duration_sec % 300 == 0):
            is_significant = True

        # 7. Log and Sync (ASYNC - don't block on logging)
        try:
            logger = get_event_logger()
            # Only log significant events to reduce I/O overhead
            if is_significant:
                logger.log_event(event)

                # Send to AWS Smart Lambda (Non-blocking, threaded)
                # Note: Running in camera sampler thread, so we use threading instead of BackgroundTasks
                threading.Thread(target=send_event_to_aws, args=(event.model_dump(mode="json"),), daemon=True).start()

        except Exception as e:
            print(f"[WARN] Failed to log/sync monitoring event: {e}")

        # Cache frame for video streaming in dev mode
        if AppConfig.is_dev_mode:
            _latest_frames[room_id] = (frame.copy(), event, time.time())

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
    camera_source: Optional[str] = Query(None, description="Camera source: device ID (e.g., '0') or RTSP URL (e.g., 'rtsp://...')"),
    camera_id: Optional[int] = Query(None, description="DEPRECATED: Use camera_source instead. Camera device ID (0 = default)"),
    fps: float = Query(0.5, description="Processing frames per second (OPTIMIZED: default 0.5 for stability)"),
    resolution_width: int = Query(640, description="Camera width"),
    resolution_height: int = Query(480, description="Camera height"),
    save_frames: bool = Query(False, description="Save captured frames to disk")
):
    """
    Start continuous monitoring for a room with support for multiple camera sources.
    
    Supports:
    - Local cameras: camera_source="0", camera_source="1", etc.
    - RTSP streams: camera_source="rtsp://username:password@ip:port/stream"
    - HTTP streams: camera_source="http://ip:port/stream"
    
    OPTIMIZED: Uses conservative defaults for stability.
    """
    try:
        # Determine camera source (backward compatibility)
        if camera_source is None and camera_id is not None:
            source = camera_id
            print(f"[WARN] camera_id parameter is deprecated. Use camera_source instead.")
        elif camera_source is not None:
            # Try to convert to int if it's a numeric string
            try:
                source = int(camera_source)
            except ValueError:
                source = camera_source  # Keep as string (RTSP URL)
        else:
            source = 0  # Default to device 0
        
        # Check if already monitoring this room
        sampler = get_camera_sampler(room_id, config=None)
        if sampler.is_running:
            return {
                "message": f"Monitoring already active for room {room_id}",
                "room_id": room_id,
                "camera_source": str(source),
                "status": "already_running"
            }

        # Create camera config with OPTIMIZED defaults
        config = CameraConfig(
            camera_source=source,
            fps=max(0.1, min(1.0, fps)),  # Clamp FPS between 0.1 and 1.0 for stability
            resolution=(resolution_width, resolution_height),
            room_id=room_id,
            save_frames=save_frames
        )

        print(f"[INFO] Starting monitoring for room '{room_id}'")
        print(f"  Source: {source} ({'RTSP/HTTP Stream' if config.is_rtsp else 'Local Camera'})")
        print(f"  FPS: {config.fps}, Resolution: {config.resolution}")

        # Create sampler
        new_sampler = CameraFrameSampler(config)

        # Create frame processor with timeout protection
        processor = FrameProcessor(process_frame_for_monitoring, max_processing_time=5.0)

        # Start monitoring
        new_sampler.start(frame_callback=processor)

        # Update global registries
        global _active_samplers, _frame_processors, _visualization_options
        from camera_sampler import _active_samplers
        _active_samplers[room_id] = new_sampler
        _frame_processors[room_id] = processor
        
        # Initialize default visualization options for this room
        if room_id not in _visualization_options:
            _visualization_options[room_id] = VisualizationOptions()

        return {
            "message": f"Monitoring started for room {room_id}",
            "room_id": room_id,
            "camera_source": str(source),
            "is_rtsp": config.is_rtsp,
            "fps": config.fps,
            "resolution": [resolution_width, resolution_height],
            "status": "started",
            "mode": APP_MODE,
            "video_streaming": AppConfig.is_dev_mode
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

            # Add processor performance stats and last_event (OPTIMIZED)
            if room_id in _frame_processors:
                processor = _frame_processors[room_id]
                processor_stats = processor.get_stats()
                stats["processor_performance"] = processor_stats
                # Include last_event so frontend can display live room data
                if processor.last_event is not None:
                    stats["last_event"] = processor.last_event.model_dump(mode="json")

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

                # Add processor performance stats and last_event (OPTIMIZED)
                if rid in _frame_processors:
                    processor = _frame_processors[rid]
                    processor_stats = processor.get_stats()
                    stats["processor_performance"] = processor_stats
                    # Include last_event so frontend can display live room data
                    if processor.last_event is not None:
                        stats["last_event"] = processor.last_event.model_dump(mode="json")

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


@app.get("/monitor/streams")
async def list_active_streams():
    """
    List all active camera streams with their configuration and status.
    
    Returns information about all currently monitored rooms including:
    - Camera source (device ID or RTSP URL)
    - Stream type (local/RTSP)
    - Status and performance metrics
    """
    try:
        from camera_sampler import _active_samplers
        
        streams = []
        for room_id, sampler in _active_samplers.items():
            stats = sampler.get_stats()
            stream_info = {
                "room_id": room_id,
                "camera_source": str(sampler.config.camera_source),
                "is_rtsp": sampler.config.is_rtsp,
                "status": "running" if sampler.is_running else "stopped",
                "fps": sampler.config.fps,
                "resolution": sampler.config.resolution,
                "frame_count": stats.get("frame_count", 0),
                "error_count": stats.get("error_count", 0),
                "uptime_sec": stats.get("uptime_sec", 0)
            }
            
            # Add current state if available
            if room_id in _room_state_trackers:
                stream_info["current_state"] = _room_state_trackers[room_id].current_state
                
            streams.append(stream_info)
        
        return {
            "total_streams": len(streams),
            "active_streams": sum(1 for s in streams if s["status"] == "running"),
            "mode": APP_MODE,
            "streams": streams
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list streams: {str(e)}")


@app.get("/monitor/analytics")
async def get_analytics():
    """
    Get aggregated analytics across all monitored rooms.
    
    Returns:
    - Total person count across all rooms
    - Total active appliances
    - Energy waste summary
    - State distribution
    - Per-room statistics
    """
    try:
        from camera_sampler import _active_samplers
        
        total_people = 0
        total_appliances = 0
        energy_waste_rooms = []
        state_distribution = {}
        room_analytics = []
        total_energy_saved = 0.0
        
        for room_id, sampler in _active_samplers.items():
            # Get latest event from processor
            processor = _frame_processors.get(room_id)
            if processor and processor.last_event:
                event = processor.last_event
                
                # Aggregate counts
                total_people += event.people_count
                total_appliances += len(event.appliances)
                total_energy_saved += event.energy_saved_kwh
                
                # Track energy waste
                if event.energy_waste_detected:
                    energy_waste_rooms.append(room_id)
                
                # State distribution
                state = event.room_state
                state_distribution[state] = state_distribution.get(state, 0) + 1
                
                # Per-room analytics
                room_analytics.append({
                    "room_id": room_id,
                    "people_count": event.people_count,
                    "appliance_count": len(event.appliances),
                    "room_state": event.room_state,
                    "energy_waste_detected": event.energy_waste_detected,
                    "energy_saved_kwh": event.energy_saved_kwh,
                    "duration_sec": event.duration_sec,
                    "confidence": event.confidence,
                    "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp)
                })
        
        # Calculate percentages
        total_rooms = len(_active_samplers)
        waste_percentage = (len(energy_waste_rooms) / total_rooms * 100) if total_rooms > 0 else 0
        
        return {
            "summary": {
                "total_rooms": total_rooms,
                "total_people": total_people,
                "total_appliances": total_appliances,
                "energy_waste_rooms": len(energy_waste_rooms),
                "waste_percentage": round(waste_percentage, 1),
                "total_energy_saved_kwh": round(total_energy_saved, 3),
                "mode": APP_MODE
            },
            "state_distribution": state_distribution,
            "energy_waste_rooms": energy_waste_rooms,
            "room_analytics": room_analytics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")



        from camera_sampler import _active_samplers
        
        streams = []
        for room_id, sampler in _active_samplers.items():
            stats = sampler.get_stats()
            stream_info = {
                "room_id": room_id,
                "camera_source": str(sampler.config.camera_source),
                "is_rtsp": sampler.config.is_rtsp,
                "status": "running" if sampler.is_running else "stopped",
                "fps": sampler.config.fps,
                "resolution": sampler.config.resolution,
                "frame_count": stats.get("frame_count", 0),
                "error_count": stats.get("error_count", 0),
                "uptime_sec": stats.get("uptime_sec", 0)
            }
            
            # Add current state if available
            if room_id in _room_state_trackers:
                stream_info["current_state"] = _room_state_trackers[room_id].current_state
                
            streams.append(stream_info)
        
        return {
            "total_streams": len(streams),
            "active_streams": sum(1 for s in streams if s["status"] == "running"),
            "mode": APP_MODE,
            "streams": streams
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list streams: {str(e)}")


@app.post("/monitor/visualizations")
async def update_visualizations(
    room_id: str = Query(..., description="Room ID to update visualizations"),
    show_skeleton: Optional[bool] = Query(None, description="Show skeleton overlay"),
    show_bounding_boxes: Optional[bool] = Query(None, description="Show bounding boxes"),
    show_keypoints: Optional[bool] = Query(None, description="Show keypoints"),
    apply_blur: Optional[bool] = Query(None, description="Apply blur effect"),
    privacy_mode: Optional[bool] = Query(None, description="Enable privacy mode"),
    show_appliance_labels: Optional[bool] = Query(None, description="Show appliance labels"),
    show_energy_info: Optional[bool] = Query(None, description="Show energy information")
):
    """
    Update visualization options for a specific room (DEV MODE ONLY).
    
    This endpoint allows toggling various visualization overlays on the video stream:
    - Skeleton overlay (pose visualization)
    - Bounding boxes (person/appliance detection)
    - Keypoints (joint positions)
    - Blur effect (background blur)
    - Privacy mode (full face/body blur)
    - Appliance labels
    - Energy information overlays
    
    Only available when APP_MODE=dev.
    """
    # Validate dev mode
    AppConfig.validate_dev_mode()
    
    try:
        # Get or create visualization options for this room
        viz_options = get_visualization_options(room_id)
        
        # Update only provided fields
        updates = {}
        if show_skeleton is not None:
            viz_options.show_skeleton = show_skeleton
            updates["show_skeleton"] = show_skeleton
        if show_bounding_boxes is not None:
            viz_options.show_bounding_boxes = show_bounding_boxes
            updates["show_bounding_boxes"] = show_bounding_boxes
        if show_keypoints is not None:
            viz_options.show_keypoints = show_keypoints
            updates["show_keypoints"] = show_keypoints
        if apply_blur is not None:
            viz_options.apply_blur = apply_blur
            updates["apply_blur"] = apply_blur
        if privacy_mode is not None:
            viz_options.privacy_mode = privacy_mode
            updates["privacy_mode"] = privacy_mode
        if show_appliance_labels is not None:
            viz_options.show_appliance_labels = show_appliance_labels
            updates["show_appliance_labels"] = show_appliance_labels
        if show_energy_info is not None:
            viz_options.show_energy_info = show_energy_info
            updates["show_energy_info"] = show_energy_info
        
        # Update global registry
        _visualization_options[room_id] = viz_options
        
        return {
            "message": f"Visualization options updated for room {room_id}",
            "room_id": room_id,
            "updates": updates,
            "current_options": viz_options.model_dump()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update visualizations: {str(e)}")


@app.get("/monitor/visualizations/{room_id}")
async def get_visualizations(room_id: str):
    """
    Get current visualization options for a room (DEV MODE ONLY).
    
    Returns the current state of all visualization toggles for the specified room.
    """
    # Validate dev mode
    AppConfig.validate_dev_mode()
    
    try:
        viz_options = get_visualization_options(room_id)
        return {
            "room_id": room_id,
            "mode": APP_MODE,
            "options": viz_options.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get visualizations: {str(e)}")


# Cleanup on app shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown: stop all camera samplers."""
    print("[INFO] Shutting down - stopping all camera samplers")
    stop_all_samplers()


# ============================================================================
# WEBSOCKET: Real-time monitoring event stream
# ============================================================================

class WebSocketManager:
    """Manages WebSocket connections per room for real-time event broadcasting."""

    def __init__(self):
        # room_id -> set of active WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        if room_id not in self._connections:
            self._connections[room_id] = set()
        self._connections[room_id].add(ws)
        print(f"[WS] Client connected to room '{room_id}' (total: {len(self._connections[room_id])})")

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self._connections:
            self._connections[room_id].discard(ws)
            print(f"[WS] Client disconnected from room '{room_id}' (remaining: {len(self._connections[room_id])})")

    async def broadcast(self, room_id: str, data: dict):
        """Send JSON data to all clients connected to a room."""
        if room_id not in self._connections or not self._connections[room_id]:
            return
        dead = set()
        for ws in list(self._connections[room_id]):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[room_id].discard(ws)


ws_manager = WebSocketManager()


@app.websocket("/ws/{room_id}")
async def websocket_monitor(room_id: str, ws: WebSocket):
    """
    WebSocket endpoint for real-time room monitoring.
    
    In DEV mode:
    - Sends RoomEvent JSON + base64-encoded video frames with visualizations
    - Frame rate controlled by VIDEO_STREAM_FPS
    
    In PROD mode:
    - Sends RoomEvent JSON only (no video)
    
    Client connects to ws://localhost:8000/ws/{room_id}
    """
    await ws_manager.connect(room_id, ws)
    try:
        last_sent_event_time = None
        last_frame_time = 0.0
        frame_interval = 1.0 / VIDEO_STREAM_FPS if AppConfig.is_dev_mode else 1.0
        
        while True:
            await asyncio.sleep(0.1)  # Check more frequently for smoother streaming

            # Check if room is being monitored
            from camera_sampler import _active_samplers
            if room_id not in _active_samplers:
                await ws.send_json({
                    "type": "status",
                    "room_id": room_id,
                    "mode": APP_MODE,
                    "message": "No active monitoring for this room. Start via POST /monitor/start"
                })
                await asyncio.sleep(2)  # Wait longer between status messages
                continue

            # Get latest event from the processor
            processor = _frame_processors.get(room_id)
            if processor is None or processor.last_event is None:
                await ws.send_json({
                    "type": "status",
                    "room_id": room_id,
                    "mode": APP_MODE,
                    "message": "Monitoring active, waiting for first frame..."
                })
                await asyncio.sleep(1)
                continue

            event = processor.last_event
            event_time = str(event.timestamp)
            current_time = time.time()

            # Check if we should send a frame update
            should_send = (event_time != last_sent_event_time) or \
                         (AppConfig.is_dev_mode and (current_time - last_frame_time >= frame_interval))

            if should_send:
                last_sent_event_time = event_time
                payload = event.model_dump(mode="json")
                payload["type"] = "room_event"
                payload["mode"] = APP_MODE
                
                # In dev mode, add video frame if available
                if AppConfig.is_dev_mode and room_id in _latest_frames:
                    frame, cached_event, frame_ts = _latest_frames[room_id]
                    
                    # Only send frames that aren't too old (within last 5 seconds)
                    if current_time - frame_ts < 5.0:
                        try:
                            # Get visualization options
                            viz_options = get_visualization_options(room_id)
                            
                            # Render visualizations
                            annotated_frame = render_visualizations(frame, cached_event, viz_options)
                            
                            # Encode frame to JPEG
                            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), VIDEO_STREAM_QUALITY]
                            _, buffer = cv2.imencode('.jpg', annotated_frame, encode_param)
                            
                            # Convert to base64
                            frame_base64 = base64.b64encode(buffer).decode('utf-8')
                            
                            payload["frame_data"] = frame_base64
                            payload["frame_timestamp"] = frame_ts
                            payload["visualization_options"] = viz_options.model_dump()
                            
                            last_frame_time = current_time
                        except Exception as e:
                            print(f"[WS] Error encoding frame for room '{room_id}': {e}")
                
                await ws.send_json(payload)

    except WebSocketDisconnect:
        ws_manager.disconnect(room_id, ws)
    except Exception as e:
        print(f"[WS] Error in room '{room_id}': {e}")
        ws_manager.disconnect(room_id, ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
