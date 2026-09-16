"use client";

import { RiskDetails } from "@/app/types/supervisor";

export function RiskExplanationCard({ risk }: { risk?: RiskDetails | null }) {
  if (!risk) return null;

  return (
    <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 space-y-4">
      <h3 className="text-xs font-mono tracking-wider text-slate-400 font-semibold">RISK ASSESSMENT & IMMEDIATE ACTIONS</h3>

      {/* Reasons */}
      {risk.reasons && risk.reasons.length > 0 && (
        <div className="space-y-2">
          <span className="text-[10px] font-mono text-slate-500 block">RISK REASONS</span>
          <ul className="space-y-1">
            {risk.reasons.map((r, i) => (
              <li key={i} className="text-xs text-amber-300 flex items-start gap-2 bg-amber-950/20 p-2 rounded border border-amber-900/30">
                <span className="text-amber-500">•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Immediate Actions */}
      {risk.immediate_actions && risk.immediate_actions.length > 0 && (
        <div className="space-y-2">
          <span className="text-[10px] font-mono text-slate-500 block">CONSERVATIVE SAFETY ACTIONS</span>
          <ul className="space-y-1">
            {risk.immediate_actions.map((act, i) => (
              <li key={i} className="text-xs text-slate-200 flex items-start gap-2 bg-slate-950/60 p-2 rounded border border-slate-800/40">
                <span className="text-cyan-400 font-bold">{i + 1}.</span>
                <span>{act}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
