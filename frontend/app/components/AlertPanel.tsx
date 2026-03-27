'use client';
import { useState } from 'react';
import type { Alert } from '../data/mockData';

interface AlertPanelProps {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
  onDismiss: (id: string) => void;
}

const severityConfig = {
  critical: { icon: '🔴', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', badge: 'bg-red-500/20 text-red-400' },
  warning: { icon: '🟡', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', badge: 'bg-amber-500/20 text-amber-400' },
  info: { icon: '🔵', color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30', badge: 'bg-blue-500/20 text-blue-400' },
  resolved: { icon: '🟢', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', badge: 'bg-emerald-500/20 text-emerald-400' },
};

function fmtTime(d: Date) {
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

function fmtRelative(d: Date) {
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export default function AlertPanel({ alerts, onAcknowledge, onDismiss }: AlertPanelProps) {
  const [sevFilter, setSevFilter] = useState<string>('all');
  const [showCount, setShowCount] = useState(6);

  const counts = {
    critical: alerts.filter(a => a.severity === 'critical').length,
    warning: alerts.filter(a => a.severity === 'warning').length,
    resolved: alerts.filter(a => a.severity === 'resolved').length,
    info: alerts.filter(a => a.severity === 'info').length,
  };

  const filtered = alerts.filter(a => sevFilter === 'all' || a.severity === sevFilter);

  const handleExport = () => {
    const rows = ['ID,Room,Severity,Message,Timestamp,Acknowledged'];
    alerts.forEach(a => {
      rows.push(`${a.id},"${a.roomName}",${a.severity},"${a.message}",${a.timestamp.toISOString()},${a.acknowledged}`);
    });
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'wattwatch_alerts.csv';
    link.click(); URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-slate-800/60 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-700/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-base">🚨</span>
            <h2 className="text-white font-bold text-sm">Alert Feed</h2>
            <span className="bg-red-500/20 text-red-400 text-[10px] font-black px-2 py-0.5 rounded-full border border-red-500/30">
              {alerts.filter(a => !a.acknowledged && a.severity !== 'resolved').length} ACTIVE
            </span>
          </div>
          <button
            onClick={handleExport}
            className="text-[10px] font-semibold text-slate-400 hover:text-white px-2 py-1 rounded-lg bg-slate-700 hover:bg-slate-600 transition-colors"
            aria-label="Export alert log as CSV"
          >
            ⬇ Export CSV
          </button>
        </div>

        {/* Counts */}
        <div className="grid grid-cols-4 gap-2 mb-3">
          {(Object.keys(counts) as Array<keyof typeof counts>).map(k => (
            <div key={k} className={`text-center p-1.5 rounded-lg ${severityConfig[k].bg} border cursor-pointer`}
              onClick={() => setSevFilter(sevFilter === k ? 'all' : k)}>
              <div className={`text-sm font-black ${severityConfig[k].color}`}>{counts[k]}</div>
              <div className="text-slate-500 text-[9px] capitalize">{k}</div>
            </div>
          ))}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 flex-wrap">
          {['all', 'critical', 'warning', 'info', 'resolved'].map(s => (
            <button
              key={s}
              onClick={() => setSevFilter(s)}
              className={`text-[10px] font-semibold px-2 py-1 rounded-full transition-colors capitalize ${
                sevFilter === s ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:text-white'
              }`}
              aria-pressed={sevFilter === s}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Alert list */}
      <div className="overflow-y-auto max-h-[480px]" role="log" aria-live="polite" aria-label="Alert feed">
        {filtered.slice(0, showCount).map(alert => {
          const cfg = severityConfig[alert.severity];
          return (
            <div
              key={alert.id}
              className={`border-b border-slate-700/30 p-3 ${cfg.bg} border-l-2 ${
                alert.severity === 'critical' ? 'border-l-red-500' :
                alert.severity === 'warning' ? 'border-l-amber-500' :
                alert.severity === 'resolved' ? 'border-l-emerald-500' : 'border-l-blue-500'
              } ${alert.acknowledged ? 'opacity-60' : ''}`}
            >
              <div className="flex items-start gap-2">
                <span className="text-base mt-0.5 flex-shrink-0">{cfg.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="text-white text-xs font-bold truncate">{alert.roomName}</span>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <span className="text-slate-500 text-[10px] font-mono">{fmtTime(alert.timestamp)}</span>
                      <span className="text-slate-600 text-[10px]">· {fmtRelative(alert.timestamp)}</span>
                    </div>
                  </div>
                  <p className="text-slate-300 text-xs mb-2 leading-relaxed">{alert.message}</p>
                  <div className="flex gap-1.5 flex-wrap">
                    {!alert.acknowledged && alert.severity !== 'resolved' && (
                      <button
                        onClick={() => onAcknowledge(alert.id)}
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-600/30 text-blue-400 hover:bg-blue-600/50 border border-blue-500/30 transition-colors"
                        aria-label={`Acknowledge alert for ${alert.roomName}`}
                      >
                        ✓ Acknowledge
                      </button>
                    )}
                    {!alert.acknowledged && alert.severity === 'critical' && (
                      <button
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-600/30 text-red-400 hover:bg-red-600/50 border border-red-500/30 transition-colors"
                        aria-label={`Send shutdown command for ${alert.roomName}`}
                      >
                        ⚡ Shutdown
                      </button>
                    )}
                    <button
                      onClick={() => onDismiss(alert.id)}
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-700 text-slate-500 hover:text-white transition-colors"
                      aria-label={`Dismiss alert for ${alert.roomName}`}
                    >
                      ✕
                    </button>
                    {alert.acknowledged && (
                      <span className="text-[10px] text-slate-600 flex items-center gap-0.5">
                        ✓ Acknowledged
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-500 text-xs">
            <div className="text-3xl mb-2">✅</div>
            No alerts matching filter
          </div>
        )}
      </div>

      {filtered.length > showCount && (
        <div className="p-3 border-t border-slate-700/30">
          <button
            onClick={() => setShowCount(c => c + 6)}
            className="w-full text-center text-xs text-slate-400 hover:text-white py-1"
          >
            Show more ({filtered.length - showCount} remaining) ↓
          </button>
        </div>
      )}
    </div>
  );
}
