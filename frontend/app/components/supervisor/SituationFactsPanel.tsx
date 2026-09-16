"use client";

import { SituationFacts } from "@/app/types/supervisor";

function FactValue({ val, type = "bool" }: { val?: boolean | number | string | null; type?: "bool" | "text" | "number" }) {
  if (val === null || val === undefined) {
    return <span className="text-slate-600 font-mono text-xs">UNKNOWN</span>;
  }

  if (type === "bool") {
    return val ? (
      <span className="text-red-400 font-mono font-bold text-xs bg-red-950/40 px-2 py-0.5 rounded border border-red-900/50">YES</span>
    ) : (
      <span className="text-emerald-400 font-mono text-xs bg-emerald-950/30 px-2 py-0.5 rounded border border-emerald-900/40">NO</span>
    );
  }

  return <span className="text-slate-200 font-mono text-xs font-semibold">{String(val)}</span>;
}

export function SituationFactsPanel({ situation }: { situation?: SituationFacts | null }) {
  const s: Partial<SituationFacts> = situation || {};

  const facts = [
    { label: "EQUIPMENT", val: s.equipment, type: "text" as const },
    { label: "LOCATION", val: s.location, type: "text" as const },
    { label: "MACHINE RUNNING", val: s.machine_running, type: "bool" as const },
    { label: "PEOPLE NEARBY", val: s.people_nearby, type: "number" as const },
    { label: "ABNORMAL VIBRATION", val: s.abnormal_vibration, type: "bool" as const },
    { label: "VIBRATION INCREASING", val: s.vibration_increasing, type: "bool" as const },
    { label: "SPARKS PRESENT", val: s.sparks, type: "bool" as const },
    { label: "SMOKE PRESENT", val: s.smoke, type: "bool" as const },
  ];

  return (
    <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono tracking-wider text-slate-400 font-semibold">SITUATION INTELLIGENCE & FACTS</h3>
        <span className="text-[10px] font-mono text-slate-600">LIVE FEED</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {facts.map((f) => (
          <div key={f.label} className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/40 flex flex-col justify-between">
            <span className="text-[10px] font-mono text-slate-500 mb-1">{f.label}</span>
            <div>
              <FactValue val={f.val} type={f.type} />
            </div>
          </div>
        ))}
      </div>

      {/* Observations */}
      {s.observations && s.observations.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-800/50 space-y-2">
          <span className="text-[10px] font-mono text-slate-500 block">WORKER OBSERVATIONS</span>
          <div className="space-y-1">
            {s.observations.map((obs: string, idx: number) => (
              <p key={idx} className="text-xs text-slate-300 italic bg-slate-950/40 p-2 rounded border border-slate-800/30">
                &ldquo;{obs}&rdquo;
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
