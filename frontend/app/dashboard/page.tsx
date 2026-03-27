/**
 * Live Dashboard Page - Phase 6
 * Read-only dashboard with real API integration
 * Uses Next.js Server Components for data fetching
 */

import { Suspense } from 'react';
import { fetchDashboardData } from '../lib/data-aggregation';
import RoomStatusGrid from '../components/RoomStatusGrid';
import ActiveAlertsList from '../components/ActiveAlertsList';
import EventTimeline from '../components/EventTimeline';
import EnergySavedCounter from '../components/EnergySavedCounter';
import AutoRefreshWrapper from '../components/AutoRefreshWrapper';

// Revalidate every 5 seconds for near-real-time updates
export const revalidate = 5;

export default async function LiveDashboard() {
  return (
    <AutoRefreshWrapper intervalSeconds={5}>
      <div className="min-h-screen bg-[#060d1a]" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 sticky top-0 z-10 backdrop-blur-sm">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-5 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
                W
              </div>
              <div>
                <h1 className="text-white font-bold text-xl">Watt Watch</h1>
                <p className="text-slate-400 text-xs">Live Energy Monitoring</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-green-400 text-xs font-medium">LIVE</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-4 md:px-5 py-5 space-y-6">
        {/* Energy Metrics */}
        <section aria-label="Energy Metrics">
          <Suspense fallback={<LoadingSkeleton type="metrics" />}>
            <DashboardMetrics />
          </Suspense>
        </section>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Room Grid (2 columns) */}
          <section aria-label="Room Status" className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-bold text-lg">Room Status</h2>
              <span className="text-slate-500 text-xs">
                Auto-refresh every 5s
              </span>
            </div>
            <Suspense fallback={<LoadingSkeleton type="grid" />}>
              <RoomGrid />
            </Suspense>
          </section>

          {/* Sidebar (1 column) */}
          <aside className="space-y-6">
            {/* Alerts */}
            <section aria-label="Active Alerts">
              <h2 className="text-white font-bold text-lg mb-3">Active Alerts</h2>
              <Suspense fallback={<LoadingSkeleton type="alerts" />}>
                <AlertsSection />
              </Suspense>
            </section>

            {/* Event Timeline */}
            <section aria-label="Event Timeline">
              <Suspense fallback={<LoadingSkeleton type="timeline" />}>
                <TimelineSection />
              </Suspense>
            </section>
          </aside>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/50 mt-8">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-5 py-4 text-center">
          <p className="text-slate-500 text-xs">
            Watt Watch • Phase 6: Live Dashboard (Read-Only)
          </p>
          <p className="text-slate-600 text-xs mt-1">
            Powered by FastAPI + Next.js Server Components
          </p>
        </div>
      </footer>
    </div>
    </AutoRefreshWrapper>
  );
}

// Server Component: Fetches and displays metrics
async function DashboardMetrics() {
  try {
    const data = await fetchDashboardData();
    return <EnergySavedCounter stats={data.stats} />;
  } catch (error) {
    return <ErrorDisplay message="Failed to load metrics" />;
  }
}

// Server Component: Fetches and displays room grid
async function RoomGrid() {
  try {
    const data = await fetchDashboardData();
    return <RoomStatusGrid rooms={data.rooms} />;
  } catch (error) {
    return <ErrorDisplay message="Failed to load room data" />;
  }
}

// Server Component: Fetches and displays alerts
async function AlertsSection() {
  try {
    const data = await fetchDashboardData();
    return <ActiveAlertsList alerts={data.alerts} />;
  } catch (error) {
    return <ErrorDisplay message="Failed to load alerts" />;
  }
}

// Server Component: Fetches and displays timeline
async function TimelineSection() {
  try {
    const data = await fetchDashboardData();
    return <EventTimeline events={data.timeline} />;
  } catch (error) {
    return <ErrorDisplay message="Failed to load timeline" />;
  }
}

// Error display component
function ErrorDisplay({ message }: { message: string }) {
  return (
    <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 text-center">
      <p className="text-red-400 text-sm font-medium">{message}</p>
      <p className="text-slate-500 text-xs mt-1">
        Make sure the backend is running on {process.env.NEXT_PUBLIC_API_URL}
      </p>
    </div>
  );
}

// Loading skeleton component
function LoadingSkeleton({ type }: { type: 'metrics' | 'grid' | 'alerts' | 'timeline' }) {
  if (type === 'metrics') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 animate-pulse"
          >
            <div className="h-4 bg-slate-800 rounded w-1/2 mb-3" />
            <div className="h-8 bg-slate-800 rounded w-3/4 mb-2" />
            <div className="h-3 bg-slate-800 rounded w-1/3" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'grid') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 h-40 animate-pulse"
          >
            <div className="h-4 bg-slate-800 rounded w-1/3 mb-3" />
            <div className="h-3 bg-slate-800 rounded w-1/2 mb-2" />
            <div className="h-3 bg-slate-800 rounded w-2/3" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'alerts' || type === 'timeline') {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 space-y-3 animate-pulse">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-3 bg-slate-800 rounded w-1/4" />
            <div className="h-4 bg-slate-800 rounded w-full" />
          </div>
        ))}
      </div>
    );
  }

  return null;
}
