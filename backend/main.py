from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from ultralytics import YOLO
import tempfile
import os
import numpy as np
import cv2
from pose_utils import (
    COCO_SKELETON_MAP, KEYPOINT_CONFIDENCE_THRESHOLD, MODEL_CONFIDENCE_THRESHOLD,
    draw_skeleton_on_image, load_image_safe
)

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

@app.on_event("startup")
async def startup_event():
    """Ensure output directory exists at startup."""
    os.makedirs(ANNOTATED_IMAGES_DIR, exist_ok=True)

# Model weight name for YOLOv8n-Pose
YOLO_POSE_MODEL = "yolov8n-pose.pt"


def _load_yolo_model(weight_name: str):
    try:
        return YOLO(weight_name)
    except FileNotFoundError:
        raise RuntimeError(f"Model weight '{weight_name}' not found locally. Please ensure {weight_name} is in the backend directory.")


# Load YOLOv8n-Pose model once at startup
pose_model = _load_yolo_model(YOLO_POSE_MODEL)


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


def _process_single_image(image: np.ndarray, filename: str, classes: Optional[List[int]] = None) -> Dict[str, Any]:
    """Process image with YOLOv8n-Pose and return pose detection results.

    Args:
        image: Image array (cv2 format, BGR) - already loaded from disk
        filename: Original filename for the result record
        classes: Optional class filter (person=0)

    Returns:
        Dict with detection results {file_name, height, width, detections}
    """
    # Run inference on pre-loaded image array (avoids redundant disk read)
    pose_results = pose_model.predict(source=image, classes=classes, verbose=False)

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
            if file.content_type.split("/")[0] != "image":
                results.append({
                    "file_name": file.filename,
                    "height": None,
                    "width": None,
                    "detections": [],
                    "error": "Not an image file"
                })
                continue

            suffix = os.path.splitext(file.filename)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                tmp_path = tf.name
                temp_files.append(tmp_path)
                contents = await file.read()
                tf.write(contents)

            try:
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

                # Optionally save annotated image (reuses already-loaded array)
                if save_annotated and final_result.get("detections"):
                    try:
                        annotated_img = draw_detection_boxes(img.copy(), final_result)
                        output_path = os.path.join(ANNOTATED_IMAGES_DIR, f"annotated_{filename}")
                        cv2.imwrite(output_path, annotated_img)
                        final_result["annotated_image_path"] = output_path
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
