import type { SessionStatus } from '../models/session';

/**
 * Identifier formats are not constrained in API Specifications & Interface Contracts v1.0.
 */
export type SessionId = string;
export type RequestId = string;

/**
 * TODO: The API contract does not define timestamp fields or their wire format.
 */
export type ApiTimestamp = string;

/**
 * Existing local session lifecycle states. TODO: Backend must confirm whether these are
 * the session retrieval route's status values before this type is used for API data.
 */
export type SessionLifecycleStatus = SessionStatus;

/**
 * The standard error example documents this nested payload shape. Its code values are not
 * enumerated, so code remains an open string.
 */
export type ApiErrorPayload = Readonly<{
  error: Readonly<{
    code: string;
    message: string;
    request_id: RequestId;
  }>;
}>;

export const API_ROUTES = {
  session: '/api/v1/sessions/{session_id}',
  health: '/api/v1/health',
} as const;

/** Path parameter documented by GET /api/v1/sessions/{session_id}. */
export type SessionRetrievalRequest = Readonly<{
  session_id: SessionId;
}>;

/**
 * TODO: The v1.0 document names this route but supplies no success response schema.
 * Keep the body opaque until the backend validates and publishes its fields.
 */
export type SessionRetrievalResponse = unknown;

/** GET /api/v1/health has no documented path parameters, query, or request body. */
export type HealthCheckRequest = void;

/**
 * TODO: The v1.0 document names this route but supplies no success response schema,
 * health status enum, or timestamp fields.
 */
export type HealthCheckResponse = unknown;
