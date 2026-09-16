"use client";

import { IncidentContext } from "@/app/types/voice";

/**
 * SENTINEL — CRITICAL alert panel (Phase 5)
 *
 * Surfaces the deterministic incident state when severity reaches CRITICAL:
 * urgency, the conservative immediate actions, and current safety/escalation
 * status. Keep intentionally small — no dashboard, no redesign.
 */
export function CriticalAlertPanel({
  context,
}: {
  context: IncidentContext;
}) {
  const statusLine = (() => {
    if (context.incident_status === "ESCALATED") {
      return context.supervisor_notified
        ? "Incident escalated — supervisor notified."
        : "Incident escalated.";
    }
    if (context.incident_status === "VERIFYING_SAFETY") {
      return "Safety verification in progress — worker not yet confirmed clear.";
    }
    return "Move away from the equipment now.";
  })();

  const actions =
    context.immediate_actions.length > 0
      ? context.immediate_actions
      : [
          "Move away from the equipment",
          "Do not touch or approach the equipment",
          "Stay clear of the affected area",
        ];

  return (
    <div className="w-full border-2 border-red-600 bg-red-950/40 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-3">
        <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
        <h2 className="text-lg font-bold tracking-widest text-red-400">
          CRITICAL
        </h2>
      </div>

      <p className="text-slate-100 font-semibold">
        Stay clear of the affected equipment.
      </p>

      <ul className="space-y-1.5">
        {actions.map((action) => (
          <li key={action} className="flex items-start gap-2 text-sm text-red-200/90">
            <span className="text-red-500 shrink-0">›</span>
            {action}
          </li>
        ))}
      </ul>

      <div className="pt-2 border-t border-red-900/60 space-y-1">
        <p className="text-sm text-amber-200">
          Safety verification: Are you safely away?
        </p>
        <p className="text-xs font-mono text-slate-400">{statusLine}</p>
      </div>
    </div>
  );
}