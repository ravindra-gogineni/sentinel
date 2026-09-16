"use client";

import { VoiceStatus } from "@/app/types/voice";

interface RiskLevel {
  label: string;
  color: string;
  bg: string;
  border: string;
  pulse: boolean;
}

const RISK_LEVELS: Record<string, RiskLevel> = {
  LOW: {
    label: "LOW",
    color: "text-emerald-400",
    bg: "bg-emerald-950/40",
    border: "border-emerald-800/60",
    pulse: false,
  },
  MEDIUM: {
    label: "MEDIUM",
    color: "text-amber-400",
    bg: "bg-amber-950/40",
    border: "border-amber-700/60",
    pulse: false,
  },
  HIGH: {
    label: "HIGH",
    color: "text-orange-400",
    bg: "bg-orange-950/40",
    border: "border-orange-700/60",
    pulse: true,
  },
  CRITICAL: {
    label: "CRITICAL",
    color: "text-red-400",
    bg: "bg-red-950/50",
    border: "border-red-600",
    pulse: true,
  },
};

interface StatusBadgeProps {
  voiceStatus: VoiceStatus;
  risk?: keyof typeof RISK_LEVELS;
}

export function StatusBadge({ voiceStatus, risk = "LOW" }: StatusBadgeProps) {
  const riskLevel = RISK_LEVELS[risk] ?? RISK_LEVELS.LOW;

  const statusLabel: Record<VoiceStatus, string> = {
    idle: "READY",
    connecting: "CONNECTING",
    listening: "LISTENING",
    speaking: "RESPONDING",
    interrupted: "INTERRUPTED",
    error: "ERROR",
    ended: "ENDED",
  };

  const statusColor: Record<VoiceStatus, string> = {
    idle: "text-slate-400",
    connecting: "text-cyan-400",
    listening: "text-cyan-300",
    speaking: "text-violet-300",
    interrupted: "text-orange-300",
    error: "text-red-400",
    ended: "text-slate-500",
  };

  return (
    <div className="flex items-center gap-4">
      {/* Voice status indicator */}
      <div className="flex items-center gap-2">
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            voiceStatus === "listening"
              ? "bg-cyan-400 animate-pulse"
              : voiceStatus === "speaking"
              ? "bg-violet-400 animate-pulse"
              : voiceStatus === "connecting"
              ? "bg-cyan-600 animate-pulse"
              : voiceStatus === "error"
              ? "bg-red-500"
              : "bg-slate-600"
          }`}
        />
        <span className={`text-xs font-mono font-semibold tracking-widest ${statusColor[voiceStatus]}`}>
          {statusLabel[voiceStatus]}
        </span>
      </div>

      {/* Risk level badge */}
      <div
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-bold tracking-wider
          ${riskLevel.bg} ${riskLevel.border} ${riskLevel.color}
          ${riskLevel.pulse ? "animate-pulse" : ""}`}
      >
        {riskLevel.label}
      </div>
    </div>
  );
}
