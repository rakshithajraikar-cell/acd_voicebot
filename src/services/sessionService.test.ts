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

  it('stores network status separately from session operation errors', () => {
    const service = makeService();

    expect(service.networkStatus).toBe('online');
    service.setNetworkStatus('offline');
    expect(service.networkStatus).toBe('offline');
    service.setNetworkStatus('online');
    expect(service.networkStatus).toBe('online');
  });

  it('keeps screen context disabled by default until explicitly enabled', async () => {
    const initialSession = createSession('session-3', 'Context check', createdAt);
    const contextService = createMockSessionService({
      initialSession,
      latencyMs: 0,
    });

    expect(initialSession.contextPanel.sources).toEqual([
      { id: 'screen-context', label: 'Screen context', type: 'screen', enabled: false },
    ]);
    expect(contextService.getEnabledContextSources(initialSession.id)).toEqual({
      ok: true,
      data: [],
    });

    const startedSession = await contextService.startSession(initialSession.id);
    expect(startedSession).toMatchObject({
      ok: true,
      data: { contextPanel: { sources: [{ id: 'screen-context', enabled: false }] } },
    });

    const enabled = contextService.setContextSourceEnabled(
      initialSession.id,
      'screen-context',
      true,
    );
    expect(enabled).toMatchObject({
      ok: true,
      data: {
        contextPanel: {
          sources: [{ id: 'screen-context', type: 'screen', enabled: true }],
        },
      },
    });
    if (!enabled.ok) throw new Error('Expected explicit context opt-in to succeed.');
    expect(contextService.getEnabledContextSources(initialSession.id)).toEqual({
      ok: true,
      data: [{ id: 'screen-context', label: 'Screen context', type: 'screen', enabled: true }],
    });

    const captureReady = contextService.recordCaptureEvent(initialSession.id, { type: 'ready' });
    expect(captureReady).toMatchObject({
      ok: true,
      data: { contextPanel: { sources: [{ enabled: true }] } },
    });
  });

  it('does not expose disabled screen sources in context data for processing', () => {
    const session = createSession('session-context-filter', 'Context filter', createdAt);
    const service = createMockSessionService({ initialSession: session, latencyMs: 0 });

    const enabled = service.setContextSourceEnabled(session.id, 'screen-context', true);
    expect(enabled.ok).toBe(true);
    expect(service.getEnabledContextSources(session.id)).toMatchObject({
      ok: true,
      data: [{ id: 'screen-context', type: 'screen', enabled: true }],
    });

    const disabled = service.setContextSourceEnabled(session.id, 'screen-context', false);
    expect(disabled).toMatchObject({
      ok: true,
      data: {
        contextPanel: {
          sources: [{ id: 'screen-context', type: 'screen', enabled: false }],
        },
      },
    });
    const context = service.getEnabledContextSources(session.id);
    expect(context).toEqual({ ok: true, data: [] });
    if (context.ok) {
      expect(context.data.some((source) => source.type === 'screen')).toBe(false);
    }
  });

  it('stores capture state and timestamps only when lifecycle events are recorded', async () => {
    const service = makeService();
    const started = await service.startSession('session-1');
    expect(started.ok).toBe(true);

    const ready = service.recordCaptureEvent('session-1', { type: 'ready' }, startedAt);
    expect(ready).toMatchObject({ ok: true, data: { captureState: 'ready' } });

    const capturing = service.recordCaptureEvent('session-1', { type: 'started' }, startedAt);
    expect(capturing).toMatchObject({ ok: true, data: { captureState: 'capturing' } });

    const pausedAt = new Date('2026-10-30T00:02:00.000Z');
    const paused = service.recordCaptureEvent('session-1', { type: 'paused' }, pausedAt);
    expect(paused).toMatchObject({
      ok: true,
      data: { captureState: 'paused', pausedAt: pausedAt.toISOString(), resumedAt: null },
    });

    const resumedAt = new Date('2026-10-30T00:03:00.000Z');
    const resumed = service.recordCaptureEvent('session-1', { type: 'resumed' }, resumedAt);
    expect(resumed).toMatchObject({
      ok: true,
      data: {
        captureState: 'capturing',
        pausedAt: pausedAt.toISOString(),
        resumedAt: resumedAt.toISOString(),
      },
    });

    expect(service.recordCaptureEvent('session-1', { type: 'ended' }, resumedAt)).toMatchObject({
      ok: true,
      data: { captureState: 'ended' },
    });
  });

  it('rejects capture events that do not match the stored capture state', () => {
    const service = makeService();

    expect(service.recordCaptureEvent('session-1', { type: 'paused' })).toEqual({
      ok: false,
      error: {
        code: 'invalid-state',
        message: 'Capture cannot transition from idle to paused.',
      },
    });
  });

  it('requires capture to emit ended before ending a capturing or paused session', async () => {
    const service = makeService();
    await service.startSession('session-1');
    service.recordCaptureEvent('session-1', { type: 'ready' }, startedAt);
    service.recordCaptureEvent('session-1', { type: 'started' }, startedAt);
    service.recordCaptureEvent('session-1', { type: 'paused' }, startedAt);

    await expect(service.endSession('session-1')).resolves.toMatchObject({
      ok: false,
      error: { code: 'invalid-state' },
    });

    service.recordCaptureEvent('session-1', { type: 'ended' }, startedAt);
    await expect(service.endSession('session-1')).resolves.toMatchObject({
      ok: true,
      data: { status: 'ended', captureState: 'ended' },
    });
  });
});
