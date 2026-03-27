'use client';
import { useState, useEffect } from 'react';

interface NavbarProps {
  darkMode: boolean;
  toggleDarkMode: () => void;
  isConnected: boolean;
  alertCount: number;
  demoMode: boolean;
  toggleDemoMode: () => void;
}

export default function Navbar({ darkMode, toggleDarkMode, isConnected, alertCount, demoMode, toggleDemoMode }: NavbarProps) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [campus, setCampus] = useState('Main Campus');
  const [notifOpen, setNotifOpen] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const fmt = (d: Date) => d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const fmtDate = (d: Date) => d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

  return (
    <nav className="sticky top-0 z-50 border-b border-slate-700/60 bg-slate-900/90 backdrop-blur-xl px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/30 text-lg">
          ⚡
        </div>
        <div>
          <div className="text-white font-black text-sm tracking-tight leading-none" style={{ fontFamily: 'monospace' }}>
            WATT-WATCH
          </div>
          <div className="text-cyan-400 text-[10px] font-semibold tracking-widest uppercase leading-none mt-0.5">
            Control Room
          </div>
        </div>
      </div>

      {/* Center group */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Campus selector */}
        <select
          value={campus}
          onChange={e => setCampus(e.target.value)}
          className="bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
          aria-label="Select campus"
        >
          <option>Main Campus</option>
          <option>North Block</option>
          <option>South Annex</option>
        </select>

        {/* Date/time */}
        <div className="hidden sm:flex flex-col items-end">
          <span className="text-white font-mono text-sm font-bold tabular-nums">{fmt(currentTime)}</span>
          <span className="text-slate-400 text-[10px]">{fmtDate(currentTime)}</span>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 bg-slate-800 rounded-full px-3 py-1.5 border border-slate-700">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`}></span>
          <span className={`text-xs font-semibold ${isConnected ? 'text-emerald-400' : 'text-red-400'}`}>
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Right group */}
      <div className="flex items-center gap-2">
        {/* Demo mode toggle */}
        <button
          onClick={toggleDemoMode}
          className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
            demoMode
              ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 animate-pulse'
              : 'bg-slate-800 border-slate-600 text-slate-400 hover:text-white'
          }`}
          aria-label="Toggle demo mode"
        >
          {demoMode ? '🔴 DEMO ON' : '▶ DEMO'}
        </button>

        {/* Dark mode */}
        <button
          onClick={toggleDarkMode}
          className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-base hover:bg-slate-700 transition-colors"
          aria-label="Toggle dark mode"
        >
          {darkMode ? '☀️' : '🌙'}
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-base hover:bg-slate-700 transition-colors relative"
            aria-label={`Notifications: ${alertCount} unread`}
          >
            🔔
            {alertCount > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-black rounded-full flex items-center justify-center animate-bounce">
                {alertCount > 9 ? '9+' : alertCount}
              </span>
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 top-10 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-64 p-3 z-50">
              <p className="text-slate-300 text-xs font-semibold mb-1">🔔 {alertCount} active alerts</p>
              <p className="text-slate-500 text-xs">Scroll to alert panel ↓</p>
            </div>
          )}
        </div>

        {/* User avatar */}
        <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center text-xs font-bold text-white">FM</div>
          <div className="hidden sm:block">
            <div className="text-white text-xs font-semibold leading-none">Rajiv Nair</div>
            <div className="text-slate-400 text-[10px] leading-none mt-0.5">Facility Manager</div>
          </div>
        </div>
      </div>
    </nav>
  );
}
