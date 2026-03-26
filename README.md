# Watt Watch

A full-stack energy monitoring application with Next.js frontend, FastAPI backend, and React Native mobile app.

## Project Structure

```
Watt_Watch/
├── frontend/          # Next.js web application
├── backend/           # FastAPI server
└── app/              # React Native mobile app (without Expo)
```

## Getting Started

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

### Backend (FastAPI)

```bash
cd backend
# Activate virtual environment
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# Run the server
python main.py
```

The API will be available at [http://localhost:8000](http://localhost:8000)
- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

**Tech Stack:**
- FastAPI
- Uvicorn
- Pydantic
- CORS middleware enabled

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

## Development

1. Start the backend server first
2. Start the frontend development server
3. Run the mobile app on an emulator or device

## Prerequisites

- Node.js 18+ and npm
- Python 3.13+
- For React Native:
  - Android Studio (for Android development)
  - Xcode (for iOS development, Mac only)
  - Java Development Kit (JDK)

## License

MIT