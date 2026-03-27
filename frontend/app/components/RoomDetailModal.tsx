'use client';
import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import type { Room } from '../data/mockData';
import { OCCUPANCY_TIMELINE } from '../data/mockData';

interface RoomDetailModalProps {
  room: Room | null;
  onClose: () => void;
}

const applianceIcons: Record<string, string> = {
  light: '💡', projector: '📽️', monitor: '🖥️', fan: '🌀', ac: '❄️',
};

export default function RoomDetailModal({ room, onClose }: RoomDetailModalProps) {
  if (!room) return null;

  const occupancyData = useMemo(() =>
    OCCUPANCY_TIMELINE.slice(-20).map((d, i) => ({
      ...d,
      time: `${19 - i}m`
    })).reverse(),
  []);

  const totalWattsOn = room.appliances.filter(a => a.state === 'on').reduce((s, a) => s + a.powerWatts, 0);
  const alertHistory = [
    { time: '10 min ago', msg: room.status === 'waste' ? '⚠ Waste detected — appliances left ON' : '✅ Room occupied normally' },
    { time: '25 min ago', msg: '🔄 Occupancy change detected' },
    { time: '45 min ago', msg: '✅ All appliances in valid state' },
    { time: '1h ago', msg: '🟢 Room cleared and secured' },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Details for ${room.name}`}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl shadow-black/50 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-slate-900 border-b border-slate-700/50 px-6 py-4 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-white font-black text-xl">{room.name}</h2>
              {room.status === 'waste' ? (
                <span className="bg-red-500/20 text-red-400 text-xs font-black px-2 py-0.5 rounded-full border border-red-500/30 animate-pulse">⚠ WASTE</span>
              ) : room.status === 'maintenance' ? (
                <span className="bg-amber-500/20 text-amber-400 text-xs font-black px-2 py-0.5 rounded-full border border-amber-500/30">🔧 MAINT.</span>
              ) : (
                <span className="bg-emerald-500/20 text-emerald-400 text-xs font-black px-2 py-0.5 rounded-full border border-emerald-500/30">✅ SECURE</span>
              )}
            </div>
            <div className="text-slate-400 text-sm">Floor {room.floor} · {room.zone} · Camera: {room.cameraOnline ? '🟢 Online' : '🔴 Offline'}</div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-xl w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 transition-colors"
            aria-label="Close room details"
          >
            ✕
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Privacy badge */}
          <div className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-xl p-3">
            <span className="text-lg">🛡️</span>
            <div>
              <div className="text-blue-400 font-bold text-xs">Ghost Mode Active — No PII Stored</div>
              <div className="text-slate-500 text-xs">All video feeds are anonymized. Face blur + skeleton pose processing active.</div>
            </div>
          </div>

          {/* Feed + metadata */}
          <div className="grid grid-cols-2 gap-4">
            {/* Ghost feed (large) */}
            <div className="relative rounded-xl overflow-hidden bg-slate-950 border border-slate-700/50 h-40">
              <div className="absolute inset-0 flex items-center justify-center gap-4">
                {Array.from({ length: room.personCount }).slice(0, 4).map((_, i) => (
                  <svg key={i} width="30" height="45" viewBox="0 0 40 60" fill="none" className="opacity-40">
                    <circle cx="20" cy="10" r="7" stroke="#60a5fa" strokeWidth="1.5" />
                    <line x1="20" y1="17" x2="20" y2="38" stroke="#60a5fa" strokeWidth="1.5" />
                    <line x1="20" y1="24" x2="8" y2="32" stroke="#60a5fa" strokeWidth="1.5" />
                    <line x1="20" y1="24" x2="32" y2="32" stroke="#60a5fa" strokeWidth="1.5" />
                    <line x1="20" y1="38" x2="10" y2="54" stroke="#60a5fa" strokeWidth="1.5" />
                    <line x1="20" y1="38" x2="30" y2="54" stroke="#60a5fa" strokeWidth="1.5" />
                  </svg>
                ))}
                {room.personCount === 0 && (
                  <div className="text-slate-600 text-xs text-center">
                    <div className="text-2xl mb-1">🚪</div>Room Empty
                  </div>
                )}
              </div>
              <div className="absolute inset-0 opacity-5" style={{
                backgroundImage: 'linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)',
                backgroundSize: '14px 14px',
              }} />
              <div className="absolute bottom-2 left-2 right-2 flex justify-between">
                <span className="bg-blue-500/80 text-[9px] font-bold text-white px-1.5 py-0.5 rounded-full">🛡 GHOST MODE</span>
                <span className="bg-slate-900/80 text-[9px] text-slate-300 px-1.5 py-0.5 rounded-full font-mono">CAM-{room.id.toUpperCase()}</span>
              </div>
            </div>

            {/* Metadata */}
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                {[
                  { l: 'Occupancy', v: `${room.personCount} / ${room.capacity}` },
                  { l: 'Floor', v: `Floor ${room.floor}` },
                  { l: 'Zone', v: room.zone },
                  { l: 'Power Draw', v: `${(totalWattsOn / 1000).toFixed(2)} kW` },
                ].map(({ l, v }) => (
                  <div key={l} className="bg-slate-800/60 rounded-lg p-2">
                    <div className="text-slate-500 text-[10px] uppercase tracking-wide">{l}</div>
                    <div className="text-white font-bold text-xs mt-0.5">{v}</div>
                  </div>
                ))}
              </div>
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2">
                <div className="text-red-400 text-[10px] uppercase tracking-wide">Wasted Today</div>
                <div className="text-red-400 font-black text-lg">{room.energyWastedKwh.toFixed(1)} kWh</div>
              </div>
            </div>
          </div>

          {/* Occupancy timeline */}
          <div>
            <h3 className="text-slate-300 text-xs font-bold mb-3 uppercase tracking-widest">Occupancy — Last 20 Minutes</h3>
            <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-3">
              <ResponsiveContainer width="100%" height={120}>
                <AreaChart data={occupancyData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="occGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="time" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 11 }}
                    formatter={(v: number) => [v, 'People']}
                  />
                  <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="url(#occGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Appliance states */}
          <div>
            <h3 className="text-slate-300 text-xs font-bold mb-3 uppercase tracking-widest">Appliance Status</h3>
            <div className="grid grid-cols-2 gap-2">
              {room.appliances.map(a => (
                <div key={a.id} className={`flex items-center justify-between p-3 rounded-lg border ${
                  a.state === 'on' ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-slate-800/60 border-slate-700/30'
                }`}>
                  <div className="flex items-center gap-2">
                    <span className="text-base">{applianceIcons[a.type]}</span>
                    <div>
                      <div className="text-white text-xs font-semibold">{a.label}</div>
                      <div className="text-slate-500 text-[10px]">{a.powerWatts}W</div>
                    </div>
                  </div>
                  <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${
                    a.state === 'on' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-500'
                  }`}>
                    {a.state.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Alert history */}
          <div>
            <h3 className="text-slate-300 text-xs font-bold mb-3 uppercase tracking-widest">Recent Activity</h3>
            <div className="space-y-2">
              {alertHistory.map((h, i) => (
                <div key={i} className="flex gap-3 text-xs">
                  <span className="text-slate-500 whitespace-nowrap font-mono">{h.time}</span>
                  <span className="text-slate-300">{h.msg}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Override buttons */}
          <div className="border-t border-slate-700/50 pt-4 flex gap-3 flex-wrap">
            <button className="flex-1 bg-red-600/20 border border-red-500/40 text-red-400 hover:bg-red-600/30 text-xs font-bold px-4 py-2.5 rounded-xl transition-colors">
              ⚡ Force Shutdown All Appliances
            </button>
            <button className="flex-1 bg-amber-600/20 border border-amber-500/40 text-amber-400 hover:bg-amber-600/30 text-xs font-bold px-4 py-2.5 rounded-xl transition-colors">
              🔧 Mark as Maintenance
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
