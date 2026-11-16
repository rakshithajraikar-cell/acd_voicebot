import { createHash } from "node:crypto";
import type {
  AudioChunkInput,
  TranscriptEvent,
  TranscriptSegment,
  TranscriptWord,
} from "../contracts/transcript.js";
import { validateTranscriptEvent } from "../contracts/transcript.js";
import type {
  SpeechToTextAdapter,
  TranscribeOptions,
  ProviderHealth,
} from "./stt-adapter.js";

export interface FakeTranscriberConfig {
  /**
   * Simulated network/processing latency in milliseconds (default: 0 for fast unit tests)
   */
  simulatedDelayMs?: number;
  /**
   * Fixed confidence to assign to generated segments (default: 0.95)
   */
  defaultConfidence?: number;
  /**
   * Optional custom dictionary mapping chunk data content strings to exact transcript phrases
   */
  customPhrases?: Record<string, string>;
}

/**
 * DeterministicFakeTranscriber
 *
 * Implements SpeechToTextAdapter without external network or API keys.
 * Guarantee: Given the exact same AudioChunkInput, it outputs byte-for-byte
 * and value-for-value identical TranscriptEvents every single execution.
 */
export class DeterministicFakeTranscriber implements SpeechToTextAdapter {
  readonly name = "deterministic-fake-transcriber";
  private isInitialized = false;
  private readonly config: Required<FakeTranscriberConfig>;
  private readonly cancelledSessions = new Set<string>();

  // Known dictionary mappings for realistic fixtures
  private static readonly DEFAULT_PHRASE_MAP: Record<string, string> = {
    academic_voicebot_system_part1: "Academic voicebot system ready.",
    ready_start_session_part2: "Start session now.",
    now_final_part3: "Awaiting your command.",
    silence_buffer: "",
  };

  constructor(config?: FakeTranscriberConfig) {
    this.config = {
      simulatedDelayMs: config?.simulatedDelayMs ?? 0,
      defaultConfidence: config?.defaultConfidence ?? 0.95,
      customPhrases: {
        ...DeterministicFakeTranscriber.DEFAULT_PHRASE_MAP,
        ...(config?.customPhrases ?? {}),
      },
    };
  }

  async initialize(config?: Record<string, unknown>): Promise<void> {
    this.isInitialized = true;
  }

  async getHealth(): Promise<ProviderHealth> {
    return {
      status: this.isInitialized ? "healthy" : "degraded",
      provider_name: this.name,
      is_mock: true,
      message: this.isInitialized
        ? "Deterministic mock transcriber is healthy and ready"
        : "Transcriber not initialized",
      details: {
        registered_phrases: Object.keys(this.config.customPhrases).length,
      },
    };
  }

  async cancel(sessionId?: string): Promise<void> {
    if (sessionId) {
      this.cancelledSessions.add(sessionId);
    } else {
      this.cancelledSessions.clear();
    }
  }

  reset(): void {
    this.cancelledSessions.clear();
  }

