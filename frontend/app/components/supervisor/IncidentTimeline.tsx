"use client";

import { AuditEvent } from "@/app/types/supervisor";

export function IncidentTimeline({ events }: { events?: AuditEvent[] | null }) {
  const auditList = events || [];

  return (
    <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono tracking-wider text-slate-400 font-semibold">AUDIT & EVENT TIMELINE</h3>
        <span className="text-[10px] font-mono text-slate-600">{auditList.length} EVENTS</span>
      </div>

      {auditList.length === 0 ? (
        <p className="text-xs text-slate-600 italic py-4 text-center">No audit events recorded yet.</p>
      ) : (
        <div className="space-y-3 relative before:absolute before:inset-0 before:left-2 before:w-0.5 before:bg-slate-800">
          {auditList.map((ev, i) => {
            const dateStr = new Date(ev.created_at).toLocaleTimeString();
            const isCritical = ev.event_type === "critical_detected";
            const isConfirmed = ev.event_type === "worker_safety_confirmed";
            const isEscalated = ev.event_type === "incident_escalated";

            let dotColor = "bg-slate-600";
            let textColor = "text-slate-300";

            if (isCritical) {
              dotColor = "bg-red-500 ring-4 ring-red-950";
              textColor = "text-red-400 font-semibold";
            } else if (isConfirmed) {
              dotColor = "bg-emerald-400 ring-4 ring-emerald-950";
              textColor = "text-emerald-300 font-semibold";
            } else if (isEscalated) {
              dotColor = "bg-purple-400 ring-4 ring-purple-950";
              textColor = "text-purple-300 font-semibold";
            }

            return (
              <div key={i} className="relative pl-6 space-y-0.5">
                <div className={`absolute left-0 top-1.5 w-4 h-4 rounded-full border-2 border-slate-900 ${dotColor}`} />
                <div className="flex items-center justify-between text-[11px]">
                  <span className={`font-mono uppercase tracking-wider ${textColor}`}>
                    {ev.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">{dateStr}</span>
                </div>
                {ev.source && (
                  <span className="text-[10px] font-mono text-slate-600 block">SOURCE: {ev.source}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
