/**
 * useScheduleWebSocket — persistent WebSocket hook for real-time schedule
 * synchronization.
 *
 * Opens a single WS connection when the user is authenticated and tears it
 * down on logout or unmount.  When a ``schedule_updated`` or
 * ``reoptimization_completed`` event arrives the hook invokes the provided
 * ``onUpdate`` callback so the consuming component can re-fetch its data.
 */
import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "@/store/authStore";

const WS_BASE_URL =
  (import.meta.env.VITE_API_URL || "").replace(/^http/, "ws") || "ws://localhost:8000";

interface WSEvent {
  type: "schedule_updated" | "reoptimization_completed" | "pong";
  user_id?: string;
  run_id?: string;
}

interface UseScheduleWebSocketOptions {
  onUpdate?: (event: WSEvent) => void;
}

export function useScheduleWebSocket({ onUpdate }: UseScheduleWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const accessToken = useAuthStore((s) => s.tokens?.accessToken);

  const connect = useCallback(() => {
    if (!accessToken) return;
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;

    const url = `${WS_BASE_URL}/ws/schedule?token=${encodeURIComponent(accessToken)}`;
    const ws = new WebSocket(url);

    ws.onmessage = (msg) => {
      try {
        const event: WSEvent = JSON.parse(msg.data);
        if (event.type === "schedule_updated" || event.type === "reoptimization_completed") {
          onUpdate?.(event);
        }
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      // Auto-reconnect after 2s unless the token is gone
      if (useAuthStore.getState().tokens?.accessToken) {
        reconnectTimer.current = setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [accessToken, onUpdate]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  /** Send a ping to keep the connection alive. */
  const ping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "ping" }));
    }
  }, []);

  return { ping };
}
