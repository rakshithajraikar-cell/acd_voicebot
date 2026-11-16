import { z } from "zod";
import { ErrorEnvelopeSchema, EventEnvelopeSchema, type ErrorEnvelope } from "./common.js";

/**
 * Word-level timing and confidence breakdown.
 *
 * @field word - The transcribed individual word or token
 * @field start_time_ms - Start offset in milliseconds from stream origin (>= 0)
 * @field end_time_ms - End offset in milliseconds (>= start_time_ms)
 * @field confidence - Confidence score in range [0.0, 1.0]
 */
export const TranscriptWordSchema = z
  .object({
    word: z.string().min(1, "word cannot be empty"),
    start_time_ms: z
      .number()
      .int("start_time_ms must be an integer")
      .nonnegative("start_time_ms cannot be negative"),
    end_time_ms: z
      .number()
      .int("end_time_ms must be an integer")
      .nonnegative("end_time_ms cannot be negative"),
    confidence: z
      .number()
      .min(0.0, "confidence cannot be less than 0.0")
      .max(1.0, "confidence cannot exceed 1.0"),
  })
  .refine((data) => data.end_time_ms >= data.start_time_ms, {
    message: "end_time_ms must be greater than or equal to start_time_ms",
    path: ["end_time_ms"],
  });
export type TranscriptWord = z.infer<typeof TranscriptWordSchema>;

/**
 * TranscriptSegment Schema
 *
 * Fundamental unit of transcribed speech produced by speech-to-text providers.
 *
 * @field segment_id - Unique string identifier for this segment
 * @field sequence_number - Monotonically increasing sequence ID (>= 0) for segment ordering
 * @field start_time_ms - Beginning of spoken segment in milliseconds relative to session start (>= 0)
 * @field end_time_ms - End of spoken segment in milliseconds relative to session start (>= start_time_ms)
 * @field text - Transcribed plain text content
 * @field confidence - Provider confidence metric between 0.0 (lowest) and 1.0 (highest)
 * @field is_final - Boolean flag: false = partial/interim guess; true = finalized, immutable segment
 * @field language - BCP-47 or ISO language tag (e.g. 'en-US', 'en', 'es-ES')
 * @field words - Optional list of detailed word-level timings
 * @field error - Optional associated error envelope if partial failure occurred
 */
export const TranscriptSegmentSchema = z
  .object({
    segment_id: z.string().min(1, "segment_id cannot be empty"),
    sequence_number: z
      .number()
      .int("sequence_number must be an integer")
      .nonnegative("sequence_number cannot be negative"),
    start_time_ms: z
      .number()
      .int("start_time_ms must be an integer")
      .nonnegative("start_time_ms must be a non-negative integer (units: milliseconds)"),
    end_time_ms: z
      .number()
      .int("end_time_ms must be an integer")
      .nonnegative("end_time_ms must be a non-negative integer (units: milliseconds)"),
    text: z.string({ required_error: "text is required" }),
    confidence: z
      .number()
      .min(0.0, "confidence must be >= 0.0")
      .max(1.0, "confidence must be <= 1.0"),
    is_final: z.boolean({ required_error: "is_final is required" }),
    language: z
      .string()
      .min(2, "language tag must be at least 2 characters")
      .default("en-US"),
    words: z.array(TranscriptWordSchema).optional(),
    error: ErrorEnvelopeSchema.optional(),
  })
  .refine((data) => data.end_time_ms >= data.start_time_ms, {
    message: "end_time_ms cannot be earlier than start_time_ms",
    path: ["end_time_ms"],
  })
  .refine(
    (data) => {
      // Finalized segments must contain at least non-empty trimmed text unless accompanied by an error
      if (data.is_final && !data.error) {
        return data.text.trim().length > 0;
      }
      return true;
    },
    {
      message: "Finalized transcript segments must contain non-empty text",
      path: ["text"],
    }
  );
export type TranscriptSegment = z.infer<typeof TranscriptSegmentSchema>;
export type TranscriptSegmentInput = z.input<typeof TranscriptSegmentSchema>;

/**
 * Standard Transcript Event Types
 */
export const TranscriptEventTypeEnum = z.enum([
  "transcript.interim",
  "transcript.final",
  "transcript.revised",
  "transcript.error",
]);
export type TranscriptEventType = z.infer<typeof TranscriptEventTypeEnum>;

/**
 * TranscriptEvent Payload Schema
 *
 * @field segment - The transcribed segment (required for interim/final/revised events)
 * @field error - Error envelope if event represents an error state
 * @field provider_name - Name of speech provider producing the event (e.g. 'deterministic-fake')
 * @field latency_ms - Processing latency in milliseconds for observability
 */
export const TranscriptPayloadSchema = z
  .object({
    segment: TranscriptSegmentSchema.optional(),
    error: ErrorEnvelopeSchema.optional(),
    provider_name: z.string().min(1).default("deterministic-fake"),
    latency_ms: z.number().int().nonnegative().optional(),
  })
  .refine(
    (data) => {
      // Must contain either a segment or an error
      return !!data.segment || !!data.error;
    },
    {
      message: "Transcript payload must include either a segment or an error",
      path: ["segment"],
    }
  );
