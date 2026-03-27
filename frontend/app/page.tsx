import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#060d1a] text-white flex items-center justify-center p-6">
      <div className="max-w-2xl text-center space-y-4">
        <h1 className="text-3xl font-bold">Watt Watch</h1>
        <p className="text-slate-300">Live dashboard now uses real backend data. No mock data artifacts on this route.</p>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-500"
        >
          Go to Live Dashboard
        </Link>
      </div>
    </main>
  );
}
