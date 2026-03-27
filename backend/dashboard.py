import streamlit as st
import cv2
import torch
import numpy as np
from ultralytics import YOLO
import time
import pandas as pd
from datetime import datetime

# --- 1. SETTINGS & CSS ---
st.set_page_config(page_title="Watt-Watch Enterprise", layout="wide", initial_sidebar_state="expanded")

def inject_custom_css():
    st.markdown("""
        <style>
        /* Base Theme */
        .stApp { background-color: #020617; color: #f8fafc; }
        [data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #1e293b; }
        
        /* Glassmorphism Cards */
        .glass-card {
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
            border-radius: 16px; padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }

        /* Pulsing Room Tile */
        .room-tile-red {
            background: #450a0a;
            border: 2px solid #ef4444;
            border-radius: 12px; padding: 20px; text-align: center;
            animation: pulse-red 2s infinite;
        }
        .room-tile-green {
            background: #064e3b;
            border: 2px solid #10b981;
            border-radius: 12px; padding: 20px; text-align: center;
        }
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        
        /* Metric Styles */
        .metric-val { font-size: 2.5rem; font-weight: 800; color: #38bdf8; }
        .metric-label { font-size: 0.9rem; color: #94a3b8; text-transform: uppercase; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. CORE AI ENGINE ---
@st.cache_resource
def load_models():
    return YOLO('yolov8x-pose-p6.pt').to('cuda'), YOLO('yolov8x.pt').to('cuda')

class AuditorEngine:
    def __init__(self):
        self.pose_m, self.det_m = load_models()
        self.skeleton = [(16,14),(14,12),(17,15),(15,13),(12,13),(6,12),(7,13),
                         (6,7),(6,8),(7,9),(8,10),(9,11),(2,3),(1,2),(1,3),(2,4),(3,5)]

    def run_audit(self, frame, l_thresh, s_thresh):
        h, w = frame.shape[:2]
        ghost = cv2.GaussianBlur(frame.copy(), (99, 99), 30)
        
        # Detection
        pose_res = self.pose_m.predict(source=frame, imgsz=1280, conf=0.15, device='cuda', verbose=False)[0]
        count = len(pose_res.boxes)
        
        # Skeletons
        if pose_res.keypoints is not None:
            for kpts_obj in pose_res.keypoints.data:
                kpts = kpts_obj.cpu().numpy()
                for s, e in self.skeleton:
                    pt1, pt2 = kpts[s-1], kpts[e-1]
                    if pt1[2] > 0.3 and pt2[2] > 0.3:
                        cv2.line(ghost, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), (0, 255, 255), 2)

        # Lights
        ceiling = frame[0:int(h*0.45), 0:w]
        gray = cv2.cvtColor(ceiling, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, l_thresh, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        lights = sum(1 for c in contours if cv2.contourArea(c) > 60)
        
        # Screens
        det_res = self.det_m.predict(source=frame, imgsz=1280, conf=0.5, device='cuda', verbose=False)[0]
        screens = 0
        if det_res.boxes is not None:
            for box in det_res.boxes:
                if int(box.cls[0]) in [62, 63]:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    if (x2-x1)*(y2-y1) < 8000: continue
                    if np.mean(cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)) > s_thresh:
                        screens += 1
                        cv2.rectangle(ghost, (x1, y1), (x2, y2), (0, 255, 0), 3)

        return ghost, count, (count == 0 and (lights > 0 or screens > 0)), (lights + screens)

# --- 3. SESSION STATE ---
if 'page' not in st.session_state: st.session_state.page = "Campus Hub"
if 'total_inr' not in st.session_state: st.session_state.total_inr = 0.0
if 'history' not in st.session_state: st.session_state.history = pd.DataFrame(columns=["Time", "INR"])
if 'is_wasting' not in st.session_state: st.session_state.is_wasting = False

# --- 4. NAVIGATION LOGIC ---
inject_custom_css()
engine = AuditorEngine()

with st.sidebar:
    st.title("⚡ WATT-WATCH PRO")
    st.markdown("---")
    if st.button("🏢 Campus Grid Hub", use_container_width=True): st.session_state.page = "Campus Hub"
    if st.button("📡 Live Command Feed", use_container_width=True): st.session_state.page = "Live Feed"
    if st.button("📊 Financial Analytics", use_container_width=True): st.session_state.page = "Analytics"
    
    st.markdown("---")
    st.subheader("💰 Live Savings")
    st.markdown(f"<div class='glass-card'><p class='metric-label'>Total Saved</p><p class='metric-val'>₹{st.session_state.total_inr:.2f}</p></div>", unsafe_allow_html=True)
    
    admin_mode = st.toggle("🔓 Admin View (Raw Feed)")
    cam_idx = st.number_input("Camera Index", value=1)
    l_thresh = st.slider("Light Sensitivity", 200, 255, 235)

# --- PAGE 1: CAMPUS HUB ---
if st.session_state.page == "Campus Hub":
    st.title("🏢 Campus Infrastructure Overview")
    st.markdown("Real-time status of all audited zones.")
    
    col1, col2, col3 = st.columns(3)
    
    # Room A-402 Tile (The Main Demo Room)
    with col1:
        status_class = "room-tile-red" if st.session_state.is_wasting else "room-tile-green"
        st.markdown(f"""<div class='{status_class}'>
            <h3>Room A-402</h3>
            <p>{'⚠️ ENERGY WASTE' if st.session_state.is_wasting else '✅ SECURE'}</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Inspect A-402 Feed", use_container_width=True):
            st.session_state.page = "Live Feed"
            st.rerun()

    # Placeholder Static Rooms
    with col2:
        st.markdown("<div class='room-tile-green'><h3>Lab 201</h3><p>✅ SECURE</p></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='room-tile-green'><h3>Library S1</h3><p>✅ SECURE</p></div>", unsafe_allow_html=True)

# --- PAGE 2: LIVE FEED ---
elif st.session_state.page == "Live Feed":
    st.title("📡 Live Auditor Command: Room A-402")
    
    c1, c2, c3, c4 = st.columns(4)
    t1 = c1.empty(); t2 = c2.empty(); t3 = c3.empty(); t4 = c4.empty()
    
    feed_placeholder = st.empty()
    
    cap = cv2.VideoCapture(int(cam_idx))
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        ghost, count, wasting, apps = engine.run_audit(frame, l_thresh, 165)
        st.session_state.is_wasting = wasting
        
        # Financial Update
        step = 0.0 if wasting else 0.45
        st.session_state.total_inr += (step * (9.5 / 3600))
        
        # Update Tiles
        t1.metric("Status", "WASTE" if wasting else "SECURE", delta="-100%" if wasting else None)
        t2.metric("Occupancy", f"{count} Students")
        t3.metric("Appliances", f"{apps} Active")
        t4.metric("Real-time Saved", f"₹{st.session_state.total_inr:.2f}")

        # Display Feed
        display = frame if admin_mode else ghost
        feed_placeholder.image(cv2.cvtColor(display, cv2.COLOR_BGR2RGB), use_container_width=True)
        
        # Update History for Analytics
        new_pt = pd.DataFrame({"Time": [datetime.now()], "INR": [st.session_state.total_inr]})
        st.session_state.history = pd.concat([st.session_state.history, new_pt]).tail(50)
        
        time.sleep(0.5)
        if st.session_state.page != "Live Feed": break

# --- PAGE 3: ANALYTICS ---
elif st.session_state.page == "Analytics":
    st.title("📊 Financial & Energy Analytics")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Cumulative Cost Savings (INR)")
        if not st.session_state.history.empty:
            st.area_chart(st.session_state.history.set_index("Time"))
        else:
            st.info("Start the Live Feed to generate analytics data.")
            
    with col_b:
        st.subheader("ROI Projection")
        st.markdown("""<div class='glass-card'>
            <h3>Daily Average: ₹142.50</h3>
            <p>Monthly Est: ₹4,275.00</p>
            <p style='color:#38bdf8'>Carbon Offset: 12.4kg CO2</p>
        </div>""", unsafe_allow_html=True)