/**
 * useWebSocket — Real-time room monitoring hook
 *
 * Connects to the backend WebSocket endpoint at:
 *   ws://<API_HOST>/ws/<room_id>
 *
 * Receives live RoomEvent JSON pushed by the backend whenever a new frame
 * is processed. Falls back gracefully if the backend is unavailable.
 *
 * Usage:
 *   const { event, status, error } = useWebSocket('room_101');
 */

'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { RoomEvent } from '../lib/api-types';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface UseWebSocketReturn {
  /** Latest RoomEvent received from the backend */
  event: RoomEvent | null;
  /** Current connection status */
  status: WebSocketStatus;
  /** Last error message, if any */
  error: string | null;
  /** Manually reconnect */
  reconnect: () => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, 'ws');

/** Build ws:// URL for a given room */
function toWsUrl(roomId: string): string {
  return `${WS_BASE}/ws/${encodeURIComponent(roomId)}`;
}

export function useWebSocket(
  roomId: string,
  options: {
    /** Auto-reconnect on unexpected close? (default: true) */
    autoReconnect?: boolean;
    /** Delay (ms) before reconnect attempts (default: 3000) */
    reconnectDelay?: number;
    /** Max reconnect attempts before giving up (default: 10) */
    maxReconnectAttempts?: number;
  } = {}
): UseWebSocketReturn {
  const {
    autoReconnect = true,
    reconnectDelay = 3000,
    maxReconnectAttempts = 10,
  } = options;

  const [event, setEvent] = useState<RoomEvent | null>(null);
  const [status, setStatus] = useState<WebSocketStatus>('connecting');
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const url = toWsUrl(roomId);
    console.log(`[WS] Connecting to ${url}`);

    setStatus('connecting');
    setError(null);

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mounted.current) { ws.close(); return; }
        console.log(`[WS] Connected to room '${roomId}'`);
        setStatus('connected');
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (e) => {
        if (!mounted.current) return;
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'room_event') {
            // Strip the extra 'type' field before storing
            const { type: _type, ...roomEvent } = data;
            setEvent(roomEvent as RoomEvent);
          }
          // Ignore status messages (type === 'status')
        } catch (err) {
          console.warn('[WS] Failed to parse message:', e.data);
        }
      };

      ws.onerror = (e) => {
        if (!mounted.current) return;
        console.error('[WS] Error:', e);
        setStatus('error');
        setError('WebSocket connection error');
      };

      ws.onclose = (e) => {
        if (!mounted.current) return;
        console.log(`[WS] Disconnected from room '${roomId}' (code: ${e.code})`);
        wsRef.current = null;

        if (e.code === 1000) {
          // Normal closure
          setStatus('disconnected');
          return;
        }

        setStatus('disconnected');

        if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          const delay = reconnectDelay * Math.min(reconnectAttempts.current, 5);
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`);
          reconnectTimer.current = setTimeout(connect, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError(`Failed to connect after ${maxReconnectAttempts} attempts`);
          setStatus('error');
        }
      };
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to create WebSocket');
    }
  }, [roomId, autoReconnect, reconnectDelay, maxReconnectAttempts]);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    if (wsRef.current) wsRef.current.close();
    connect();
  }, [connect]);

  useEffect(() => {
    mounted.current = true;
    connect();

    return () => {
      mounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { event, status, error, reconnect };
}
