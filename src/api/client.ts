import {
  API_ROUTES,
  type ApiErrorPayload,
  type HealthCheckResponse,
  type SessionRetrievalRequest,
  type SessionRetrievalResponse,
} from './contracts';
import { createSession } from '../models/session';

/**
 * Stable boundary for the API routes currently in scope.
 */
export interface ApiClient {
  getSession(request: SessionRetrievalRequest): Promise<SessionRetrievalResponse>;
  healthCheck(): Promise<HealthCheckResponse>;
}

export type MockApiClientResponses = Readonly<{
  session: SessionRetrievalResponse;
  health: HealthCheckResponse;
}>;

export type MockApiScenario =
  | 'success'
  | 'session-not-found'
  | 'server-error'
  | 'network-failure';

export type MockApiClientOptions = Readonly<{
  scenario?: MockApiScenario;
  responses?: MockApiClientResponses;
}>;

export type HttpApiClientOptions = Readonly<{
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}>;

export type ApiClientConfiguration =
  | Readonly<{ mode: 'mock'; scenario?: MockApiScenario }>
  | Readonly<{ mode: 'http'; baseUrl?: string }>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (!isRecord(value) || !isRecord(value.error)) {
    return false;
  }

  const { code, message, request_id: requestId } = value.error;
  return typeof code === 'string' && typeof message === 'string' && typeof requestId === 'string';
}

export class ApiClientError extends Error {
  constructor(
    public readonly kind: 'http' | 'network' | 'invalid-response',
    public readonly status: number | undefined,
    public readonly payload: unknown,
    message?: string,
    public readonly cause?: unknown,
  ) {
    const errorMessage = isApiErrorPayload(payload)
      ? payload.error.message
      : `API request failed with status ${status}.`;
    super(message ?? errorMessage);
    this.name = 'ApiClientError';
  }

  get apiError(): ApiErrorPayload | undefined {
    return isApiErrorPayload(this.payload) ? this.payload : undefined;
  }
}

/**
 * Mock implementation. Responses are injected because the contract does not define either
 * route's success payload yet.
 */
export class MockApiClient implements ApiClient {
  private readonly scenario: MockApiScenario;
  private readonly responses: MockApiClientResponses;

  constructor(options: MockApiClientOptions = {}) {
    this.scenario = options.scenario ?? 'success';
    this.responses = options.responses ?? {
      // TODO: Replace mock-only response shapes after backend validates the route schemas.
      session: createSession(
        'session-001',
        'Product design review',
        new Date('2026-10-30T10:42:00.000Z'),
      ),
      health: { status: 'healthy' },
    };
  }

  async getSession(request: SessionRetrievalRequest): Promise<SessionRetrievalResponse> {
    if (this.scenario === 'session-not-found') {
      throw createMockHttpError(
        404,
        'SESSION_NOT_FOUND',
        `Session '${request.session_id}' not found.`,
      );
    }
    if (this.scenario === 'server-error') {
      throw createMockHttpError(500, 'INTERNAL_SERVER_ERROR', 'The mock server failed.');
    }
    if (this.scenario === 'network-failure') {
      throw createMockNetworkError();
    }
    return this.responses.session;
  }

  async healthCheck(): Promise<HealthCheckResponse> {
    if (this.scenario === 'server-error') {
      throw createMockHttpError(500, 'INTERNAL_SERVER_ERROR', 'The mock server failed.');
    }
    if (this.scenario === 'network-failure') {
      throw createMockNetworkError();
    }
    return this.responses.health;
  }
}

function createMockHttpError(status: number, code: string, message: string): ApiClientError {
  const payload: ApiErrorPayload = {
    error: {
      code,
      message,
      request_id: `mock-request-${status}`,
    },
  };
  return new ApiClientError('http', status, payload);
}

function createMockNetworkError(): ApiClientError {
  return new ApiClientError('network', undefined, undefined, 'Mock network failure.');
}

/**
 * HTTP implementation for only GET /sessions/{session_id} and GET /health.
 * Success payloads remain unknown until the backend publishes their schemas.
 */
export class HttpApiClient implements ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: HttpApiClientOptions = {}) {
    this.baseUrl = options.baseUrl?.replace(/\/+$/, '') ?? '';
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  getSession(request: SessionRetrievalRequest): Promise<SessionRetrievalResponse> {
    const path = API_ROUTES.session.replace('{session_id}', encodeURIComponent(request.session_id));
    return requestJson(this.fetchImpl, this.baseUrl, path);
  }

  healthCheck(): Promise<HealthCheckResponse> {
    return requestJson(this.fetchImpl, this.baseUrl, API_ROUTES.health);
  }
}

async function requestJson(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
  } catch (error) {
    throw new ApiClientError(
      'network',
      undefined,
      undefined,
      error instanceof Error ? error.message : 'Network request failed.',
      error,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (error) {
    throw new ApiClientError(
      'invalid-response',
      response.status,
      undefined,
      `API returned an invalid JSON response for status ${response.status}.`,
      error,
    );
  }

  if (!response.ok) {
    throw new ApiClientError('http', response.status, payload);
  }

  return payload;
}

export function createHttpApiClient(options: HttpApiClientOptions = {}): ApiClient {
  return new HttpApiClient(options);
}

export function createApiClient(configuration: ApiClientConfiguration): ApiClient {
  if (configuration.mode === 'mock') {
    return new MockApiClient({ scenario: configuration.scenario });
  }
  return new HttpApiClient({ baseUrl: configuration.baseUrl });
}
