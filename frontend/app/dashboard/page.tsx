/**
 * Live Dashboard Page - Phase 6
 * Read-only dashboard with real API integration
 * Uses Next.js Server Components for data fetching
 */

import { Suspense } from 'react';
import { fetchDashboardData } from '../lib/data-aggregation';
import Navbar from '../components/Navbar';
import RoomStatusGrid from '../components/RoomStatusGrid';
import ActiveAlertsList from '../components/ActiveAlertsList';
import EventTimeline from '../components/EventTimeline';
import EnergySavedCounter from '../components/EnergySavedCounter';
import AutoRefreshWrapper from '../components/AutoRefreshWrapper';

// Revalidate every 5 seconds for near-real-time updates
export const revalidate = 5;

export default async function LiveDashboard() {
  // Fetch high-level data for Navbar
  let alertCount = 0;
  let isConnected = false;
  try {
    const data = await fetchDashboardData();
    alertCount = data.alerts?.length || 0;
    isConnected = true;
  } catch (e) {
    console.error('Failed to fetch dashboard data for Navbar:', e);
    isConnected = false;
  }

  return (
    <AutoRefreshWrapper intervalSeconds={5}>
      <div className="min-h-screen bg-[#060d1a] text-slate-200" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      
      {/* Navbar replaces hardcoded header */}
      <Navbar isConnected={isConnected} alertCount={alertCount} />

      <main className="max-w-screen-2xl mx-auto px-4 md:px-5 py-6 space-y-8">
        {/* Energy Metrics */}
        <section aria-label="Energy Metrics">
          <Suspense fallback={<LoadingSkeleton type="metrics" />}>
            <DashboardMetrics />
          </Suspense>
        </section>

        {/* Grid Layout: Adjusted proportions for better UX */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Main Content Area (3/4 on large screens) */}
          <div className="xl:col-span-3 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-bold text-xl tracking-tight">Facility Overview</h2>
              <span className="bg-slate-800/50 text-slate-400 text-[10px] uppercase tracking-wider px-2 py-1 rounded border border-slate-700/50">
                Auto-syncing (5s)
              </span>
            </div>
            <Suspense fallback={<LoadingSkeleton type="grid" />}>
              <RoomGrid />
            </Suspense>
          </div>

          {/* Right Sidebar (1/4) */}
          <aside className="xl:col-span-1 flex flex-col gap-6">
            {/* Alerts */}
            <section aria-label="Active Alerts">
              <h2 className="text-white font-bold text-lg mb-3 tracking-tight">Active Alerts</h2>
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

// Loading skeleton component with glassmorphism
function LoadingSkeleton({ type }: { type: 'metrics' | 'grid' | 'alerts' | 'timeline' }) {
  if (type === 'metrics') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="bg-slate-900/40 backdrop-blur-md border border-slate-700/50 shadow-xl shadow-black/20 rounded-xl p-5 animate-pulse"
          >
            <div className="h-4 bg-slate-800/60 rounded w-1/2 mb-3" />
            <div className="h-8 bg-slate-800/60 rounded w-3/4 mb-2" />
            <div className="h-3 bg-slate-800/60 rounded w-1/3" />
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
            className="bg-slate-900/40 backdrop-blur-md border border-slate-700/50 shadow-xl shadow-black/20 rounded-xl p-5 h-40 animate-pulse"
          >
            <div className="h-4 bg-slate-800/60 rounded w-1/3 mb-3" />
            <div className="h-3 bg-slate-800/60 rounded w-1/2 mb-2" />
            <div className="h-3 bg-slate-800/60 rounded w-2/3" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'alerts' || type === 'timeline') {
    return (
      <div className="bg-slate-900/40 backdrop-blur-md border border-slate-700/50 shadow-xl shadow-black/20 rounded-xl p-4 space-y-3 animate-pulse">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-3 bg-slate-800/60 rounded w-1/4" />
            <div className="h-4 bg-slate-800/60 rounded w-full" />
          </div>
        ))}
      </div>
    );
  }

  return null;
}
