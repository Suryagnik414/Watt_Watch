/**
 * Power Trend Sparkline Component
 * Displays a mini line chart showing power consumption trend
 */
'use client';

import { LineChart, Line, ResponsiveContainer } from 'recharts';

interface PowerTrendSparklineProps {
  trend?: 'up' | 'down' | 'stable';
  data?: Array<{ value: number }>;
}

export default function PowerTrendSparkline({ 
  trend = 'stable',
  data
}: PowerTrendSparklineProps) {
  // Generate mock trend data if not provided
  const trendData = data || generateTrendData(trend);
  
  // Determine color based on trend
  const trendColor = trend === 'down' 
    ? '#10b981' // Green - good (energy decreasing)
    : trend === 'up'
    ? '#ef4444' // Red - bad (energy increasing)
    : '#6366f1'; // Indigo - neutral

  const trendIcon = trend === 'down' 
    ? '↓' 
    : trend === 'up'
    ? '↑'
    : '→';

  return (
    <div className="flex items-center gap-2">
      {/* Sparkline Chart */}
      <div className="flex-1 h-8">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={trendData}>
            <Line
              type="monotone"
              dataKey="value"
              stroke={trendColor}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Trend Indicator */}
      <div 
        className="text-xs font-bold tabular-nums flex items-center gap-0.5"
        style={{ color: trendColor }}
      >
        <span className="text-base">{trendIcon}</span>
        <span className="uppercase text-[9px] tracking-wider opacity-80">
          {trend}
        </span>
      </div>
    </div>
  );
}

// Generate mock trend data based on trend direction
function generateTrendData(trend: 'up' | 'down' | 'stable'): Array<{ value: number }> {
  const points = 12;
  const data: Array<{ value: number }> = [];
  
  let baseValue = 50;
  
  for (let i = 0; i < points; i++) {
    const noise = (Math.random() - 0.5) * 10;
    
    if (trend === 'up') {
      baseValue += Math.random() * 3 + 1;
    } else if (trend === 'down') {
      baseValue -= Math.random() * 3 + 1;
    }
    
    data.push({ value: Math.max(10, Math.min(90, baseValue + noise)) });
  }
  
  return data;
}
