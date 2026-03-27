'use client';

/**
 * Real-time RTSP Monitoring Dashboard with Analytics
 * Features:
 * - 6 RTSP stream cards with live video (dev mode)
 * - Analytics charts (donut, bar, line)
 * - Dev/Prod mode toggle
 * - WebSocket real-time updates
 */

import { useState, useEffect } from 'react';
import { Play, Pause, Video, VideoOff, Eye, EyeOff } from 'lucide-react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts';

// Types
interface RoomEvent {
  room_id: string;
  people_count: number;
  room_state: string;
  appliances: any[];
  energy_waste_detected: boolean;
  energy_saved_kwh: number;
  frame_data?: string;
  timestamp: string;
}

interface Analytics {
  summary: {
    total_rooms: number;
    total_people: number;
    total_appliances: number;
    energy_waste_rooms: number;
    waste_percentage: number;
    total_energy_saved_kwh: number;
    mode: string;
  };
  state_distribution: Record<string, number>;
  room_analytics: any[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE = API_BASE.replace('http', 'ws');

const ROOM_IDS = ['room_1', 'room_2', 'room_3', 'room_4', 'room_5', 'room_6'];

export default function MonitoringDashboard() {
  const [mode, setMode] = useState<'dev' | 'prod'>('dev');
  const [roomEvents, setRoomEvents] = useState<Record<string, RoomEvent>>({});
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [showAnalytics, setShowAnalytics] = useState(true);

  // Fetch analytics data
  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const response = await fetch(`${API_BASE}/monitor/analytics`);
        const data = await response.json();
        setAnalytics(data);
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      }
    };

    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 5000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket connections for each room
  useEffect(() => {
    const sockets: Record<string, WebSocket> = {};

    ROOM_IDS.forEach((roomId) => {
      const ws = new WebSocket(`${WS_BASE}/ws/${roomId}`);

      ws.onopen = () => {
        console.log(`Connected to ${roomId}`);
        setConnected((prev) => ({ ...prev, [roomId]: true }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'room_event') {
            setRoomEvents((prev) => ({ ...prev, [roomId]: data }));
          }
        } catch (error) {
          console.error(`Error parsing message from ${roomId}:`, error);
        }
      };

      ws.onclose = () => {
        setConnected((prev) => ({ ...prev, [roomId]: false }));
      };

      sockets[roomId] = ws;
    });

    return () => {
      Object.values(sockets).forEach((ws) => ws.close());
    };
  }, []);

  // Chart data
  const stateData = analytics?.state_distribution
    ? Object.entries(analytics.state_distribution).map(([state, count]) => ({
        name: state.replace('_', ' '),
        value: count,
      }))
    : [];

  const roomData = ROOM_IDS.map((roomId) => {
    const event = roomEvents[roomId];
    return {
      room: roomId.replace('_', ' ').toUpperCase(),
      people: event?.people_count || 0,
      appliances: event?.appliances?.length || 0,
    };
  });

