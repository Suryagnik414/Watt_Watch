// Minimal mock-data shim kept for compatibility with legacy UI components.

export interface Appliance {
  id: string;
  type: 'light' | 'projector' | 'monitor' | 'fan' | 'ac';
  label: string;
  state: 'on' | 'off';
  powerWatts: number;
}

export interface Room {
  id: string;
  name: string;
  floor: number;
  zone: string;
  personCount: number;
  capacity: number;
  appliances: Appliance[];
  status: 'secure' | 'waste' | 'maintenance';
  lastUpdated: Date;
  cameraOnline: boolean;
  ghostModeActive: boolean;
  energyWastedKwh: number;
}

export interface Alert {
  id: string;
  roomId: string;
  roomName: string;
  severity: 'critical' | 'warning' | 'info' | 'resolved';
  message: string;
  timestamp: Date;
  acknowledged: boolean;
  thumbnailUrl?: string;
}

export interface DashboardStats {
  totalRooms: number;
  totalOccupancy: number;
  activeAppliances: number;
  totalAppliances: number;
  activeAlerts: number;
  energySavedKwh: number;
  costSavedINR: number;
  energySavedPercent: number;
  avgResponseTime: string;
}

export const INITIAL_ROOMS: Room[] = [];
export const INITIAL_ALERTS: Alert[] = [];

export interface EnergyPoint { time: string; saved: number; wasted: number; }
export interface WasteRoom { name: string; hours: number; kwh: number; }
export interface ApplianceDistributionItem { name: string; value: number; color: string; }
export interface OccupancyPoint { time: string; count: number; }

export const ENERGY_HOURLY: EnergyPoint[] = [];
export const ENERGY_WEEKLY: EnergyPoint[] = [];
export const TOP_WASTING_ROOMS: WasteRoom[] = [];
export const APPLIANCE_DISTRIBUTION: ApplianceDistributionItem[] = [];
export const OCCUPANCY_TIMELINE: OccupancyPoint[] = [];
