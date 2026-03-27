'use client';
import { useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { ENERGY_HOURLY, ENERGY_WEEKLY, TOP_WASTING_ROOMS, APPLIANCE_DISTRIBUTION } from '../data/mockData';

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-2.5 shadow-xl text-xs">
        <p className="text-slate-300 font-semibold mb-1">{label}</p>
        {payload.map((p: any) => (
          <p key={p.name} style={{ color: p.color }} className="font-bold">
            {p.name}: {p.value} kWh
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function EnergyCharts() {
  const [timeRange, setTimeRange] = useState<'today' | 'week'>('today');
  const data = timeRange === 'today' ? ENERGY_HOURLY : ENERGY_WEEKLY;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">📊</span>
          <h2 className="text-white font-bold text-sm">Energy Analytics</h2>
        </div>
        <div className="flex gap-1">
          {(['today', 'week'] as const).map(r => (
            <button
              key={r}
              onClick={() => setTimeRange(r)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all ${
                timeRange === r ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:text-white'
              }`}
            >
              {r === 'today' ? 'Today' : 'This Week'}
            </button>
          ))}
        </div>
      </div>

      {/* Avg response stat */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-3 text-center">
          <div className="text-emerald-400 text-xl font-black">34.7</div>
          <div className="text-slate-400 text-xs">kWh Saved Today</div>
        </div>
        <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-3 text-center">
          <div className="text-red-400 text-xl font-black">6.4</div>
          <div className="text-slate-400 text-xs">kWh Wasted Today</div>
        </div>
        <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-3 text-center">
          <div className="text-amber-400 text-xl font-black">2m 34s</div>
          <div className="text-slate-400 text-xs">Avg Response Time</div>
        </div>
      </div>

      {/* Line chart */}
      <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4">
        <h3 className="text-slate-300 text-xs font-bold mb-3 uppercase tracking-widest">
          Energy Saved vs Wasted — {timeRange === 'today' ? 'Hourly Today' : 'Daily This Week'}
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
            <Line type="monotone" dataKey="saved" name="Saved" stroke="#10b981" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
            <Line type="monotone" dataKey="wasted" name="Wasted" stroke="#ef4444" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} strokeDasharray="5 3" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Bar + Donut */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bar chart */}
        <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4">
          <h3 className="text-slate-300 text-xs font-bold mb-3 uppercase tracking-widest">
            Top 5 Waste Rooms
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={TOP_WASTING_ROOMS} layout="vertical" margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 9 }} tickLine={false} axisLine={false} width={90} />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: '#f1f5f9' }}
                formatter={(v: number) => [`${v} kWh`, 'Wasted']}
              />
              <Bar dataKey="kwh" fill="#ef4444" radius={[0, 4, 4, 0]} opacity={0.85} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Donut chart */}
        <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4">
          <h3 className="text-slate-300 text-xs font-bold mb-3 uppercase tracking-widest">
            Appliance Distribution
          </h3>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={140} height={140}>
              <PieChart>
                <Pie
                  data={APPLIANCE_DISTRIBUTION}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={60}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {APPLIANCE_DISTRIBUTION.map((entry, i) => (
                    <Cell key={i} fill={entry.color} opacity={0.9} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 11 }}
                  formatter={(v: number) => [`${v}%`, '']}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-1.5 flex-1">
              {APPLIANCE_DISTRIBUTION.map((item) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full" style={{ background: item.color }} />
                    <span className="text-slate-400 text-xs">{item.name}</span>
                  </div>
                  <span className="text-slate-200 text-xs font-bold">{item.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
