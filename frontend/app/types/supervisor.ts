export type IncidentSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IncidentLifecycleStatus = "INVESTIGATING" | "CRITICAL" | "VERIFYING_SAFETY" | "ESCALATED";

export interface AuditEvent {
  incident_id: string;
  event_type: string;
  source: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface SituationFacts {
  session_id: string;
  equipment?: string | null;
  location?: string | null;
  machine_running?: boolean | null;
  people_nearby?: number | null;
  abnormal_vibration?: boolean | null;
  vibration_increasing?: boolean | null;
  sparks?: boolean | null;
  smoke?: boolean | null;
  worker_safe?: boolean | null;
  observations?: string[];
}

export interface RiskDetails {
  severity: IncidentSeverity;
  reasons: string[];
  immediate_actions: string[];
}

export interface IncidentDetail {
  session_id: string;
  incident_id: string;
  incident_status: IncidentLifecycleStatus;
  severity: IncidentSeverity;
  worker_safe: boolean | null;
  supervisor_notified: boolean;
  supervisor_notification_status: string;
  escalation_status: string;
  situation: SituationFacts;
  risk: RiskDetails;
  audit_events: AuditEvent[];
}
