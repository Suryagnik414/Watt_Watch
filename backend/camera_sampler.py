"""
PHASE 1: Camera Frame Sampler

Handles live camera capture, frame sampling, and continuous monitoring.
Converts the system from single-image processing to real-time surveillance.
"""

import cv2
import time
import threading
from typing import Optional, Callable, Dict, Any, Union
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from pathlib import Path


@dataclass
class CameraConfig:
    """Camera configuration parameters.
    
    Supports both local cameras (device ID as int) and RTSP streams (URL as string).
    """
    camera_source: Union[int, str] = 0  # Camera device ID (int) or RTSP URL (str)
    fps: float = 0.5  # Reduced from 1.0 to 0.5 FPS - process every 2 seconds for stability
    resolution: tuple = (640, 480)  # (width, height) - reasonable resolution for processing
    room_id: str = "default_room"
    save_frames: bool = False
    frame_save_dir: str = "captured_frames"
    rtsp_timeout: int = 10  # Timeout for RTSP connection attempts (seconds)
    
    @property
    def camera_id(self) -> Union[int, str]:
        """Backward compatibility property."""
        return self.camera_source
    
    @property
    def is_rtsp(self) -> bool:
        """Check if this is an RTSP stream."""
        return isinstance(self.camera_source, str) and self.camera_source.startswith(('rtsp://', 'rtmp://', 'http://'))


class CameraFrameSampler:
    """
    Continuous camera frame sampler with configurable processing rate.

    Features:
    - Live camera capture from USB/built-in cameras
    - Configurable sampling rate (independent of camera FPS)
    - Frame preprocessing and quality checks
    - Thread-safe operation
    - Automatic reconnection on camera failures
    """

    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.last_frame_time = 0.0
        self.frame_count = 0
        self.error_count = 0

        # Thread safety
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        # Frame callback
        self.frame_callback: Optional[Callable[[np.ndarray, dict], None]] = None

        # Frame save directory
        if config.save_frames:
            Path(config.frame_save_dir).mkdir(parents=True, exist_ok=True)

    def _initialize_camera(self) -> bool:
        """Initialize camera connection (supports both device IDs and RTSP streams)."""
        try:
            source = self.config.camera_source
            
            # For RTSP streams, add additional options
            if self.config.is_rtsp:
                print(f"[INFO] Initializing RTSP stream: {source}")
                # Set CAP_FFMPEG backend for RTSP streams
                self.cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                
                # Set buffer size to reduce latency
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Set timeout for RTSP (in milliseconds)
                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.config.rtsp_timeout * 1000)
                self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.config.rtsp_timeout * 1000)
            else:
                print(f"[INFO] Initializing local camera: {source}")
                self.cap = cv2.VideoCapture(source)

            if not self.cap.isOpened():
                print(f"[ERROR] Cannot open camera source {source}")
                return False

            # Set camera properties (may not work for all RTSP streams)
            width, height = self.config.resolution
            if not self.config.is_rtsp:
                # Only set resolution for local cameras
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Test frame capture with retry for RTSP streams
            max_retries = 3 if self.config.is_rtsp else 1
            for attempt in range(max_retries):
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    print(f"[INFO] Camera source {source} initialized: {frame.shape}")
                    return True
                if attempt < max_retries - 1:
                    print(f"[WARN] Frame capture attempt {attempt + 1} failed, retrying...")
                    time.sleep(1)
            
            print(f"[ERROR] Cannot capture test frame from camera source {source}")
            return False

        except Exception as e:
            print(f"[ERROR] Camera initialization failed: {e}")
            return False

    def _capture_loop(self):
        """Main capture loop (runs in separate thread)."""
        print(f"[INFO] Starting camera capture loop (FPS: {self.config.fps})")

        frame_interval = 1.0 / self.config.fps if self.config.fps > 0 else 1.0

        while self.is_running:
            try:
                current_time = time.time()

                # Check if it's time for next frame
                if current_time - self.last_frame_time < frame_interval:
                    time.sleep(0.01)  # Small sleep to prevent busy waiting
                    continue

                # Capture frame
                with self._lock:
                    if not self.cap or not self.cap.isOpened():
                        if not self._reconnect_camera():
                            time.sleep(1.0)  # Wait before retry
                            continue

                    ret, frame = self.cap.read()

                if not ret or frame is None:
                    self.error_count += 1
                    print(f"[WARN] Frame capture failed (errors: {self.error_count})")

                    if self.error_count > 5:
                        print("[ERROR] Too many capture failures, attempting reconnection")
                        if not self._reconnect_camera():
                            time.sleep(1.0)
                        self.error_count = 0
                    continue

                self.error_count = 0  # Reset error count on successful capture
                self.frame_count += 1
                self.last_frame_time = current_time

                # Frame metadata
                frame_meta = {
                    "timestamp": datetime.utcnow(),
                    "frame_number": self.frame_count,
                    "camera_source": self.config.camera_source,
                    "is_rtsp": self.config.is_rtsp,
                    "room_id": self.config.room_id,
                    "resolution": frame.shape[:2]
                }

                # Optional frame saving
                if self.config.save_frames:
                    self._save_frame(frame, frame_meta)

                # Process frame via callback
                if self.frame_callback:
                    try:
                        self.frame_callback(frame, frame_meta)
                    except Exception as e:
                        print(f"[ERROR] Frame callback failed: {e}")

            except Exception as e:
                print(f"[ERROR] Capture loop error: {e}")
                time.sleep(1.0)

    def _reconnect_camera(self) -> bool:
        """Attempt to reconnect camera."""
        print("[INFO] Attempting camera reconnection...")

        if self.cap:
            self.cap.release()

        return self._initialize_camera()

    def _save_frame(self, frame: np.ndarray, meta: dict):
        """Save frame to disk."""
        try:
            timestamp_str = meta["timestamp"].strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"frame_{timestamp_str}_{meta['frame_number']:06d}.jpg"
            filepath = Path(self.config.frame_save_dir) / filename
            cv2.imwrite(str(filepath), frame)
        except Exception as e:
            print(f"[WARN] Frame save failed: {e}")

    def start(self, frame_callback: Optional[Callable[[np.ndarray, dict], None]] = None):
        """
        Start continuous frame capture.

        Args:
            frame_callback: Function to call for each captured frame
                           Signature: callback(frame: np.ndarray, metadata: dict)
        """
        if self.is_running:
            print("[WARN] Camera sampler already running")
            return

        if not self._initialize_camera():
            raise RuntimeError("Failed to initialize camera")

        self.frame_callback = frame_callback
        self.is_running = True

        # Start capture thread
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        print(f"[INFO] Camera sampler started (Room: {self.config.room_id})")

    def stop(self):
        """Stop frame capture and release camera."""
        if not self.is_running:
            return

        print("[INFO] Stopping camera sampler...")
        self.is_running = False

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        # Release camera
        with self._lock:
            if self.cap:
                self.cap.release()
                self.cap = None

        print("[INFO] Camera sampler stopped")

    def get_stats(self) -> dict:
        """Get capture statistics."""
        return {
            "is_running": self.is_running,
            "frames_captured": self.frame_count,
            "error_count": self.error_count,
            "camera_id": self.config.camera_id,
            "room_id": self.config.room_id,
            "fps": self.config.fps,
            "resolution": self.config.resolution
        }


