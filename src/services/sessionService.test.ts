import { describe, expect, it } from 'vitest';
import { createSession } from '../models/session';
import { createMockSessionService } from './sessionService';

describe('mock session service', () => {
  const createdAt = new Date('2026-10-30T00:00:00.000Z');
  const startedAt = new Date('2026-10-30T00:01:00.000Z');

  function makeService() {
    return createMockSessionService({
      initialSession: createSession('session-1', 'Planning', createdAt),
      latencyMs: 0,
      createId: () => 'session-2',
      now: () => startedAt,
    });
  }

  it('creates, starts, and ends sessions through simulated async methods', async () => {
    const service = makeService();
    const created = await service.createSession('Design review');
    expect(created).toMatchObject({
      ok: true,
      data: { id: 'session-2', title: 'Design review', status: 'ready' },
    });

    const started = await service.startSession('session-1');
    expect(started).toMatchObject({
      ok: true,
      data: { status: 'active', startedAt: startedAt.toISOString() },
    });

    const ended = await service.endSession('session-1');
    expect(ended).toMatchObject({
      ok: true,
      data: { status: 'ended', endedAt: startedAt.toISOString() },
    });
    await expect(service.startSession('session-1')).resolves.toMatchObject({
      ok: false,
      error: { code: 'invalid-state' },
    });
  });

  it('returns typed errors for invalid operations', async () => {
    const service = makeService();
    const emptyService = createMockSessionService({ latencyMs: 0 });

    await expect(service.createSession('  ')).resolves.toEqual({
      ok: false,
      error: {
        code: 'invalid-title',
        message: 'Enter a title before creating a session.',
      },
    });
    await expect(service.startSession('missing')).resolves.toEqual({
      ok: false,
      error: { code: 'not-found', message: 'This session could not be found.' },
    });
    await expect(emptyService.startSession('missing')).resolves.toMatchObject({
      ok: false,
      error: { code: 'not-found' },
    });
    await expect(service.endSession('session-1')).resolves.toEqual({
      ok: false,
      error: {
        code: 'invalid-state',
        message: 'Only an active session can be ended.',
      },
    });
  });
});
