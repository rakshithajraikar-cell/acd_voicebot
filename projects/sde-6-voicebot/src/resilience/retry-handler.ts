import type { ErrorEnvelope } from "../contracts/common.js";

export interface RetryPolicy {
  /**
   * Maximum retry attempts before giving up (default: 2, bounded)
   */
  maxRetries?: number;
  /**
   * Initial backoff delay in milliseconds (default: 50ms)
   */
  initialBackoffMs?: number;
  /**
   * Multiplier applied to backoff delay per retry (default: 2.0)
   */
  backoffMultiplier?: number;
  /**
   * Per-attempt timeout in milliseconds (default: 2000ms)
   */
  timeoutMs?: number;
}

export type ResilienceResult<T> =
  | { success: true; data: T; attempts: number }
  | { success: false; error: ErrorEnvelope; attempts: number };

/**
 * RetryHandler
 *
 * Provides bounded retries, per-attempt timeout limits, and error normalization.
 * Guarantee: Never leaks unhandled raw exceptions or private stack traces to calling layers.
 */
export class RetryHandler {
  readonly maxRetries: number;
  readonly initialBackoffMs: number;
  readonly backoffMultiplier: number;
  readonly timeoutMs: number;

  constructor(policy?: RetryPolicy) {
    this.maxRetries = policy?.maxRetries ?? 2;
    this.initialBackoffMs = policy?.initialBackoffMs ?? 50;
    this.backoffMultiplier = policy?.backoffMultiplier ?? 2.0;
    this.timeoutMs = policy?.timeoutMs ?? 2000;
  }

  /**
   * Executes an async operation with timeout and bounded retries.
   */
  async execute<T>(
    operation: (signal: AbortSignal, attempt: number) => Promise<T>,
    correlationId: string = "corr-resilience",
    isRetryableError?: (err: unknown) => boolean
  ): Promise<ResilienceResult<T>> {
    let attempt = 0;
    let lastError: unknown;

    while (attempt <= this.maxRetries) {
      attempt++;
      const controller = new AbortController();
      let timer: ReturnType<typeof setTimeout> | undefined;

      const timeoutPromise = new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          const timeoutErr = new Error(`Operation timed out after ${this.timeoutMs}ms`);
          timeoutErr.name = "TimeoutError";
          reject(timeoutErr);
        }, this.timeoutMs);
      });

      try {
        const result = await Promise.race([
          operation(controller.signal, attempt),
          timeoutPromise,
        ]);
        clearTimeout(timer);
        return { success: true, data: result, attempts: attempt };
      } catch (err: unknown) {
        clearTimeout(timer);
        lastError = err;

        // Check if error is retryable and attempts remain
        const retryable =
          attempt <= this.maxRetries &&
          (isRetryableError ? isRetryableError(err) : this.defaultIsRetryable(err));

        if (!retryable) {
          break;
        }

        // Apply exponential backoff with slight jitter
        const delay = Math.round(
          this.initialBackoffMs *
            Math.pow(this.backoffMultiplier, attempt - 1) *
            (0.8 + Math.random() * 0.4)
        );
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    // Normalize error envelope
    const normalizedError = this.normalizeError(lastError, correlationId);
    return {
      success: false,
      error: normalizedError,
      attempts: attempt,
    };
  }

  /**
   * Determines if error is transient/retryable by default.
   */
  private defaultIsRetryable(err: unknown): boolean {
    if (err instanceof Error) {
      if (err.name === "TimeoutError") return true;
      if (err.message.includes("network") || err.message.includes("transient")) return true;
      if (err.message.includes("503") || err.message.includes("rate limit")) return true;
    }
    return false;
  }

  /**
   * Normalizes any raw exception into a clean, safe ErrorEnvelope.
   */
  normalizeError(err: unknown, correlationId: string): ErrorEnvelope {
    if (err && typeof err === "object" && "code" in err && "message_safe_for_user" in err) {
      return err as ErrorEnvelope;
    }

    if (err instanceof Error) {
      if (err.name === "TimeoutError") {
        return {
          code: "PROVIDER_TIMEOUT",
          message_safe_for_user: `Speech-to-text provider exceeded deadline of ${this.timeoutMs}ms.`,
          retryable: true,
          correlation_id: correlationId,
          details_redacted: { timeout_ms: this.timeoutMs },
        };
      }

      if (err.name === "AbortError") {
        return {
          code: "OPERATION_ABORTED",
          message_safe_for_user: "The transcription operation was cancelled.",
          retryable: false,
          correlation_id: correlationId,
          details_redacted: { aborted: true },
        };
      }

      return {
        code: "PROVIDER_EXECUTION_ERROR",
        message_safe_for_user: "The speech recognition engine encountered an error while processing audio.",
        retryable: false,
        correlation_id: correlationId,
        details_redacted: { error_type: err.name, message: err.message },
      };
    }

    return {
      code: "UNKNOWN_PROVIDER_ERROR",
      message_safe_for_user: "An unexpected error occurred in the transcription pipeline.",
      retryable: false,
      correlation_id: correlationId,
      details_redacted: { raw_type: typeof err },
    };
  }
}