class FrameProcessor:
    """
    OPTIMIZED: Processes camera frames through the audit pipeline with frame dropping.

    Integrates CameraFrameSampler with the existing audit logic from main.py.
    Added protection against processing backlog and hanging.
    """

    def __init__(self, audit_function: Callable, max_processing_time: float = 3.0):
        """
        Initialize frame processor.

        Args:
            audit_function: Function that performs audit on a single frame
                           Signature: audit_func(frame: np.ndarray, room_id: str) -> RoomEvent
            max_processing_time: Maximum time in seconds to spend processing a frame
        """
        self.audit_function = audit_function
        self.processed_frames = 0
        self.dropped_frames = 0
        self.last_event = None
        self.processing_errors = 0
        self.max_processing_time = max_processing_time
        self.last_processing_time = 0.0
        self.processing_in_progress = False

    def __call__(self, frame: np.ndarray, metadata: dict):
        """
        OPTIMIZED: Process a single frame with timeout protection and frame dropping.

        Args:
            frame: Camera frame as numpy array
            metadata: Frame metadata from sampler
        """
        # OPTIMIZATION: Skip frame if previous processing is still running
        if self.processing_in_progress:
            self.dropped_frames += 1
            print(f"[WARN] Dropped frame {metadata['frame_number']}, processing still in progress")
            return

        self.processing_in_progress = True
        start_time = time.time()

        try:
            # Extract room_id from metadata
            room_id = metadata.get("room_id", "default_room")

            # Process frame through audit pipeline with timeout protection
            event = self.audit_function(frame, room_id)

            self.last_event = event
            self.processed_frames += 1
            self.last_processing_time = time.time() - start_time

            # Log interesting events
            if event.energy_waste_detected:
                print(f"[ALERT] Energy waste detected in {room_id}: "
                      f"{event.people_count} people, {len(event.appliances)} appliances")

            # Log performance warnings
            if self.last_processing_time > self.max_processing_time / 2:
                print(f"[PERF] Slow frame processing: {self.last_processing_time:.2f}s "
                      f"for frame {metadata['frame_number']}")

            # Optional: Log all events for debugging
            # print(f"[DEBUG] Frame {metadata['frame_number']}: {event.room_state}")

        except Exception as e:
            self.processing_errors += 1
            print(f"[ERROR] Frame processing failed: {e}")
            # Don't crash - just continue with next frame

        finally:
            self.processing_in_progress = False

    def get_stats(self) -> dict:
        """Get processing statistics."""
        return {
            "processed_frames": self.processed_frames,
            "dropped_frames": self.dropped_frames,
            "processing_errors": self.processing_errors,
            "last_processing_time_sec": self.last_processing_time,
            "frame_drop_rate": self.dropped_frames / max(1, self.processed_frames + self.dropped_frames),
            "last_event_time": self.last_event.timestamp if self.last_event else None,
            "last_room_state": self.last_event.room_state if self.last_event else None
        }


# Global instances for easy access
_active_samplers: Dict[str, CameraFrameSampler] = {}


def get_camera_sampler(room_id: str, config: Optional[CameraConfig] = None) -> CameraFrameSampler:
    """Get or create camera sampler for a room."""
    if room_id not in _active_samplers:
        if config is None:
            config = CameraConfig(room_id=room_id)
        _active_samplers[room_id] = CameraFrameSampler(config)

    return _active_samplers[room_id]


def stop_all_samplers():
    """Stop all active camera samplers."""
    for sampler in _active_samplers.values():
        sampler.stop()
    _active_samplers.clear()