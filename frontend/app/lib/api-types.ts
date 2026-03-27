/**
 * Backend API Type Definitions
 * Matches schemas.py from backend
 */

// FROZEN ENUMS - matches backend
export type ApplianceState = "ON" | "OFF" | "UNKNOWN";
export type RoomState = "OCCUPIED" | "EMPTY_SAFE" | "EMPTY_WASTING";

// Individual appliance detection within a room event
export interface ApplianceDetection {
  name: string; // e.g., 'Projector/TV', 'Laptop'
  state: ApplianceState;
  confidence: number; // 0-1
  bbox?: number[]; // [x1, y1, x2, y2]
  brightness?: number;
}

// Canonical room event structure (PHASE 0 FROZEN SCHEMA)
export interface RoomEvent {
  // Event identity and timing
  room_id: string;
  timestamp: string; // ISO 8601 datetime

  // Occupancy detection
  people_count: number;

  // State machine output
  room_state: RoomState;

  // Appliance monitoring
  appliances: ApplianceDetection[];

  // Energy waste metrics
  energy_waste_detected: boolean;
  energy_saved_kwh: number;

  // State duration tracking
  duration_sec: number;

  // Overall confidence
  confidence: number;

  // Optional metadata
  image_path?: string;
  privacy_mode: boolean;
}

// Response wrapper for /audit endpoint
export interface AuditResponse {
  event: RoomEvent;
  processing_time_ms: number;
  model_versions: Record<string, any>;
}

// Monitoring status response
export interface MonitoringStatus {
  room_id: string;
  is_active: boolean;
  camera_id?: number;
  frame_count?: number;
  sample_interval_sec?: number;
  last_event?: RoomEvent;
  uptime_sec?: number;
}

// Health check response
export interface HealthResponse {
  status: string;
}

// Device info response
export interface DeviceInfo {
  device: string;
  cuda_available: boolean;
  gpu_name?: string;
  gpu_memory_gb?: number;
  cuda_version?: string;
}
