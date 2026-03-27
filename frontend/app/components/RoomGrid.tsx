'use client';
import { useState, useMemo } from 'react';
import RoomCard from './RoomCard';
import type { Room } from '../data/mockData';

type FilterType = 'all' | 'waste' | 'occupied' | 'empty';

interface RoomGridProps {
  rooms: Room[];
  onSelectRoom: (room: Room) => void;
  heatmapView: boolean;
  toggleHeatmap: () => void;
}

export default function RoomGrid({ rooms, onSelectRoom, heatmapView, toggleHeatmap }: RoomGridProps) {
  const [filter, setFilter] = useState<FilterType>('all');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    return rooms.filter(r => {
      const matchSearch = r.name.toLowerCase().includes(search.toLowerCase()) ||
        r.zone.toLowerCase().includes(search.toLowerCase());
      if (!matchSearch) return false;
      if (filter === 'waste') return r.status === 'waste';
      if (filter === 'occupied') return r.personCount > 0;
      if (filter === 'empty') return r.personCount === 0;
      return true;
    });
  }, [rooms, filter, search]);

  const filters: { key: FilterType; label: string; count: number }[] = [
    { key: 'all', label: 'All Rooms', count: rooms.length },
    { key: 'waste', label: '⚠ Waste Alerts', count: rooms.filter(r => r.status === 'waste').length },
    { key: 'occupied', label: '👥 Occupied', count: rooms.filter(r => r.personCount > 0).length },
    { key: 'empty', label: '🚪 Empty', count: rooms.filter(r => r.personCount === 0).length },
  ];

  return (
    <div>
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          {filters.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${
                filter === f.key
                  ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/30'
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white hover:border-slate-600'
              }`}
              aria-pressed={filter === f.key}
            >
              {f.label}
              <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-black ${
                filter === f.key ? 'bg-white/20' : 'bg-slate-700'
              }`}>{f.count}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
            <input
              type="text"
              placeholder="Search rooms..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg pl-7 pr-3 py-1.5 w-44 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-500"
              aria-label="Search rooms"
            />
          </div>
          {/* Heatmap toggle */}
          <button
            onClick={toggleHeatmap}
            className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all ${
              heatmapView
                ? 'bg-violet-600/20 border-violet-500/50 text-violet-400'
                : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
            }`}
            aria-pressed={heatmapView}
          >
            {heatmapView ? '🗺 Heatmap' : '⊞ Grid'}
          </button>
        </div>
      </div>

      {/* Results count */}
      <div className="text-slate-500 text-xs mb-3">
        Showing <span className="text-slate-300 font-semibold">{filtered.length}</span> of {rooms.length} rooms
      </div>

      {/* Heatmap view */}
      {heatmapView ? (
        <div>
          {[1, 2, 3].map(floor => {
            const floorRooms = filtered.filter(r => r.floor === floor);
            if (!floorRooms.length) return null;
            return (
              <div key={floor} className="mb-6">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">Floor {floor}</span>
                  <div className="h-px flex-1 bg-slate-700" />
                </div>
                <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
                  {floorRooms.map(r => (
                    <RoomCard key={r.id} room={r} onSelect={onSelectRoom} heatmap />
                  ))}
                </div>
              </div>
            );
          })}
          {/* Legend */}
          <div className="flex items-center gap-4 mt-4 text-xs text-slate-500">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/30 border border-emerald-500/60" />Secure</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/30 border border-red-500/60" />Waste Alert</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500/20 border border-amber-500/40" />Maintenance</span>
          </div>
        </div>
      ) : (
        /* Card grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(r => (
            <RoomCard key={r.id} room={r} onSelect={onSelectRoom} />
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center py-16 text-slate-500">
              <div className="text-4xl mb-3">🔍</div>
              <div className="text-sm">No rooms match your filter</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
