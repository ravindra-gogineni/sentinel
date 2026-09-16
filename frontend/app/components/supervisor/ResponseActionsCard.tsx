"use client";

import { IncidentDetail } from "@/app/types/supervisor";

export function ResponseActionsCard({ incident }: { incident: IncidentDetail | null }) {
  if (!incident) return null;

  const notificationStatus = incident.supervisor_notification_status || "not_configured";
  const escalationStatus = incident.escalation_status || "not_escalated";

  return (
    <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 space-y-4">
      <h3 className="text-xs font-mono tracking-wider text-slate-400 font-semibold">RESPONSE & NOTIFICATION WORKFLOW</h3>

      <div className="grid grid-cols-2 gap-4">
        {/* Supervisor Notification State */}
        <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/50">
          <span className="text-[10px] font-mono text-slate-500 block">SUPERVISOR NOTIFICATION</span>
          <span className="text-xs font-mono font-bold text-slate-200 uppercase mt-1 block">
            {notificationStatus === "created" ? "CREATED (SIMULATED)" : notificationStatus.toUpperCase()}
          </span>
        </div>

        {/* Escalation State */}
        <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/50">
          <span className="text-[10px] font-mono text-slate-500 block">ESCALATION STATUS</span>
          <span className={`text-xs font-mono font-bold uppercase mt-1 block ${escalationStatus === "escalated" ? "text-purple-400" : "text-slate-400"}`}>
            {escalationStatus.toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  );
}
