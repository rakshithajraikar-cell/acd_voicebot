import { describe, expect, it, vi } from 'vitest';
import {
  ApiClientError,
  HttpApiClient,
  MockApiClient,
  createApiClient,
  type ApiClient,
} from './client';
import { resolveApiClientConfiguration } from './configuredClient';

describe('API clients', () => {
  it('exposes only the session retrieval and health check methods', () => {
    expect(Object.getOwnPropertyNames(MockApiClient.prototype).sort()).toEqual([
      'constructor',
      'getSession',
      'healthCheck',
    ]);
    expect(Object.getOwnPropertyNames(HttpApiClient.prototype).sort()).toEqual([
      'constructor',
      'getSession',
      'healthCheck',
    ]);
  });

  it('implements the same typed boundary for injected mock responses', async () => {
    const responses = {
      session: { mock: 'session response' },
      health: { mock: 'health response' },
    };
    const client: ApiClient = new MockApiClient({ responses });

    await expect(client.getSession({ session_id: 'session-001' })).resolves.toEqual(
      responses.session,
    );
    await expect(client.healthCheck()).resolves.toEqual(responses.health);
  });

  it('defaults to a predictable valid session and healthy mock response', async () => {
    const client = createApiClient(resolveApiClientConfiguration({}));

    await expect(client.getSession({ session_id: 'session-001' })).resolves.toMatchObject({
      id: 'session-001',
      title: 'Product design review',
      status: 'ready',
    });
    await expect(client.healthCheck()).resolves.toEqual({ status: 'healthy' });
  });

  it('provides explicit mock 404, 500, and network failure cases', async () => {
    const notFound = new MockApiClient({ scenario: 'session-not-found' });
    await expect(notFound.getSession({ session_id: 'missing' })).rejects.toMatchObject({
      kind: 'http',
      status: 404,
      apiError: {
        error: {
          code: 'SESSION_NOT_FOUND',
          message: 'Session not found.',
        },
      },
    });
    await expect(notFound.healthCheck()).resolves.toEqual({ status: 'healthy' });

    const serverError = new MockApiClient({ scenario: 'server-error' });
    await expect(serverError.getSession({ session_id: 'session-001' })).rejects.toMatchObject({
      kind: 'http',
      status: 500,
    });
    await expect(serverError.healthCheck()).rejects.toMatchObject({
      kind: 'http',
      status: 500,
    });

    const networkFailure = new MockApiClient({ scenario: 'network-failure' });
    await expect(
      networkFailure.getSession({ session_id: 'session-001' }),
    ).rejects.toMatchObject({
      kind: 'network',
      status: undefined,
      message: 'Mock network failure.',
    });
    await expect(networkFailure.healthCheck()).rejects.toMatchObject({
      kind: 'network',
      status: undefined,
    });
  });

  it('supports mock and HTTP configuration through the same client boundary', () => {
    expect(resolveApiClientConfiguration({})).toEqual({ mode: 'mock', scenario: 'success' });
    expect(
      resolveApiClientConfiguration({
        VITE_API_MOCK_SCENARIO: 'network-failure',
      }),
    ).toEqual({ mode: 'mock', scenario: 'network-failure' });
    expect(
      resolveApiClientConfiguration({
        VITE_API_CLIENT_MODE: 'http',
        VITE_API_BASE_URL: 'https://api.example.test',
      }),
    ).toEqual({ mode: 'http', baseUrl: 'https://api.example.test' });
    expect(() =>
      resolveApiClientConfiguration({ VITE_API_CLIENT_MODE: 'remote' }),
    ).toThrow('Unsupported VITE_API_CLIENT_MODE: remote');
  });

  it('calls only the documented session and health GET routes', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async () => {
      return new Response(JSON.stringify({ result: 'opaque response' }), { status: 200 });
    });
    const client = new HttpApiClient({
      baseUrl: 'https://api.example.test/',
      fetchImpl,
    });

    await expect(client.getSession({ session_id: 'session / 001' })).resolves.toEqual({
      result: 'opaque response',
    });
    await expect(client.healthCheck()).resolves.toEqual({ result: 'opaque response' });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      'https://api.example.test/api/v1/sessions/session%20%2F%20001',
      { method: 'GET', headers: { Accept: 'application/json' } },
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(2, 'https://api.example.test/api/v1/health', {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
  });

  it('surfaces the documented standard error payload', async () => {
    const errorPayload = {
      error: {
        code: 'INVALID_REQUEST',
        message: 'The request is invalid.',
        request_id: 'req-001',
      },
    };
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify(errorPayload), { status: 400 }));
    const client = new HttpApiClient({ fetchImpl });

    await expect(client.healthCheck()).rejects.toMatchObject({
      name: 'ApiClientError',
      status: 400,
      message: 'The request is invalid.',
      apiError: errorPayload,
    } satisfies Partial<ApiClientError>);
  });

  it('reports malformed JSON responses explicitly', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response('not json', { status: 200 }));
    const client = new HttpApiClient({ fetchImpl });

    await expect(client.healthCheck()).rejects.toMatchObject({
      name: 'ApiClientError',
      status: 200,
      message: 'API returned an invalid JSON response for status 200.',
    });
  });

  it('wraps HTTP transport failures as network errors', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new Error('Connection refused'));
    const client = new HttpApiClient({ fetchImpl });

    await expect(client.healthCheck()).rejects.toMatchObject({
      name: 'ApiClientError',
      kind: 'network',
      message: 'Connection refused',
    });
  });
});
