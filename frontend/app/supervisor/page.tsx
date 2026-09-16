"use client";

import { useSupervisorDashboard } from "@/app/hooks/useSupervisorDashboard";
import { IncidentHeader } from "@/app/components/supervisor/IncidentHeader";
import { WorkerSafetyCard } from "@/app/components/supervisor/WorkerSafetyCard";
import { ResponseActionsCard } from "@/app/components/supervisor/ResponseActionsCard";
import { SituationFactsPanel } from "@/app/components/supervisor/SituationFactsPanel";
import { RiskExplanationCard } from "@/app/components/supervisor/RiskExplanationCard";
import { IncidentTimeline } from "@/app/components/supervisor/IncidentTimeline";

export default function SupervisorPage() {
  const {
    incidents,
    activeIncident,
    selectedSessionId,
    setSelectedSessionId,
    isConnected,
  } = useSupervisorDashboard();

  return (
    <div className="min-h-screen bg-[#080c14] text-white flex flex-col">
      {/* ── Top Bar ────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800/60 bg-slate-950/40">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 rounded-full border-2 border-purple-500/60 animate-pulse" />
            <div className="relative w-8 h-8 rounded-full border-2 border-purple-400 bg-purple-950/50 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-purple-400" />
            </div>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-[0.2em] text-white">SENTINEL</h1>
            <p className="text-xs text-purple-400 font-mono tracking-wider">
              SUPERVISOR COMMAND CENTER
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Session selector if multiple active incidents exist */}
          {incidents.length > 1 && (
            <select
              value={selectedSessionId || ""}
              onChange={(e) => setSelectedSessionId(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 rounded px-3 py-1.5 focus:outline-none focus:border-purple-500"
            >
              {incidents.map((inc) => (
                <option key={inc.session_id} value={inc.session_id}>
                  {inc.incident_id} ({inc.severity})
                </option>
              ))}
            </select>
          )}

          {/* Connection Status Badge */}
          <div className="flex items-center gap-2 px-3 py-1 rounded-full border border-slate-800 bg-slate-900/60 text-xs font-mono">
            <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400 animate-pulse" : "bg-red-500"}`} />
            <span className={isConnected ? "text-emerald-400" : "text-red-400"}>
              {isConnected ? "LIVE WEBSOCKET" : "DISCONNECTED"}
            </span>
          </div>
        </div>
      </header>

      {/* ── Main Command Center Layout ──────────────────────────────────── */}
      <main className="flex-1 px-6 py-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Incident Header */}
        <IncidentHeader incident={activeIncident} />

        {/* 2-Column Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column — Critical & Safety State (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            <WorkerSafetyCard incident={activeIncident} />
            <ResponseActionsCard incident={activeIncident} />
            <RiskExplanationCard risk={activeIncident?.risk} />
          </div>

          {/* Right Column — Intelligence & Timeline (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <SituationFactsPanel situation={activeIncident?.situation} />
            <IncidentTimeline events={activeIncident?.audit_events} />
          </div>
        </div>
      </main>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="px-6 py-3 border-t border-slate-800/40 flex items-center justify-between text-xs text-slate-700">
        <span>SENTINEL v0.1 — Supervisor Monitoring</span>
        <span>AssemblyAI Safety Intelligence</span>
      </footer>
    </div>
  );
}
