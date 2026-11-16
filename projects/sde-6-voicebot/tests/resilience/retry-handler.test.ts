import { describe, it, expect, vi } from "vitest";
import { RetryHandler } from "../../src/resilience/retry-handler.js";

describe("W2 Resilience & Retry Layer (Timeouts, Retries & Error Normalization)", () => {
  it("should return successfully on attempt 1 when no failure occurs", async () => {
    const handler = new RetryHandler({ maxRetries: 2, timeoutMs: 1000 });
    const op = vi.fn().mockResolvedValue("transcript-result");

    const result = await handler.execute(op, "corr-1");
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toBe("transcript-result");
      expect(result.attempts).toBe(1);
    }
    expect(op).toHaveBeenCalledTimes(1);
  });

  it("should perform bounded retries on transient errors and succeed", async () => {
    const handler = new RetryHandler({ maxRetries: 3, initialBackoffMs: 10 });
    let calls = 0;
    const op = vi.fn().mockImplementation(async () => {
      calls++;
      if (calls < 3) {
        throw new Error("transient network timeout");
      }
      return "recovered-success";
    });

    const result = await handler.execute(op, "corr-2");
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toBe("recovered-success");
      expect(result.attempts).toBe(3);
    }
  });

  it("should normalize exhausted retries into a clean ErrorEnvelope without throwing", async () => {
    const handler = new RetryHandler({ maxRetries: 2, initialBackoffMs: 10 });
    const op = vi.fn().mockRejectedValue(new Error("transient network drop"));

    const result = await handler.execute(op, "corr-exhausted");
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.code).toBe("PROVIDER_EXECUTION_ERROR");
      expect(result.error.message_safe_for_user).toBeDefined();
      expect(result.error.correlation_id).toBe("corr-exhausted");
      expect(result.attempts).toBe(3); // 1 initial + 2 retries
    }
  });

  it("should handle timeout and return PROVIDER_TIMEOUT ErrorEnvelope", async () => {
    const handler = new RetryHandler({ maxRetries: 0, timeoutMs: 50 });
    const hangingOp = vi.fn().mockImplementation(() => {
      return new Promise((resolve) => setTimeout(resolve, 500));
    });

    const result = await handler.execute(hangingOp, "corr-timeout");
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.code).toBe("PROVIDER_TIMEOUT");
      expect(result.error.retryable).toBe(true);
    }
  });
});