  const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-screen-2xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center text-white font-bold text-xl">
                W
              </div>
              <div>
                <h1 className="text-white font-bold text-2xl">Watt Watch Monitor</h1>
                <p className="text-slate-400 text-sm">6 RTSP Streams • Real-time Analytics</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Mode Toggle */}
              <div className="flex items-center gap-2 bg-slate-800 rounded-lg p-1">
                <button
                  onClick={() => setMode('dev')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    mode === 'dev'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Eye className="w-4 h-4 inline mr-2" />
                  Dev Mode
                </button>
                <button
                  onClick={() => setMode('prod')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    mode === 'prod'
                      ? 'bg-green-600 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <EyeOff className="w-4 h-4 inline mr-2" />
                  Prod Mode
                </button>
              </div>

              {/* Analytics Toggle */}
              <button
                onClick={() => setShowAnalytics(!showAnalytics)}
                className="px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors"
              >
                {showAnalytics ? 'Hide' : 'Show'} Analytics
              </button>

              {/* Connection Status */}
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-green-400 text-sm font-medium">
                  {Object.values(connected).filter(Boolean).length}/{ROOM_IDS.length} LIVE
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-6 py-6 space-y-6">
        {/* Summary Cards */}
        {analytics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <SummaryCard
              title="Total People"
              value={analytics.summary.total_people}
              color="blue"
            />
            <SummaryCard
              title="Active Appliances"
              value={analytics.summary.total_appliances}
              color="purple"
            />
            <SummaryCard
              title="Energy Waste"
              value={`${analytics.summary.waste_percentage}%`}
              color="red"
            />
            <SummaryCard
              title="Energy Saved"
              value={`${analytics.summary.total_energy_saved_kwh.toFixed(2)} kWh`}
              color="green"
            />
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Room Streams - 2 columns */}
          <div className="xl:col-span-2 space-y-4">
            <h2 className="text-white font-bold text-xl">Live Streams</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ROOM_IDS.map((roomId) => (
                <RoomCard
                  key={roomId}
                  roomId={roomId}
                  event={roomEvents[roomId]}
                  connected={connected[roomId]}
                  mode={mode}
                />
              ))}
            </div>
          </div>

          {/* Analytics - 1 column */}
          {showAnalytics && analytics && (
            <div className="space-y-4">
              <h2 className="text-white font-bold text-xl">Analytics</h2>

              {/* State Distribution Pie Chart */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                <h3 className="text-white font-semibold mb-3">Room States</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={stateData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={(entry) => entry.name}
                      outerRadius={70}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {stateData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Person/Appliance Bar Chart */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                <h3 className="text-white font-semibold mb-3">Room Activity</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={roomData}>
                    <XAxis dataKey="room" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: '8px',
                      }}
                    />
                    <Legend />
                    <Bar dataKey="people" fill="#3b82f6" name="People" />
                    <Bar dataKey="appliances" fill="#10b981" name="Appliances" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// Summary Card Component
function SummaryCard({
  title,
  value,
  color,
}: {
  title: string;
  value: string | number;
  color: string;
}) {
  const colors = {
    blue: 'from-blue-500 to-blue-600',
    purple: 'from-purple-500 to-purple-600',
    red: 'from-red-500 to-red-600',
    green: 'from-green-500 to-green-600',
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
      <p className="text-slate-400 text-sm font-medium mb-2">{title}</p>
      <p className={`text-3xl font-bold bg-gradient-to-r ${colors[color as keyof typeof colors]} bg-clip-text text-transparent`}>
        {value}
      </p>
    </div>
  );
}

// Room Card Component
function RoomCard({
  roomId,
  event,
  connected,
  mode,
}: {
  roomId: string;
  event?: RoomEvent;
  connected?: boolean;
  mode: 'dev' | 'prod';
}) {
  const hasVideo = mode === 'dev' && event?.frame_data;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
      {/* Video/Status Area */}
      <div className="aspect-video bg-slate-900 relative">
        {hasVideo ? (
          <img
            src={`data:image/jpeg;base64,${event.frame_data}`}
            alt={`${roomId} feed`}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            {mode === 'prod' ? (
              <VideoOff className="w-12 h-12 text-slate-600" />
            ) : (
              <Video className="w-12 h-12 text-slate-600 animate-pulse" />
            )}
          </div>
        )}

        {/* Connection Badge */}
        <div className="absolute top-2 right-2">
          <span
            className={`px-2 py-1 rounded-md text-xs font-medium ${
              connected
                ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                : 'bg-red-500/20 text-red-400 border border-red-500/50'
            }`}
          >
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Info Area */}
      <div className="p-4 space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold">{roomId.replace('_', ' ').toUpperCase()}</h3>
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${
              event?.energy_waste_detected
                ? 'bg-red-500/20 text-red-400'
                : 'bg-green-500/20 text-green-400'
            }`}
          >
            {event?.room_state?.replace('_', ' ') || 'UNKNOWN'}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <p className="text-slate-400 text-xs">People</p>
            <p className="text-white font-semibold">{event?.people_count || 0}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs">Appliances</p>
            <p className="text-white font-semibold">{event?.appliances?.length || 0}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs">Saved</p>
            <p className="text-white font-semibold">
              {event?.energy_saved_kwh?.toFixed(2) || '0.00'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
