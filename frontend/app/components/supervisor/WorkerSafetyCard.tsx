"use client";

import { IncidentDetail } from "@/app/types/supervisor";

export function WorkerSafetyCard({ incident }: { incident: IncidentDetail | null }) {
  const safe = incident?.worker_safe;
  const isCritical = incident?.severity === "CRITICAL";

  let statusText = "UNKNOWN";
  let badgeStyle = "border-slate-800 bg-slate-900/60 text-slate-400";
  let description = "Worker safety has not yet been requested or verified.";

  if (safe === true) {
    statusText = "CONFIRMED SAFE";
    badgeStyle = "border-emerald-500/60 bg-emerald-950/40 text-emerald-300";
    description = "Worker confirmed they are safely clear of the equipment.";
  } else if (safe === false) {
    statusText = "NOT CONFIRMED SAFE";
    badgeStyle = "border-red-500/60 bg-red-950/60 text-red-300 animate-pulse";
    description = "Worker reported they are NOT safely away from the equipment!";
  } else if (isCritical) {
    statusText = "VERIFYING SAFETY";
    badgeStyle = "border-amber-500/60 bg-amber-950/50 text-amber-300 animate-pulse";
    description = "SENTINEL is actively instructing worker to step clear and verify safety.";
  }

  return (
    <div className={`p-5 rounded-xl border transition-all ${isCritical && safe !== true ? "bg-red-950/20 border-red-900/60" : "bg-slate-900/50 border-slate-800/80"}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono tracking-wider text-slate-400 font-semibold">WORKER SAFETY STATUS</span>
        <div className={`px-3 py-1 rounded-md border text-xs font-mono font-bold tracking-wider ${badgeStyle}`}>
          {statusText}
        </div>
      </div>
      <p className="text-sm text-slate-300 font-medium leading-relaxed">
        {description}
      </p>
    </div>
  );
}
