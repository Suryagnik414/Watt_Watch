/**
 * Read-Only Energy Saved Counter Component
 * Server Component - displays aggregated energy metrics
 */

import { DashboardStats } from '../lib/data-aggregation';

interface EnergySavedCounterProps {
  stats: DashboardStats;
}

export default function EnergySavedCounter({ stats }: EnergySavedCounterProps) {
  // Calculate cost saved (assuming ₹8 per kWh - typical commercial rate in India)
  const costPerKwh = 8;
  const costSavedINR = Math.floor(stats.energy_saved_kwh * costPerKwh);

  // Calculate waste percentage
  const totalEnergy = stats.energy_saved_kwh + stats.energy_wasted_kwh;
  const wastePercent = totalEnergy > 0
    ? ((stats.energy_wasted_kwh / totalEnergy) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Energy Saved */}
      <MetricCard
        title="Energy Saved"
        value={stats.energy_saved_kwh.toFixed(2)}
        unit="kWh"
        icon="⚡"
        color="green"
        subtitle="Potential waste prevented"
      />

      {/* Cost Saved */}
      <MetricCard
        title="Cost Saved"
        value={costSavedINR.toLocaleString()}
        unit="INR"
        icon="₹"
        color="emerald"
        subtitle={`@ ₹${costPerKwh}/kWh`}
      />

      {/* Energy Wasted */}
      <MetricCard
        title="Energy Wasted"
        value={stats.energy_wasted_kwh.toFixed(2)}
        unit="kWh"
        icon="⚠"
        color="red"
        subtitle={`${wastePercent}% of total`}
      />

      {/* Active Alerts */}
      <MetricCard
        title="Active Alerts"
        value={stats.active_alerts.toString()}
        unit="alerts"
        icon="🔔"
        color="yellow"
        subtitle="Requiring attention"
      />
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: string;
  unit: string;
  icon: string;
  color: 'green' | 'emerald' | 'red' | 'yellow' | 'blue';
  subtitle: string;
}

function MetricCard({ title, value, unit, icon, color, subtitle }: MetricCardProps) {
  const colorConfig = {
    green: {
      bg: 'bg-green-900/20',
      border: 'border-green-700/50',
      text: 'text-green-400',
      iconBg: 'bg-green-900/40',
    },
    emerald: {
      bg: 'bg-emerald-900/20',
      border: 'border-emerald-700/50',
      text: 'text-emerald-400',
      iconBg: 'bg-emerald-900/40',
    },
    red: {
      bg: 'bg-red-900/20',
      border: 'border-red-700/50',
      text: 'text-red-400',
      iconBg: 'bg-red-900/40',
    },
    yellow: {
      bg: 'bg-yellow-900/20',
      border: 'border-yellow-700/50',
      text: 'text-yellow-400',
      iconBg: 'bg-yellow-900/40',
    },
    blue: {
      bg: 'bg-blue-900/20',
      border: 'border-blue-700/50',
      text: 'text-blue-400',
      iconBg: 'bg-blue-900/40',
    },
  };

  const config = colorConfig[color];

  return (
    <div
      className={`${config.bg} ${config.border} border rounded-lg p-4 transition-all hover:scale-[1.02]`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-slate-400 text-xs font-medium uppercase tracking-wide">
            {title}
          </p>
        </div>
        <div className={`${config.iconBg} rounded-lg p-2 text-lg`}>
          {icon}
        </div>
      </div>

      <div className="mb-2">
        <div className="flex items-baseline gap-2">
          <span className={`${config.text} text-3xl font-bold`}>{value}</span>
          <span className="text-slate-500 text-sm">{unit}</span>
        </div>
      </div>

      <p className="text-slate-500 text-xs">{subtitle}</p>
    </div>
  );
}
