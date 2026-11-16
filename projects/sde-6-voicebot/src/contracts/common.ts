import { z } from "zod";

/**
 * Standard Session States across the voicebot lifecycle (Section 8)
 */
export const SessionStateEnum = z.enum([
  "created",
  "active",
  "paused",
  "stopping",
  "completed",
  "failed",
  "expired",
]);
export type SessionState = z.infer<typeof SessionStateEnum>;

/**
 * Standard Workflow States across the agentic engine (Section 8)
 */
export const WorkflowStateEnum = z.enum([
  "draft",
  "awaiting_approval",
  "running",
  "paused",
  "succeeded",
  "failed",
  "cancelled",
]);
export type WorkflowState = z.infer<typeof WorkflowStateEnum>;

/**
 * Standard Error Envelope Schema (Section 8)
 * Ensures consistent, sanitized error reporting across all modules.
 *
 * @field code - Unique machine-readable error code (e.g., 'INVALID_PAYLOAD', 'PROVIDER_TIMEOUT')
 * @field message_safe_for_user - Clean, end-user friendly message that never exposes raw internals or secrets
 * @field retryable - Boolean flag indicating if caller may retry the operation
 * @field correlation_id - Tracing ID linking error to specific request/stream
 * @field details_redacted - Redacted diagnostics map without personal/confidential payloads
 */
export const ErrorEnvelopeSchema = z.object({
  code: z
    .string()
    .min(1, "Error code cannot be empty")
    .regex(/^[A-Z0-9_]+$/, "Error code must be UPPER_SNAKE_CASE"),
  message_safe_for_user: z
    .string()
    .min(1, "message_safe_for_user must not be empty"),
  retryable: z.boolean(),
  correlation_id: z.string().min(1, "correlation_id is required"),
  details_redacted: z.record(z.string(), z.unknown()).default({}),
});
export type ErrorEnvelope = z.infer<typeof ErrorEnvelopeSchema>;

/**
 * Standard Event Envelope Schema (Section 8)
 * Every event emitted across backend, UI, and STT must conform to this envelope.
 *
 * @field event_id - Unique event identifier (UUID v4 or deterministic ID)
 * @field event_type - Categorical dot-notated event name (e.g. 'transcript.final')
 * @field schema_version - Semantic version of this contract (e.g. '1.0.0')
 * @field session_id - Voicebot active session identifier
 * @field correlation_id - Correlation identifier for end-to-end tracing
 * @field timestamp - ISO 8601 UTC timestamp of creation (e.g. '2026-10-31T10:00:00.000Z')
 * @field producer - Module emitting the event (e.g. 'w2-speech-to-text')
 * @field payload - Strongly-typed domain payload
 */
export const EventEnvelopeSchema = z.object({
  event_id: z.string().min(1, "event_id is required"),
  event_type: z.string().min(1, "event_type is required"),
  schema_version: z.string().default("1.0.0"),
  session_id: z.string().min(1, "session_id is required"),
  correlation_id: z.string().min(1, "correlation_id is required"),
  timestamp: z
    .string()
    .datetime({ message: "timestamp must be a valid ISO 8601 UTC string" }),
  producer: z.string().min(1, "producer is required"),
  payload: z.record(z.string(), z.unknown()),
});
export type EventEnvelope = z.infer<typeof EventEnvelopeSchema>;
