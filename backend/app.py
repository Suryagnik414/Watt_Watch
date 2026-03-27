"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          WATT-WATCH ENTERPRISE — Streamlit App v2.0                         ║
║          Drop-in replacement for the original app.py                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run:
    streamlit run app.py

Requires:  watt_watch_engine.py  in the same directory.
"""

import streamlit as st
import cv2
import torch
import numpy as np
import time
import pandas as pd
from datetime import datetime

# ── Import the new engine ─────────────────────────────────────────────────────
from watt_watch_engine import (
    AuditorEngine, AuditResult, compute_financials,
    ApplianceType, LightType,
    WATTAGE_TABLE, LIGHT_WATTAGE,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Watt-Watch Enterprise",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STYLES
# ─────────────────────────────────────────────────────────────────────────────
def inject_css(wasting: bool):
    base_bg      = "#020617" if not wasting else "#1a0505"
    border_color = "#38bdf8" if not wasting else "#ef4444"
    animation    = "pulse-red 1.5s infinite" if wasting else "none"
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@400;600;700&display=swap');
        html, body, .stApp {{ font-family: 'Space Grotesk', sans-serif; background-color: {base_bg}; color: #f1f5f9; transition: all 0.5s; }}
        [data-testid="stSidebar"] {{ background-color: #0f172a; border-right: 1px solid #1e293b; }}
        .metric-card {{ background: rgba(15,23,42,0.8); border: 1px solid {border_color}; border-radius: 12px; padding: 20px; text-align: center; }}
        .room-tile {{ border-radius: 16px; padding: 40px; text-align: center; border: 2px solid; margin-bottom: 20px; }}
        .tile-secure {{ background: #064e3b; border-color: #10b981; }}
        .tile-waste  {{ background: #450a0a; border-color: #ef4444; animation: {animation}; }}
        .appliance-row {{ display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 8px; background: rgba(255,255,255,0.04); margin-bottom: 6px; font-family: 'JetBrains Mono', monospace; font-size: 13px; }}
        .dot-on  {{ width:10px; height:10px; border-radius:50%; background:#10b981; display:inline-block; }}
        .dot-off {{ width:10px; height:10px; border-radius:50%; background:#6b7280; display:inline-block; }}
        @keyframes pulse-red {{
            0%   {{ box-shadow: 0 0 0 0   rgba(239,68,68,0.7); }}
            70%  {{ box-shadow: 0 0 0 20px rgba(239,68,68,0);   }}
            100% {{ box-shadow: 0 0 0 0   rgba(239,68,68,0);    }}
        }}
        </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "page"      : "Campus Grid",
        "total_inr" : 0.0,
        "history"   : pd.DataFrame(columns=["Time", "INR", "Watts"]),
        "wasting"   : False,
        "last_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ─────────────────────────────────────────────────────────────────────────────
# MODEL LOAD (cached)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def load_engine() -> AuditorEngine:
    return AuditorEngine()

engine = load_engine()
inject_css(st.session_state.wasting)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ WATT-WATCH PRO")
    st.markdown("---")

    nav_options = ["🏢 Campus Grid", "📡 Live Feed", "📊 Analytics", "🔬 Device Explorer"]
    for opt in nav_options:
        key = opt.split(" ", 1)[1]
        if st.button(opt, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key
            st.rerun()

    st.markdown("---")
    st.markdown("### Calibration")
    l_thresh = st.slider("Bulb Intensity Gate", 180, 255, 248, help="Min brightness to detect active lights")
    s_thresh = st.slider("Screen Active Gate",  100, 255, 170, help="Min mean brightness to classify screen as ON")

    st.markdown("### Camera")
    cam_idx    = st.number_input("Camera Index", value=0, min_value=0)
    admin_mode = st.toggle("🔓 Admin Mode (Full Detail)")

    st.markdown("---")
    st.markdown("### Reference Wattages")
    for atype, w in WATTAGE_TABLE.items():
        st.caption(f"{atype.value}: **{w:.0f}W**")

    if torch.cuda.is_available():
        st.success(f"GPU: {torch.cuda.get_device_name(0)}")
    else:
        st.warning("Running on CPU — expect lower FPS")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1: CAMPUS GRID
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.page == "Campus Grid":
    st.title("🏢 Campus Infrastructure Overview")
    cols = st.columns(3)

    with cols[0]:
        style = "tile-waste" if st.session_state.wasting else "tile-secure"
        badge = "🚨 ENERGY WASTE" if st.session_state.wasting else "✅ ROOM SECURE"
        st.markdown(f"<div class='room-tile {style}'><h3>Room A-402</h3><p>{badge}</p></div>",
                    unsafe_allow_html=True)
        if st.button("OPEN COMMAND CENTER (A-402)", use_container_width=True):
            st.session_state.page = "Live Feed"
            st.rerun()

    with cols[1]:
        st.markdown("<div class='room-tile tile-secure'><h3>Lab 101</h3><p>✅ SECURE</p></div>",
                    unsafe_allow_html=True)
    with cols[2]:
        st.markdown("<div class='room-tile tile-secure'><h3>Library B1</h3><p>✅ SECURE</p></div>",
                    unsafe_allow_html=True)

    # Live snapshot from last result (if any)
    if st.session_state.last_result is not None:
        result: AuditResult = st.session_state.last_result
        st.markdown("---")
        st.subheader("Last Audit Snapshot — A-402")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Occupancy",    f"{result.person_count} persons")
        c2.metric("Active Lights", result.active_light_count)
        c3.metric("Active Devices", result.active_appliance_count)
        c4.metric("Total Load",   f"{result.total_active_wattage:.0f} W")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2: LIVE FEED
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "Live Feed":
    st.title("📡 Live Auditor Command: Room A-402")

    # Metric placeholders
    m1, m2, m3, m4, m5 = st.columns(5)
    ph_status   = m1.empty()
    ph_persons  = m2.empty()
    ph_lights   = m3.empty()
    ph_devices  = m4.empty()
    ph_cost     = m5.empty()

    # Detail panels
    col_feed, col_detail = st.columns([3, 1])
    with col_feed:
        feed_spot = st.empty()
    with col_detail:
        st.markdown("### Live Detections")
        ph_light_list   = st.empty()
        ph_device_list  = st.empty()

    cap = cv2.VideoCapture(int(cam_idx))
    frame_t = time.perf_counter()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            st.error("Camera feed lost.")
            break

        # ── Run engine ──────────────────────────────────────────────────────
        result: AuditResult = engine.process(
            frame,
            light_threshold=l_thresh,
            screen_threshold=s_thresh,
        )
        now = time.perf_counter()
        dt  = now - frame_t
        frame_t = now

        # ── Financials ──────────────────────────────────────────────────────
        fin = compute_financials(result, elapsed_seconds=dt)
        st.session_state.total_inr += fin["wasted_inr"]
        st.session_state.wasting    = result.is_wasting_energy
        st.session_state.last_result = result
        inject_css(result.is_wasting_energy)

        # ── Update metrics ──────────────────────────────────────────────────
        ph_status.metric(
            "Status",
            "⚠ WASTE"  if result.is_wasting_energy else "✅ OK",
            delta_color="inverse" if result.is_wasting_energy else "normal",
        )
        ph_persons.metric("Occupancy",    f"{result.person_count} persons")
        ph_lights.metric ("Active Lights",result.active_light_count)
        ph_devices.metric("Devices On",   result.active_appliance_count)
        ph_cost.metric(
            "Wasted Cost (INR)",
            f"₹{st.session_state.total_inr:.4f}",
            delta=f"₹{fin['wasted_inr']*3600:.2f}/hr" if result.is_wasting_energy else "₹0/hr",
        )

        # ── Feed ─────────────────────────────────────────────────────────────
        view = result.admin_frame if admin_mode else result.ghost_frame
        feed_spot.image(cv2.cvtColor(view, cv2.COLOR_BGR2RGB), use_container_width=True)

        # ── Sidebar detection lists ──────────────────────────────────────────
        light_html = "<b>Lights</b><br>"
        for lt in result.lights:
            dot   = "dot-on" if lt.is_active else "dot-off"
            watt  = LIGHT_WATTAGE[lt.type]
            light_html += (
                f"<div class='appliance-row'>"
                f"<span class='{dot}'></span>"
                f"{lt.type.value} — {watt:.0f}W"
                f"</div>"
            )
        if not result.lights:
            light_html += "<div class='appliance-row'>No lights detected</div>"
        ph_light_list.markdown(light_html, unsafe_allow_html=True)

        device_html = "<b>Appliances</b><br>"
        for ap in result.appliances:
            dot   = "dot-on" if ap.is_active else "dot-off"
            device_html += (
                f"<div class='appliance-row'>"
                f"<span class='{dot}'></span>"
                f"{ap.type.value} — {ap.wattage:.0f}W"
                f"</div>"
            )
        if not result.appliances:
            device_html += "<div class='appliance-row'>No devices detected</div>"
        ph_device_list.markdown(device_html, unsafe_allow_html=True)

        # ── Log history ──────────────────────────────────────────────────────
        new_pt = pd.DataFrame({
            "Time" : [datetime.now()],
            "INR"  : [st.session_state.total_inr],
            "Watts": [result.total_active_wattage],
        })
        st.session_state.history = pd.concat(
            [st.session_state.history, new_pt]
        ).tail(120)

        time.sleep(0.35)
        if st.session_state.page != "Live Feed":
            cap.release()
            break

    cap.release()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3: ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "Analytics":
    st.title("📊 Energy & Cost Analytics Intelligence")

    if not st.session_state.history.empty:
        df = st.session_state.history.set_index("Time")

        st.subheader("Cumulative Wasted Cost (INR)")
        st.area_chart(df[["INR"]])

        st.subheader("Instantaneous Load (Watts)")
        st.line_chart(df[["Watts"]])

        st.markdown(f"### Total Wasted Cost: ₹{st.session_state.total_inr:.4f}")

        # Appliance breakdown from last result
        if st.session_state.last_result is not None:
            result: AuditResult = st.session_state.last_result
            st.subheader("Appliance Load Breakdown (last frame)")
            if result.appliance_summary:
                breakdown_df = pd.DataFrame(
                    list(result.appliance_summary.items()),
                    columns=["Device", "Count"]
                )
                st.bar_chart(breakdown_df.set_index("Device"))
    else:
        st.warning("No data yet. Launch the Live Feed to begin auditing.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 4: DEVICE EXPLORER
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "Device Explorer":
    st.title("🔬 Device & Light Classification Explorer")
    st.markdown(
        "Reference table of all device types the engine can detect, "
        "their classification heuristics, and energy estimates."
    )

    st.subheader("Appliances")
    appl_data = [
        {
            "Type"           : atype.value,
            "Wattage (W)"    : w,
            "Detection Method": _appl_method(atype),
        }
        for atype, w in WATTAGE_TABLE.items()
    ]
    st.dataframe(pd.DataFrame(appl_data), use_container_width=True)

    st.subheader("Lights")
    light_data = [
        {
            "Type"           : ltype.value,
            "Wattage (W)"    : w,
            "Detection Cue"  : _light_cue(ltype),
        }
        for ltype, w in LIGHT_WATTAGE.items()
    ]
    st.dataframe(pd.DataFrame(light_data), use_container_width=True)

    st.subheader("Skeleton Keypoints (COCO-17)")
    from watt_watch_engine import KEYPOINT_NAMES
    kp_df = pd.DataFrame({
        "Index": list(range(17)),
        "Keypoint": KEYPOINT_NAMES,
        "Body Zone": (
            ["Face"] * 5 +
            ["Upper body"] * 6 +
            ["Lower body"] * 6
        )
    })
    st.dataframe(kp_df, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS for Device Explorer page
# ─────────────────────────────────────────────────────────────────────────────
def _appl_method(atype: "ApplianceType") -> str:
    m = {
        ApplianceType.LAPTOP   : "YOLO class 63 + area < 60k px² + desk height",
        ApplianceType.MONITOR  : "YOLO class 62/63 + area > 60k px²",
        ApplianceType.PROJECTOR: "YOLO screen + area > 80k px² + high on wall",
        ApplianceType.TV       : "YOLO class 62 + AR ≥ 1.6 + area > 40k px²",
        ApplianceType.AC_UNIT  : "Ceiling zone + wide blob (AR > 2.5)",
        ApplianceType.CEILING_FAN: "Ceiling zone + symmetric blob (AR 0.6–1.6)",
        ApplianceType.PRINTER  : "YOLO class 74",
        ApplianceType.SPEAKER  : "YOLO class 76",
        ApplianceType.MICROWAVE: "YOLO class 68",
        ApplianceType.UNKNOWN  : "Fallback",
    }
    return m.get(atype, "—")


def _light_cue(ltype: "LightType") -> str:
    m = {
        LightType.TUBELIGHT : "Blob aspect ratio ≥ 3.0 (wide & thin)",
        LightType.LED_PANEL : "Near-square blob, area ≥ 800 px²",
        LightType.BULB      : "Compact blob, AR < 1.5, area < 800 px²",
        LightType.SPOTLIGHT : "Very small blob, area < 200 px²",
        LightType.UNKNOWN   : "Fallback",
    }
    return m.get(ltype, "—")