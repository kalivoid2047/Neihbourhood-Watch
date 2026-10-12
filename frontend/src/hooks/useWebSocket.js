/**
 * Generic WebSocket hook with automatic reconnection.
 *
 * @param {() => WebSocket | null} factory  Function that opens a WebSocket.
 *   Return null to skip connecting (e.g. when the user is not authenticated).
 * @param {(event: MessageEvent) => void} onMessage  Called for every message.
 * @param {object}  [opts]
 * @param {boolean} [opts.enabled=true]  Set to false to disconnect.
 * @param {number}  [opts.reconnectDelayMs=3000]
 *
 * @returns {{ connected: boolean }}
 */
import { useEffect, useRef, useState } from 'react';
import { refreshAccessToken } from '../api';

export default function useWebSocket(factory, onMessage, opts = {}) {
  const { enabled = true, reconnectDelayMs = 3000 } = opts;
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    let authRetried = false; // one token refresh per failure streak

    function connect() {
      const ws = factory();
      if (!ws) return;
      wsRef.current = ws;

      ws.onopen = () => {
        authRetried = false;
        if (!cancelled) setConnected(true);
      };
      ws.onmessage = (event) => {
        onMessageRef.current(event);
      };
      ws.onclose = (event) => {
        if (cancelled) return;
        setConnected(false);
        // 4003: authenticated but not allowed to watch this resource. Retrying can't help.
        if (event?.code === 4003) return;
        if (event?.code === 4001) {
          if (authRetried) return; // still rejected after a refresh: session is invalid
          authRetried = true;
          // The server rejected our JWT (usually expired). Refresh it once and
          // reconnect; if that fails the session is over, so stop retrying.
          refreshAccessToken()
            .then(() => { if (!cancelled) connect(); })
            .catch(() => {});
          return;
        }
        timerRef.current = setTimeout(connect, reconnectDelayMs);
      };
      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(timerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, [enabled, factory, reconnectDelayMs]);

  return { connected };
}
