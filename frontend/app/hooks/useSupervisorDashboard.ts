"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { IncidentDetail } from "@/app/types/supervisor";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function useSupervisorDashboard() {
  const [incidents, setIncidents] = useState<IncidentDetail[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch initial state over REST
  const fetchInitialIncidents = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/incidents`);
      if (res.ok) {
        const data: IncidentDetail[] = await res.json();
        setIncidents(data);
        if (data.length > 0) {
          setSelectedSessionId((prev) => prev || data[0].session_id);
        }
      }
    } catch (err: unknown) {
      console.warn("Failed to fetch initial incidents via REST:", err);
    }
  }, []);

  // Connect to WebSocket endpoint
  useEffect(() => {
    let isMounted = true;

    async function init() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/incidents`);
        if (res.ok && isMounted) {
          const data: IncidentDetail[] = await res.json();
          setIncidents(data);
          if (data.length > 0) {
            setSelectedSessionId((prev) => prev || data[0].session_id);
          }
        }
      } catch (err: unknown) {
        console.warn("Failed to fetch initial incidents via REST:", err);
      }
    }

    void init();

    const wsUrl = BACKEND_URL.replace(/^http/, "ws") + "/ws/supervisor";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (isMounted) {
        setIsConnected(true);
        setError(null);
      }
    };

    ws.onmessage = (event) => {
      if (!isMounted) return;
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "initial_state" && Array.isArray(payload.incidents)) {
          setIncidents(payload.incidents);
          if (payload.incidents.length > 0) {
            setSelectedSessionId((prev) => prev || payload.incidents[0].session_id);
          }
        } else if (payload.type === "incident_updated" && payload.incident) {
          const updated: IncidentDetail = payload.incident;
          setIncidents((prev) => {
            const idx = prev.findIndex((i) => i.session_id === updated.session_id);
            if (idx >= 0) {
              const copy = [...prev];
              copy[idx] = updated;
              return copy;
            }
            return [updated, ...prev];
          });
          setSelectedSessionId((prev) => prev || updated.session_id);
        }
      } catch (e) {
        console.error("Failed to parse supervisor WS payload:", e);
      }
    };

    ws.onerror = () => {
      if (isMounted) {
        setIsConnected(false);
        setError("WebSocket connection error");
      }
    };

    ws.onclose = () => {
      if (isMounted) {
        setIsConnected(false);
      }
    };

    return () => {
      isMounted = false;
      ws.close();
    };
  }, []);

  const activeIncident = incidents.find((i) => i.session_id === selectedSessionId) || incidents[0] || null;

  return {
    incidents,
    activeIncident,
    selectedSessionId,
    setSelectedSessionId,
    isConnected,
    error,
    refetch: fetchInitialIncidents,
  };
}
