import { describe, expect, it } from 'vitest';
import { API_ROUTES } from './contracts';
import type { ApiErrorPayload, HealthCheckRequest, SessionRetrievalRequest } from './contracts';

describe('documented API contracts', () => {
  it('records the documented session and health routes', () => {
    expect(API_ROUTES).toEqual({
      session: '/api/v1/sessions/{session_id}',
      health: '/api/v1/health',
    });
  });

  it('uses the documented session path parameter and standard error shape', () => {
    const request: SessionRetrievalRequest = { session_id: 'session-001' };
    const healthRequest: HealthCheckRequest = undefined;
    const error: ApiErrorPayload = {
      error: {
        code: 'INVALID_REQUEST',
        message: 'The request is invalid.',
        request_id: 'req-001',
      },
    };

    expect(request.session_id).toBe('session-001');
    expect(healthRequest).toBeUndefined();
    expect(error.error.request_id).toBe('req-001');
  });
});
