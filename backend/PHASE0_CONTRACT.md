# PHASE 0: CONTRACT FREEZE

**Status:** FROZEN ❄️
**Version:** 1.0.0
**Date:** 2026-03-27
**Compliance:** All edge devices, cloud services, and replay systems MUST use this schema.

---

## Purpose

This document defines the **immutable contract** for all event data in the Watt Watch system.
PHASE 0 establishes the canonical event schema, state machine, and alert logic that must remain stable across all future phases.

**DO NOT MODIFY** these contracts without explicit versioning and migration strategy.

---

## 1. Canonical Event Schema

All events produced by the system MUST conform to the `RoomEvent` schema defined in `schemas.py`.

### RoomEvent Fields (FROZEN)

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `room_id` | string | ✅ | Unique identifier for room/camera | Non-empty |
| `timestamp` | datetime | ✅ | Event capture time (ISO 8601 UTC) | Valid ISO format |
| `people_count` | int | ✅ | Number of people detected | ≥ 0 |
| `room_state` | enum | ✅ | Current FSM state | See State Machine |
| `appliances` | array | ✅ | List of detected appliances | See ApplianceDetection |
| `energy_waste_detected` | bool | ✅ | True if waste conditions met | - |
| `energy_saved_kwh` | float | ✅ | Estimated savings potential | ≥ 0.0 |
| `duration_sec` | int | ✅ | Time in current state | ≥ 0 |
| `confidence` | float | ✅ | Overall detection confidence | 0.0 - 1.0 |
| `image_path` | string | ❌ | Path to annotated image (optional) | Valid path or null |
| `privacy_mode` | bool | ✅ | True if privacy mode enabled | Default: false |

### ApplianceDetection Fields (FROZEN)

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `name` | string | ✅ | Appliance type | "Projector/TV", "Laptop", etc. |
| `state` | enum | ✅ | Power state | "ON", "OFF", "UNKNOWN" |
| `confidence` | float | ✅ | Detection confidence | 0.0 - 1.0 |
| `bbox` | array | ❌ | Bounding box [x1, y1, x2, y2] | Optional |
| `brightness` | float | ❌ | Measured brightness value | Optional, for inference |

### Enumerated Types (FROZEN)

```python
# Appliance power states
ApplianceState = Literal["ON", "OFF", "UNKNOWN"]

# Room FSM states
RoomState = Literal["OCCUPIED", "EMPTY_SAFE", "EMPTY_WASTING"]
```

---

## 2. State Machine Definition (FSM)

The system uses a **Finite State Machine** to classify room occupancy and energy waste.

### States

| State | Description | Meaning |
|-------|-------------|---------|
| **OCCUPIED** | People present in room | Normal operation, no waste (people using resources) |
| **EMPTY_SAFE** | No people, appliances OFF/unknown | No energy waste (safe state) |
| **EMPTY_WASTING** | No people, appliances ON | ⚠️ Energy waste detected (alert condition) |

### State Transition Rules (FROZEN)

```
┌─────────────────────────────────────────────────────────────┐
│                    Room State Machine                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   [ANY STATE]                                                │
│       │                                                       │
│       ├─ people_count > 0 ───────► OCCUPIED                  │
│       │                              │                        │
│       │                              │ (people leave)         │
│       │                              ▼                        │
│       ├─ people_count == 0 ────► Check Appliances           │
│                                      │                        │
│                                      ├─ All OFF/UNKNOWN      │
│                                      │   ───────► EMPTY_SAFE │
│                                      │                        │
│                                      └─ Any ON               │
│                                          ───────► EMPTY_WASTING│
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Transition Logic (FROZEN)

1. **Rule 1: Occupancy Override**
   - IF `people_count > 0`
   - THEN `room_state = OCCUPIED`
   - AND `energy_waste_detected = false`
   - **Rationale:** People are using the room, no waste condition.

2. **Rule 2: Empty + Safe**
   - IF `people_count == 0`
   - AND all high-confidence appliances have `state != "ON"`
   - THEN `room_state = EMPTY_SAFE`
   - AND `energy_waste_detected = false`
   - **Rationale:** Room is empty but no appliances are consuming power.

3. **Rule 3: Empty + Wasting**
   - IF `people_count == 0`
   - AND any high-confidence appliance has `state == "ON"`
   - THEN `room_state = EMPTY_WASTING`
   - AND `energy_waste_detected = true`
   - **Rationale:** Room is empty but appliances are still consuming power (waste).

### Confidence Filtering (FROZEN)

- Only appliances with `confidence >= 0.7` are considered for state evaluation
- This threshold prevents spurious detections from triggering false alerts

---

## 3. Alert Conditions (FROZEN)

### Primary Alert Trigger

```python
def should_alert(room_state: RoomState) -> bool:
    return room_state == "EMPTY_WASTING"
