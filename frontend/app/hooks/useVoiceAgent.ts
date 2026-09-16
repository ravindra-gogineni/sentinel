"use client";

/**
 * SENTINEL — useVoiceAgent hook
 *
 * Manages the full AssemblyAI Voice Agent session:
 *   - Mints token from SENTINEL backend (server-side key, never exposed to browser)
 *   - Opens WebSocket to AssemblyAI wss://agents.assemblyai.com/v1/ws?token=<token>
 *   - Sends session.update with agent_id to bind the stored SENTINEL agent
 *   - Captures microphone audio (PCM16, 24kHz) via AudioWorklet
 *   - Streams input.audio to AssemblyAI
 *   - Plays back reply.audio chunks with scheduled timing
 *   - Handles reply.done { status: "interrupted" } (barge-in: flushes playback)
 *   - Streams transcript.user.delta (full text so far, NOT additive chunks)
 *   - Streams transcript.agent.delta (incremental word tokens, IS additive)
 *
 * API reference verified against:
 *   https://www.assemblyai.com/docs/voice-agents/voice-agent-api/events-reference
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  TranscriptEntry,
  VoiceStatus,
  IncidentContext,
  ToolResultBody,
} from "@/app/types/voice";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const AAI_WS_URL = "wss://agents.assemblyai.com/v1/ws";
const TARGET_SAMPLE_RATE = 24000;

// Fetch timeout for the situation backend call.
// MUST stay below the agent's tool timeout_seconds (15s) so the agent never
// hits its own timeout while we are still waiting on our fetch.
const TOOL_FETCH_TIMEOUT_MS = 8000;
const HEALTH_CHECK_TIMEOUT_MS = 3000;

interface PendingToolResult {
  call_id: string;
  result: unknown;
  is_error: boolean;
}

interface UseVoiceAgentReturn {
  status: VoiceStatus;
  transcript: TranscriptEntry[];
  /** Current partial text (SENTINEL is speaking, streaming in) */
  agentPartial: string;
  /** Current partial text (worker is speaking, streaming in) */
  workerPartial: string;
  error: string | null;
  /** 0–1 audio level for waveform animation */
  audioLevel: number;
  /** Latest backend incident context (severity, critical alert, escalation) */
  incidentContext: IncidentContext | null;
  startSession: () => Promise<void>;
  endSession: () => void;
}

