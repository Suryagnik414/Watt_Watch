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

export const INITIAL_ROOMS: Room[] = [
  {
    id: 'r1', name: 'Lab 101', floor: 1, zone: 'East Wing',
    personCount: 0, capacity: 40,
    appliances: [
      { id: 'a1', type: 'light', label: 'Lights', state: 'on', powerWatts: 120 },
      { id: 'a2', type: 'projector', label: 'Projector', state: 'on', powerWatts: 300 },
      { id: 'a3', type: 'fan', label: 'Fan', state: 'on', powerWatts: 75 },
    ],
    status: 'waste', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 1.2,
  },
  {
    id: 'r2', name: 'Seminar 102', floor: 1, zone: 'East Wing',
    personCount: 23, capacity: 60,
    appliances: [
      { id: 'a4', type: 'light', label: 'Lights', state: 'on', powerWatts: 150 },
      { id: 'a5', type: 'ac', label: 'AC', state: 'on', powerWatts: 1200 },
      { id: 'a6', type: 'projector', label: 'Projector', state: 'on', powerWatts: 300 },
    ],
    status: 'secure', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
  {
    id: 'r3', name: 'Library Reading', floor: 1, zone: 'Central',
    personCount: 14, capacity: 80,
    appliances: [
      { id: 'a7', type: 'light', label: 'Lights', state: 'on', powerWatts: 200 },
      { id: 'a8', type: 'monitor', label: 'Monitors', state: 'on', powerWatts: 180 },
      { id: 'a9', type: 'ac', label: 'AC', state: 'on', powerWatts: 1200 },
    ],
    status: 'secure', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
  {
    id: 'r4', name: 'Staff Room 104', floor: 1, zone: 'West Wing',
    personCount: 0, capacity: 20,
    appliances: [
      { id: 'a10', type: 'light', label: 'Lights', state: 'on', powerWatts: 80 },
      { id: 'a11', type: 'ac', label: 'AC', state: 'on', powerWatts: 900 },
      { id: 'a12', type: 'monitor', label: 'Monitors', state: 'off', powerWatts: 120 },
    ],
    status: 'waste', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0.8,
  },
  {
    id: 'r5', name: 'Lab 201', floor: 2, zone: 'East Wing',
    personCount: 31, capacity: 45,
    appliances: [
      { id: 'a13', type: 'light', label: 'Lights', state: 'on', powerWatts: 120 },
      { id: 'a14', type: 'monitor', label: 'Monitors', state: 'on', powerWatts: 360 },
      { id: 'a15', type: 'fan', label: 'Fans', state: 'on', powerWatts: 150 },
      { id: 'a16', type: 'projector', label: 'Projector', state: 'on', powerWatts: 300 },
    ],
    status: 'secure', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
  {
    id: 'r6', name: 'Conference 202', floor: 2, zone: 'Central',
    personCount: 0, capacity: 25,
    appliances: [
      { id: 'a17', type: 'light', label: 'Lights', state: 'on', powerWatts: 100 },
      { id: 'a18', type: 'projector', label: 'Projector', state: 'on', powerWatts: 300 },
      { id: 'a19', type: 'ac', label: 'AC', state: 'on', powerWatts: 1200 },
    ],
    status: 'waste', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 1.6,
  },
  {
    id: 'r7', name: 'Lecture Hall 203', floor: 2, zone: 'West Wing',
    personCount: 67, capacity: 120,
    appliances: [
      { id: 'a20', type: 'light', label: 'Lights', state: 'on', powerWatts: 400 },
      { id: 'a21', type: 'projector', label: 'Projector', state: 'on', powerWatts: 300 },
      { id: 'a22', type: 'ac', label: 'AC', state: 'on', powerWatts: 2400 },
      { id: 'a23', type: 'fan', label: 'Fans', state: 'off', powerWatts: 300 },
    ],
    status: 'secure', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
  {
    id: 'r8', name: 'Research Lab 204', floor: 2, zone: 'East Wing',
    personCount: 0, capacity: 15,
    appliances: [
      { id: 'a24', type: 'light', label: 'Lights', state: 'off', powerWatts: 60 },
      { id: 'a25', type: 'monitor', label: 'Monitors', state: 'on', powerWatts: 240 },
      { id: 'a26', type: 'ac', label: 'AC', state: 'on', powerWatts: 900 },
    ],
    status: 'waste', lastUpdated: new Date(), cameraOnline: false, ghostModeActive: true, energyWastedKwh: 0.9,
  },
  {
    id: 'r9', name: 'Lab 301', floor: 3, zone: 'East Wing',
    personCount: 12, capacity: 40,
    appliances: [
      { id: 'a27', type: 'light', label: 'Lights', state: 'on', powerWatts: 120 },
      { id: 'a28', type: 'monitor', label: 'Monitors', state: 'on', powerWatts: 360 },
      { id: 'a29', type: 'fan', label: 'Fans', state: 'on', powerWatts: 150 },
    ],
    status: 'secure', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
  {
    id: 'r10', name: 'HOD Office 302', floor: 3, zone: 'Central',
    personCount: 1, capacity: 5,
    appliances: [
      { id: 'a30', type: 'light', label: 'Lights', state: 'on', powerWatts: 40 },
      { id: 'a31', type: 'ac', label: 'AC', state: 'on', powerWatts: 900 },
      { id: 'a32', type: 'monitor', label: 'Monitor', state: 'on', powerWatts: 120 },
    ],
    status: 'secure', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
  {
    id: 'r11', name: 'Seminar 303', floor: 3, zone: 'West Wing',
    personCount: 0, capacity: 50,
    appliances: [
      { id: 'a33', type: 'light', label: 'Lights', state: 'on', powerWatts: 180 },
      { id: 'a34', type: 'projector', label: 'Projector', state: 'off', powerWatts: 300 },
      { id: 'a35', type: 'ac', label: 'AC', state: 'off', powerWatts: 1200 },
      { id: 'a36', type: 'fan', label: 'Fans', state: 'on', powerWatts: 150 },
    ],
    status: 'waste', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0.5,
  },
  {
    id: 'r12', name: 'Server Room 304', floor: 3, zone: 'East Wing',
    personCount: 0, capacity: 5,
    appliances: [
      { id: 'a37', type: 'light', label: 'Lights', state: 'off', powerWatts: 40 },
      { id: 'a38', type: 'ac', label: 'AC', state: 'on', powerWatts: 2400 },
      { id: 'a39', type: 'monitor', label: 'Monitors', state: 'on', powerWatts: 120 },
    ],
    status: 'maintenance', lastUpdated: new Date(), cameraOnline: true, ghostModeActive: true, energyWastedKwh: 0,
  },
];

export const INITIAL_ALERTS: Alert[] = [
  {
    id: 'al1', roomId: 'r1', roomName: 'Lab 101', severity: 'critical',
    message: 'Room empty for 8 min — Projector, Lights & Fan still ON',
    timestamp: new Date(Date.now() - 2 * 60000), acknowledged: false,
  },
  {
    id: 'al2', roomId: 'r6', roomName: 'Conference 202', severity: 'critical',
    message: 'Room empty for 12 min — Projector & AC running at full load',
    timestamp: new Date(Date.now() - 5 * 60000), acknowledged: false,
  },
  {
    id: 'al3', roomId: 'r4', roomName: 'Staff Room 104', severity: 'warning',
    message: 'Room empty for 5 min — Lights & AC still ON',
    timestamp: new Date(Date.now() - 8 * 60000), acknowledged: false,
  },
  {
    id: 'al4', roomId: 'r8', roomName: 'Research Lab 204', severity: 'critical',
    message: 'Room empty for 20 min — Monitors & AC consuming 1.14 kW',
    timestamp: new Date(Date.now() - 11 * 60000), acknowledged: true,
  },
  {
    id: 'al5', roomId: 'r11', roomName: 'Seminar 303', severity: 'warning',
    message: 'Room empty for 3 min — Lights & Fans left ON',
    timestamp: new Date(Date.now() - 15 * 60000), acknowledged: false,
  },
  {
    id: 'al6', roomId: 'r2', roomName: 'Seminar 102', severity: 'resolved',
    message: 'Energy waste resolved — 6 people detected, AC auto-adjusted',
    timestamp: new Date(Date.now() - 22 * 60000), acknowledged: true,
  },
  {
    id: 'al7', roomId: 'r7', roomName: 'Lecture Hall 203', severity: 'info',
    message: 'Occupancy at 56% capacity — Energy optimization active',
    timestamp: new Date(Date.now() - 30 * 60000), acknowledged: true,
  },
  {
    id: 'al8', roomId: 'r5', roomName: 'Lab 201', severity: 'resolved',
    message: 'Previously empty room now occupied — Appliances validated OK',
    timestamp: new Date(Date.now() - 45 * 60000), acknowledged: true,
  },
];

export const ENERGY_HOURLY = [
  { time: '08:00', saved: 2.1, wasted: 3.4 },
  { time: '09:00', saved: 4.7, wasted: 2.1 },
  { time: '10:00', saved: 6.2, wasted: 1.8 },
  { time: '11:00', saved: 7.8, wasted: 1.2 },
  { time: '12:00', saved: 5.3, wasted: 2.9 },
  { time: '13:00', saved: 3.9, wasted: 4.1 },
  { time: '14:00', saved: 8.4, wasted: 0.9 },
  { time: '15:00', saved: 9.1, wasted: 0.6 },
  { time: '16:00', saved: 7.6, wasted: 1.3 },
  { time: 'Now', saved: 5.8, wasted: 2.2 },
];

export const ENERGY_WEEKLY = [
  { time: 'Mon', saved: 34.2, wasted: 12.1 },
  { time: 'Tue', saved: 41.7, wasted: 8.4 },
  { time: 'Wed', saved: 38.9, wasted: 10.2 },
  { time: 'Thu', saved: 44.1, wasted: 7.6 },
  { time: 'Fri', saved: 29.3, wasted: 15.8 },
  { time: 'Sat', saved: 18.6, wasted: 5.2 },
  { time: 'Today', saved: 34.7, wasted: 6.4 },
];

export const TOP_WASTING_ROOMS = [
  { name: 'Conference 202', hours: 4.2, kwh: 6.7 },
  { name: 'Lab 101', hours: 3.1, kwh: 4.8 },
  { name: 'Research Lab 204', hours: 2.8, kwh: 3.9 },
  { name: 'Staff Room 104', hours: 2.1, kwh: 2.6 },
  { name: 'Seminar 303', hours: 1.4, kwh: 1.8 },
];

export const APPLIANCE_DISTRIBUTION = [
  { name: 'Lights', value: 28, color: '#fbbf24' },
  { name: 'AC Units', value: 38, color: '#60a5fa' },
  { name: 'Projectors', value: 18, color: '#a78bfa' },
  { name: 'Monitors', value: 11, color: '#34d399' },
  { name: 'Fans', value: 5, color: '#fb923c' },
];

export const OCCUPANCY_TIMELINE = Array.from({ length: 60 }, (_, i) => ({
  time: `${59 - i}m ago`,
  count: Math.max(0, Math.floor(Math.random() * 15 + Math.sin(i / 10) * 8)),
})).reverse();
