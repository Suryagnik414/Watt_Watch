# Watt Watch

A full-stack energy monitoring application with Next.js frontend, FastAPI backend, and React Native mobile app.

**🆕 v1.1.0 - Now with Multi-RTSP Stream Support & Dev/Prod Modes!**

## ✨ New Features

- **Multiple RTSP Streams**: Monitor multiple rooms with IP cameras (RTSP/HTTP streams)
- **Dev/Prod Modes**: Toggle video streaming for development vs. production deployments
- **Real-time Video Streaming**: WebSocket-based video feed with visualization controls (dev mode)
- **Visualization Controls**: Toggle skeleton, bounding boxes, blur, and privacy mode per room

See [backend/QUICK_REFERENCE.md](backend/QUICK_REFERENCE.md) for usage examples.

## Project Structure

```
Watt_Watch/
├── frontend/          # Next.js web application
├── backend/           # FastAPI server with RTSP support
│   ├── main.py                      # Main server (enhanced)
│   ├── camera_sampler.py           # RTSP/local camera handler
│   ├── RTSP_STREAMING_GUIDE.md     # Complete RTSP documentation
│   ├── QUICK_REFERENCE.md          # Quick command reference
│   └── test_rtsp_features.py       # Test suite
└── app/              # React Native mobile app (without Expo)
```

## Getting Started

### Backend (FastAPI) - Enhanced with RTSP Support

```bash
cd backend

# Configure environment
cp .env.example .env
# Edit .env and set:
#   APP_MODE=dev     # For development with video streaming
#   APP_MODE=prod    # For production (processing only, no video)

# Activate virtual environment
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# Run the server
python main.py
```

The API will be available at [http://localhost:8000](http://localhost:8000)
- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- WebSocket: `ws://localhost:8000/ws/{room_id}`

**Tech Stack:**
- FastAPI with WebSocket support
- OpenCV for RTSP stream handling
- YOLO for pose/object detection
- Uvicorn, Pydantic
- CORS middleware enabled

**Quick Example - Start Monitoring:**
```bash
# Local webcam
curl -X POST "http://localhost:8000/monitor/start?room_id=office&camera_source=0"

# RTSP camera
curl -X POST "http://localhost:8000/monitor/start?room_id=living_room&camera_source=rtsp://admin:password@192.168.1.100:554/stream1"

# List active streams
curl "http://localhost:8000/monitor/streams"
```

### Frontend (Next.js)

```bash
cd frontend
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000)

**Tech Stack:**
- Next.js 15+ with App Router
- TypeScript
- Tailwind CSS
- ESLint
- Turbopack

### Mobile App (React Native)

```bash
cd app
npm install

# For Android
npx react-native run-android

# For iOS (Mac only)
npx react-native run-ios
```

**Tech Stack:**
- React Native 0.84.1 (CLI, not Expo)
- Metro bundler

## 📖 Documentation

- **[RTSP Streaming Guide](backend/RTSP_STREAMING_GUIDE.md)** - Complete guide for RTSP cameras and video streaming
- **[Quick Reference](backend/QUICK_REFERENCE.md)** - Common commands and examples
- **[Implementation Summary](backend/IMPLEMENTATION_SUMMARY.md)** - Technical details of v1.1.0

## Development

1. Start the backend server first (with your desired APP_MODE)
2. Start the frontend development server
3. Run the mobile app on an emulator or device

### Testing

```bash
# Test RTSP features
cd backend
python test_rtsp_features.py
```

## Prerequisites

- Node.js 18+ and npm
- Python 3.13+
- For React Native:
  - Android Studio (for Android development)
  - Xcode (for iOS development, Mac only)
  - Java Development Kit (JDK)

## 🎥 Supported Camera Sources

- **Local Cameras**: USB webcams, built-in cameras (device ID: 0, 1, 2, etc.)
- **RTSP Streams**: IP cameras from Hikvision, Dahua, Axis, Amcrest, Foscam, TP-Link, Reolink, etc.
- **HTTP Streams**: HTTP-based camera feeds
- **Multiple Simultaneous Streams**: Monitor multiple rooms/cameras at once

## License

MIT