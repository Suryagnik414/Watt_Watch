# Watt Watch - Phase 6: Live API-Integrated Dashboard

## Overview

The frontend has been updated with **real API integration** to fetch live data from the FastAPI backend. This implements **Phase 6** of the project - a read-only Vercel dashboard using Next.js Server Components.

## Architecture

### Tech Stack
- **Next.js 14** - App Router with Server Components
- **TypeScript** - Full type safety
- **Tailwind CSS** - Styling
- **FastAPI Backend** - Data source

### Key Features

✅ **Server-Side Rendering** - Data fetched on the server for optimal performance
✅ **Auto-Refresh** - Updates every 5 seconds via Next.js revalidation
✅ **Type-Safe API Client** - Matches backend schemas exactly
✅ **Read-Only First** - No control buttons, only monitoring
✅ **Edge-Ready** - Can be deployed to Vercel Edge Functions

## Getting Started

### 1. Environment Configuration

Create `.env.local` in the frontend directory:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Start the Backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 3. Start Monitoring Rooms

Use the backend API to start monitoring:

```bash
# Start monitoring for room_101
curl -X POST "http://localhost:8000/monitor/start?room_id=room_101&camera_id=0"

# Start monitoring for room_102
curl -X POST "http://localhost:8000/monitor/start?room_id=room_102&camera_id=0"
```

### 4. Start the Frontend

```bash
cd frontend
npm run dev
```

### 5. View the Dashboard

Navigate to: **http://localhost:3000/dashboard**

## Dashboard Components

### 1. Energy Saved Counter
- Displays total energy saved (kWh)
- Cost saved in INR (₹8/kWh rate)
- Energy wasted
- Active alerts count

### 2. Room Status Grid
- Live status for each monitored room
- Occupancy count
- Appliance states (ON/OFF)
- Energy waste indicators
- Color-coded status:
  - 🟢 **Green** - Secure (occupied or safe)
  - 🔴 **Red** - Wasting (empty with appliances on)
  - ⚪ **Gray** - Offline

### 3. Active Alerts List
- Critical and warning alerts
- Room-specific incidents
- Timestamp and duration
- Severity indicators

### 4. Event Timeline
- Chronological event history
- Waste detection events
- Occupancy changes
- Real-time updates

## API Integration

### API Client (`app/lib/api-client.ts`)

Provides typed functions for all backend endpoints:

```typescript
import { getMonitoringStatus, startMonitoring } from '@/lib/api-client';

// Get status for all rooms
const statuses = await getMonitoringStatus();

// Get status for specific room
const status = await getMonitoringStatus('room_101');

// Start monitoring
await startMonitoring('room_101', 0, 5, false);
```

### Data Aggregation (`app/lib/data-aggregation.ts`)

Server-side utilities for transforming backend data:

```typescript
import { fetchDashboardData } from '@/lib/data-aggregation';

const { rooms, alerts, stats, timeline } = await fetchDashboardData();
```

## Server Components

All dashboard components are **Server Components** by default:

```tsx
// app/dashboard/page.tsx
export const revalidate = 5; // Revalidate every 5 seconds

export default async function LiveDashboard() {
  const data = await fetchDashboardData();
  return <RoomStatusGrid rooms={data.rooms} />;
}
```

## Auto-Refresh

The dashboard automatically refreshes every 5 seconds using:

1. **Next.js ISR** - `revalidate: 5` for Server Components
2. **Client-Side Router Refresh** - Optional manual refresh controls

Users can:
- Pause auto-refresh
- Manually trigger refresh
- See last update timestamp

## Deployment

### Vercel Deployment

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd frontend
vercel --prod
```

Set environment variable on Vercel:
- `NEXT_PUBLIC_API_URL` = Your backend URL

### Backend Deployment

Deploy the FastAPI backend to:
- Railway
- Render
- Your own server

Then update `NEXT_PUBLIC_API_URL` to point to your production backend.

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/device` | GET | GPU/CPU info |
| `/monitor/status` | GET | Get monitoring status |
| `/monitor/start` | POST | Start monitoring |
| `/monitor/stop` | POST | Stop monitoring |

## Type Definitions

All types match the backend schemas:

```typescript
// Room State (from schemas.py)
type RoomState = "OCCUPIED" | "EMPTY_SAFE" | "EMPTY_WASTING";

// Appliance State
type ApplianceState = "ON" | "OFF" | "UNKNOWN";

// Room Event (FROZEN SCHEMA)
interface RoomEvent {
  room_id: string;
  timestamp: string;
  people_count: number;
  room_state: RoomState;
  appliances: ApplianceDetection[];
  energy_waste_detected: boolean;
  energy_saved_kwh: number;
  duration_sec: number;
  confidence: number;
}
```

## Troubleshooting

### Backend Not Running

**Error**: `Failed to fetch dashboard data`

**Solution**: Ensure backend is running on `http://localhost:8000`

```bash
cd backend
python -m uvicorn main:app --reload
```

### No Rooms Shown

**Error**: Empty dashboard

**Solution**: Start monitoring at least one room:

```bash
curl -X POST "http://localhost:8000/monitor/start?room_id=test_room&camera_id=0"
```

### CORS Issues

**Error**: CORS policy blocking requests

**Solution**: Backend already has CORS enabled for all origins in development. For production, update `allow_origins` in `backend/main.py`.

## Next Steps (Future Phases)

- [ ] **Phase 7**: Add control buttons (turn off appliances)
- [ ] **Phase 8**: WebSocket integration for real-time push
- [ ] **Phase 9**: Historical analytics and charts
- [ ] **Phase 10**: AI-powered predictions and recommendations

## Files Created

```
frontend/
├── .env.local                          # Environment config
├── app/
│   ├── dashboard/
│   │   └── page.tsx                    # Main dashboard page (Server Component)
│   ├── lib/
│   │   ├── api-client.ts               # Typed API client
│   │   ├── api-types.ts                # TypeScript types (matches backend)
│   │   └── data-aggregation.ts         # Server-side data utilities
│   └── components/
│       ├── RoomStatusGrid.tsx          # Room grid component
│       ├── ActiveAlertsList.tsx        # Alerts component
│       ├── EventTimeline.tsx           # Timeline component
│       ├── EnergySavedCounter.tsx      # Metrics component
│       └── AutoRefreshWrapper.tsx      # Client-side refresh control
└── README_API_INTEGRATION.md           # This file
```

## Summary

✅ **Real API Integration** - Fetches live data from backend
✅ **Server Components** - Optimal performance with SSR
✅ **Auto-Refresh** - Updates every 5 seconds
✅ **Type-Safe** - Full TypeScript integration
✅ **Read-Only** - No control logic, pure monitoring
✅ **Production Ready** - Can be deployed to Vercel

The dashboard is now fully integrated with the backend API and ready for real-time monitoring! 🚀
