/**
 * Read-Only Active Alerts List Component
 * Server Component - displays alerts from aggregated data
 */

import { DashboardAlert } from '../lib/data-aggregation';

interface ActiveAlertsListProps {
  alerts: DashboardAlert[];
}

export default function ActiveAlertsList({ alerts }: ActiveAlertsListProps) {
  if (alerts.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 text-center">
        <div className="text-4xl mb-2">✓</div>
        <p className="text-green-400 font-medium text-sm">All Clear</p>
        <p className="text-slate-500 text-xs mt-1">No active alerts</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {alerts.map(alert => (
        <AlertCard key={alert.id} alert={alert} />
      ))}
    </div>
  );
}

function AlertCard({ alert }: { alert: DashboardAlert }) {
  const severityConfig = {
    critical: {
      bg: 'bg-red-900/20',
      border: 'border-red-700/50',
      text: 'text-red-400',
      icon: '🔴',
      label: 'CRITICAL',
    },
    warning: {
      bg: 'bg-yellow-900/20',
      border: 'border-yellow-700/50',
      text: 'text-yellow-400',
      icon: '⚠️',
      label: 'WARNING',
    },
    info: {
      bg: 'bg-blue-900/20',
      border: 'border-blue-700/50',
      text: 'text-blue-400',
      icon: 'ℹ️',
      label: 'INFO',
    },
  };

  const config = severityConfig[alert.severity];
  const timestamp = new Date(alert.timestamp);
  const timeAgo = getTimeAgo(timestamp);

  return (
    <div
      className={`${config.bg} ${config.border} border rounded-lg p-4 transition-all hover:border-opacity-70`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Severity badge */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-base">{config.icon}</span>
            <span
              className={`${config.text} text-xs font-bold uppercase tracking-wide`}
            >
              {config.label}
            </span>
            <span className="text-slate-500 text-xs">·</span>
            <span className="text-slate-500 text-xs">{alert.room_id}</span>
          </div>

          {/* Alert message */}
          <p className="text-white text-sm leading-relaxed">{alert.message}</p>

          {/* Timestamp */}
          <p className="text-slate-500 text-xs mt-2" suppressHydrationWarning>
            {timeAgo}
          </p>
        </div>

        {/* Duration indicator (if available) */}
        {alert.duration_sec > 0 && (
          <div className="text-right">
            <p className="text-slate-400 text-xs">Duration</p>
            <p className={`${config.text} text-sm font-bold`}>
              {formatDuration(alert.duration_sec)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function getTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
