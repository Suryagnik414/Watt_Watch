import streamlit as st
import cv2
import torch
import numpy as np
from ultralytics import YOLO
import time
import pandas as pd
from datetime import datetime

# --- 1. ENTERPRISE UI & CSS CONFIG ---
st.set_page_config(page_title="Watt-Watch Enterprise Elite", layout="wide", initial_sidebar_state="expanded")

def inject_enterprise_css(wasting):
    base_bg = "#020617" if not wasting else "#1a0505"
    border_color = "#38bdf8" if not wasting else "#ef4444"
    animation = "pulse-red 1.5s infinite" if wasting else "none"

    st.markdown(f"""
        <style>
        .stApp {{ background-color: {base_bg}; color: #f1f5f9; transition: all 0.5s; }}
        [data-testid="stSidebar"] {{ background-color: #0f172a; border-right: 1px solid #1e293b; }}
        
        .metric-card {{
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid {border_color};
            border-radius: 12px; padding: 20px; text-align: center;
            box-shadow: 0 0 20px {border_color}22;
        }}
        
        .room-tile {{
            border-radius: 16px; padding: 40px; text-align: center;
            transition: 0.3s; cursor: pointer; border: 2px solid; margin-bottom: 20px;
        }}
        .tile-secure {{ background: #064e3b; border-color: #10b981; color: white; }}
        .tile-waste {{ background: #450a0a; border-color: #ef4444; color: white; animation: {animation}; }}
        
        @keyframes pulse-red {{
            0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
            70% {{ box-shadow: 0 0 0 20px rgba(239, 68, 68, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
        }}
        </style>
    """, unsafe_allow_html=True)

# --- 2. THE AI AUDIT ENGINE ---
@st.cache_resource
def load_models():
    # P6 for 36+ student count | X for high-precision appliance detection
    return YOLO('yolov8x-pose-p6.pt').to('cuda'), YOLO('yolov8x.pt').to('cuda')

class AuditorEngine:
    def __init__(self):
        self.pose_m, self.det_m = load_models()
        self.skeleton = [(16,14),(14,12),(17,15),(15,13),(12,13),(6,12),(7,13),
                         (6,7),(6,8),(7,9),(8,10),(9,11),(2,3),(1,2),(1,3),(2,4),(3,5)]

    def process_raw_audit(self, frame, l_thresh, s_thresh):
        """AI TRACKS EVERYTHING ON RAW FEED INTERNALLY."""
        h, w = frame.shape[:2]
        raw_annotated = frame.copy()
        
        # A. LIGHT TRACKING (RAW)
        ceiling = frame[0:int(h*0.45), 0:w]
        gray = cv2.cvtColor(ceiling, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, l_thresh, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        light_count = 0
        light_boxes = []
        for cnt in contours:
            if cv2.contourArea(cnt) > 45:
                light_count += 1
                light_boxes.append(cv2.boundingRect(cnt))

        # B. HUMAN OCCUPANCY (RAW)
        pose_res = self.pose_m.predict(source=frame, imgsz=1280, conf=0.15, device='cuda', verbose=False)[0]
        person_count = len(pose_res.boxes)

        # C. APPLIANCE TRACKING (RAW)
        det_res = self.det_m.predict(source=frame, imgsz=1280, conf=0.5, device='cuda', verbose=False)[0]
        screen_count = 0
        screen_boxes = []
        if det_res.boxes is not None:
            for box in det_res.boxes:
                if int(box.cls[0]) in [62, 63]: # TV/Monitor, Laptop
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    if (x2-x1)*(y2-y1) < 8000: continue # Paper filter
                    if np.mean(cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)) > s_thresh:
                        screen_count += 1
                        screen_boxes.append((x1, y1, x2, y2))

        # D. GENERATE TWO VIEWS (Admin vs Ghost)
        ghost_view = cv2.GaussianBlur(frame.copy(), (99, 99), 30)
        admin_view = frame.copy()

        def draw_annotations(target_img):
            # Draw Skeletons
            if pose_res.keypoints is not None:
                for kpts_obj in pose_res.keypoints.data:
                    kpts = kpts_obj.cpu().numpy()
                    for s, e in self.skeleton:
                        pt1, pt2 = kpts[s-1], kpts[end-1] if 'end' in locals() else kpts[e-1]
                        if pt1[2] > 0.3 and pt2[2] > 0.3:
                            cv2.line(target_img, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), (0, 255, 255), 2)
            # Draw Lights
            for (lx, ly, lw, lh) in light_boxes:
                cv2.rectangle(target_img, (lx, ly), (lx+lw, ly+lh), (0, 255, 255), 3)
                cv2.putText(target_img, "LIGHT: ON", (lx, ly-10), 1, 1.2, (0, 255, 255), 2)
            # Draw Screens
            for (x1, y1, x2, y2) in screen_boxes:
                cv2.rectangle(target_img, (x1, y1), (x2, y2), (0, 255, 0), 4)
                cv2.putText(target_img, "SCREEN: ACTIVE", (x1, y1-15), 1, 1.5, (0, 255, 0), 2)
            return target_img

        final_admin = draw_annotations(admin_view)
        final_ghost = draw_annotations(ghost_view)
        
        is_wasting = (person_count == 0 and (light_count > 0 or screen_count > 0))
        return final_admin, final_ghost, person_count, is_wasting, (light_count + screen_count)

