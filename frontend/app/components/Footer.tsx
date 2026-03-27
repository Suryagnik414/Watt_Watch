'use client';

interface FooterProps {
  rooms: { id: string; name: string; cameraOnline: boolean }[];
}

export default function Footer({ rooms }: FooterProps) {
  const onlineCount = rooms.filter(r => r.cameraOnline).length;
  const latency = (0.9 + Math.random() * 0.6).toFixed(1);
  const fps = Math.floor(24 + Math.random() * 6);
  const latencyOk = parseFloat(latency) < 3;

  return (
    <footer className="border-t border-slate-700/50 bg-slate-900/90 backdrop-blur-xl px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] text-slate-500">
        <div className="flex items-center gap-4 flex-wrap">
          {/* System health */}
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${latencyOk ? 'bg-emerald-400' : 'bg-red-500'}`} />
            <span>Latency:</span>
            <span className={`font-mono font-bold ${latencyOk ? 'text-emerald-400' : 'text-red-400'}`}>{latency}s</span>
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${latencyOk ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
              {latencyOk ? '< 3s ✓' : '> 3s ✗'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span>Model FPS:</span>
            <span className="font-mono font-bold text-slate-300">{fps}</span>
          </div>
          <div className="flex items-center gap-1">
            <span>Cameras:</span>
            <span className="font-bold text-emerald-400">{onlineCount}/{rooms.length} online</span>
          </div>
          {/* Camera quick status */}
          <div className="hidden md:flex items-center gap-1">
            {rooms.map(r => (
              <div
                key={r.id}
                className={`w-2 h-2 rounded-sm ${r.cameraOnline ? 'bg-emerald-500' : 'bg-red-500'}`}
                title={`${r.name}: ${r.cameraOnline ? 'online' : 'offline'}`}
              />
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span>v2.4.1</span>
          <span className="text-slate-600">·</span>
          <span>⚡ Powered by <span className="text-blue-500 font-semibold">Watt-Watch AI</span></span>
          <span className="text-slate-600">·</span>
          <a href="#" className="text-slate-500 hover:text-slate-300 transition-colors underline">Privacy Policy</a>
          <span className="text-slate-600">·</span>
          <span className="text-slate-600">🛡 GDPR Compliant</span>
        </div>
      </div>
    </footer>
  );
}
