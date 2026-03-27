'use client';

interface ScenarioControlsProps {
  onScenario: (s: 'lecture_ends' | 'morning_rush' | 'reset') => void;
}

export default function ScenarioControls({ onScenario }: ScenarioControlsProps) {
  return (
    <div className="bg-slate-800/60 backdrop-blur-sm rounded-xl border border-slate-700/50 p-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm">🎬</span>
        <span className="text-slate-300 text-xs font-bold uppercase tracking-widest">Demo Scenarios</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onScenario('lecture_ends')}
          className="flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/25 transition-all"
          aria-label="Run scenario: Lecture ends, rooms empty but appliances stay on"
        >
          <span>▶</span>
          <span>Scenario 1: Lecture Ends</span>
          <span className="text-[10px] text-red-500 bg-red-500/10 px-1 rounded">Waste alerts fire</span>
        </button>
        <button
          onClick={() => onScenario('morning_rush')}
          className="flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 transition-all"
          aria-label="Run scenario: Morning rush, rooms fill up"
        >
          <span>▶</span>
          <span>Scenario 2: Morning Rush</span>
          <span className="text-[10px] text-emerald-500 bg-emerald-500/10 px-1 rounded">All clear</span>
        </button>
        <button
          onClick={() => onScenario('reset')}
          className="flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-xl bg-slate-700 text-slate-400 border border-slate-600 hover:text-white transition-all"
          aria-label="Reset to initial state"
        >
          ↺ Reset
        </button>
      </div>
    </div>
  );
}