# --- 3. DASHBOARD STATE & NAVIGATION ---
if 'page' not in st.session_state: st.session_state.page = "Campus Grid"
if 'total_inr' not in st.session_state: st.session_state.total_inr = 0.0
if 'history' not in st.session_state: st.session_state.history = pd.DataFrame(columns=["Time", "INR"])
if 'wasting' not in st.session_state: st.session_state.wasting = False

# --- 4. SIDEBAR COMMANDS ---
engine = AuditorEngine()
with st.sidebar:
    st.title("⚡ WATT-WATCH ELITE")
    st.markdown("---")
    if st.button("🏢 Campus Overview Hub", use_container_width=True): st.session_state.page = "Campus Grid"
    if st.button("📡 Live Command Feed", use_container_width=True): st.session_state.page = "Live Feed"
    if st.button("📊 Financial Analytics", use_container_width=True): st.session_state.page = "Analytics"
    
    st.markdown("---")
    st.subheader("💰 Live Statistics")
    st.markdown(f"<div class='metric-card'><p style='color:#94a3b8; font-size:0.8rem;'>INR SAVED</p><h2 style='color:#38bdf8; margin:0;'>₹{st.session_state.total_inr:.2f}</h2></div>", unsafe_allow_html=True)
    
    admin_mode = st.toggle("🔓 ADMIN ACCESS (Raw Feed)")
    cam_idx = st.number_input("Camera Index", value=1)
    l_thresh = st.slider("Ceiling Light Thresh", 150, 255, 235)
    st.info(f"Hardware Acceleration: {torch.cuda.get_device_name(0)}")

# --- PAGE 1: CAMPUS HUB ---
if st.session_state.page == "Campus Grid":
    inject_enterprise_css(st.session_state.wasting)
    st.title("🏢 Campus Infrastructure Map")
    
    cols = st.columns(3)
    # Room A-402 Tile
    with cols[0]:
        style = "tile-waste" if st.session_state.wasting else "tile-secure"
        st.markdown(f"""<div class='room-tile {style}'>
            <h3>ROOM A-402</h3>
            <p>{'🚨 ENERGY WASTE' if st.session_state.wasting else '✅ SYSTEM SECURE'}</p>
        </div>""", unsafe_allow_html=True)
        if st.button("OPEN COMMAND CENTER", use_container_width=True):
            st.session_state.page = "Live Feed"
            st.rerun()

    with cols[1]: st.markdown("<div class='room-tile tile-secure'><h3>LAB 101</h3><p>✅ SECURE</p></div>", unsafe_allow_html=True)
    with cols[2]: st.markdown("<div class='room-tile tile-secure'><h3>LIBRARY B1</h3><p>✅ SECURE</p></div>", unsafe_allow_html=True)

# --- PAGE 2: LIVE FEED ---
elif st.session_state.page == "Live Feed":
    st.title("📡 Live Auditor Command: Room A-402")
    t1, t2, t3, t4 = st.columns(4)
    tile1 = t1.empty(); tile2 = t2.empty(); tile3 = t3.empty(); tile4 = t4.empty()
    feed_placeholder = st.empty()
    
    cap = cv2.VideoCapture(int(cam_idx))
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        # AUDIT RAW - Output both versions
        admin_v, ghost_v, count, wasting, apps = engine.process_raw_audit(frame, l_thresh, 165)
        st.session_state.wasting = wasting
        inject_enterprise_css(wasting)
        
        # Financials
        saving = 0.0 if wasting else 0.45
        st.session_state.total_inr += (saving * (9.50 / 3600))
        
        # Tiles (Task 5 Metrics)
        tile1.metric("Status", "WASTE" if wasting else "SECURE", delta="ALERT" if wasting else "OK")
        tile2.metric("Students", f"{count}")
        tile3.metric("Tracking", f"{apps} Sources")
        tile4.metric("Savings", f"₹{st.session_state.total_inr:.2f}")

        # Update Analytics
        new_row = pd.DataFrame({"Time": [datetime.now()], "INR": [st.session_state.total_inr]})
        st.session_state.history = pd.concat([st.session_state.history, new_row]).tail(30)

        # Presentation View
        final_out = admin_v if admin_mode else ghost_v
        feed_placeholder.image(cv2.cvtColor(final_out, cv2.COLOR_BGR2RGB), use_container_width=True)
        
        time.sleep(0.4)
        if st.session_state.page != "Live Feed": break

# --- PAGE 3: ANALYTICS ---
elif st.session_state.page == "Analytics":
    inject_enterprise_css(False)
    st.title("📊 Financial cost Savings Intelligence")
    ca, cb = st.columns([2, 1])
    with ca:
        st.subheader("INR Savings Momentum")
        if not st.session_state.history.empty:
            st.area_chart(st.session_state.history.set_index("Time"))
    with cb:
        st.subheader("Total Savings")
        st.markdown(f"<div class='metric-card'><h1 style='color:#10b981'>₹{st.session_state.total_inr:.2f}</h1><p>Carbon Saved: 14.2kg</p></div>", unsafe_allow_html=True)