'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Navbar from './components/Navbar';
import KpiStrip from './components/KpiStrip';
import RoomGrid from './components/RoomGrid';
import AlertPanel from './components/AlertPanel';
import EnergyCharts from './components/EnergyCharts';
import RoomDetailModal from './components/RoomDetailModal';
import ScenarioControls from './components/ScenarioControls';
import Footer from './components/Footer';
import { INITIAL_ROOMS, INITIAL_ALERTS, type Room, type Alert, type DashboardStats } from './data/mockData';

export default function WattWatchDashboard() {
  const [rooms, setRooms] = useState<Room[]>(() =>
    INITIAL_ROOMS.map(r => ({ ...r, lastUpdated: new Date(), appliances: r.appliances.map(a => ({ ...a })) }))
  );
  const [alerts, setAlerts] = useState<Alert[]>(() =>
    INITIAL_ALERTS.map(a => ({ ...a }))
  );
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [heatmapView, setHeatmapView] = useState(false);
  const [activeTab, setActiveTab] = useState<'monitoring' | 'alerts' | 'analytics'>('monitoring');
  const [energySaved, setEnergySaved] = useState(34.7);
  const [costSaved, setCostSaved] = useState(2890);

  // Live demo simulation
  useEffect(() => {
    if (!demoMode) return;
    const interval = setInterval(() => {
      setRooms(prev => prev.map(r => {
        if (r.status === 'maintenance') return r;
        const countDelta = Math.random() < 0.3 ? Math.floor(Math.random() * 3 - 1) : 0;
        const newCount = Math.max(0, Math.min(r.capacity, r.personCount + countDelta));
        const newAppliances = r.appliances.map(a => ({
          ...a,
          state: (Math.random() < 0.06 ? (a.state === 'on' ? 'off' : 'on') : a.state) as 'on' | 'off',
        }));
        const hasWaste = newCount === 0 && newAppliances.some(a => a.state === 'on');
        return {
          ...r,
          personCount: newCount,
          appliances: newAppliances,
          status: hasWaste ? 'waste' : 'secure',
          lastUpdated: new Date(),
        };
      }));
      setEnergySaved(e => parseFloat((e + Math.random() * 0.04).toFixed(2)));
      setCostSaved(c => c + Math.floor(Math.random() * 4));

      // Occasionally fire new alert
      if (Math.random() < 0.12) {
        setRooms(current => {
          const wasteRoom = current.find(r => r.status === 'waste');
          if (wasteRoom) {
            const newAlert: Alert = {
              id: `al_${Date.now()}`,
              roomId: wasteRoom.id,
              roomName: wasteRoom.name,
              severity: 'critical',
              message: `Room empty — ${wasteRoom.appliances.filter(a => a.state === 'on').map(a => a.label).join(', ')} still ON`,
              timestamp: new Date(),
              acknowledged: false,
            };
            setAlerts(prev => [newAlert, ...prev].slice(0, 20));
          }
          return current;
        });
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [demoMode]);

  const handleScenario = useCallback((scenario: 'lecture_ends' | 'morning_rush' | 'reset') => {
    if (scenario === 'lecture_ends') {
      setRooms(prev => prev.map(r => ({
        ...r, personCount: 0, status: 'waste' as const,
        appliances: r.appliances.map(a => ({ ...a, state: 'on' as const })),
      })));
      const newAlerts: Alert[] = INITIAL_ROOMS.map((r, i) => ({
        id: `sc1_${i}`, roomId: r.id, roomName: r.name, severity: 'critical' as const,
        message: 'Room empty — all appliances running unattended after lecture ended',
        timestamp: new Date(Date.now() - i * 800), acknowledged: false,
      }));
      setAlerts(prev => [...newAlerts, ...prev].slice(0, 20));
    } else if (scenario === 'morning_rush') {
      setRooms(prev => prev.map(r => ({
        ...r,
        personCount: Math.floor(r.capacity * 0.55 + Math.random() * r.capacity * 0.35),
        status: 'secure' as const,
        appliances: r.appliances.map(a => ({ ...a, state: 'on' as const })),
      })));
      setAlerts(prev => prev.map(a => ({
        ...a,
        severity: a.severity === 'critical' || a.severity === 'warning' ? 'resolved' as const : a.severity,
        acknowledged: true,
      })));
    } else {
      setRooms(INITIAL_ROOMS.map(r => ({ ...r, lastUpdated: new Date(), appliances: r.appliances.map(a => ({ ...a })) })));
      setAlerts(INITIAL_ALERTS.map(a => ({ ...a })));
      setEnergySaved(34.7);
      setCostSaved(2890);
    }
  }, []);

  const stats: DashboardStats = useMemo(() => ({
    totalRooms: rooms.length,
    totalOccupancy: rooms.reduce((s, r) => s + r.personCount, 0),
    activeAppliances: rooms.reduce((s, r) => s + r.appliances.filter(a => a.state === 'on').length, 0),
    totalAppliances: rooms.reduce((s, r) => s + r.appliances.length, 0),
    activeAlerts: alerts.filter(a => !a.acknowledged && a.severity !== 'resolved').length,
    energySavedKwh: energySaved,
    costSavedINR: costSaved,
    energySavedPercent: 12,
    avgResponseTime: '2m 34s',
  }), [rooms, alerts, energySaved, costSaved]);

  const ackAlert = useCallback((id: string) => setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a)), []);
  const dismissAlert = useCallback((id: string) => setAlerts(prev => prev.filter(a => a.id !== id)), []);

  return (
    <div className={`min-h-screen flex flex-col ${darkMode ? 'dark' : ''}`}
      style={{ background: '#060d1a', fontFamily: "'DM Sans', sans-serif" }}>
      <Navbar
        darkMode={darkMode} toggleDarkMode={() => setDarkMode(d => !d)}
        isConnected={true} alertCount={stats.activeAlerts}
        demoMode={demoMode} toggleDemoMode={() => setDemoMode(d => !d)}
      />
      <main className="flex-1 p-4 md:p-5 space-y-5 max-w-screen-2xl mx-auto w-full">
        <ScenarioControls onScenario={handleScenario} />
        <section aria-label="KPI Summary">
          <KpiStrip stats={stats} />
        </section>
        {/* Tabs */}
        <div className="flex border-b border-slate-800">
          {([['monitoring','⊞ Live Monitoring'],['alerts','🚨 Alert Log'],['analytics','📊 Energy Analytics']] as const).map(([k,l])=>(
            <button key={k} onClick={()=>setActiveTab(k as any)}
              className={`px-5 py-3 text-xs font-bold border-b-2 transition-all ${activeTab===k?'text-blue-400 border-blue-500':'text-slate-500 border-transparent hover:text-slate-300'}`}>
              {l}
            </button>
          ))}
        </div>
        {activeTab === 'monitoring' && (
          <RoomGrid rooms={rooms} onSelectRoom={setSelectedRoom} heatmapView={heatmapView} toggleHeatmap={() => setHeatmapView(h => !h)} />
        )}
        {activeTab === 'alerts' && (
          <div className="max-w-2xl">
            <AlertPanel alerts={alerts} onAcknowledge={ackAlert} onDismiss={dismissAlert} />
          </div>
        )}
        {activeTab === 'analytics' && <EnergyCharts />}
      </main>
      <Footer rooms={rooms} />
      {selectedRoom && <RoomDetailModal room={selectedRoom} onClose={() => setSelectedRoom(null)} />}
    </div>
  );
}