export function useVoiceAgent(): UseVoiceAgentReturn {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [agentPartial, setAgentPartial] = useState("");
  const [workerPartial, setWorkerPartial] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [incidentContext, setIncidentContext] = useState<IncidentContext | null>(
    null
  );

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const playbackTimeRef = useRef<number>(0);
  const activeRef = useRef(false);
  const animFrameRef = useRef<number>(0);

  // Phase 3: Tool orchestration refs
  const sessionIdRef = useRef<string | null>(null);
  const lastEventRef = useRef<string | null>(null);

  // Phase 4.1: Tool-result lifecycle. Per AssemblyAI client-side-tools docs,
  // tool.result MUST be sent only when reply.done is the latest event received.
  // We ACCUMULATE results here on tool.call, then DRAIN inside reply.done.
  const pendingToolsRef = useRef<PendingToolResult[]>([]);
  // call_ids for in-flight fetches that were discarded on an interruption.
  // If their result lands after the interruption, it is dropped so a stale
  // result from a just-ended (interrupted) reply is never delivered.
  const discardedCallIdsRef = useRef<Set<string>>(new Set());

  // ── Cleanup ────────────────────────────────────────────────────────────
  const cleanup = useCallback(() => {
    activeRef.current = false;
    cancelAnimationFrame(animFrameRef.current);

    // Phase 4.1: clear any pending tool results on teardown so no stale
    // callbacks remain after the session ends.
    pendingToolsRef.current = [];
    discardedCallIdsRef.current.clear();

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    workletRef.current?.disconnect();
    workletRef.current = null;

    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;
    playbackTimeRef.current = 0;
  }, []);

  // ── End session cleanly (sends session.end first) ─────────────────────
  const endSession = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "session.end" }));
      // cleanup() happens in the session.ended handler
    } else {
      cleanup();
      setStatus("idle");
    }
  }, [cleanup]);



  // ── Schedule a PCM16 audio chunk for playback ─────────────────────────
  // reply.audio carries base64-encoded raw PCM16 mono 24kHz
  const scheduleAudioChunk = useCallback((base64Data: string) => {
    const ctx = audioCtxRef.current;
    if (!ctx) return;

    try {
      const raw = atob(base64Data);
      const byteCount = raw.length;
      const sampleCount = Math.floor(byteCount / 2); // 2 bytes per Int16 sample
      const pcm16 = new Int16Array(sampleCount);
      for (let i = 0; i < sampleCount; i++) {
        // Little-endian Int16
        pcm16[i] =
          (raw.charCodeAt(i * 2) & 0xff) |
          ((raw.charCodeAt(i * 2 + 1) & 0xff) << 8);
      }
      const float32 = new Float32Array(sampleCount);
      for (let i = 0; i < sampleCount; i++) {
        float32[i] = pcm16[i] / 32768;
      }

      const buffer = ctx.createBuffer(1, float32.length, TARGET_SAMPLE_RATE);
      buffer.getChannelData(0).set(float32);

      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(ctx.destination);

      const now = ctx.currentTime;
      playbackTimeRef.current = Math.max(playbackTimeRef.current, now);
      src.start(playbackTimeRef.current);
      playbackTimeRef.current += buffer.duration;
    } catch (err) {
      console.error("[SENTINEL] Audio playback error:", err);
    }
  }, []);

  // ── Flush pending tool results ───────────────────────────────────────
  // AssemblyAI client-side-tools lifecycle:
  //   tool.call → accumulate result → reply.done → drain (send tool.result)
  // Only send when reply.done is the latest event received (see docs).
  // Called from the tool.call completion AND from the reply.done handler.
  const flushPendingTools = useCallback(() => {
    if (lastEventRef.current !== "reply.done") return;
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const pending = pendingToolsRef.current;
    if (pending.length === 0) return;
    for (const t of pending) {
      console.log(
        "[SENTINEL] tool.result → sending",
        { call_id: t.call_id, is_error: t.is_error },
        "wsState=OPEN"
      );
      ws.send(
        JSON.stringify({
          type: "tool.result",
          call_id: t.call_id,
          result: JSON.stringify(t.result),
          is_error: t.is_error,
        })
      );
    }
    pendingToolsRef.current = [];
  }, []);

  // ── Surface the backend's structured result in the UI (Phase 5) ───────
  // Additive only: called on the SUCCESS path of a tool result. Never mutates
  // the queue/flush/discard lifecycle.
  const applyResult = useCallback((body: unknown) => {
    if (!body || typeof body !== "object" || Array.isArray(body)) return;
    const result = body as ToolResultBody;
    if (result.status === "error") return;
    setIncidentContext({
      severity: result.severity ?? "LOW",
      immediate_actions: result.immediate_actions ?? [],
      incident_status: result.incident_status ?? null,
      worker_safe: result.worker_safe ?? null,
      supervisor_notified: result.supervisor_notified ?? null,
      supervisor_notification_status: result.supervisor_notification_status ?? null,
      escalation_status: result.escalation_status ?? null,
    });
  }, []);

  // ── Relay a tool.call to the SENTINEL backend ─────────────────────────
  // Phase 4.1 lifecycle is preserved EXACTLY: the result is queued here on
  // tool.call, and only drained by flushPendingTools() inside reply.done.
  // Shared by BOTH tools (update_situation + verify_worker_safety) so the
  // reliability behavior (timeout, interruption-discard, structured errors)
  // can never diverge.
  const relayToolCall = useCallback(
    (call_id: string, toolName: string, endpoint: string, rawArguments: unknown) => {
      const session_id = sessionIdRef.current;

      // Guard: no session ID → return a structured error result so the
      // tool call is never left permanently unresolved.
      if (!session_id) {
        console.error("[SENTINEL] tool.call: missing session_id");
        pendingToolsRef.current.push({
          call_id,
          result: { status: "error", error: "missing_session_id", call_id },
          is_error: true,
        });
        // lastEvent may already be "reply.done" when a tool returns late
        flushPendingTools();
        return;
      }

      // Reserve a slot so this call is resolved exactly once.
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TOOL_FETCH_TIMEOUT_MS);

      // Queue a result, unless this call was discarded by an
      // interruption (stale result from an interrupted reply is dropped).
      const queueResult = (result: unknown, is_error: boolean) => {
        if (discardedCallIdsRef.current.has(call_id)) {
          console.warn(
            "[SENTINEL] dropping result for discarded call",
            { call_id }
          );
          discardedCallIdsRef.current.delete(call_id);
          return;
        }
        pendingToolsRef.current.push({ call_id, result, is_error });
        if (!is_error) applyResult(result);
      };

      console.log(
        "[SENTINEL] backend request started",
        `POST ${BACKEND_URL}${endpoint}/${session_id}`,
        { call_id, tool_name: toolName }
      );

      fetch(`${BACKEND_URL}${endpoint}/${session_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rawArguments),
        signal: controller.signal,
      })
        .then(async (res) => {
          console.log("[SENTINEL] backend response status", res.status);
          const text = await res.text();
          let body: unknown;
          try {
            body = JSON.parse(text);
          } catch {
            console.error(
              "[SENTINEL] backend response was not valid JSON",
              text.slice(0, 300)
            );
            queueResult(
              { status: "error", error: "invalid_backend_response", call_id },
              true
            );
            return;
          }
          if (!res.ok) {
            queueResult(
              { status: "error", error: `backend_http_${res.status}`, call_id },
              true
            );
            return;
          }
          console.log("[SENTINEL] backend response body", body);
          queueResult(body, false);
        })
        .catch((err) => {
          const aborted =
            err instanceof DOMException && err.name === "AbortError";
          console.error(
            "[SENTINEL] backend request error",
            aborted ? "timeout" : err
          );
          queueResult(
            {
              status: "error",
              error: aborted ? "backend_timeout" : "backend_error",
              call_id,
            },
            true
          );
        })
        .finally(() => {
          clearTimeout(timer);
          // Queue updated — flush if we are idle on reply.done.
          flushPendingTools();
        });
    },
    [flushPendingTools, applyResult]
  );

  // ── Handle incoming WebSocket messages ───────────────────────────────
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let msg: Record<string, any>;
      try {
        msg = JSON.parse(event.data as string);
      } catch {
        console.warn("[SENTINEL] Non-JSON WS message:", event.data);
        return;
      }

      // Dev logging — skip noisy reply.audio
      if (process.env.NODE_ENV === "development" && msg.type !== "reply.audio") {
        console.log("[AAI →]", msg.type, msg);
      }

      switch (msg.type as string) {

        // ── Session lifecycle ──────────────────────────────────────────
        case "session.ready": {
          console.log("[SENTINEL] Session ready. ID:", msg.session_id);
          sessionIdRef.current = msg.session_id;
          activeRef.current = true;
          setStatus("listening");
          break;
        }

        case "session.updated": {
          // Server echoes config after session.update — no action needed
          break;
        }

        case "session.error": {
          // Codes: UNAUTHORIZED, FORBIDDEN, agent_not_found, invalid_format, etc.
          const code: string = msg.code ?? "unknown";
          const message: string = msg.message ?? "Unknown session error";
          console.error("[SENTINEL] Session error:", code, message);
          setError(`${code}: ${message}`);
          setStatus("error");
          cleanup();
          break;
        }

        case "session.ended": {
          console.log(
            "[SENTINEL] Session ended.",
            `Duration: ${msg.session_duration_seconds?.toFixed(1)}s`
          );
          setStatus("idle");
          cleanup();
          break;
        }

        // ── User speech ────────────────────────────────────────────────
        case "input.speech.started": {
          // User has started speaking — clear any accumulated partial
          lastEventRef.current = "input.speech.started";
          setWorkerPartial("");
          break;
        }

        case "input.speech.stopped": {
          // User finished — partial becomes final via transcript.user
          break;
        }

        case "transcript.user.delta": {
          // IMPORTANT: `text` is the FULL transcript so far for this item_id,
          // NOT an incremental chunk. Replace, do not append.
          // Verified from docs: "text is the full transcript so far, not an incremental chunk"
          const fullText: string = msg.text ?? "";
          setWorkerPartial(fullText);
          break;
        }

        case "transcript.user": {
          // Final utterance — commit to transcript history
          const text: string = msg.text ?? "";
          if (text.trim()) {
            const entry: TranscriptEntry = {
              id: `worker-${msg.item_id ?? Date.now()}`,
              role: "worker",
              text,
              timestamp: new Date(),
            };
            setTranscript((prev) => [...prev, entry]);
          }
          setWorkerPartial("");
          break;
        }

        // ── Agent reply ────────────────────────────────────────────────
        case "reply.started": {
          lastEventRef.current = "reply.started";
          setStatus("speaking");
          setAgentPartial(""); // fresh reply — reset partial
          break;
        }

        case "reply.audio": {
          // PCM16 base64 chunk — schedule for playback immediately
          if (msg.data) {
            scheduleAudioChunk(msg.data as string);
          }
          break;
        }

        case "transcript.agent.delta": {
          // IMPORTANT: `delta` is an incremental WORD token — IS additive.
          // Verified from docs: "The next word (or token) of the agent's speech"
          const word: string = msg.delta ?? "";
          setAgentPartial((prev) =>
            prev ? prev + " " + word : word
          );
          break;
        }

        case "transcript.agent": {
          // Full agent reply — commit to transcript history
          const text: string = msg.text ?? "";
          if (text.trim()) {
            const entry: TranscriptEntry = {
              id: `sentinel-${msg.item_id ?? Date.now()}`,
              role: "sentinel",
              text,
              timestamp: new Date(),
            };
            setTranscript((prev) => [...prev, entry]);
          }
          setAgentPartial("");
          break;
        }

        case "reply.done": {
          lastEventRef.current = "reply.done";
          // status: "completed" | "interrupted"
          if (msg.status === "interrupted") {
            // Barge-in: flush the playback buffer so stale audio doesn't play
            playbackTimeRef.current = audioCtxRef.current?.currentTime ?? 0;
            setAgentPartial("");
            // Documented lifecycle: on interruption, DISCARD any pending
            // tool.result accumulators from the just-ended reply. This prevents
            // stale/duplicate results and keeps the session from deadlocking.
            if (pendingToolsRef.current.length > 0) {
              console.log(
                "[SENTINEL] reply.done interrupted — discarding pending tool results",
                pendingToolsRef.current.map((t) => t.call_id)
              );
              for (const t of pendingToolsRef.current) {
                discardedCallIdsRef.current.add(t.call_id);
              }
              pendingToolsRef.current = [];
            }
          } else {
            // Completed reply → drain any pending tool results now.
            flushPendingTools();
          }
          setStatus("listening");
          break;
        }

        // ── Tool calls (Phase 3 + 4.1 reliability) ──────────────────
        case "tool.call": {
          console.log("[SENTINEL] tool.call received", {
            call_id: msg.call_id,
            name: msg.name,
            arguments: msg.arguments,
            session_id: sessionIdRef.current,
          });
          // Phase 5: two structured tools, relayed through the SAME Phase 4.1
          // queue/flush/discard mechanism (relayToolCall). The backend is
          // authoritative for both.
          if (msg.name === "update_situation") {
            relayToolCall(msg.call_id, "update_situation", "/api/situation", msg.arguments);
          } else if (msg.name === "verify_worker_safety") {
            relayToolCall(msg.call_id, "verify_worker_safety", "/api/verify", msg.arguments);
          } else if (msg.name === "search_factory_knowledge") {
            relayToolCall(msg.call_id, "search_factory_knowledge", "/api/knowledge/search", msg.arguments);
          } else {
            // Unknown tool — resolve it as an error so the agent never hangs.
            console.warn("[SENTINEL] unknown tool.call", msg.name);
            pendingToolsRef.current.push({
              call_id: msg.call_id,
              result: { status: "error", error: "unknown_tool", call_id: msg.call_id },
              is_error: true,
            });
            flushPendingTools();
          }
          break;
        }

        default: {
          // Unknown event — log and ignore
          if (msg.type) {
            console.log("[SENTINEL] Unhandled event:", msg.type);
          }
          break;
        }
      }
    },
    [scheduleAudioChunk, cleanup, flushPendingTools, relayToolCall]
  );

  // ── Start a voice session ─────────────────────────────────────────────
  const startSession = useCallback(async () => {
    if (activeRef.current) return;

    setStatus("connecting");
    setError(null);
    setTranscript([]);
    setAgentPartial("");
    setWorkerPartial("");
    setIncidentContext(null);

    try {
      // ── Step 1: Backend health check (single, no retry loop) ───────
      // If FastAPI is unavailable, surface a clear user-facing error rather
      // than failing later at token mint. Not polled repeatedly.
      let healthOk = false;
      try {
        const hc = await fetch(`${BACKEND_URL}/health`, {
          signal: AbortSignal.timeout(HEALTH_CHECK_TIMEOUT_MS),
        });
        healthOk = hc.ok;
      } catch {
        healthOk = false;
      }
      if (!healthOk) {
        throw new Error(
          "Backend not reachable. Start it with: cd backend && python -m uvicorn app.main:app --reload --port 8000"
        );
      }

      // ── Step 2: Mint session token from backend ────────────────────
      // The backend holds the AssemblyAI API key and returns a short-lived
      // single-use token. The API key NEVER touches the browser.
      const resp = await fetch(`${BACKEND_URL}/api/token`);
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(
          (data as { detail?: string }).detail ??
            `Backend error: HTTP ${resp.status}`
        );
      }
      const { token, agent_id } = (await resp.json()) as {
        token: string;
        agent_id: string;
      };
      console.log("[SENTINEL] Token minted. Agent:", agent_id);

      // ── Step 3: Set up AudioContext for capture + playback ─────────
      // Use browser's native rate + resample in AudioWorklet.
      // This handles Firefox (would lose echo cancellation at forced 24kHz)
      // and Safari (ignores sampleRate option entirely).
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      playbackTimeRef.current = audioCtx.currentTime;

      await audioCtx.audioWorklet.addModule("/pcm-processor.js");

      // ── Step 4: Open microphone with echo cancellation ─────────────
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,   // CRITICAL: prevents agent TTS from being re-captured
          noiseSuppression: false,  // server-side suppression is better quality
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const source = audioCtx.createMediaStreamSource(stream);

      // AudioWorklet resamples from browser native rate → 24kHz
      const worklet = new AudioWorkletNode(audioCtx, "pcm-processor", {
        processorOptions: {
          inputSampleRate: audioCtx.sampleRate,
          targetSampleRate: TARGET_SAMPLE_RATE,
        },
      });
      workletRef.current = worklet;

      // Analyser for waveform level meter
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.7;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      source.connect(analyser);
      source.connect(worklet);
      // Worklet must be connected to destination to stay alive (WebAudio spec)
      worklet.connect(audioCtx.destination);

      // Poll analyser for audio level (drives waveform animation)
      const pollLevel = () => {
        if (!activeRef.current) return;
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length / 128; // 0–1
        setAudioLevel(avg);
        animFrameRef.current = requestAnimationFrame(pollLevel);
      };
      animFrameRef.current = requestAnimationFrame(pollLevel);

      // ── Step 5: Connect to AssemblyAI Voice Agent WebSocket ────────
      // Token in query param — no Authorization header needed in browser
      const wsUrl = new URL(AAI_WS_URL);
      wsUrl.searchParams.set("token", token);
      const ws = new WebSocket(wsUrl.toString());
      wsRef.current = ws;

      ws.addEventListener("open", () => {
        console.log("[SENTINEL] WebSocket open — sending session.update");
        // Bind to the stored SENTINEL agent by ID. The tool is now configured on the stored agent.
        ws.send(
          JSON.stringify({
            type: "session.update",
            session: { agent_id }
          })
        );
      });

      ws.addEventListener("message", handleMessage);

      ws.addEventListener("error", () => {
        // Note: browser WebSocket error events carry no useful detail
        // Real info comes from the close event or session.error
        console.error("[SENTINEL] WebSocket error event");
      });

      ws.addEventListener("close", (e) => {
        console.log("[SENTINEL] WebSocket closed:", e.code, e.reason);
        if (activeRef.current) {
          // Unexpected close without session.ended — network drop or auth failure
          // Pre-handshake failures (UNAUTHORIZED) surface here with code 1006 in browsers
          const msg =
            e.code === 1008
              ? "Auth failed — check API key"
              : e.code === 1006
              ? "Connection failed — check API key or network"
              : `Connection closed (${e.code})`;
          setError(msg);
          setStatus("error");
          cleanup();
        }
      });

      // ── Step 6: Stream mic audio after session.ready ────────────────
      // We don't send audio until session.ready fires (activeRef.current = true)
      worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        if (activeRef.current && ws.readyState === WebSocket.OPEN) {
          // Convert PCM16 ArrayBuffer → base64 string for JSON transport
          const bytes = new Uint8Array(e.data);
          let binary = "";
          // Use chunked approach to avoid call stack limits on large buffers
          for (let i = 0; i < bytes.length; i += 1024) {
            binary += String.fromCharCode(...bytes.slice(i, i + 1024));
          }
          ws.send(
            JSON.stringify({ type: "input.audio", audio: btoa(binary) })
          );
        }
      };
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to start session";
      console.error("[SENTINEL] startSession error:", err);
      setError(message);
      setStatus("error");
      cleanup();
    }
  }, [handleMessage, cleanup]);

  // ── Cleanup on component unmount ──────────────────────────────────────
  useEffect(() => {
    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "session.end" }));
      }
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    status,
    transcript,
    agentPartial,
    workerPartial,
    error,
    audioLevel,
    incidentContext,
    startSession,
    endSession,
  };
}
