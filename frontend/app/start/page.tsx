/**
 * Quick Start Guide Component
 * Landing page to help users navigate between dashboards
 */

export default function QuickStart() {
  return (
    <div className="min-h-screen bg-[#060d1a] flex items-center justify-center p-4" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="max-w-3xl w-full">
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center text-white font-bold text-4xl mx-auto mb-4">
            W
          </div>
          <h1 className="text-white font-bold text-4xl mb-2">Watt Watch</h1>
          <p className="text-slate-400 text-lg">Smart Energy Monitoring System</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Demo Dashboard */}
          <DashboardCard
            title="Demo Dashboard"
            description="Interactive demo with simulated data"
            features={[
              'Live simulation mode',
              'Scenario controls',
              'Interactive UI',
              'Mock real-time updates',
            ]}
            href="/"
            badge="Demo"
            badgeColor="yellow"
          />

          {/* Live API Dashboard */}
          <DashboardCard
            title="Live Dashboard"
            description="Real API integration with backend"
            features={[
              'Real-time monitoring',
              'Server Components',
              'Auto-refresh (5s)',
              'Production-ready',
            ]}
            href="/dashboard"
            badge="Phase 6"
            badgeColor="green"
          />
        </div>

        <div className="mt-8 bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-white font-bold text-lg mb-3">Getting Started</h2>
          <div className="space-y-3 text-sm">
            <div className="flex items-start gap-3">
              <span className="text-blue-400 font-bold">1.</span>
              <div className="flex-1">
                <p className="text-slate-300">Start the backend server:</p>
                <code className="block mt-1 bg-slate-900 text-green-400 px-3 py-2 rounded text-xs">
                  cd backend && python -m uvicorn main:app --reload
                </code>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-blue-400 font-bold">2.</span>
              <div className="flex-1">
                <p className="text-slate-300">Start monitoring a room:</p>
                <code className="block mt-1 bg-slate-900 text-green-400 px-3 py-2 rounded text-xs">
                  curl -X POST "http://localhost:8000/monitor/start?room_id=room_101"
                </code>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-blue-400 font-bold">3.</span>
              <div className="flex-1">
                <p className="text-slate-300">View the Live Dashboard →</p>
              </div>
            </div>
          </div>
        </div>

        <footer className="mt-8 text-center text-slate-500 text-xs">
          <p>Built with Next.js 14 • FastAPI • YOLOv8</p>
          <p className="mt-1">Phase 6: Vercel Dashboard (Read-Only)</p>
        </footer>
      </div>
    </div>
  );
}

interface DashboardCardProps {
  title: string;
  description: string;
  features: string[];
  href: string;
  badge: string;
  badgeColor: 'yellow' | 'green';
}

function DashboardCard({ title, description, features, href, badge, badgeColor }: DashboardCardProps) {
  const badgeStyles = {
    yellow: 'bg-yellow-900/30 text-yellow-400 border-yellow-700/50',
    green: 'bg-green-900/30 text-green-400 border-green-700/50',
  };

  return (
    <a
      href={href}
      className="block bg-slate-900/50 border border-slate-800 rounded-lg p-6 hover:border-blue-600/50 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-white font-bold text-xl group-hover:text-blue-400 transition-colors">
          {title}
        </h3>
        <span className={`px-2 py-1 border rounded text-xs font-semibold ${badgeStyles[badgeColor]}`}>
          {badge}
        </span>
      </div>

      <p className="text-slate-400 text-sm mb-4">{description}</p>

      <ul className="space-y-2">
        {features.map((feature, idx) => (
          <li key={idx} className="flex items-center gap-2 text-slate-300 text-sm">
            <span className="text-blue-500">✓</span>
            {feature}
          </li>
        ))}
      </ul>

      <div className="mt-6 flex items-center gap-2 text-blue-400 text-sm font-medium group-hover:gap-3 transition-all">
        <span>Open Dashboard</span>
        <span>→</span>
      </div>
    </a>
  );
}
