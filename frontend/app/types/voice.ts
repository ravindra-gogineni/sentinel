/**
 * SENTINEL — Shared TypeScript types for the voice layer.
 */

// ── AssemblyAI Voice Agent WebSocket Event Types ──────────────────────────

export type AAIEventType =
  | "session.ready"
  | "session.error"
  | "session.ended"
  | "input.speech.started"
  | "input.speech.stopped"
  | "transcript.user.delta"
  | "transcript.user"
  | "transcript.agent.delta"
  | "transcript.agent"
  | "reply.started"
  | "reply.audio"
  | "reply.done"
  | "tool.call";

export interface AAIEvent {
  type: AAIEventType;
  [key: string]: unknown;
}

export interface SessionReadyEvent extends AAIEvent {
  type: "session.ready";
  session_id: string;
}

export interface SessionErrorEvent extends AAIEvent {
  type: "session.error";
  code: string;
  message: string;
}

export interface TranscriptUserEvent extends AAIEvent {
  type: "transcript.user";
  text: string;
}

export interface TranscriptAgentEvent extends AAIEvent {
  type: "transcript.agent";
  text: string;
}

export interface TranscriptDeltaEvent extends AAIEvent {
  type: "transcript.user.delta" | "transcript.agent.delta";
  delta: string;
}

export interface ReplyAudioEvent extends AAIEvent {
  type: "reply.audio";
  data: string; // base64 PCM16
}

export interface ReplyDoneEvent extends AAIEvent {
  type: "reply.done";
  status: "completed" | "interrupted";
}

export interface ToolCallEvent extends AAIEvent {
  type: "tool.call";
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
}

// ── Voice Session State ────────────────────────────────────────────────────

export type VoiceStatus =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "interrupted"
  | "error"
  | "ended";

// ── Transcript Entry ────────────────────────────────────────────────────────

export interface TranscriptEntry {
  id: string;
  role: "worker" | "sentinel";
  text: string;
  timestamp: Date;
  delta?: string; // streaming partial text
}

// ── Incident Context (Phase 5) ──────────────────────────────────────────────

export type IncidentStatusType =
  | "INVESTIGATING"
  | "CRITICAL"
  | "VERIFYING_SAFETY"
  | "ESCALATED";

/** Populated from the backend's structured tool result (severity + incident state). */
export interface IncidentContext {
  severity: string;
  immediate_actions: string[];
  incident_status: IncidentStatusType | null;
  worker_safe: boolean | null;
  supervisor_notified: boolean | null;
  supervisor_notification_status: string | null;
  escalation_status: string | null;
}

/** Shape of a successful tool result returned by the SENTINEL backend. */
export interface ToolResultBody {
  status?: string;
  severity?: string;
  immediate_actions?: string[];
  incident_status?: IncidentStatusType;
  worker_safe?: boolean | null;
  supervisor_notified?: boolean | null;
  supervisor_notification_status?: string | null;
  escalation_status?: string | null;
  [key: string]: unknown;
}
