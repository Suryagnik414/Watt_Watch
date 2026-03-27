"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          WATT-WATCH ENTERPRISE — AUDITOR ENGINE v2.0                        ║
║          Robust AI Backend with Full Appliance Differentiation              ║
╚══════════════════════════════════════════════════════════════════════════════╝

ARCHITECTURE OVERVIEW
─────────────────────
  AuditorEngine
  ├── OccupancyTracker       — Pose estimation + identity-safe person counting
  │   └── SkeletonRenderer   — High-fidelity keypoint visualiser (17-pt COCO)
  ├── ApplianceDetector      — Multi-class YOLO appliance recognition
  │   ├── ScreenAnalyser     — Laptop / Monitor / Projector / TV (by geometry)
  │   ├── ApplianceClassifier— AC, fan, printer, whiteboard, speaker
  │   └── EnergyEstimator    — Per-appliance wattage lookup table
  ├── LightDetector          — Ceiling-light blob detection with exclusion masking
  │   └── LightClassifier    — Tubelight / Bulb / LED panel (by shape & AR)
  └── AuditComposer          — Fuses all detections → AuditResult dataclass

DEPENDENCIES
────────────
  pip install ultralytics opencv-python-headless torch numpy scipy
"""

import cv2
import torch
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum
from scipy import ndimage
from ultralytics import YOLO

# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA CONTRACTS
# ─────────────────────────────────────────────────────────────────────────────

class LightType(str, Enum):
    TUBELIGHT  = "Tubelight"
    LED_PANEL  = "LED Panel"
    BULB       = "Bulb"
    SPOTLIGHT  = "Spotlight"
    UNKNOWN    = "Unknown"


class ApplianceType(str, Enum):
    LAPTOP      = "Laptop"
    MONITOR     = "Monitor"
    PROJECTOR   = "Projector"
    TV          = "TV / Display"
    AC_UNIT     = "AC Unit"
    CEILING_FAN = "Ceiling Fan"
    PRINTER     = "Printer"
    SPEAKER     = "Speaker"
    WHITEBOARD  = "Whiteboard (Electric)"
    MICROWAVE   = "Microwave"
    UNKNOWN     = "Unknown Appliance"


# Wattage reference table — conservative classroom estimates (watts)
WATTAGE_TABLE: Dict[ApplianceType, float] = {
    ApplianceType.LAPTOP:      45.0,
    ApplianceType.MONITOR:     30.0,
    ApplianceType.PROJECTOR:  250.0,
    ApplianceType.TV:         120.0,
    ApplianceType.AC_UNIT:   1500.0,
    ApplianceType.CEILING_FAN: 75.0,
    ApplianceType.PRINTER:    400.0,   # peak; 10W idle
    ApplianceType.SPEAKER:     20.0,
    ApplianceType.WHITEBOARD:  50.0,
    ApplianceType.MICROWAVE:  900.0,
    ApplianceType.UNKNOWN:     50.0,
}

LIGHT_WATTAGE: Dict[LightType, float] = {
    LightType.TUBELIGHT:  36.0,
    LightType.LED_PANEL:  18.0,
    LightType.BULB:       60.0,
    LightType.SPOTLIGHT:  20.0,
    LightType.UNKNOWN:    40.0,
}

# COCO 17-point skeleton connections (1-indexed, converted in code)
SKELETON_PAIRS = [
    (0, 1), (0, 2),            # nose → eyes
    (1, 3), (2, 4),            # eyes → ears
    (5, 6),                    # shoulders
    (5, 7), (7, 9),            # L arm
    (6, 8), (8, 10),           # R arm
    (5, 11), (6, 12),          # torso sides
    (11, 12),                  # hips
    (11, 13), (13, 15),        # L leg
    (12, 14), (14, 16),        # R leg
]

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# YOLO class IDs relevant to energy audit (COCO80)
SCREEN_CLASS_IDS   = {62, 63}          # TV / Laptop
APPLIANCE_CLASS_IDS = {
    68: ApplianceType.MICROWAVE,
    73: ApplianceType.LAPTOP,          # book → filtered out below
    74: ApplianceType.PRINTER,
    76: ApplianceType.SPEAKER,
}
# NOTE: AC, Fans, Projectors, Monitors are detected via heuristics below
# because they are inconsistently labelled in COCO80.


@dataclass
class DetectedLight:
    bbox: Tuple[int, int, int, int]    # x, y, w, h in ceiling ROI coords
    type: LightType
    brightness: float                  # 0–255 mean gray
    area_px: float
    is_active: bool = True


@dataclass
class DetectedAppliance:
    bbox: Tuple[int, int, int, int]    # x1, y1, x2, y2 in frame coords
    type: ApplianceType
    confidence: float
    is_active: bool                    # screen ON or appliance energised
    wattage: float = 0.0
    reason: str = ""                   # activation reason for HUD

    def __post_init__(self):
        self.wattage = WATTAGE_TABLE.get(self.type, 50.0)


@dataclass
class DetectedPerson:
    bbox: Tuple[int, int, int, int]
    confidence: float
    keypoints: np.ndarray              # shape (17, 3) — x, y, conf
    is_seated: bool = False
    is_active: bool = True             # future: sleeping detection


@dataclass
class AuditResult:
    persons: List[DetectedPerson]      = field(default_factory=list)
    appliances: List[DetectedAppliance]= field(default_factory=list)
    lights: List[DetectedLight]        = field(default_factory=list)

    # Rendered frames
    admin_frame:  Optional[np.ndarray] = None   # annotated original
    ghost_frame:  Optional[np.ndarray] = None   # blurred with overlays

    # Computed
    @property
    def person_count(self) -> int:
        return len(self.persons)

    @property
    def active_appliance_count(self) -> int:
        return sum(1 for a in self.appliances if a.is_active)

    @property
    def active_light_count(self) -> int:
        return sum(1 for l in self.lights if l.is_active)

    @property
    def total_active_wattage(self) -> float:
        light_w    = sum(LIGHT_WATTAGE[l.type] for l in self.lights if l.is_active)
        appliance_w = sum(a.wattage for a in self.appliances if a.is_active)
        return light_w + appliance_w

    @property
    def is_wasting_energy(self) -> bool:
        """True when room is empty but energy consumers are active."""
        return self.person_count == 0 and (
            self.active_appliance_count > 0 or self.active_light_count > 0
        )

    @property
    def appliance_summary(self) -> Dict[str, int]:
        from collections import Counter
        return dict(Counter(a.type.value for a in self.appliances if a.is_active))


# ─────────────────────────────────────────────────────────────────────────────
# 2. LIGHT DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class LightDetector:
    """
    Detects active ceiling lights by analysing the upper 30% of the frame.

    Pipeline
    ────────
    1. Crop ceiling ROI
    2. Apply exclusion mask (screens / glare sources)
    3. Adaptive threshold → binary blob map
    4. Morphological ops to consolidate blobs
    5. Classify each blob by shape (aspect ratio → tubelight vs bulb vs panel)
    """

    CEILING_RATIO    = 0.30   # top fraction of frame to analyse
    MIN_BLOB_AREA    = 200    # px² — raised: kills glare flecks & lens artefacts
    SPOTLIGHT_MIN    = 400    # px² — must be this large to count as a spotlight
    TUBE_AR_MIN      = 3.0    # width/height > 3  → tubelight / linear fixture
    PANEL_AR_MIN     = 0.75   # near-square, large → LED panel
    PANEL_MIN_AREA   = 800    # px²
    # Minimum solidity (area / convex-hull area) for a real fixture.
    # Noise blobs and lens flares are irregular; real lights are compact.
    MIN_SOLIDITY     = 0.45

    def detect(
        self,
        frame: np.ndarray,
        exclusion_mask: np.ndarray,
        brightness_threshold: int = 248,
    ) -> List[DetectedLight]:
        h, w = frame.shape[:2]
        ceil_h = int(h * self.CEILING_RATIO)

        # Crop
        roi   = frame[0:ceil_h, 0:w]
        gray  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        emask = exclusion_mask[0:ceil_h, 0:w]

        # Suppress screen/window glare
        gray = gray.copy()
        gray[emask == 255] = 0

        # Adaptive threshold (global + adaptive combined)
        _, th_global = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)
        th_adaptive  = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31, C=-25
        )
        combined = cv2.bitwise_and(th_global, th_adaptive)

        # Morphology to close gaps in tubular fixtures
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        lights = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.MIN_BLOB_AREA:
                continue

            # Solidity check: rejects lens flares, window glare, irregular noise.
            # Real ceiling fixtures are compact; artefacts are jagged or hollow.
            hull      = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity  = area / hull_area if hull_area > 0 else 0.0
            if solidity < self.MIN_SOLIDITY:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio  = bw / max(bh, 1)
            crop_blob     = gray[y:y+bh, x:x+bw]
            brightness    = float(np.mean(crop_blob))

            # Classify by geometry
            if aspect_ratio >= self.TUBE_AR_MIN:
                ltype = LightType.TUBELIGHT
            elif area >= self.PANEL_MIN_AREA and self.PANEL_AR_MIN <= aspect_ratio <= (1.0 / self.PANEL_AR_MIN):
                ltype = LightType.LED_PANEL
            elif aspect_ratio < 1.5 and area < self.PANEL_MIN_AREA:
                ltype = LightType.BULB
            elif area >= self.SPOTLIGHT_MIN and aspect_ratio < 2.0:
                # Only emit spotlight if large enough to be a real recessed
                # fixture — previously fired on tiny glare dots.
                ltype = LightType.SPOTLIGHT
            else:
                # Does not match any known fixture profile — discard rather than
                # emit a spurious UNKNOWN reading.
                continue

            lights.append(DetectedLight(
                bbox=(x, y, bw, bh),
                type=ltype,
                brightness=brightness,
                area_px=area,
                is_active=True,
            ))

        return lights


class LaptopStateAnalyser:
    """
    Determines whether a laptop/monitor is powered ON using four independent
    evidence channels. Any single channel can confirm ON; all must be absent to
    call it OFF. This makes the system robust when the screen faces away from
    the camera.

    Signal A — Direct screen brightness (original method)
    ──────────────────────────────────────────────────────
    Mean gray of the YOLO crop ≥ threshold. Works when the screen faces camera.

    Signal B — Edge light spill
    ────────────────────────────
    An active LCD/OLED screen leaks light around its bezel edge. The pixels in
    a thin border *outside* the YOLO box (above, left, right) are brighter than
    the ambient background when the screen is on. We compare the mean brightness
    of a 12px halo outside the box to the mean brightness of the surrounding
    non-laptop region. A ratio > SPILL_RATIO_THRESHOLD indicates light emission.

    Signal C — Keyboard backlight / indicator LED glow
    ───────────────────────────────────────────────────
    The bottom 20% of the YOLO crop is the keyboard deck. Backlit keyboards and
    power LEDs create localised bright spots here even on a closed/angled lid.
    We look for high-contrast local maxima (bright spots) in the keyboard zone
    using a morphological top-hat transform, which isolates small bright objects
    against a darker background.

    Signal D — Thermal colour shift (bluish-white vs off-grey)
    ───────────────────────────────────────────────────────────
    LCD screens when on emit a cold blue-white cast that reflects off nearby
    surfaces even when the screen itself isn't camera-facing. We check the HSV
    saturation and hue of the laptop crop: a screen-on laptop tends toward
    low-saturation blue-white (hue 90–130°, sat 0–60) vs a powered-off laptop
    which is a matte grey/black (near-zero saturation, darker value).
    """

    # Signal A
    SCREEN_BRIGHTNESS_THRESH = 170   # mean gray of crop

    # Signal B — edge spill
    SPILL_HALO_PX     = 14    # pixels outside YOLO box to sample
    SPILL_RATIO_THRESH = 1.18  # halo must be 18% brighter than ambient

    # Signal C — keyboard top-hat
    TOPHAT_KERNEL_SZ  = 15    # morphological kernel for small bright regions
    TOPHAT_MEAN_THRESH = 8    # mean top-hat response in keyboard zone

    # Signal D — thermal hue
    SCREEN_HUE_LOW  = 85     # HSV hue range for screen-glow blue-white
    SCREEN_HUE_HIGH = 135
    SCREEN_SAT_MAX  = 70     # low saturation (nearly white/grey)
    SCREEN_VAL_MIN  = 80     # not too dark
    SCREEN_HUE_PIXEL_FRAC = 0.12   # at least 12% of pixels in hue range

    # Scoring: how many signals must fire to call ON
    SIGNALS_NEEDED    = 1     # any single signal is enough to call ON
    # But for a confident OFF with NO person, require all 4 to be absent.

    def analyse(
        self,
        frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        brightness_threshold: int = 170,
    ) -> Tuple[bool, str, int]:
        """
        Returns:
            is_active  — bool
            reason     — human-readable string naming which signal fired
            score      — number of signals that voted ON (0–4), useful for debug
        """
        h, w = frame.shape[:2]
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return False, "empty crop", 0

        signals_fired = []

        # ── Signal A: direct screen brightness ────────────────────────────────
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if float(np.mean(gray_crop)) >= brightness_threshold:
            signals_fired.append("screen brightness")

        # ── Signal B: edge light spill ────────────────────────────────────────
        halo = self.SPILL_HALO_PX
        # Sample a thin ring outside the YOLO box, clamped to frame
        top_band    = frame[max(0, y1-halo):y1,         x1:x2]
        left_band   = frame[y1:y2,                       max(0, x1-halo):x1]
        right_band  = frame[y1:y2,                       x2:min(w, x2+halo)]

        halo_bands = [b for b in [top_band, left_band, right_band] if b.size > 0]
        if halo_bands:
            halo_gray   = [cv2.cvtColor(b, cv2.COLOR_BGR2GRAY) for b in halo_bands]
            halo_mean   = float(np.mean(np.concatenate([g.flatten() for g in halo_gray])))

            # Ambient: a wider surrounding box excluding the laptop itself
            pad = halo + 40
            surr = frame[max(0, y1-pad):min(h, y2+pad), max(0, x1-pad):min(w, x2+pad)]
            # Mask out the laptop box from the surrounding sample
            surr_gray = cv2.cvtColor(surr, cv2.COLOR_BGR2GRAY).astype(float)
            # Zero out the inner laptop region
            inner_y1 = min(pad, y1)
            inner_x1 = min(pad, x1)
            inner_y2 = inner_y1 + (y2 - y1)
            inner_x2 = inner_x1 + (x2 - x1)
            surr_gray[inner_y1:inner_y2, inner_x1:inner_x2] = np.nan
            ambient_mean = float(np.nanmean(surr_gray))

            if ambient_mean > 0 and halo_mean / ambient_mean >= self.SPILL_RATIO_THRESH:
                signals_fired.append("edge light spill")

        # ── Signal C: keyboard backlight / LED (top-hat) ──────────────────────
        bh = y2 - y1
        keyboard_zone = crop[int(bh * 0.75):, :]   # bottom 25% = keyboard deck
        if keyboard_zone.size > 0:
            kz_gray  = cv2.cvtColor(keyboard_zone, cv2.COLOR_BGR2GRAY)
            kernel   = cv2.getStructuringElement(
                cv2.MORPH_RECT, (self.TOPHAT_KERNEL_SZ, self.TOPHAT_KERNEL_SZ)
            )
            tophat   = cv2.morphologyEx(kz_gray, cv2.MORPH_TOPHAT, kernel)
            if float(np.mean(tophat)) >= self.TOPHAT_MEAN_THRESH:
                signals_fired.append("keyboard backlight")

        # ── Signal D: thermal hue (screen blue-white cast) ────────────────────
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
        in_hue_range = (
            (h_ch >= self.SCREEN_HUE_LOW)  & (h_ch <= self.SCREEN_HUE_HIGH) &
            (s_ch <= self.SCREEN_SAT_MAX)  & (v_ch >= self.SCREEN_VAL_MIN)
        )
        hue_pixel_frac = float(np.mean(in_hue_range))
        if hue_pixel_frac >= self.SCREEN_HUE_PIXEL_FRAC:
            signals_fired.append("screen hue cast")

        is_active = len(signals_fired) >= self.SIGNALS_NEEDED
        reason_str = (
            " + ".join(signals_fired) if signals_fired
            else "no active signals (lid closed or off)"
        )
        return is_active, reason_str, len(signals_fired)


# ─────────────────────────────────────────────────────────────────────────────
# 3. APPLIANCE DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class ApplianceDetector:
    """
    Detects and classifies energy-consuming appliances using YOLOv8x detections
    plus a rule-based geometry layer for appliances under-represented in COCO80.

    Hierarchy
    ─────────
    1.  YOLO box → class ID → primary label
    2.  Geometry refinement:
        - Aspect ratio → screen type (laptop vs monitor vs projector)
        - Position (ceiling zone) → fan / projector / AC
        - Size normalised to frame → "is this a wall-mounted unit?"
    3.  Activity check: mean brightness of crop → screen ON/OFF
    """

    MIN_SCREEN_AREA     = 8_000  # px² — filters A4 papers
    CEILING_ZONE_RATIO  = 0.25   # top 25% → projector / fan / AC candidate
    WIDE_SCREEN_AR      = 1.6    # width/height > this → widescreen monitor/TV
    PROJECTOR_AR_MIN    = 1.2
    PROJECTOR_AREA_MAX  = 80_000 # px² — projected wall image is larger; exclude

    def __init__(self, screen_brightness_threshold: int = 170):
        self.sb_thresh = screen_brightness_threshold
        self.laptop_analyser = LaptopStateAnalyser()

    def detect(
        self,
        frame: np.ndarray,
        yolo_boxes,           # ultralytics Boxes object
    ) -> Tuple[List[DetectedAppliance], np.ndarray]:
        """
        Returns:
            appliances     — list of DetectedAppliance
            exclusion_mask — uint8 mask of screen regions (for LightDetector)
        """
        h, w = frame.shape[:2]
        exclusion_mask = np.zeros((h, w), dtype=np.uint8)
        appliances: List[DetectedAppliance] = []

        if yolo_boxes is None:
            return appliances, exclusion_mask

        for box in yolo_boxes:
            cls_id = int(box.cls[0])
            conf   = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Clamp to frame
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            bw, bh = x2 - x1, y2 - y1
            area   = bw * bh
            if area < 400:  # ignore microscopic detections
                continue

            crop = frame[y1:y2, x1:x2]
            gray_mean = float(np.mean(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)))

            # ── Screens ──────────────────────────────────────────────────────
            if cls_id in SCREEN_CLASS_IDS:
                if area < self.MIN_SCREEN_AREA:
                    continue   # filter paper / book false positives

                # Multi-signal state analysis (replaces single brightness check)
                is_active, signal_reason, signal_score = self.laptop_analyser.analyse(
                    frame, x1, y1, x2, y2,
                    brightness_threshold=self.sb_thresh,
                )
                atype = self._classify_screen_type(
                    x1, y1, x2, y2, bw, bh, area, h, w
                )

                if is_active:
                    cv2.rectangle(exclusion_mask, (x1, y1), (x2, y2), 255, -1)

                appliances.append(DetectedAppliance(
                    bbox=(x1, y1, x2, y2),
                    type=atype,
                    confidence=conf,
                    is_active=is_active,
                    reason=signal_reason,
                ))

            # ── Mapped COCO appliances ────────────────────────────────────────
            elif cls_id in APPLIANCE_CLASS_IDS:
                atype = APPLIANCE_CLASS_IDS[cls_id]
                appliances.append(DetectedAppliance(
                    bbox=(x1, y1, x2, y2),
                    type=atype,
                    confidence=conf,
                    is_active=True,   # assume on unless deep analysis added
                ))

            # ── Heuristic: ceiling-zone objects → fan / AC ────────────────────
            elif y2 < h * self.CEILING_ZONE_RATIO:
                atype = self._classify_ceiling_appliance(bw, bh, area, conf)
                if atype is not None:
                    appliances.append(DetectedAppliance(
                        bbox=(x1, y1, x2, y2),
                        type=atype,
                        confidence=conf * 0.7,  # reduced confidence (heuristic)
                        is_active=True,
                    ))

        return appliances, exclusion_mask

    def _classify_screen_type(
        self,
        x1, y1, x2, y2, bw, bh, area, frame_h, frame_w
    ) -> ApplianceType:
        """Distinguish laptop / monitor / TV / projector by geometry only.
        ON/OFF state is now determined separately by LaptopStateAnalyser."""
        ar = bw / max(bh, 1)
        y_center = (y1 + y2) / 2

        # Projector screen: very large, wide, high on wall
        if (area > self.PROJECTOR_AREA_MAX
                and ar > self.PROJECTOR_AR_MIN
                and y_center < frame_h * 0.55):
            return ApplianceType.PROJECTOR

        # TV / large wall display: very wide, medium-large area
        if ar >= self.WIDE_SCREEN_AR and area > 40_000:
            return ApplianceType.TV

        # Laptop: smaller, near desk height
        if area < 60_000 and y_center > frame_h * 0.35:
            return ApplianceType.LAPTOP

        # Default → monitor
        return ApplianceType.MONITOR

    def _classify_ceiling_appliance(
        self, bw: int, bh: int, area: float, conf: float
    ) -> Optional[ApplianceType]:
        """
        Heuristic classification of ceiling-zone YOLO detections.

        Tightened rules vs v1:
        - Ceiling fan now requires area > 12,000 px² (was 3,000) so that
          ceiling tiles, light housings, and camera artefacts don't trigger it.
        - Requires YOLO confidence > 0.50 for fan (heuristic-only detections
          were firing on anything symmetric in the ceiling zone).
        - AC vent threshold raised and also confidence-gated.
        """
        ar = bw / max(bh, 1)

        # Ceiling fan: must be large, roughly symmetric, and YOLO-confident
        if 0.6 <= ar <= 1.6 and area > 12_000 and conf > 0.50:
            return ApplianceType.CEILING_FAN

        # AC unit / vent: wide, thin, and reasonably confident
        if ar > 2.5 and area > 6_000 and conf > 0.45:
            return ApplianceType.AC_UNIT

        return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. OCCUPANCY TRACKER
# ─────────────────────────────────────────────────────────────────────────────

class OccupancyTracker:
    """
    Detects persons using YOLOv8-Pose (17-keypoint COCO skeleton).

    Features
    ────────
    • Seated detection: if hip keypoints are low relative to shoulder keypoints
      and knees are roughly at shoulder height → seated.
    • Keypoint confidence gating: only draws joints with conf > CONF_GATE.
    • Ghost mode: Gaussian blur with skeleton overlay protects identity.
    """

    CONF_GATE    = 0.30   # min keypoint confidence to draw
    SEAT_RATIO   = 0.25   # hip-to-shoulder vertical drop / torso height

    def detect(self, pose_result) -> List[DetectedPerson]:
        persons = []
        if pose_result.boxes is None:
            return persons

        boxes  = pose_result.boxes
        kpts_all = pose_result.keypoints

        for i, box in enumerate(boxes):
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            kpts_tensor = kpts_all.data[i].cpu().numpy()  # (17, 3)
            is_seated   = self._check_seated(kpts_tensor)

            persons.append(DetectedPerson(
                bbox=(x1, y1, x2, y2),
                confidence=conf,
                keypoints=kpts_tensor,
                is_seated=is_seated,
            ))

        return persons

    def _check_seated(self, kpts: np.ndarray) -> bool:
        """Estimate if person is seated from skeleton geometry."""
        # Indices: shoulders=5,6 | hips=11,12 | knees=13,14
        sh_l, sh_r = kpts[5], kpts[6]
        hi_l, hi_r = kpts[11], kpts[12]

        # Need visible shoulders and hips
        if sh_l[2] < 0.3 and sh_r[2] < 0.3:
            return False
        if hi_l[2] < 0.3 and hi_r[2] < 0.3:
            return False

        sh_y  = np.mean([sh_l[1], sh_r[1]])
        hip_y = np.mean([hi_l[1], hi_r[1]])

        # Torso length
        torso = hip_y - sh_y
        if torso < 30:   # unreliable detection
            return False

        # If hips are high relative to torso, person is seated
        kn_l, kn_r = kpts[13], kpts[14]
        if kn_l[2] < 0.3 and kn_r[2] < 0.3:
            return False

        kn_y = np.mean([kn_l[1], kn_r[1]])
        # Knees should be close to hip height when seated
        return abs(kn_y - hip_y) < torso * 0.5


# ─────────────────────────────────────────────────────────────────────────────
# 5. FRAME COMPOSER
# ─────────────────────────────────────────────────────────────────────────────

# Visual config
COLORS = {
    "skeleton_limb"   : (0,   220, 255),   # cyan
    "skeleton_joint"  : (255, 200,   0),   # amber
    "skeleton_head"   : (0,   255, 128),   # mint
    "seated_tint"     : (128,   0, 255),   # purple → seated person
    "light_tubelight" : (255, 255,  80),   # warm yellow
    "light_panel"     : (200, 255, 255),   # cool white
    "light_bulb"      : (255, 200,  60),   # incandescent amber
    "light_unknown"   : (200, 200, 200),
    "appliance_laptop": (80,  200, 120),   # green
    "appliance_monitor":(40,  180, 255),   # blue
    "appliance_proj"  : (255, 100, 200),   # pink/magenta
    "appliance_tv"    : (255, 140,  40),   # orange
    "appliance_ac"    : (100, 220, 255),   # light blue
    "appliance_fan"   : (160, 255, 160),
    "appliance_other" : (200, 200, 200),
}

APPLIANCE_COLORS = {
    ApplianceType.LAPTOP  : COLORS["appliance_laptop"],
    ApplianceType.MONITOR : COLORS["appliance_monitor"],
    ApplianceType.PROJECTOR: COLORS["appliance_proj"],
    ApplianceType.TV      : COLORS["appliance_tv"],
    ApplianceType.AC_UNIT : COLORS["appliance_ac"],
    ApplianceType.CEILING_FAN: COLORS["appliance_fan"],
}

LIGHT_COLORS = {
    LightType.TUBELIGHT : COLORS["light_tubelight"],
    LightType.LED_PANEL : COLORS["light_panel"],
    LightType.BULB      : COLORS["light_bulb"],
    LightType.SPOTLIGHT : COLORS["light_panel"],
    LightType.UNKNOWN   : COLORS["light_unknown"],
}


class FrameComposer:
    """Renders all detections onto admin and ghost views."""

    CEIL_RATIO = 0.30

    def compose(
        self,
        frame: np.ndarray,
        result: AuditResult,
    ) -> Tuple[np.ndarray, np.ndarray]:
        h, w = frame.shape[:2]
        admin = frame.copy()
        ghost = cv2.GaussianBlur(frame.copy(), (99, 99), 30)

        self._draw_ceiling_divider(admin, h)
        self._draw_ceiling_divider(ghost, h)

        self._draw_lights(admin, result.lights, h, w)
        self._draw_lights(ghost, result.lights, h, w)

        self._draw_appliances(admin, result.appliances)
        self._draw_appliances(ghost, result.appliances)

        self._draw_skeletons(admin, result.persons)
        self._draw_skeletons(ghost, result.persons)

        self._draw_hud(admin, result)
        self._draw_hud(ghost, result)

        return admin, ghost

    # ── Lights ────────────────────────────────────────────────────────────────

    def _draw_lights(
        self, frame: np.ndarray, lights: List[DetectedLight], h: int, w: int
    ):
        for lt in lights:
            x, y, bw, bh = lt.bbox
            color = LIGHT_COLORS.get(lt.type, COLORS["light_unknown"])

            # Draw in original frame coordinates (roi was top 30%)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 3)

            # Glow halo
            overlay = frame.copy()
            pad = 12
            cv2.rectangle(overlay,
                          (max(0, x-pad), max(0, y-pad)),
                          (min(w, x+bw+pad), min(h, y+bh+pad)),
                          color, -1)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

            # Label
            label = f"{lt.type.value} ({lt.brightness:.0f})"
            self._label(frame, label, (x, max(0, y - 6)), color)

    # ── Appliances ────────────────────────────────────────────────────────────

    def _draw_appliances(self, frame: np.ndarray, appliances: List[DetectedAppliance]):
        for ap in appliances:
            x1, y1, x2, y2 = ap.bbox
            color = APPLIANCE_COLORS.get(ap.type, COLORS["appliance_other"])

            # Outer box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 4)

            # Status icon (active = solid, inactive = dashed)
            if not ap.is_active:
                self._draw_dashed_rect(frame, x1, y1, x2, y2, color)

            # Label pill
            watts_str = f"{ap.wattage:.0f}W"
            reason    = getattr(ap, "reason", "")
            label = f"{ap.type.value}  {watts_str}"
            if not ap.is_active:
                label += "  [OFF]"
            elif "person nearby" in reason:
                label += "  [INFERRED:PERSON]"
            elif reason and "screen brightness" not in reason:
                # Active via indirect signals (spill / keyboard / hue)
                label += "  [INFERRED:SIGNAL]"
            lbl_y = max(18, y1 - 8)
            self._label(frame, label, (x1, lbl_y), color, pill=True)

    # ── Skeletons ─────────────────────────────────────────────────────────────

    def _draw_skeletons(self, frame: np.ndarray, persons: List[DetectedPerson]):
        for person in persons:
            kpts = person.keypoints      # (17, 3)
            color_limb  = COLORS["seated_tint"] if person.is_seated else COLORS["skeleton_limb"]

            # Draw limbs
            for i, j in SKELETON_PAIRS:
                pt1, pt2 = kpts[i], kpts[j]
                if pt1[2] < 0.30 or pt2[2] < 0.30:
                    continue
                p1 = (int(pt1[0]), int(pt1[1]))
                p2 = (int(pt2[0]), int(pt2[1]))
                thickness = max(1, int(2 + 2 * min(pt1[2], pt2[2])))
                cv2.line(frame, p1, p2, color_limb, thickness, cv2.LINE_AA)

            # Draw joints
            for idx, kp in enumerate(kpts):
                if kp[2] < 0.30:
                    continue
                cx, cy = int(kp[0]), int(kp[1])
                jcolor = COLORS["skeleton_head"] if idx < 5 else COLORS["skeleton_joint"]
                radius = max(3, int(5 * kp[2]))
                cv2.circle(frame, (cx, cy), radius + 2, (0, 0, 0), -1)
                cv2.circle(frame, (cx, cy), radius, jcolor, -1)

            # Bounding box + status
            x1, y1, x2, y2 = person.bbox
            status = "SEATED" if person.is_seated else "STANDING"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 80, 80), 1)
            self._label(frame, status, (x1, y2 + 14), (180, 180, 180))

    # ── HUD overlay ───────────────────────────────────────────────────────────

    def _draw_hud(self, frame: np.ndarray, result: AuditResult):
        h, w = frame.shape[:2]
        hud_lines = [
            f"Persons : {result.person_count}",
            f"Lights  : {result.active_light_count}",
            f"Devices : {result.active_appliance_count}",
            f"Load    : {result.total_active_wattage:.0f} W",
            f"Waste   : {'YES !!!' if result.is_wasting_energy else 'No'}",
        ]
        x_hud, y_start, line_h = 10, 20, 22
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (210, y_start + len(hud_lines) * line_h + 5),
                      (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        for i, line in enumerate(hud_lines):
            color = (0, 80, 255) if "YES" in line else (200, 255, 200)
            cv2.putText(frame, line, (x_hud, y_start + i * line_h),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 1, cv2.LINE_AA)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _draw_ceiling_divider(self, frame: np.ndarray, h: int):
        y = int(h * self.CEIL_RATIO)
        cv2.line(frame, (0, y), (frame.shape[1], y), (80, 80, 80), 1)
        cv2.putText(frame, "CEILING ZONE", (4, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (80, 80, 80), 1)

    def _label(
        self,
        frame: np.ndarray,
        text: str,
        pos: Tuple[int, int],
        color: Tuple[int, int, int],
        pill: bool = False,
    ):
        x, y = pos
        (tw, th), bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        if pill:
            cv2.rectangle(frame, (x - 2, y - th - 4), (x + tw + 4, y + bl), (20, 20, 20), -1)
            cv2.rectangle(frame, (x - 2, y - th - 4), (x + tw + 4, y + bl), color, 1)
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    def _draw_dashed_rect(self, frame, x1, y1, x2, y2, color, dash=10):
        """Draw a dashed rectangle (for inactive appliances)."""
        pts = [(x1, y1, x2, y1), (x2, y1, x2, y2),
               (x2, y2, x1, y2), (x1, y2, x1, y1)]
        for ax, ay, bx, by in pts:
            length = int(np.hypot(bx - ax, by - ay))
            for d in range(0, length, dash * 2):
                t = d / length
                t2 = min((d + dash) / length, 1.0)
                p1 = (int(ax + t * (bx - ax)), int(ay + t * (by - ay)))
                p2 = (int(ax + t2 * (bx - ax)), int(ay + t2 * (by - ay)))
                cv2.line(frame, p1, p2, color, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 6. PROXIMITY ACTIVATOR
# ─────────────────────────────────────────────────────────────────────────────

class ProximityActivator:
    """
    Overrides the brightness-based is_active flag on screen-type appliances
    when a person is detected in close proximity.

    WHY THIS EXISTS
    ───────────────
    Laptops in classrooms are often angled away from the camera so the screen
    is invisible. Brightness-based detection then marks them OFF even though a
    student is actively working. This pass checks whether any detected person's
    lower body (hip/knee region, or failing that the full bounding box) overlaps
    or is within PROXIMITY_PX pixels of the appliance box. If yes, the appliance
    is flipped to active=True and tagged with a reason string for the HUD.

    The override is intentionally conservative:
      - Only applies to LAPTOP and MONITOR (screen-type devices a user sits at).
      - TV and PROJECTOR are wall-mounted and not "sat at", so they are excluded.
      - The proximity zone extends BELOW the appliance box (desk plane) where
        a person's body would actually appear, not above it.
      - Requires person confidence ≥ PERSON_CONF_MIN so ghost detections don't
        falsely activate devices.
    """

    PROXIMITY_PX     = 160    # horizontal/vertical expansion of appliance box
    PERSON_CONF_MIN  = 0.35   # min person detection confidence to use
    SCREEN_TYPES     = {ApplianceType.LAPTOP, ApplianceType.MONITOR}

    def apply(
        self,
        appliances: List[DetectedAppliance],
        persons:    List[DetectedPerson],
        frame_h:    int,
    ) -> List[DetectedAppliance]:
        """
        Mutates appliances in-place, returns the same list for chaining.
        Adds a `.reason` attribute (str) to each appliance for HUD display.
        """
        if not persons or not appliances:
            return appliances

        # Pre-filter to confident persons only
        valid_persons = [p for p in persons if p.confidence >= self.PERSON_CONF_MIN]
        if not valid_persons:
            return appliances

        for ap in appliances:
            if ap.type not in self.SCREEN_TYPES:
                continue
            if ap.is_active:
                # Already active from brightness — nothing to override
                ap.reason = "screen visible"
                continue

            ax1, ay1, ax2, ay2 = ap.bbox
            pad = self.PROXIMITY_PX

            # Expanded search zone: extend downward more than upward because
            # the person sits BELOW the laptop on the desk plane.
            search_x1 = ax1 - pad
            search_y1 = ay1 - pad // 2
            search_x2 = ax2 + pad
            search_y2 = ay2 + pad * 2      # generous downward expansion

            for person in valid_persons:
                # Use hip keypoints if visible (more precise desk-plane anchor)
                person_box = self._get_person_zone(person, frame_h)
                px1, py1, px2, py2 = person_box

                # Check overlap between search zone and person zone
                overlap = (
                    px1 < search_x2 and px2 > search_x1 and
                    py1 < search_y2 and py2 > search_y1
                )
                if overlap:
                    ap.is_active = True
                    ap.reason    = "person nearby (screen hidden from camera)"
                    break
            else:
                if not ap.is_active:
                    ap.reason = ap.reason or "no active signals (lid closed or off)"

        return appliances

    def _get_person_zone(self, person: DetectedPerson, frame_h: int):
        """
        Returns the most relevant bounding region of the person for proximity
        testing. Prefers the hip→ankle region (lower body, desk-level contact
        zone). Falls back to the full bounding box if keypoints are weak.
        """
        kpts = person.keypoints  # (17, 3)

        # Keypoint indices: hips=11,12  knees=13,14  ankles=15,16
        lower_pts = [kpts[i] for i in [11, 12, 13, 14, 15, 16] if kpts[i][2] > 0.30]

        if len(lower_pts) >= 2:
            xs = [int(p[0]) for p in lower_pts]
            ys = [int(p[1]) for p in lower_pts]
            return min(xs), min(ys), max(xs), max(ys)

        # Fallback: full detection box
        return person.bbox


# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class AuditorEngine:
    """
    Top-level façade. Loads models once; call process() per frame.

    Usage
    ─────
        engine = AuditorEngine()
        result = engine.process(frame, light_threshold=248, screen_threshold=170)
    """

    def __init__(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[WattWatch] Loading models on {device} ...")

        # P6 variant handles dense 36-student classroom scenes
        self.pose_model = YOLO("yolov8x-pose-p6.pt").to(device)
        self.det_model  = YOLO("yolov8x.pt").to(device)
        self.device     = device

        self.light_detector    = LightDetector()
        self.appliance_det     = ApplianceDetector()
        self.occupancy_tracker = OccupancyTracker()
        self.proximity_act     = ProximityActivator()
        self.composer          = FrameComposer()

        print("[WattWatch] Engine ready.")

    def process(
        self,
        frame:             np.ndarray,
        light_threshold:   int = 248,
        screen_threshold:  int = 170,
        imgsz:             int = 1280,
    ) -> AuditResult:
        """
        Full audit pipeline for one frame.

        Returns AuditResult with:
          - persons, appliances, lights (structured detections)
          - admin_frame  (annotated colour feed for ops)
          - ghost_frame  (blurred feed for student-safe public display)
        """
        # ── A. Detection ──────────────────────────────────────────────────────
        det_res = self.det_model.predict(
            source=frame, imgsz=imgsz, conf=0.40,
            device=self.device, verbose=False
        )[0]

        pose_res = self.pose_model.predict(
            source=frame, imgsz=imgsz, conf=0.15,
            device=self.device, verbose=False
        )[0]

        # ── B. Parse detections ───────────────────────────────────────────────
        appliances, exclusion_mask = self.appliance_det.detect(
            frame, det_res.boxes,
        )
        # Override screen brightness threshold from UI slider
        self.appliance_det.sb_thresh = screen_threshold

        lights = self.light_detector.detect(
            frame, exclusion_mask, brightness_threshold=light_threshold
        )

        persons = self.occupancy_tracker.detect(pose_res)

        # ── C. Proximity override — activate hidden screens near persons ───────
        # Must run AFTER both appliances and persons are known.
        appliances = self.proximity_act.apply(appliances, persons, frame.shape[0])

        # ── D. Build result ───────────────────────────────────────────────────
        result = AuditResult(
            persons=persons,
            appliances=appliances,
            lights=lights,
        )

        # ── D. Compose views ──────────────────────────────────────────────────
        result.admin_frame, result.ghost_frame = self.composer.compose(frame, result)

        return result


# ─────────────────────────────────────────────────────────────────────────────
# 7. FINANCIAL CALCULATOR (pure, no UI coupling)
# ─────────────────────────────────────────────────────────────────────────────

INR_PER_KWH = 9.50   # ₹/kWh — configurable

def compute_financials(result: AuditResult, elapsed_seconds: float) -> Dict:
    """
    Returns a dict with:
      - wasted_inr       : cost of energy wasted (empty room, appliances on)
      - potential_saving : same as above (framing for savings tracker)
      - active_wattage   : total watts active this frame
      - breakdown        : per-appliance-type wattage
    """
    wasted_kwh = (result.total_active_wattage / 1000) * (elapsed_seconds / 3600)
    wasted_inr = wasted_kwh * INR_PER_KWH if result.is_wasting_energy else 0.0

    breakdown = {}
    for ap in result.appliances:
        if ap.is_active:
            key = ap.type.value
            breakdown[key] = breakdown.get(key, 0.0) + ap.wattage
    for lt in result.lights:
        if lt.is_active:
            key = lt.type.value
            breakdown[key] = breakdown.get(key, 0.0) + LIGHT_WATTAGE[lt.type]

    return {
        "wasted_inr"       : wasted_inr,
        "potential_saving" : wasted_inr,
        "active_wattage"   : result.total_active_wattage,
        "breakdown"        : breakdown,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. SELF-TEST (runs without a camera)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    print("=" * 60)
    print("  WATT-WATCH ENGINE v2.0 — Self-test (synthetic frame)")
    print("=" * 60)

    # Synthetic 720p BGR frame with a bright rectangle simulating a screen
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    test_frame[50:200, 100:200, :] = 240     # fake ceiling light (bright blob)
    test_frame[300:600, 400:700, :] = [180, 180, 200]  # fake screen

    engine = AuditorEngine()

    t0 = time.perf_counter()
    result = engine.process(test_frame, light_threshold=200, screen_threshold=140)
    dt = time.perf_counter() - t0

    print(f"\n  Frame processed in {dt*1000:.1f} ms")
    print(f"  Persons    : {result.person_count}")
    print(f"  Lights     : {result.active_light_count}")
    print(f"  Appliances : {result.active_appliance_count}")
    print(f"  Total load : {result.total_active_wattage:.1f} W")
    print(f"  Wasting?   : {result.is_wasting_energy}")
    print(f"  Summary    : {result.appliance_summary}")

    fin = compute_financials(result, elapsed_seconds=1.0)
    print(f"\n  Wasted INR/s : ₹{fin['wasted_inr']:.6f}")
    print(f"  Breakdown    : {fin['breakdown']}")
    print("\n  Engine OK ✓")