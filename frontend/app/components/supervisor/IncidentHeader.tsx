"use client";

import { IncidentDetail } from "@/app/types/supervisor";

export function IncidentHeader({ incident }: { incident: IncidentDetail | null }) {
  if (!incident) {
    return (
      <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 flex items-center justify-between">
        <div>
          <span className="text-xs font-mono text-slate-500">INCIDENT ID</span>
          <h2 className="text-xl font-bold text-slate-400">NO ACTIVE INCIDENT</h2>
        </div>
      </div>
    );
  }

  const severityColors = {
    LOW: "border-slate-700 bg-slate-800/40 text-slate-300",
    MEDIUM: "border-amber-500/50 bg-amber-950/40 text-amber-300",
    HIGH: "border-orange-500/50 bg-orange-950/40 text-orange-300",
    CRITICAL: "border-red-500 bg-red-950/70 text-red-300 animate-pulse",
  };

  const statusColors = {
    INVESTIGATING: "text-cyan-400 border-cyan-500/40 bg-cyan-950/30",
    CRITICAL: "text-red-400 border-red-500/50 bg-red-950/40",
    VERIFYING_SAFETY: "text-amber-400 border-amber-500/40 bg-amber-950/30",
    ESCALATED: "text-purple-400 border-purple-500/50 bg-purple-950/40",
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-500 tracking-wider">INCIDENT RECORD</span>
          <span className="text-xs font-mono text-slate-600">SESSION: {incident.session_id}</span>
        </div>
        <h2 className="text-2xl font-black tracking-tight text-white mt-1">{incident.incident_id}</h2>
      </div>

      <div className="flex items-center gap-3">
        {/* Severity Badge */}
        <div className={`px-4 py-1.5 rounded-lg border text-xs font-mono font-bold tracking-widest ${severityColors[incident.severity]}`}>
          SEVERITY: {incident.severity}
        </div>

        {/* Lifecycle Status Badge */}
        <div className={`px-4 py-1.5 rounded-lg border text-xs font-mono font-bold tracking-widest ${statusColors[incident.incident_status]}`}>
          STATUS: {incident.incident_status}
        </div>
      </div>
    </div>
  );
}
