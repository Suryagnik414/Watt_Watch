/**
 * Data Aggregation Utilities for Dashboard
 * Server-side functions to aggregate monitoring data from the backend
 */

import { MonitoringStatus, RoomEvent, RoomState } from './api-types';
import { pollMonitoringStatus } from './api-client';

export interface AggregatedRoomData {
  room_id: string;
  status: 'secure' | 'waste' | 'offline' | 'maintenance';
  people_count: number;
  active_appliances: number;
  total_appliances: number;
  room_state: RoomState | null;
  energy_wasted_kwh: number;
  last_updated: string;
  is_monitored: boolean;
  appliances: Array<{
    name: string;
    state: 'on' | 'off' | 'unknown';
    power_watts?: number;
  }>;
}

export interface DashboardAlert {
  id: string;
  room_id: string;
  severity: 'critical' | 'warning' | 'info';
  message: string;
  timestamp: string;
  duration_sec: number;
}

export interface DashboardStats {
  total_rooms: number;
  monitored_rooms: number;
  total_occupancy: number;
  active_appliances: number;
  total_appliances: number;
  active_alerts: number;
  energy_saved_kwh: number;
  energy_wasted_kwh: number;
}

export interface EventTimelineItem {
  id: string;
  room_id: string;
  event_type: 'waste_detected' | 'waste_resolved' | 'occupancy_change';
  message: string;
  timestamp: string;
  people_count: number;
}

/**
 * Convert monitoring status to room state
 */
function monitoringStatusToRoomState(
  status: MonitoringStatus
): AggregatedRoomData['status'] {
  if (!status.is_running) return 'offline';

  const event = status.last_event;
  if (!event) return 'offline';

  if (event.energy_waste_detected) return 'waste';
  if (event.room_state === 'OCCUPIED' || event.room_state === 'EMPTY_SAFE') {
    return 'secure';
  }

  return 'waste';
}

/**
 * Aggregate room data from monitoring status
 */
export function aggregateRoomData(
  statuses: Record<string, MonitoringStatus>
): AggregatedRoomData[] {
  return Object.entries(statuses).map(([roomId, status]) => {
    const event = status.last_event;

    return {
      room_id: roomId,
      status: monitoringStatusToRoomState(status),
      people_count: event?.people_count || 0,
      active_appliances: event?.appliances.filter(a => a.state === 'ON').length || 0,
      total_appliances: event?.appliances.length || 0,
      room_state: event?.room_state || null,
      energy_wasted_kwh: event?.energy_saved_kwh || 0,
      last_updated: event?.timestamp || new Date().toISOString(),
      is_monitored: status.is_running,
      appliances: event?.appliances.map(a => ({
        name: a.name,
        state: a.state.toLowerCase() as 'on' | 'off' | 'unknown',
        power_watts: undefined, // Could be inferred from appliance type
      })) || [],
    };
  });
}

/**
 * Generate dashboard alerts from room data
 */
export function generateAlerts(
  rooms: AggregatedRoomData[]
): DashboardAlert[] {
  const alerts: DashboardAlert[] = [];

  rooms.forEach(room => {
    if (room.status === 'waste' && room.active_appliances > 0) {
      const applianceNames = room.appliances
        .filter(a => a.state === 'on')
        .map(a => a.name)
        .join(', ');

      alerts.push({
        id: `alert_${room.room_id}_${Date.now()}`,
        room_id: room.room_id,
        severity: 'critical',
        message: `Room empty — ${applianceNames} still ON`,
        timestamp: room.last_updated,
        duration_sec: 0, // Would need state tracking to calculate
      });
    }

    if (room.status === 'offline') {
      alerts.push({
        id: `alert_${room.room_id}_offline`,
        room_id: room.room_id,
        severity: 'warning',
        message: 'Camera offline or monitoring stopped',
        timestamp: room.last_updated,
        duration_sec: 0,
      });
    }
  });

  return alerts.sort((a, b) =>
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}

/**
 * Calculate dashboard statistics
 */
export function calculateStats(
  rooms: AggregatedRoomData[]
): DashboardStats {
  const monitored = rooms.filter(r => r.is_monitored);

  return {
    total_rooms: rooms.length,
    monitored_rooms: monitored.length,
    total_occupancy: rooms.reduce((sum, r) => sum + r.people_count, 0),
    active_appliances: rooms.reduce((sum, r) => sum + r.active_appliances, 0),
    total_appliances: rooms.reduce((sum, r) => sum + r.total_appliances, 0),
    active_alerts: generateAlerts(rooms).filter(a => a.severity !== 'info').length,
    energy_saved_kwh: rooms.reduce((sum, r) =>
      r.status === 'waste' ? sum : sum + r.energy_wasted_kwh, 0
    ),
    energy_wasted_kwh: rooms.reduce((sum, r) =>
      r.status === 'waste' ? sum + r.energy_wasted_kwh : sum, 0
    ),
  };
}

/**
 * Generate event timeline from room events
 */
export function generateEventTimeline(
  rooms: AggregatedRoomData[],
  limit: number = 50
): EventTimelineItem[] {
  const events: EventTimelineItem[] = [];

  rooms.forEach(room => {
    if (room.status === 'waste') {
      events.push({
        id: `event_${room.room_id}_waste`,
        room_id: room.room_id,
        event_type: 'waste_detected',
        message: `Energy waste detected in ${room.room_id}`,
        timestamp: room.last_updated,
        people_count: room.people_count,
      });
    }
  });

  return events
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, limit);
}

/**
 * Fetch and aggregate all dashboard data
 */
export async function fetchDashboardData() {
  try {
    const statuses = await pollMonitoringStatus();
    const rooms = aggregateRoomData(statuses);
    const alerts = generateAlerts(rooms);
    const stats = calculateStats(rooms);
    const timeline = generateEventTimeline(rooms);

    return {
      rooms,
      alerts,
      stats,
      timeline,
      lastUpdate: new Date().toISOString(),
    };
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error);
    throw error;
  }
}
