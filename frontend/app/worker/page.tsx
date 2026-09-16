"use client";

import { useEffect, useRef } from "react";
import { useVoiceAgent } from "@/app/hooks/useVoiceAgent";
import { Waveform } from "@/app/components/Waveform";
import { StatusBadge } from "@/app/components/StatusBadge";
import { CriticalAlertPanel } from "@/app/components/CriticalAlertPanel";
import { TranscriptEntry } from "@/app/types/voice";

export default function WorkerPage() {
  const {
    status,
    transcript,
    agentPartial,
    workerPartial,
    error,
    audioLevel,
    incidentContext,
    startSession,
    endSession,
  } = useVoiceAgent();

  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const isActive = status !== "idle" && status !== "error" && status !== "ended";

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, agentPartial, workerPartial]);

  // Real risk from the backend tool result (Phase 5). LOW until first result.
  type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  const RISK_LEVELS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
  const risk: RiskLevel = RISK_LEVELS.includes(
    (incidentContext?.severity ?? "LOW") as RiskLevel
  )
    ? (incidentContext?.severity as RiskLevel)
    : "LOW";
  const isCritical = incidentContext?.severity === "CRITICAL";

  return (
    <div className="min-h-screen bg-[#080c14] text-white flex flex-col">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800/50">
        <div className="flex items-center gap-3">
          {/* SENTINEL logo mark */}
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 rounded-full border-2 border-cyan-500/60 animate-ping opacity-40" />
            <div className="relative w-8 h-8 rounded-full border-2 border-cyan-400 bg-cyan-950/50 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-cyan-400" />
            </div>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-[0.2em] text-white">SENTINEL</h1>
            <p className="text-xs text-slate-500 tracking-wider">
              SAFETY INTELLIGENCE
            </p>
          </div>
        </div>
        <StatusBadge voiceStatus={status} risk={risk} />
      </header>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-8 gap-8 max-w-2xl mx-auto w-full">

        {/* Idle state — big start button */}
        {status === "idle" && (
          <div className="flex flex-col items-center gap-8 text-center">
            <div className="space-y-2">
              <p className="text-slate-400 text-sm tracking-wider">
                WORKPLACE SAFETY ASSISTANT
              </p>
              <p className="text-2xl font-light text-slate-200">
                Tell SENTINEL what&apos;s happening
              </p>
              <p className="text-slate-500 text-sm max-w-sm">
                SENTINEL investigates safety incidents in real time.
                Say what you see — no forms, no menus.
              </p>
            </div>

            <button
              id="start-sentinel-btn"
              onClick={startSession}
              className="relative group"
            >
              {/* Outer pulse ring */}
              <div className="absolute inset-0 rounded-full bg-cyan-500/20 scale-110 group-hover:scale-125 transition-transform duration-300" />
              {/* Main button */}
              <div className="relative w-32 h-32 rounded-full border-2 border-cyan-500/70 bg-cyan-950/30 
                hover:bg-cyan-900/40 hover:border-cyan-400 transition-all duration-200
                flex flex-col items-center justify-center gap-2 cursor-pointer">
                <svg className="w-8 h-8 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                </svg>
                <span className="text-xs font-semibold text-cyan-300 tracking-widest">SPEAK</span>
              </div>
            </button>

            <p className="text-slate-600 text-xs">
              Microphone access required
            </p>
          </div>
        )}

        {/* Connecting state */}
        {status === "connecting" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full border-2 border-cyan-500/40 border-t-cyan-400 animate-spin" />
            <p className="text-cyan-400 text-sm font-mono tracking-widest">
              CONNECTING TO SENTINEL...
            </p>
          </div>
        )}

        {/* Active session */}
        {isActive && (
          <div className="w-full flex flex-col gap-6">
            {/* CRITICAL alert (Phase 5) */}
            {isCritical && incidentContext && (
              <CriticalAlertPanel context={incidentContext} />
            )}
            {/* Waveform + prompt */}
            <div className="flex flex-col items-center gap-4">
              <div className="text-slate-400 text-sm font-mono tracking-wider">
                {status === "listening" ? "● LISTENING" : status === "speaking" ? "◈ RESPONDING" : ""}
              </div>
              <Waveform
                level={audioLevel}
                active={status === "listening"}
                color={status === "speaking" ? "#a78bfa" : "#22d3ee"}
              />
            </div>

            {/* Transcript feed */}
            <div className="w-full bg-slate-900/50 rounded-xl border border-slate-800/60 p-4 space-y-3 max-h-80 overflow-y-auto">
              {transcript.length === 0 && !agentPartial && !workerPartial && (
                <p className="text-slate-600 text-sm text-center py-4">
                  Conversation will appear here...
                </p>
              )}

              {transcript.map((entry: TranscriptEntry) => (
                <TranscriptLine key={entry.id} entry={entry} />
              ))}

              {/* Streaming worker text */}
              {workerPartial && (
                <div className="flex gap-3 items-start opacity-70">
                  <span className="text-xs font-mono text-cyan-600 mt-0.5 shrink-0">YOU</span>
                  <p className="text-slate-300 text-sm leading-relaxed">{workerPartial}<span className="animate-pulse">▊</span></p>
                </div>
              )}

              {/* Streaming agent text */}
              {agentPartial && (
                <div className="flex gap-3 items-start opacity-80">
                  <span className="text-xs font-mono text-violet-400 mt-0.5 shrink-0">SNT</span>
                  <p className="text-slate-100 text-sm font-medium leading-relaxed">{agentPartial}<span className="animate-pulse">▊</span></p>
                </div>
              )}

              <div ref={transcriptEndRef} />
            </div>

            {/* End session button */}
            <div className="flex justify-center">
              <button
                id="end-session-btn"
                onClick={endSession}
                className="px-6 py-2 rounded-lg border border-slate-700 text-slate-400 
                  hover:border-red-800 hover:text-red-400 text-xs font-mono tracking-wider 
                  transition-colors duration-150"
              >
                END SESSION
              </button>
            </div>
          </div>
        )}

        {/* Error state */}
        {status === "error" && (
          <div className="flex flex-col items-center gap-6 text-center max-w-md">
            <div className="w-12 h-12 rounded-full bg-red-950/50 border border-red-800 flex items-center justify-center">
              <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
            </div>
            <div className="space-y-2">
              <p className="text-red-400 font-semibold">Connection Failed</p>
              <p className="text-slate-400 text-sm">{error}</p>
            </div>
            <button
              id="retry-btn"
              onClick={startSession}
              className="px-6 py-2 rounded-lg border border-cyan-800 text-cyan-400 
                hover:bg-cyan-950/30 text-sm font-mono tracking-wider transition-colors"
            >
              RETRY CONNECTION
            </button>
          </div>
        )}
      </main>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="px-6 py-3 border-t border-slate-800/40 flex items-center justify-between text-xs text-slate-700">
        <span>SENTINEL v0.1 — Prototype</span>
        <span>AssemblyAI Voice Agent</span>
      </footer>
    </div>
  );
}

function TranscriptLine({ entry }: { entry: TranscriptEntry }) {
  const isWorker = entry.role === "worker";
  return (
    <div className={`flex gap-3 items-start ${isWorker ? "" : "bg-slate-800/30 rounded-lg px-3 py-2"}`}>
      <span className={`text-xs font-mono mt-0.5 shrink-0 ${isWorker ? "text-cyan-600" : "text-violet-400"}`}>
        {isWorker ? "YOU" : "SNT"}
      </span>
      <p className={`text-sm leading-relaxed ${isWorker ? "text-slate-400" : "text-slate-100 font-medium"}`}>
        {entry.text}
      </p>
    </div>
  );
}