export type TranscriptPayload = z.infer<typeof TranscriptPayloadSchema>;

/**
 * TranscriptEvent Schema
 *
 * Concrete specialization of EventEnvelope for the Speech-To-Text pipeline.
 *
 * @field event_id - Unique event identifier
 * @field event_type - One of 'transcript.interim', 'transcript.final', 'transcript.revised', 'transcript.error'
 * @field schema_version - Always '1.0.0'
 * @field session_id - Associated voice session
 * @field correlation_id - Tracing ID for audio chunk to transcript event propagation
 * @field timestamp - ISO 8601 UTC timestamp
 * @field producer - Module identifier: 'w2-speech-to-text'
 * @field payload - Strongly validated TranscriptPayload
 */
export const TranscriptEventSchema = EventEnvelopeSchema.extend({
  event_type: TranscriptEventTypeEnum,
  producer: z.literal("w2-speech-to-text"),
  payload: TranscriptPayloadSchema,
});
export type TranscriptEvent = z.infer<typeof TranscriptEventSchema>;

/**
 * Audio Chunk Input Schema (represents audio delivered by W1 Audio)
 *
 * @field chunk_id - Unique chunk identifier
 * @field sequence_number - Incremental chunk index from audio capture
 * @field session_id - Voicebot session ID
 * @field correlation_id - Request/trace correlation ID
 * @field timestamp_ms - Time offset in milliseconds of chunk start
 * @field duration_ms - Length of chunk in milliseconds
 * @field sample_rate - Audio sample rate (e.g. 16000 Hz)
 * @field channels - Number of audio channels (e.g. 1 for mono)
 * @field data - Base64 encoded or binary byte buffer of PCM/audio data
 * @field is_speech - VAD detection flag from W1
 */
export const AudioChunkInputSchema = z.object({
  chunk_id: z.string().min(1, "chunk_id is required"),
  sequence_number: z.number().int().nonnegative("sequence_number cannot be negative"),
  session_id: z.string().min(1, "session_id is required"),
  correlation_id: z.string().min(1, "correlation_id is required"),
  timestamp_ms: z.number().int().nonnegative("timestamp_ms must be >= 0"),
  duration_ms: z.number().int().positive("duration_ms must be > 0"),
  sample_rate: z.number().int().refine((val) => [8000, 16000, 44100, 48000].includes(val), {
    message: "sample_rate must be 8000, 16000, 44100, or 48000 Hz",
  }),
  channels: z.number().int().min(1).max(2, "channels must be 1 (mono) or 2 (stereo)"),
  data: z.union([
    z.string().min(1, "Audio data cannot be empty"),
    z.custom<Uint8Array>((val) => val instanceof Uint8Array, "Must be a Uint8Array"),
  ]),
  is_speech: z.boolean().default(true),
});
export type AudioChunkInput = z.infer<typeof AudioChunkInputSchema>;

/**
 * Helper Validation Result Type
 */
export type ValidationResult<T> =
  | { success: true; data: T; error?: never }
  | { success: false; data?: never; error: ErrorEnvelope };

/**
 * Validates a TranscriptSegment payload with detailed user-safe error reporting.
 */
export function validateTranscriptSegment(
  payload: unknown,
  correlationId: string = "unknown-correlation-id"
): ValidationResult<TranscriptSegment> {
  const result = TranscriptSegmentSchema.safeParse(payload);
  if (result.success) {
    return { success: true, data: result.data };
  }

  const issues = result.error.issues
    .map((issue) => `[${issue.path.join(".") || "root"}]: ${issue.message}`)
    .join("; ");

  return {
    success: false,
    error: {
      code: "INVALID_SEGMENT_PAYLOAD",
      message_safe_for_user: `Transcript segment failed schema validation: ${issues}`,
      retryable: false,
      correlation_id: correlationId,
      details_redacted: {
        issue_count: result.error.issues.length,
        paths: result.error.issues.map((i) => i.path.join(".")),
      },
    },
  };
}

/**
 * Validates a TranscriptEvent payload with detailed user-safe error reporting.
 */
export function validateTranscriptEvent(
  payload: unknown,
  correlationId: string = "unknown-correlation-id"
): ValidationResult<TranscriptEvent> {
  const result = TranscriptEventSchema.safeParse(payload);
  if (result.success) {
    return { success: true, data: result.data };
  }

  const issues = result.error.issues
    .map((issue) => `[${issue.path.join(".") || "root"}]: ${issue.message}`)
    .join("; ");

  return {
    success: false,
    error: {
      code: "INVALID_EVENT_PAYLOAD",
      message_safe_for_user: `Transcript event failed schema validation: ${issues}`,
      retryable: false,
      correlation_id: correlationId,
      details_redacted: {
        issue_count: result.error.issues.length,
        paths: result.error.issues.map((i) => i.path.join(".")),
      },
    },
  };
}