```

**Alert triggered when:**
- Room state is `EMPTY_WASTING`
- This indicates energy waste is actively occurring

### Alert Suppression (Future Extension)

The following conditions may suppress alerts in future phases (not yet implemented):

- `duration_sec < 60`: Brief transitions (< 1 minute) may not warrant alerts
- Scheduled maintenance windows
- User-defined "occupied-equivalent" zones (e.g., motion sensor areas)

**Note:** These are NOT part of PHASE 0 frozen contract. They require explicit design review.

---

## 4. Energy Savings Calculation (FROZEN)

### Formula

```
energy_saved_kwh = Σ(appliance_power_watts) × duration_sec / (1000 × 3600)
```

### Appliance Power Consumption (FROZEN)

| Appliance Type | Power (Watts) |
|---------------|---------------|
| Projector/TV | 150W |
| Laptop | 50W |
| Desktop | 100W |
| Monitor | 30W |
| **Default** | 100W |

### Calculation Rules

- Only appliances with `state == "ON"` contribute to savings
- Calculation only applies when `room_state == "EMPTY_WASTING"`
- `duration_sec` tracks time in current state (0 for single-frame inference)

---

## 5. Privacy Guarantees (FROZEN)

### Privacy Mode Requirements

When `privacy_mode = true`:

1. ✅ **No face extraction or recognition**
   - No face models loaded
   - No facial feature analysis

2. ✅ **Heavy blur applied to image data**
   - Gaussian blur (kernel size ≥ 51)
   - Makes individuals unrecognizable

3. ✅ **Skeleton overlay only**
   - Only pose keypoints rendered
   - No bounding boxes around people
   - Appliance bounding boxes allowed (non-PII)

4. ✅ **No transient storage of identifiable frames**
   - Annotated images saved only if `save_annotated=true`
   - Original frames discarded after inference

5. ✅ **Event data contains no PII**
   - Only aggregate counts and states
   - No tracking of individual identities

### Non-Privacy Mode

When `privacy_mode = false`:
- Full image with standard annotations
- Still no face recognition or PII extraction
- Useful for debugging and system validation

---

## 6. API Contract (FROZEN)

### `/audit` Endpoint

**Request:**
```
POST /audit
Content-Type: multipart/form-data

Parameters:
- file: UploadFile (required) - Image file to analyze
- room_id: string (optional, default: "default_room")
- sensitivity: int (optional, default: 160) - Brightness threshold [0-255]
- save_annotated: bool (optional, default: false)
- privacy_mode: bool (optional, default: false)
```

**Response:**
```json
{
  "event": {
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
    "energy_waste_detected": true,
    "energy_saved_kwh": 0.0417,
    "duration_sec": 0,
    "confidence": 0.92,
    "image_path": "/path/to/annotated.jpg",
    "privacy_mode": false
  },
  "processing_time_ms": 245.3,
  "model_versions": {
    "pose_model": "yolov8x-pose",
    "detection_model": "yolov8x",
    "schema_version": "PHASE_0_FROZEN"
  }
}
```

---

## 7. Implementation Files

| File | Purpose | Status |
|------|---------|--------|
| `schemas.py` | Pydantic models for RoomEvent and ApplianceDetection | ✅ FROZEN |
| `state_machine.py` | FSM logic and energy calculations | ✅ FROZEN |
| `main.py` | `/audit` endpoint with schema enforcement | ✅ IMPLEMENTED |
| `PHASE0_CONTRACT.md` | This document | ✅ FROZEN |

---

## 8. Compliance Checklist

Before deploying any component that produces or consumes events, verify:

- [ ] All events conform to `RoomEvent` schema
- [ ] FSM logic matches frozen transition rules
- [ ] Appliance confidence filtering uses threshold = 0.7
- [ ] Energy calculations use frozen power consumption table
- [ ] Privacy mode guarantees are enforced
- [ ] API responses include `schema_version: "PHASE_0_FROZEN"`
- [ ] No modifications to frozen enums (`ApplianceState`, `RoomState`)

---

## 9. Breaking Changes Policy

**This contract is FROZEN.**

Any breaking changes require:
1. Explicit approval from architecture review
2. New schema version (e.g., `PHASE_1_v2`)
3. Migration path for existing data
4. Backwards compatibility layer during transition

**Non-breaking extensions allowed:**
- Adding optional fields to `RoomEvent` (must have defaults)
- Adding new appliance types to power consumption table
- Adding helper methods to state machine (must not change core logic)

---

## 10. Test Cases (Validation)

### Test Case 1: Occupied Room
```python
people_count = 2
appliances = [ApplianceDetection(name="TV", state="ON", confidence=0.9)]

Expected:
  room_state = "OCCUPIED"
  energy_waste_detected = False
```

### Test Case 2: Empty + Safe
```python
people_count = 0
appliances = [ApplianceDetection(name="TV", state="OFF", confidence=0.9)]

Expected:
  room_state = "EMPTY_SAFE"
  energy_waste_detected = False
```

### Test Case 3: Empty + Wasting
```python
people_count = 0
appliances = [ApplianceDetection(name="Projector", state="ON", confidence=0.95)]

Expected:
  room_state = "EMPTY_WASTING"
  energy_waste_detected = True
  energy_saved_kwh > 0
```

### Test Case 4: Low Confidence Ignore
```python
people_count = 0
appliances = [ApplianceDetection(name="TV", state="ON", confidence=0.5)]

Expected:
  room_state = "EMPTY_SAFE"  # Low confidence ignored
  energy_waste_detected = False
```

---

## Approval

**Frozen By:** PHASE 0 Implementation Team
**Date:** 2026-03-27
**Status:** ✅ LOCKED FOR PRODUCTION

**Next Steps:**
- PHASE 1: Edge core implementation (camera sampler, stateful tracking)
- PHASE 2: Privacy layer audit and certification
- PHASE 3: Event streaming and replay infrastructure

---

**END OF PHASE 0 CONTRACT**
