/**
 * Read-Only Room Status Grid Component
 * Server Component - fetches data from backend API
 */

import { AggregatedRoomData } from '../lib/data-aggregation';

interface RoomStatusGridProps {
  rooms: AggregatedRoomData[];
}

export default function RoomStatusGrid({ rooms }: RoomStatusGridProps) {
  if (rooms.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-8 text-center">
        <p className="text-slate-400 text-sm">No rooms being monitored</p>
        <p className="text-slate-500 text-xs mt-2">
          Start monitoring rooms via the API to see data here
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {rooms.map(room => (
        <RoomCard key={room.room_id} room={room} />
      ))}
    </div>
  );
}

function RoomCard({ room }: { room: AggregatedRoomData }) {
  const statusConfig = {
    secure: {
      bg: 'bg-green-900/20',
      border: 'border-green-700/50',
      text: 'text-green-400',
      icon: '✓',
      label: 'Secure',
    },
    waste: {
      bg: 'bg-red-900/20',
      border: 'border-red-700/50',
      text: 'text-red-400',
      icon: '⚠',
      label: 'Wasting',
    },
    offline: {
      bg: 'bg-slate-900/20',
      border: 'border-slate-700/50',
      text: 'text-slate-400',
      icon: '○',
      label: 'Offline',
    },
    maintenance: {
      bg: 'bg-yellow-900/20',
      border: 'border-yellow-700/50',
      text: 'text-yellow-400',
      icon: '🔧',
      label: 'Maintenance',
    },
  };

  const config = statusConfig[room.status];
  const lastUpdateTime = new Date(room.last_updated).toLocaleTimeString();

  return (
    <div
      className={`${config.bg} ${config.border} border rounded-lg p-4 transition-all hover:scale-[1.02]`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-white font-bold text-sm">{room.room_id}</h3>
          <p className="text-slate-500 text-xs mt-0.5" suppressHydrationWarning>
            {lastUpdateTime}
          </p>
        </div>
        <span
          className={`${config.text} text-lg font-bold`}
          title={config.label}
        >
          {config.icon}
        </span>
      </div>

      {/* Occupancy */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-slate-400 text-xs">Occupancy:</span>
        <span className="text-white text-sm font-bold">
          {room.people_count} {room.people_count === 1 ? 'person' : 'people'}
        </span>
      </div>

      {/* Appliances */}
      <div className="space-y-1.5">
        <p className="text-slate-400 text-xs">
          Appliances: {room.active_appliances}/{room.total_appliances} active
        </p>
        {room.appliances.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {room.appliances.map((appliance, idx) => (
              <span
                key={idx}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
                  appliance.state === 'on'
                    ? 'bg-blue-900/30 text-blue-300 border border-blue-700/50'
                    : 'bg-slate-800/30 text-slate-500 border border-slate-700/30'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    appliance.state === 'on' ? 'bg-blue-400' : 'bg-slate-600'
                  }`}
                />
                {appliance.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Energy waste indicator */}
      {room.status === 'waste' && room.energy_wasted_kwh > 0 && (
        <div className="mt-3 pt-3 border-t border-red-800/30">
          <p className="text-red-400 text-xs font-medium">
            ⚡ ~{room.energy_wasted_kwh.toFixed(2)} kWh wasted
          </p>
        </div>
      )}
    </div>
  );
}
