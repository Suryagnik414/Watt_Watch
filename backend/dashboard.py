import streamlit as st
import cv2
import torch
import numpy as np
from ultralytics import YOLO
import time
from datetime import datetime
import pandas as pd

# --- TASK 5: PROFESSIONAL COMMAND CENTER CONFIG ---
st.set_page_config(page_title="Watt-Watch: FINAL CHAMPION", layout="wide")

@st.cache_resource
def load_gpu_models():
    # SOTA P6 Model for 36+ students (Task 1)
    pose_model = YOLO('yolov8x-pose-p6.pt').to('cuda')
    # X-Large model for Laptops/Projectors (Task 2)
    detect_model = YOLO('yolov8x.pt').to('cuda')
    return pose_model, detect_model

class WattWatchChampion:
    def __init__(self):
        self.pose_model, self.detect_model = load_gpu_models()
        self.skeleton = [(16,14),(14,12),(17,15),(15,13),(12,13),(6,12),(7,13),
                         (6,7),(6,8),(7,9),(8,10),(9,11),(2,3),(1,2),(1,3),(2,4),(3,5)]
        # Target IDs: 62 (TV/Monitor/Projector), 63 (Laptop)
        self.appliance_ids = [62, 63]

    def detect_ceiling_lights(self, frame, ghost_view):
        """TASK 2: Intelligent Light Detection (Glow Analysis)."""
        h, w = frame.shape[:2]
        # We only look at the top 40% of the frame for lights (Ceiling Area)
        ceiling_area = frame[0:int(h*0.4), 0:w]
        gray = cv2.cvtColor(ceiling_area, cv2.COLOR_BGR2GRAY)
        
        # Look for extreme brightness (Glow Blobs > 240 brightness)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        lights_on = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter: Lights must be big enough to not be 'glare' (e.g. > 100px)
            if area > 100:
                lights_on += 1
                x, y, lw, lh = cv2.boundingRect(cnt)
                # Draw light detection on ghost view
                cv2.rectangle(ghost_view, (x, y), (x+lw, y+lh), (0, 255, 255), 2)
                cv2.putText(ghost_view, "LIGHT: ON", (x, y-5), 1, 1.2, (0, 255, 255), 2)
        return lights_on

    def audit_frame(self, frame, sensitivity):
        h, w = frame.shape[:2]
        
        # 1. TASK 1: P6 GPU OCCUPANCY (Using imgsz=1280 for accuracy)
        pose_res = self.pose_model.predict(source=frame, imgsz=1280, conf=0.15, device='cuda', verbose=False)[0]
        person_count = len(pose_res.boxes) if pose_res.boxes is not None else 0
        
        # 2. TASK 3: PRIVACY GHOST MODE (Anonymization)
        ghost_view = cv2.GaussianBlur(frame.copy(), (99, 99), 30)
        if pose_res.keypoints is not None:
            for kpts_obj in pose_res.keypoints.data:
                kpts = kpts_obj.cpu().numpy()
                for start, end in self.skeleton:
                    pt1, pt2 = kpts[start-1], kpts[end-1]
                    if pt1[2] > 0.2 and pt2[2] > 0.2:
                        cv2.line(ghost_view, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), (0, 255, 255), 2)

        # 3. TASK 2: CEILING LIGHT DETECTION
        lights_active = self.detect_ceiling_lights(frame, ghost_view)

        # 4. TASK 2: PROJECTOR/LAPTOP RECOGNITION (Fixing Paper False Positives)
        # Higher confidence (0.5) ensures we don't detect white paper
        det_res = self.detect_model.predict(source=frame, imgsz=1280, conf=0.5, device='cuda', verbose=False)[0]
        screens_on = 0
        
        if det_res.boxes is not None:
            for box in det_res.boxes:
                cls = int(box.cls[0])
                if cls in self.appliance_ids:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    # Filter small white artifacts (Area check)
                    if (x2-x1)*(y2-y1) < 8000: continue 
                    
                    crop = frame[max(0,y1):min(y2,h), max(0,x1):min(x2,w)]
                    brightness = np.mean(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
                    status = "ON" if brightness > sensitivity else "OFF"
                    if status == "ON": screens_on += 1
                    
                    color = (0, 255, 0) if status == "ON" else (0, 0, 255)
                    cv2.rectangle(ghost_view, (x1, y1), (x2, y2), color, 4)
                    cv2.putText(ghost_view, f"SCREEN: {status}", (x1, y1-15), 1, 1.8, color, 3)

        # --- TASK 4: LOGIC ENGINE (The Energy Rule) ---
        is_wasting = (person_count == 0 and (screens_on > 0 or lights_active > 0))
        energy_saved = 0.00 if is_wasting else 0.45
        return ghost_view, person_count, is_wasting, energy_saved, (screens_on + lights_active)

# --- STREAMLIT UI ---
auditor = WattWatchChampion()

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Control Room Setup")
    cam_index = st.number_input("Camera Index (OBS Virtual)", min_value=0, max_value=2, value=1)
    sensitivity = st.slider("Screen Brightness Thresh", 0, 255, 160)
    start_btn = st.button("🚀 INITIATE CAMPUS AUDIT")
    st.info(f"Hardware: {torch.cuda.get_device_name(0)}")

# --- THE RED ALERT CSS ---
def apply_alert_style(wasting):
    if wasting:
        st.markdown("""
        <style>
        .stApp { background-color: #4a0404; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { background-color: #4a0404; } 50% { background-color: #b30000; } 100% { background-color: #4a0404; } }
        h1, h2, h3, p, span, label { color: white !important; }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<style>.stApp { background-color: #0e1117; }</style>", unsafe_allow_html=True)

# UI TILES
st.title("🛡️ Campus 'Watt-Watch' Command Center")
st.markdown("---")

c1, c2, c3, c4 = st.columns(4)
tile_status = c1.empty()
tile_count = c2.empty()
tile_app = c3.empty()
tile_savings = c4.empty()

live_placeholder = st.empty()

if start_btn:
    cap = cv2.VideoCapture(int(cam_index))
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        t_start = time.time()
        ghost, count, wasting, savings, apps = auditor.audit_frame(frame, sensitivity)
        latency = time.time() - t_start

        apply_alert_style(wasting)

        # UPDATE TILES (Task 5)
        status_txt = "🚨 WASTE DETECTED" if wasting else "✅ ROOM SECURE"
        tile_status.metric("System Status", status_txt)
        tile_count.metric("Occupancy", f"{count} Students")
        tile_app.metric("Active Appliances", f"{apps} Zones")
        tile_savings.metric("EnergySaved Metric", f"{savings} kWh", delta="Waste" if wasting else "Saving")

        live_placeholder.image(cv2.cvtColor(ghost, cv2.COLOR_BGR2RGB), use_container_width=True)
        st.sidebar.write(f"GPU Latency: {latency:.3f}s (Goal < 3s)")
        time.sleep(1.0)