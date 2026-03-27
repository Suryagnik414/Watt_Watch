/**
 * API Client for Watt Watch Backend
 * Provides typed functions for all backend endpoints
 */

import {
  HealthResponse,
  DeviceInfo,
  MonitoringStatus,
  RoomEvent,
  AuditResponse,
} from './api-types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public data?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new APIError(
        errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        errorData
      );
    }

    return response.json();
  } catch (error) {
    if (error instanceof APIError) throw error;
    throw new APIError(
      error instanceof Error ? error.message : 'Unknown error occurred'
    );
  }
}

// Health & Status Endpoints
export async function getHealth(): Promise<HealthResponse> {
  return fetchAPI<HealthResponse>('/health');
}

export async function getDeviceInfo(): Promise<DeviceInfo> {
  return fetchAPI<DeviceInfo>('/device');
}

// Monitoring Endpoints
export async function getMonitoringStatus(
  roomId?: string
): Promise<MonitoringStatus | Record<string, MonitoringStatus>> {
  const params = roomId ? `?room_id=${encodeURIComponent(roomId)}` : '';
  return fetchAPI(`/monitor/status${params}`);
}

export async function startMonitoring(
  roomId: string,
  cameraId: number = 0,
  fps: number = 0.5,
  resolutionWidth: number = 640,
  resolutionHeight: number = 480,
  saveFrames: boolean = false
): Promise<{ message: string; room_id: string; status: string }> {
  const params = new URLSearchParams({
    room_id: roomId,
    camera_id: cameraId.toString(),
    fps: fps.toString(),
    resolution_width: resolutionWidth.toString(),
    resolution_height: resolutionHeight.toString(),
    save_frames: saveFrames.toString(),
  });

  return fetchAPI(`/monitor/start?${params}`, {
    method: 'POST',
  });
}

export async function stopMonitoring(
  roomId: string
): Promise<{ message: string }> {
  return fetchAPI(`/monitor/stop?room_id=${encodeURIComponent(roomId)}`, {
    method: 'POST',
  });
}

export async function stopAllMonitoring(): Promise<{ message: string }> {
  return fetchAPI('/monitor/stop-all', {
    method: 'POST',
  });
}

// Utility function to poll monitoring status with cache control
export async function pollMonitoringStatus(
  roomIds?: string[]
): Promise<Record<string, MonitoringStatus>> {
  const status = await getMonitoringStatus();

  // Backend /monitor/status (no room_id) returns { total_rooms, active_rooms, rooms: {...} }
  if (status && typeof status === 'object' && 'rooms' in (status as any)) {
    const allRooms = (status as any).rooms as Record<string, MonitoringStatus>;
    if (roomIds) {
      const filtered: Record<string, MonitoringStatus> = {};
      for (const roomId of roomIds) {
        if (allRooms[roomId]) filtered[roomId] = allRooms[roomId];
      }
      return filtered;
    }
    return allRooms;
  }

  // If single room response (room_id present at top-level), convert to record
  if ('room_id' in status) {
    const singleStatus = status as MonitoringStatus;
    return { [singleStatus.room_id]: singleStatus };
  }

  return status as Record<string, MonitoringStatus>;
}

export { APIError };
