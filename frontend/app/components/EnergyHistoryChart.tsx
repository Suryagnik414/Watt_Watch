/**
 * Energy History Chart Component
 * Displays facility-wide power consumption over time
 */
'use client';

import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from 'recharts';

interface EnergyHistoryChartProps {
  data?: Array<{
    time: string;
    consumption: number;
    threshold: number;
  }>;
}

export default function EnergyHistoryChart({ data }: EnergyHistoryChartProps) {
  // Generate mock data if not provided
  const chartData = data || generateMockData();

  return (
    <div className="bg-slate-900/40 backdrop-blur-md border border-slate-700/50 shadow-xl shadow-black/10 rounded-xl p-5">
      <div className="mb-4">
        <h3 className="text-white font-bold text-sm tracking-tight">Power Consumption Trend</h3>
        <p className="text-slate-500 text-[10px] uppercase tracking-wider mt-0.5">
          Last 24 hours
        </p>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorConsumption" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorThreshold" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
              </linearGradient>
            </defs>
            
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            
            <XAxis 
              dataKey="time" 
              stroke="#64748b"
              style={{ fontSize: '10px', fontFamily: 'monospace' }}
              tick={{ fill: '#64748b' }}
            />
            
            <YAxis 
              stroke="#64748b"
              style={{ fontSize: '10px', fontFamily: 'monospace' }}
              tick={{ fill: '#64748b' }}
              label={{ 
                value: 'kW', 
                angle: -90, 
                position: 'insideLeft',
                style: { fontSize: '10px', fill: '#64748b', fontWeight: 'bold' }
              }}
            />
            
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '12px'
              }}
              labelStyle={{ color: '#cbd5e1', fontWeight: 'bold' }}
              itemStyle={{ color: '#06b6d4' }}
            />
            
            <Legend 
              wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
              iconType="line"
            />

            {/* Threshold line */}
            <Area
              type="monotone"
              dataKey="threshold"
              stroke="#ef4444"
              strokeWidth={2}
              strokeDasharray="5 5"
              fill="url(#colorThreshold)"
              name="Safe Threshold"
            />
            
            {/* Actual consumption */}
            <Area
              type="monotone"
              dataKey="consumption"
              stroke="#06b6d4"
              strokeWidth={2}
              fill="url(#colorConsumption)"
              name="Consumption"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-700/50">
        <div className="text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Peak</p>
          <p className="text-cyan-400 font-bold text-lg tabular-nums">
            {Math.max(...chartData.map(d => d.consumption)).toFixed(1)} kW
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Average</p>
          <p className="text-white font-bold text-lg tabular-nums">
            {(chartData.reduce((sum, d) => sum + d.consumption, 0) / chartData.length).toFixed(1)} kW
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Current</p>
          <p className="text-emerald-400 font-bold text-lg tabular-nums">
            {chartData[chartData.length - 1].consumption.toFixed(1)} kW
          </p>
        </div>
      </div>
    </div>
  );
}

// Generate mock 24-hour data
function generateMockData() {
  const data = [];
  const now = new Date();
  
  for (let i = 23; i >= 0; i--) {
    const hour = new Date(now.getTime() - i * 3600000);
    const hourStr = hour.getHours().toString().padStart(2, '0') + ':00';
    
    // Simulate realistic consumption pattern (higher during day, lower at night)
    const hourOfDay = hour.getHours();
    let baseConsumption = 30;
    
    if (hourOfDay >= 6 && hourOfDay < 18) {
      // Daytime - higher consumption
      baseConsumption = 50 + Math.random() * 20;
    } else if (hourOfDay >= 18 && hourOfDay < 22) {
      // Evening - moderate
      baseConsumption = 40 + Math.random() * 15;
    } else {
      // Night - lower
      baseConsumption = 20 + Math.random() * 10;
    }
    
    data.push({
      time: hourStr,
      consumption: parseFloat(baseConsumption.toFixed(1)),
      threshold: 60, // Safe threshold line
    });
  }
  
  return data;
}
