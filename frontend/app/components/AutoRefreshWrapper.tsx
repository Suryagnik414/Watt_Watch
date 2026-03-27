'use client';

/**
 * Auto-Refresh Wrapper Component
 * Client Component that handles automatic page refresh for near-real-time updates
 */

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface AutoRefreshWrapperProps {
  children: React.ReactNode;
  intervalSeconds?: number;
}

export default function AutoRefreshWrapper({
  children,
  intervalSeconds = 5,
}: AutoRefreshWrapperProps) {
  const router = useRouter();
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Ensure component is mounted before showing time-based content
  useEffect(() => {
    setMounted(true);
    setLastRefresh(new Date());
  }, []);

  useEffect(() => {
    if (isPaused || !mounted) return;

    const interval = setInterval(() => {
      router.refresh();
      setLastRefresh(new Date());
    }, intervalSeconds * 1000);

    return () => clearInterval(interval);
  }, [router, intervalSeconds, isPaused, mounted]);

  return (
    <>
      {/* Refresh control bar - only show after mount to avoid hydration errors */}
      {mounted && (
        <div className="fixed bottom-4 right-4 z-50">
          <div className="bg-slate-900/95 border border-slate-700 rounded-lg px-4 py-2 shadow-xl">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${isPaused ? 'bg-yellow-500' : 'bg-green-500 animate-pulse'}`}
                />
                <span className="text-slate-300 text-xs font-medium">
                  {isPaused ? 'Paused' : 'Auto-refresh'}
                </span>
              </div>

              <button
                onClick={() => setIsPaused(!isPaused)}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 text-xs font-medium transition-colors"
              >
                {isPaused ? 'Resume' : 'Pause'}
              </button>

              <button
                onClick={() => {
                  router.refresh();
                  setLastRefresh(new Date());
                }}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-white text-xs font-medium transition-colors"
              >
                Refresh Now
              </button>
            </div>

            {lastRefresh && (
              <p className="text-slate-500 text-xs mt-1" suppressHydrationWarning>
                Last update: {lastRefresh.toLocaleTimeString()}
              </p>
            )}
          </div>
        </div>
      )}

      {children}
    </>
  );
}
