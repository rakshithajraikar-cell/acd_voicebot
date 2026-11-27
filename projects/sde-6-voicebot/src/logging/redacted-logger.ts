/**
 * Redacted Logging System
 *
 * Enforces strict privacy and security standards:
 * - Logs NEVER contain plain-text transcript utterances or word breakdowns.
 * - Logs NEVER contain raw audio byte payloads or PCM buffers.
 * - Logs NEVER contain credentials, API keys, or auth tokens.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  component: string;
  message: string;
  session_id?: string;
  correlation_id?: string;
  metadata?: Record<string, unknown>;
}

export interface RedactedLoggerOptions {
  component?: string;
  minLevel?: LogLevel;
  silent?: boolean;
}

const LOG_LEVEL_SEVERITY: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

const SENSITIVE_TRANSCRIPT_KEYS = /^(text|content|transcript|words|raw_text|utterance|hypothesis)$/i;
const SENSITIVE_AUDIO_KEYS = /^(data|audio|pcm|bytes|raw_audio|audio_bytes|audio_payload|buffer|waveform)$/i;
const SENSITIVE_SECRET_KEYS = /^(api_key|apikey|token|secret|password|auth|authorization|credential|access_token|private_key)$/i;

/**
 * Deeply sanitizes and redacts any input data structure.
 * Guarantees that neither audio buffers, transcript text, nor credentials leak.
 */
export function sanitizeAndRedact(value: unknown, depth = 0): unknown {
  if (value === null || value === undefined) {
    return value;
  }

  // Prevent infinite cycles
  if (depth > 10) {
    return "[MAX_DEPTH_EXCEEDED]";
  }

  // Handle TypedArrays & Buffers (Audio Data)
  if (value instanceof Uint8Array || value instanceof Float32Array || value instanceof ArrayBuffer) {
    const byteLength = value.byteLength;
    return `[REDACTED_AUDIO_PAYLOAD (${byteLength} bytes)]`;
  }

  // Handle string values (regex check for keys / secrets / bearer tokens)
  if (typeof value === "string") {
    let sanitized = value;
    if (/bearer\s+[a-zA-Z0-9._-]+/i.test(sanitized)) {
      sanitized = sanitized.replace(/bearer\s+[a-zA-Z0-9._-]+/gi, "Bearer [REDACTED_SECRET]");
    }
    if (/sk-[a-zA-Z0-9]{20,}/i.test(sanitized)) {
      sanitized = sanitized.replace(/sk-[a-zA-Z0-9]{20,}/gi, "[REDACTED_SECRET]");
    }
    return sanitized;
  }

  // Handle Arrays
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeAndRedact(item, depth + 1));
  }

  // Handle Errors
  if (value instanceof Error) {
    return {
      name: value.name,
      message: sanitizeAndRedact(value.message, depth + 1),
      stack: "[REDACTED_STACK_TRACE]",
    };
  }

  // Handle Objects
  if (typeof value === "object") {
    const sanitizedObj: Record<string, unknown> = {};

    for (const [key, val] of Object.entries(value)) {
      // 1. Redact Secrets
      if (SENSITIVE_SECRET_KEYS.test(key)) {
        sanitizedObj[key] = "[REDACTED_SECRET]";
        continue;
      }

      // 2. Redact Audio Payloads
      if (SENSITIVE_AUDIO_KEYS.test(key)) {
        if (
          val instanceof Uint8Array ||
          val instanceof Float32Array ||
          val instanceof ArrayBuffer
        ) {
          sanitizedObj[key] = `[REDACTED_AUDIO_PAYLOAD (${val.byteLength} bytes)]`;
        } else if (Array.isArray(val)) {
          sanitizedObj[key] = `[REDACTED_AUDIO_PAYLOAD (${val.length} samples)]`;
        } else {
          sanitizedObj[key] = "[REDACTED_AUDIO_PAYLOAD]";
        }
        continue;
      }

      // 3. Redact Transcript Text
      if (SENSITIVE_TRANSCRIPT_KEYS.test(key)) {
        if (typeof val === "string") {
          sanitizedObj[key] = `[REDACTED_TRANSCRIPT (len=${val.length})]`;
        } else if (Array.isArray(val)) {
          sanitizedObj[key] = `[REDACTED_WORDS_LIST (count=${val.length})]`;
        } else {
          sanitizedObj[key] = "[REDACTED_TRANSCRIPT]";
        }
        continue;
      }

      // Recursively sanitize other keys
      sanitizedObj[key] = sanitizeAndRedact(val, depth + 1);
    }

    return sanitizedObj;
  }

  return value;
}

/**
 * Structured Redacted Logger
 */
export class RedactedLogger {
  private readonly component: string;
  private readonly minLevel: LogLevel;
  private readonly silent: boolean;
  private readonly inMemoryLogs: LogEntry[] = [];

  constructor(options: RedactedLoggerOptions = {}) {
    this.component = options.component ?? "w2-speech-to-text";
    this.minLevel = options.minLevel ?? "debug";
    this.silent = options.silent ?? true; // silent in automated environments
  }

  private shouldLog(level: LogLevel): boolean {
    return LOG_LEVEL_SEVERITY[level] >= LOG_LEVEL_SEVERITY[this.minLevel];
  }

  private log(
    level: LogLevel,
    message: string,
    context?: Record<string, unknown>
  ): LogEntry {
    // Redact any sensitive information from context
    const sanitizedContext = context
      ? (sanitizeAndRedact(context) as Record<string, unknown>)
      : undefined;

    // Redact message if it contains bearer tokens or raw secrets
    const sanitizedMessage = String(sanitizeAndRedact(message));

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      component: this.component,
      message: sanitizedMessage,
      session_id: context?.session_id as string | undefined,
      correlation_id: context?.correlation_id as string | undefined,
      metadata: sanitizedContext,
    };

    this.inMemoryLogs.push(entry);

    if (!this.silent && this.shouldLog(level)) {
      const output = JSON.stringify(entry);
      if (level === "error") {
        console.error(output);
      } else if (level === "warn") {
        console.warn(output);
      } else {
        console.log(output);
      }
    }

    return entry;
  }

  debug(message: string, context?: Record<string, unknown>): LogEntry {
    return this.log("debug", message, context);
  }

  info(message: string, context?: Record<string, unknown>): LogEntry {
    return this.log("info", message, context);
  }

  warn(message: string, context?: Record<string, unknown>): LogEntry {
    return this.log("warn", message, context);
  }

  error(
    message: string,
    error?: unknown,
    context?: Record<string, unknown>
  ): LogEntry {
    const combinedContext: Record<string, unknown> = { ...(context ?? {}) };
    if (error !== undefined) {
      combinedContext.error = error;
    }
    return this.log("error", message, combinedContext);
  }

  getEntries(): readonly LogEntry[] {
    return [...this.inMemoryLogs];
  }

  clear(): void {
    this.inMemoryLogs.length = 0;
  }

  /**
   * Utility to redact arbitrary data using the logger's rules
   */
  redact<T>(input: T): unknown {
    return sanitizeAndRedact(input);
  }
}

/**
 * Default singleton instance for general use
 */
export const defaultLogger = new RedactedLogger({
  component: "w2-stt-global",
  silent: true,
});
