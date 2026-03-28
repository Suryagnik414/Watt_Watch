/**
 * Read-Only Event Timeline Component
 * Server Component - displays chronological event history
 */

import { EventTimelineItem } from '../lib/data-aggregation';

interface EventTimelineProps {
  events: EventTimelineItem[];
}

export default function EventTimeline({ events }: EventTimelineProps) {
  if (events.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 text-center">
        <p className="text-slate-400 text-sm">No recent events</p>
        <p className="text-slate-500 text-xs mt-1">
          Events will appear as rooms are monitored
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/40 backdrop-blur-md border border-slate-700/50 shadow-xl shadow-black/10 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700/50 bg-slate-800/30">
        <h3 className="text-white font-bold text-sm tracking-tight">Recent Events</h3>
        <p className="text-slate-500 text-[10px] mt-0.5 uppercase tracking-wider">
          Live event stream
        </p>
      </div>

      {/* Timeline */}
      <div className="max-h-[500px] overflow-y-auto">
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-8 top-0 bottom-0 w-px bg-slate-800" />

          {/* Events */}
          <div className="space-y-0">
            {events.map((event, idx) => (
              <EventItem key={event.id} event={event} isLast={idx === events.length - 1} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EventItem({ event, isLast }: { event: EventTimelineItem; isLast: boolean }) {
  const eventConfig = {
    waste_detected: {
      icon: '⚠️',
      color: 'text-red-400',
      bg: 'bg-red-900/20',
      border: 'border-red-700/50',
    },
    waste_resolved: {
      icon: '✓',
      color: 'text-green-400',
      bg: 'bg-green-900/20',
      border: 'border-green-700/50',
    },
    occupancy_change: {
      icon: '👥',
      color: 'text-blue-400',
      bg: 'bg-blue-900/20',
      border: 'border-blue-700/50',
    },
  };

  const config = eventConfig[event.event_type];
  const timestamp = new Date(event.timestamp);
  const timeStr = timestamp.toLocaleTimeString();

  return (
    <div className={`relative px-4 py-3 hover:bg-slate-800/20 transition-colors ${!isLast ? 'border-b border-slate-800/50' : ''}`}>
      <div className="flex items-start gap-3">
        {/* Timeline dot */}
        <div className="relative flex-shrink-0 mt-1">
          <div
            className={`w-6 h-6 rounded-full ${config.bg} border-2 ${config.border} flex items-center justify-center text-xs z-10 relative`}
          >
            {config.icon}
          </div>
        </div>

        {/* Event content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm leading-relaxed font-medium">
                {event.message}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-slate-500 text-[10px] font-semibold uppercase tracking-wider">{event.room_id}</span>
                <span className="text-slate-600 text-xs">·</span>
                <span className="text-slate-500 text-xs tabular-nums">
                  {event.people_count} {event.people_count === 1 ? 'person' : 'people'}
                </span>
              </div>
            </div>
            <span className="text-slate-500 text-[10px] whitespace-nowrap font-mono tabular-nums" suppressHydrationWarning>
              {timeStr}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
