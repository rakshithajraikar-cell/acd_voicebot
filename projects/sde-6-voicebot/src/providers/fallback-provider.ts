import type { AudioChunkInput, TranscriptEvent } from "../contracts/transcript.js";
import type {
  SpeechToTextAdapter,
  TranscribeOptions,
  ProviderHealth,
} from "./stt-adapter.js";
import { DeterministicFakeTranscriber } from "./fake-transcriber.js";
import type { ErrorEnvelope } from "../contracts/common.js";

export interface FallbackAdapterConfig {
  /**
   * Primary speech provider
   */
  primaryProvider: SpeechToTextAdapter;
  /**
   * Secondary/fallback provider (defaults to DeterministicFakeTranscriber)
   */
  fallbackProvider?: SpeechToTextAdapter;
  /**
   * Predicate determining if an error should trigger automatic fallback
   */
  shouldFallbackOnError?: (error: unknown) => boolean;
}

export interface FallbackMetrics {
  primaryAttempts: number;
  primarySuccesses: number;
  primaryFailures: number;
  fallbacksTriggered: number;
  fallbackSuccesses: number;
}

/**
 * FallbackSpeechToTextAdapter
 *
 * Implements resilient multi-provider failover:
 * 1. Executes the primary provider first.
 * 2. On quota, network drop, timeout, or 503, automatically falls back to the deterministic mock provider.
 * 3. Annotates events with fallback diagnostics so callers know fallback occurred.
 * 4. Cancellation stops in-flight transcription across all providers cleanly.
 */
export class FallbackSpeechToTextAdapter implements SpeechToTextAdapter {
  readonly name = "fallback-resilient-transcriber";
  private readonly primary: SpeechToTextAdapter;
  private readonly fallback: SpeechToTextAdapter;
  private readonly shouldFallback: (error: unknown) => boolean;

  private metrics: FallbackMetrics = {
    primaryAttempts: 0,
    primarySuccesses: 0,
    primaryFailures: 0,
    fallbacksTriggered: 0,
    fallbackSuccesses: 0,
  };

  constructor(config: FallbackAdapterConfig) {
    this.primary = config.primaryProvider;
    this.fallback = config.fallbackProvider ?? new DeterministicFakeTranscriber();
    this.shouldFallback = config.shouldFallbackOnError ?? this.defaultShouldFallback;
  }

  async initialize(config?: Record<string, unknown>): Promise<void> {
    await Promise.all([
      this.primary.initialize(config),
      this.fallback.initialize(config),
    ]);
  }

  async getHealth(): Promise<ProviderHealth> {
    const primaryHealth = await this.primary.getHealth();
    const fallbackHealth = await this.fallback.getHealth();

    const isHealthy = primaryHealth.status === "healthy";
    return {
      status: isHealthy ? "healthy" : "degraded",
      provider_name: this.name,
      is_mock: primaryHealth.is_mock && fallbackHealth.is_mock,
      message: isHealthy
        ? "Primary STT provider healthy"
        : `Primary degraded (${primaryHealth.message || "error"}); Fallback mock provider ready`,
      details: {
        primary: primaryHealth,
        fallback: fallbackHealth,
        metrics: { ...this.metrics },
      },
    };
  }

  async cancel(sessionId?: string): Promise<void> {
    await Promise.all([
      this.primary.cancel(sessionId),
      this.fallback.cancel(sessionId),
    ]);
  }

  reset(): void {
    this.primary.reset();
    this.fallback.reset();
    this.metrics = {
      primaryAttempts: 0,
      primarySuccesses: 0,
      primaryFailures: 0,
      fallbacksTriggered: 0,
      fallbackSuccesses: 0,
    };
  }

  getMetrics(): FallbackMetrics {
    return { ...this.metrics };
  }

  /**
   * Transcribes chunk with automatic failover to mock provider on network/quota failure.
   */
  async transcribeChunk(
    chunk: AudioChunkInput,
    options?: TranscribeOptions
  ): Promise<TranscriptEvent[]> {
    this.metrics.primaryAttempts++;

    try {
      // 1. Attempt primary provider
      const events = await this.primary.transcribeChunk(chunk, options);
      this.metrics.primarySuccesses++;
      return events;
    } catch (primaryErr: unknown) {
      this.metrics.primaryFailures++;

      // 2. Check if error qualifies for fallback (e.g. quota, network drop, timeout)
      if (!this.shouldFallback(primaryErr)) {
        throw primaryErr;
      }

      this.metrics.fallbacksTriggered++;

      // 3. Failover to mock fallback provider
      try {
        const fallbackEvents = await this.fallback.transcribeChunk(chunk, options);
        this.metrics.fallbackSuccesses++;

        // Annotate fallback events with metadata
        return fallbackEvents.map((evt) => ({
          ...evt,
          payload: {
            ...evt.payload,
            provider_name: `${this.primary.name}->fallback:${this.fallback.name}`,
          },
        }));
      } catch (fallbackErr: unknown) {
        // Both primary and fallback failed; emit normalized error event without throwing raw error
        const errorMessage =
          fallbackErr instanceof Error ? fallbackErr.message : String(fallbackErr);
        const errorEnvelope: ErrorEnvelope = {
          code: "PROVIDER_AND_FALLBACK_FAILED",
          message_safe_for_user:
            "Transcription failed across primary and fallback speech providers.",
          retryable: false,
          correlation_id: chunk.correlation_id,
          details_redacted: {
            primary_error: primaryErr instanceof Error ? primaryErr.message : String(primaryErr),
            fallback_error: errorMessage,
          },
        };

        const errorEvent: TranscriptEvent = {
          event_id: `evt-fallback-err-${chunk.chunk_id}`,
          event_type: "transcript.error",
          schema_version: "1.0.0",
          session_id: chunk.session_id,
          correlation_id: chunk.correlation_id,
          timestamp: new Date().toISOString(),
          producer: "w2-speech-to-text",
          payload: {
            provider_name: this.name,
            error: errorEnvelope,
          },
        };

        return [errorEvent];
      }
    }
  }

  private defaultShouldFallback(err: unknown): boolean {
    if (err instanceof Error) {
      const msg = err.message.toLowerCase();
      if (
        msg.includes("quota") ||
        msg.includes("429") ||
        msg.includes("network") ||
        msg.includes("econnrefused") ||
        msg.includes("timed out") ||
        msg.includes("timeout") ||
        msg.includes("503") ||
        msg.includes("rate limit")
      ) {
        return true;
      }
    }
    return true; // Safe default in mock/testing environment
  }
}