  /**
   * Transcribes an audio chunk deterministically.
   */
  async transcribeChunk(
    chunk: AudioChunkInput,
    options?: TranscribeOptions
  ): Promise<TranscriptEvent[]> {
    // 1. Check for immediate cancellation or session abort
    if (options?.signal?.aborted || this.cancelledSessions.has(chunk.session_id)) {
      throw new Error(`Transcription request aborted for session ${chunk.session_id}`);
    }

    // 2. Simulated delay if configured
    if (this.config.simulatedDelayMs > 0) {
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(resolve, this.config.simulatedDelayMs);
        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            clearTimeout(timeout);
            reject(new Error("Operation cancelled during processing delay"));
          });
        }
      });
    }

    // 3. Handle silence chunk
    if (!chunk.is_speech) {
      return [];
    }

    // 4. Handle error trigger chunk (for testing failure handling & resilience)
    const rawDataStr = typeof chunk.data === "string" ? chunk.data : "";
    if (rawDataStr.includes("__TRIGGER_PROVIDER_ERROR__")) {
      const errorEvent: TranscriptEvent = {
        event_id: this.computeDeterministicId("error", chunk),
        event_type: "transcript.error",
        schema_version: "1.0.0",
        session_id: chunk.session_id,
        correlation_id: chunk.correlation_id,
        timestamp: new Date(1700000000000 + chunk.timestamp_ms).toISOString(),
        producer: "w2-speech-to-text",
        payload: {
          provider_name: this.name,
          error: {
            code: "PROVIDER_TRANSLATION_FAILED",
            message_safe_for_user: "The speech-to-text engine encountered an unrecoverable input error.",
            retryable: false,
            correlation_id: chunk.correlation_id,
            details_redacted: { chunk_id: chunk.chunk_id },
          },
        },
      };
      return [errorEvent];
    }

    // 5. Derive deterministic text and words
    const transcribedText = this.deriveDeterministicText(chunk);
    if (!transcribedText || transcribedText.trim().length === 0) {
      return [];
    }

    const words = this.deriveDeterministicWords(transcribedText, chunk.timestamp_ms, chunk.duration_ms);

    const events: TranscriptEvent[] = [];
    const fixedIsoTimestamp = new Date(1700000000000 + chunk.timestamp_ms).toISOString();

    // 6. If caller requested interim hypotheses, generate interim event first
    if (options?.emitInterim) {
      const interimWords = words.slice(0, Math.max(1, Math.floor(words.length / 2)));
      const interimText = interimWords.map((w) => w.word).join(" ");
      const interimSegment: TranscriptSegment = {
        segment_id: this.computeDeterministicId("seg-interim", chunk),
        sequence_number: chunk.sequence_number,
        start_time_ms: chunk.timestamp_ms,
        end_time_ms: chunk.timestamp_ms + Math.floor(chunk.duration_ms / 2),
        text: interimText,
        confidence: Math.max(0.1, Number((this.config.defaultConfidence * 0.8).toFixed(2))),
        is_final: false,
        language: options.language ?? "en-US",
        words: interimWords,
      };

      const interimEvent: TranscriptEvent = {
        event_id: this.computeDeterministicId("evt-interim", chunk),
        event_type: "transcript.interim",
        schema_version: "1.0.0",
        session_id: chunk.session_id,
        correlation_id: chunk.correlation_id,
        timestamp: fixedIsoTimestamp,
        producer: "w2-speech-to-text",
        payload: {
          provider_name: this.name,
          latency_ms: 12,
          segment: interimSegment,
        },
      };

      const interimVal = validateTranscriptEvent(interimEvent, chunk.correlation_id);
      if (interimVal.success) {
        events.push(interimVal.data);
      }
    }

    // 7. Generate final segment event
    const finalSegment: TranscriptSegment = {
      segment_id: this.computeDeterministicId("seg-final", chunk),
      sequence_number: chunk.sequence_number,
      start_time_ms: chunk.timestamp_ms,
      end_time_ms: chunk.timestamp_ms + chunk.duration_ms,
      text: transcribedText,
      confidence: this.config.defaultConfidence,
      is_final: true,
      language: options?.language ?? "en-US",
      words,
    };

    const finalEvent: TranscriptEvent = {
      event_id: this.computeDeterministicId("evt-final", chunk),
      event_type: "transcript.final",
      schema_version: "1.0.0",
      session_id: chunk.session_id,
      correlation_id: chunk.correlation_id,
      timestamp: fixedIsoTimestamp,
      producer: "w2-speech-to-text",
      payload: {
        provider_name: this.name,
        latency_ms: 24,
        segment: finalSegment,
      },
    };

    const finalVal = validateTranscriptEvent(finalEvent, chunk.correlation_id);
    if (!finalVal.success) {
      throw new Error(`Generated event failed contract validation: ${finalVal.error.message_safe_for_user}`);
    }
    events.push(finalVal.data);

    return events;
  }

  /**
   * Derives repeatable text based on chunk content or hash.
   */
  private deriveDeterministicText(chunk: AudioChunkInput): string {
    if (typeof chunk.data === "string" && this.config.customPhrases[chunk.data]) {
      return this.config.customPhrases[chunk.data];
    }

    // Deterministic synthetic fallback phrase generator
    const hash = createHash("sha256")
      .update(
        typeof chunk.data === "string"
          ? chunk.data
          : Buffer.from(chunk.data)
      )
      .update(String(chunk.sequence_number))
      .digest("hex");

    const vocabulary = [
      "Voicebot", "system", "recognized", "academic", "command",
      "audio", "stream", "active", "processing", "speech"
    ];

    const idx1 = parseInt(hash.slice(0, 2), 16) % vocabulary.length;
    const idx2 = parseInt(hash.slice(2, 4), 16) % vocabulary.length;
    const idx3 = parseInt(hash.slice(4, 6), 16) % vocabulary.length;

    return `${vocabulary[idx1]} ${vocabulary[idx2]} ${vocabulary[idx3]}.`;
  }

  /**
   * Generates word timing intervals distributed across duration.
   */
  private deriveDeterministicWords(
    text: string,
    startTimeMs: number,
    durationMs: number
  ): TranscriptWord[] {
    const rawWords = text.trim().split(/\s+/).filter(Boolean);
    if (rawWords.length === 0) return [];

    const slotMs = Math.floor(durationMs / rawWords.length);
    return rawWords.map((word, i) => {
      const wStart = startTimeMs + i * slotMs;
      const wEnd = i === rawWords.length - 1 ? startTimeMs + durationMs : wStart + slotMs;
      return {
        word,
        start_time_ms: wStart,
        end_time_ms: wEnd,
        confidence: Number((this.config.defaultConfidence - (i % 3) * 0.02).toFixed(2)),
      };
    });
  }

  /**
   * Computes a deterministic UUID-like string from chunk identity
   */
  private computeDeterministicId(prefix: string, chunk: AudioChunkInput): string {
    const hash = createHash("md5")
      .update(`${prefix}:${chunk.session_id}:${chunk.chunk_id}:${chunk.sequence_number}`)
      .digest("hex");
    return `${prefix}-${hash.slice(0, 8)}-${hash.slice(8, 12)}-${hash.slice(12, 16)}`;
  }
}
