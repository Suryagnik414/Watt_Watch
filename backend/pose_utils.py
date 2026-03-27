"""
Shared pose detection utilities for Watt Watch.
Centralized constants and functions for skeleton drawing and keypoint parsing.
"""
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple

# COCO Skeleton connections (17 keypoints)
COCO_SKELETON_MAP = [
    (16, 14), (14, 12), (17, 15), (15, 13), (12, 13), (6, 12),
    (7, 13), (6, 7), (6, 8), (7, 9), (8, 10), (9, 11),
    (2, 3), (1, 2), (1, 3), (2, 4), (3, 5)
]

# Confidence thresholds
KEYPOINT_CONFIDENCE_THRESHOLD = 0.3
MODEL_CONFIDENCE_THRESHOLD = 0.25

# Visual parameters
SKELETON_COLOR = (255, 255, 0)  # Cyan in BGR
JOINT_COLOR = (0, 0, 255)  # Red in BGR
SKELETON_LINE_THICKNESS = 2
JOINT_RADIUS = 3


def draw_skeleton_on_image(
    image: np.ndarray,
    keypoints: List[Dict[str, float]],
    skeleton_map: List[Tuple[int, int]] = COCO_SKELETON_MAP,
    confidence_threshold: float = KEYPOINT_CONFIDENCE_THRESHOLD
) -> np.ndarray:
    """
    Draw skeleton (bones and joints) on image in-place.

    Args:
        image: Input image (cv2 format, BGR)
        keypoints: List of dicts with 'x', 'y', 'confidence' keys
        skeleton_map: List of (start_idx, end_idx) bone connections
        confidence_threshold: Minimum confidence to draw a keypoint

    Returns:
        Modified image array with skeleton drawn
    """
    if not keypoints:
        return image

    # Draw bones (skeleton connections)
    for start, end in skeleton_map:
        start_idx, end_idx = start - 1, end - 1
        if start_idx < len(keypoints) and end_idx < len(keypoints):
            pt1_kpt = keypoints[start_idx]
            pt2_kpt = keypoints[end_idx]
            conf1 = pt1_kpt.get("confidence", 0)
            conf2 = pt2_kpt.get("confidence", 0)

            # Check confidence and validate coordinates are not at (0,0)
            if conf1 > confidence_threshold and conf2 > confidence_threshold:
                x1, y1 = int(pt1_kpt["x"]), int(pt1_kpt["y"])
                x2, y2 = int(pt2_kpt["x"]), int(pt2_kpt["y"])

                # Skip if either keypoint is at (0,0) - indicates undetected keypoint
                if (x1 > 0 or y1 > 0) and (x2 > 0 or y2 > 0):
                    cv2.line(image, (x1, y1), (x2, y2), SKELETON_COLOR, SKELETON_LINE_THICKNESS)

    # Draw joints (keypoints)
    for kpt in keypoints:
        if kpt.get("confidence", 0) > confidence_threshold:
            x, y = int(kpt["x"]), int(kpt["y"])
            # Skip if keypoint is at (0,0) - indicates undetected keypoint
            if x > 0 or y > 0:
                cv2.circle(image, (x, y), JOINT_RADIUS, JOINT_COLOR, -1)

    return image


def load_image_safe(image_path: str) -> np.ndarray:
    """
    Safely load image from disk.

    Args:
        image_path: Path to image file

    Returns:
        Image array in cv2 format (BGR)

    Raises:
        ValueError: If image cannot be loaded
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image from {image_path}")
    return img
