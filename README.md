# ⚡ Watt Watch

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green.svg)](https://fastapi.tiangolo.com/)

Watt Watch is a privacy-first, edge AI-powered energy monitoring system designed to detect energy waste in smart buildings. By utilizing advanced computer vision to monitor occupancy and appliance states, the system helps organizations automatically reduce their carbon footprint and electricity costs.

## 📑 Table of Contents
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [API Reference](#-api-reference)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features
- 👁️ **Edge-First Computer Vision**: Detects people and appliances locally using YOLOv8 models.
- 🔒 **Privacy-by-Design**: Implements a "Ghost Mode" using heavy Gaussian blur and skeleton keypoints to prevent PII (Personally Identifiable Information) collection.
- 📉 **Real-time Energy Analytics**: Monitors occupancy vs. appliance power states to flag `EMPTY_WASTING` conditions.
- 📋 **Canonical Event Schema**: Strict `RoomEvent` structure ensures consistency across edge devices, storage, and cloud syncing.
- 🔄 **Live Event Replay**: Replay logged JSONL events to simulate past scenarios and test system responses.
- 📊 **Interactive Dashboard**: Next.js-based dashboard with Server Components for real-time monitoring and analytics.

## 🛠 Tech Stack
| Component | Technology |
| :--- | :--- |
| **Backend** | Python, FastAPI, Pydantic, Uvicorn |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| **AI/ML** | YOLOv8 (Ultralytics), OpenCV, PyTorch |
| **Data Storage** | JSONL (Local Logs), SQLite (Cloud Simulation) |


## 🚀 Installation & Setup Instructions

To get Watt Watch up and running, follow these steps. The project is primarily composed of a Python backend service and a conceptual Next.js frontend (implied by technologies).

### 1. Clone the Repository

```bash
git clone https://github.com/Utsav9163/Watt_Watch.git
cd Watt_Watch
```

### 2. Backend Setup (Python)

Navigate to the `backend` directory, set up a virtual environment, and install dependencies.

```bash
cd backend

# Create a Python virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows: `venv\Scripts\activate`

# Install required Python packages
pip install -r requirements.txt

# Copy the example environment file and configure it
cp .env.example .env
# Open .env and adjust variables as needed (e.g., API keys, database settings)
```

### 3. Running the Backend

Once dependencies are installed and the `.env` file is configured, you can start the FastAPI backend server.

```bash
# From the 'backend' directory, with virtual environment activated
python main.py
# Or, if using uvicorn directly (common for FastAPI):
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The backend will typically be accessible at `http://localhost:8000`.

### 4. Frontend Setup (Conceptual, Next.js)

While a specific `frontend` directory is not provided in the structure, the use of Next.js implies a frontend component. If a frontend exists, its setup would typically involve:

```bash
# Navigate to the frontend directory (if it exists)
# cd ../frontend # Assuming 'frontend' is a sibling to 'backend'

# Install Node.js dependencies
npm install # or `yarn install`

# Start the development server
npm run dev # or `yarn dev`
```
The frontend would then be accessible, commonly at `http://localhost:3000`.

## 💡 Usage

### Start Monitoring
Begin real-time analysis for a specific room:
```bash
curl -X POST "http://localhost:8000/monitor/start?room_id=office_101&camera_id=0"
```

### Audit Single Image
Use the audit endpoint to analyze a static frame for energy waste:
```bash
curl -X POST "http://localhost:8000/audit?room_id=office_101&privacy_mode=true" \
  -F "file=@room_snapshot.jpg"
```

## 📁 Project Structure
```text
Watt_Watch/
├── backend/
│   ├── main.py             # FastAPI entry point
│   ├── state_machine.py    # FSM Logic & Energy calculations
│   ├── camera_sampler.py   # Live frame processing
│   ├── event_logger.py     # JSONL Persistence
│   └── schemas.py          # Frozen PHASE 0 contract
├── frontend/
│   ├── app/                # Next.js App Router
│   ├── components/         # Reusable UI components
│   └── lib/                # API client and aggregators
└── event_logs/             # Persistent JSONL data
```
## ⚙️ Configuration Options

Configuration for the backend is handled via environment variables, specified in the `.env` file. A `.env.example` file is provided in the `backend/` directory as a template.

**Example `.env` (backend):**

```env
# FastAPI server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# YOLO model settings
MODEL_PATH=./models/yolov8s.pt # Example path
CONFIDENCE_THRESHOLD=0.25
IOU_THRESHOLD=0.7

# Event logging settings
EVENT_LOGS_DIR=./event_logs
```
Please ensure to create and configure your `.env` file based on `.env.example` for proper system operation.

## 🌐 API Reference
- **POST /detect**: Standard pose/object detection.
- **POST /audit**: Run full energy audit flow.
- **POST /monitor/start**: Initiate live stream processing.
- **GET /monitor/status**: Query health and event status of monitored rooms.

## 🤝 Contributing
Contributions are welcome! Please fork the repository and submit a pull request with descriptive changes.

## 🙏 Acknowledgments

*   **FastAPI**: For providing a modern, fast (high-performance) web framework for building APIs with Python.
*   **Next.js**: For the robust framework for building React applications.
*   **YOLO Models**: For the excellent real-time object detection capabilities critical to the system's AI core.
*   **Node.js & Python Communities**: For their invaluable tools and extensive libraries.

## 📜 License
Distributed under the MIT License.

--- 
**Maintained by Utsav9163**
🔗 [Repository URL](https://github.com/Utsav9163/Watt_Watch)
✨ If you found this project helpful, please consider starring it!

---
