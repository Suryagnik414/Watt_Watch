'use client';
import type { Room } from '../data/mockData';

const applianceIcons: Record<string, string> = {
  light: '💡', projector: '📽️', monitor: '🖥️', fan: '🌀', ac: '❄️',
};

interface RoomCardProps {
  room: Room;
  onSelect: (room: Room) => void;
  heatmap?: boolean;
}

function GhostFeed({ cameraOnline }: { cameraOnline: boolean }) {
  return (
    <div className="relative w-full h-20 rounded-lg overflow-hidden bg-slate-950 border border-slate-700/50 mb-3">
      {/* Simulated ghost/skeleton overlay */}
      <div className="absolute inset-0 flex items-center justify-center">
        <svg width="40" height="60" viewBox="0 0 40 60" fill="none" className="opacity-30">
          {/* Head */}
          <circle cx="20" cy="10" r="7" stroke="#60a5fa" strokeWidth="1.5" />
          {/* Body */}
          <line x1="20" y1="17" x2="20" y2="38" stroke="#60a5fa" strokeWidth="1.5" />
          {/* Arms */}
          <line x1="20" y1="24" x2="8" y2="32" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="24" x2="32" y2="32" stroke="#60a5fa" strokeWidth="1.5" />
          {/* Legs */}
          <line x1="20" y1="38" x2="10" y2="54" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="38" x2="30" y2="54" stroke="#60a5fa" strokeWidth="1.5" />
        </svg>
        <svg width="40" height="60" viewBox="0 0 40 60" fill="none" className="opacity-15 -ml-6 mt-2">
          <circle cx="20" cy="10" r="7" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="17" x2="20" y2="38" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="24" x2="8" y2="32" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="24" x2="32" y2="32" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="38" x2="10" y2="54" stroke="#60a5fa" strokeWidth="1.5" />
          <line x1="20" y1="38" x2="30" y2="54" stroke="#60a5fa" strokeWidth="1.5" />
        </svg>
      </div>
      {/* Scan line effect */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/5 to-transparent animate-pulse" />
      {/* Grid overlay */}
      <div className="absolute inset-0 opacity-10" style={{
        backgroundImage: 'linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)',
        backgroundSize: '12px 12px',
      }} />
      {/* Ghost mode badge */}
      <div className="absolute top-1 right-1 bg-blue-500/80 text-[9px] font-bold text-white px-1.5 py-0.5 rounded-full">
        🛡 GHOST
      </div>
      {!cameraOnline && (
        <div className="absolute inset-0 bg-slate-900/80 flex items-center justify-center">
          <span className="text-red-400 text-xs font-bold">📷 OFFLINE</span>
        </div>
      )}
    </div>
  );
}

export default function RoomCard({ room, onSelect, heatmap }: RoomCardProps) {
  const isWaste = room.status === 'waste';
  const isMaintenance = room.status === 'maintenance';

  const borderColor = isWaste
    ? 'border-red-500/60'
    : isMaintenance
    ? 'border-amber-500/40'
    : 'border-slate-700/50';

  const leftAccent = isWaste
    ? 'bg-red-500'
    : isMaintenance
    ? 'bg-amber-500'
    : 'bg-emerald-500';

  if (heatmap) {
    const heatColor = isWaste
      ? 'bg-red-500/30 border-red-500/60 text-red-300'
      : isMaintenance
      ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
      : 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300';

    return (
      <button
        onClick={() => onSelect(room)}
        className={`${heatColor} border rounded-lg p-3 text-left hover:scale-105 transition-all cursor-pointer`}
        aria-label={`${room.name}: ${room.status}`}
      >
        <div className="text-xs font-bold">{room.name}</div>
        <div className="text-[10px] opacity-70">F{room.floor}</div>
        <div className="text-xs mt-1">👤 {room.personCount}</div>
        {isWaste && <div className="text-[10px] mt-1 font-bold animate-pulse">⚠ WASTE</div>}
      </button>
    );
  }

  return (
    <div
      className={`relative bg-slate-800/60 backdrop-blur-sm rounded-xl border ${borderColor} overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 hover:-translate-y-0.5 ${
        isWaste ? 'shadow-[0_0_20px_rgba(239,68,68,0.25)] shadow-red-500/20' : ''
      }`}
      role="article"
      aria-label={`Room ${room.name}, status: ${room.status}`}
    >
      {/* Left accent bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${leftAccent} ${isWaste ? 'animate-pulse' : ''}`} />

      <div className="p-4 pl-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="text-white font-bold text-sm leading-tight">{room.name}</div>
            <div className="text-slate-400 text-xs">Floor {room.floor} · {room.zone}</div>
          </div>
          <div>
            {isWaste ? (
              <span className="bg-red-500/20 text-red-400 text-[10px] font-black px-2 py-0.5 rounded-full border border-red-500/30 animate-pulse uppercase tracking-wide">
                ⚠ Waste
              </span>
            ) : isMaintenance ? (
              <span className="bg-amber-500/20 text-amber-400 text-[10px] font-black px-2 py-0.5 rounded-full border border-amber-500/30 uppercase tracking-wide">
                🔧 Maint.
              </span>
            ) : (
              <span className="bg-emerald-500/20 text-emerald-400 text-[10px] font-black px-2 py-0.5 rounded-full border border-emerald-500/30 uppercase tracking-wide">
                ✅ Secure
              </span>
            )}
          </div>
        </div>

        {/* Ghost Feed */}
        <GhostFeed cameraOnline={room.cameraOnline} />

        {/* Person count */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5">
            <span className="text-base">👤</span>
            <span className="text-white font-bold text-lg tabular-nums">{room.personCount}</span>
            <span className="text-slate-400 text-xs">/ {room.capacity}</span>
          </div>
          <div className="text-slate-500 text-[10px]">
            Updated {Math.floor((Date.now() - room.lastUpdated.getTime()) / 1000)}s ago
          </div>
        </div>

        {/* Appliance row */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {room.appliances.map(a => (
            <div
              key={a.id}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                a.state === 'on'
                  ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                  : 'bg-slate-700/50 text-slate-500 border-slate-600/30'
              }`}
              aria-label={`${a.label}: ${a.state}`}
              title={`${a.powerWatts}W`}
            >
              <span>{applianceIcons[a.type]}</span>
              <span>{a.label}</span>
              <span>{a.state === 'on' ? '✓' : '✗'}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <button
          onClick={() => onSelect(room)}
          className="w-full text-center text-xs text-blue-400 hover:text-blue-300 font-semibold py-1.5 rounded-lg hover:bg-blue-500/10 transition-colors border border-transparent hover:border-blue-500/20"
          aria-label={`View details for ${room.name}`}
        >
          View Details →
        </button>
      </div>
    </div>
  );
}
