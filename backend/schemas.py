"""
PHASE 0: Canonical Event Schema (FROZEN)

This schema is the contract for all event data flowing through the system.
Once frozen, these fields and types must not change without versioning.
"""

from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field


# FROZEN ENUMS - Do not modify
ApplianceState = Literal["ON", "OFF", "UNKNOWN"]
RoomState = Literal["OCCUPIED", "EMPTY_SAFE", "EMPTY_WASTING"]


class ApplianceDetection(BaseModel):
    """Individual appliance detection within a room event."""
    name: str = Field(..., description="Appliance type (e.g., 'Projector/TV', 'Laptop')")
    state: ApplianceState = Field(..., description="Appliance power state")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence [0-1]")
    bbox: Optional[List[float]] = Field(None, description="Bounding box [x1, y1, x2, y2]")
    brightness: Optional[float] = Field(None, description="Measured brightness for state inference")


class RoomEvent(BaseModel):
    """
    PHASE 0 FROZEN SCHEMA - Canonical room event structure.

    This is the single source of truth for event data.
    All edge inference, local storage, and cloud transmission must use this schema.
    """
    # Event identity and timing
    room_id: str = Field(..., description="Unique identifier for the room/camera")
    timestamp: datetime = Field(..., description="Event capture timestamp (ISO 8601)")

    # Occupancy detection
    people_count: int = Field(..., ge=0, description="Number of people detected in frame")

    # State machine output
    room_state: RoomState = Field(..., description="Current room state from FSM")

    # Appliance monitoring
    appliances: List[ApplianceDetection] = Field(default_factory=list, description="Detected appliances")

    # Energy waste metrics
    energy_waste_detected: bool = Field(..., description="True if waste conditions met")
    energy_saved_kwh: float = Field(0.0, ge=0.0, description="Estimated energy savings potential (kWh)")

    # State duration tracking
    duration_sec: int = Field(0, ge=0, description="Duration in current room_state (seconds)")

    # Overall confidence
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall event confidence")

    # Optional metadata
    image_path: Optional[str] = Field(None, description="Path to annotated image (if saved)")
    privacy_mode: bool = Field(False, description="True if privacy mode was enabled")

    class Config:
        json_schema_extra = {
            "example": {
                "room_id": "room_101",
                "timestamp": "2026-03-27T14:30:00Z",
                "people_count": 0,
                "room_state": "EMPTY_WASTING",
                "appliances": [
                    {
                        "name": "Projector/TV",
                        "state": "ON",
                        "confidence": 0.95,
                        "bbox": [100, 150, 300, 400],
                        "brightness": 185.5
                    }
                ],
                "energy_waste_detected": True,
                "energy_saved_kwh": 0.5,
                "duration_sec": 300,
                "confidence": 0.92,
                "privacy_mode": False
            }
        }


class AuditResponse(BaseModel):
    """Response wrapper for /audit endpoint."""
    event: RoomEvent = Field(..., description="Canonical room event")
    processing_time_ms: float = Field(..., description="Backend processing time")
    model_versions: dict = Field(default_factory=dict, description="Model version info")
