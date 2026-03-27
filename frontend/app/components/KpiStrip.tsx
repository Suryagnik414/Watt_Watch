'use client';
import { useEffect, useRef } from 'react';
import type { DashboardStats } from '../data/mockData';

interface KpiStripProps {
  stats: DashboardStats;
}

function AnimatedNumber({ value, decimals = 0, prefix = '', suffix = '' }: { value: number; decimals?: number; prefix?: string; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(value);

  useEffect(() => {
    if (!ref.current) return;
    const start = prev.current;
    const end = value;
    const dur = 600;
    const startTime = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - startTime) / dur, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      const cur = start + (end - start) * ease;
      if (ref.current) {
        ref.current.textContent = prefix + cur.toFixed(decimals) + suffix;
      }
      if (p < 1) requestAnimationFrame(tick);
      else prev.current = end;
    };
    requestAnimationFrame(tick);
  }, [value, decimals, prefix, suffix]);

  return <span ref={ref}>{prefix}{value.toFixed(decimals)}{suffix}</span>;
}

const KpiCard = ({
  icon, label, value, sub, trend, trendUp, color, decimals = 0, prefix = '', suffix = '',
}: {
  icon: string; label: string; value: number; sub: string; trend?: string; trendUp?: boolean;
  color: 'blue' | 'green' | 'amber' | 'red' | 'violet'; decimals?: number; prefix?: string; suffix?: string;
}) => {
  const colors = {
    blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-400',
    green: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-400',
    amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-400',
    red: 'from-red-500/20 to-red-600/10 border-red-500/30 text-red-400',
    violet: 'from-violet-500/20 to-violet-600/10 border-violet-500/30 text-violet-400',
  };
  return (
    <div className={`relative flex-1 min-w-[140px] rounded-xl border bg-gradient-to-br ${colors[color]} p-4 overflow-hidden`}>
      <div className="absolute top-0 right-0 text-4xl opacity-10 p-2">{icon}</div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-lg">{icon}</span>
        <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-white text-2xl font-black tabular-nums">
        <AnimatedNumber value={value} decimals={decimals} prefix={prefix} suffix={suffix} />
      </div>
      <div className="text-slate-400 text-xs mt-0.5">{sub}</div>
      {trend && (
        <div className={`text-xs font-bold mt-1 ${trendUp ? 'text-emerald-400' : 'text-red-400'}`}>
          {trendUp ? '▲' : '▼'} {trend}
        </div>
      )}
    </div>
  );
};

export default function KpiStrip({ stats }: KpiStripProps) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide" role="region" aria-label="Key performance indicators">
      <KpiCard icon="🏛️" label="Rooms" value={stats.totalRooms} sub="Monitored campus-wide" color="blue" />
      <KpiCard icon="👥" label="Occupancy" value={stats.totalOccupancy} sub="People right now" color="green" />
      <KpiCard
        icon="⚡" label="Appliances ON" value={stats.activeAppliances}
        sub={`of ${stats.totalAppliances} total`} color="violet"
      />
      <KpiCard
        icon="🔴" label="Waste Alerts" value={stats.activeAlerts}
        sub="Rooms wasting energy" color={stats.activeAlerts > 3 ? 'red' : 'amber'}
      />
      <KpiCard
        icon="🌿" label="Energy Saved" value={stats.energySavedKwh}
        sub="kilowatt-hours today" trend={`${stats.energySavedPercent}% vs yesterday`}
        trendUp={true} color="green" decimals={1} suffix=" kWh"
      />
      <KpiCard
        icon="💰" label="Cost Saved" value={stats.costSavedINR}
        sub="Rupees today" trend="₹142 avg/day" trendUp={true}
        color="green" prefix="₹"
      />
    </div>
  );
}
