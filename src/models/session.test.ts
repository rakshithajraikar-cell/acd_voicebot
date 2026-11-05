import { describe, expect, it } from 'vitest';
import {
  applyCaptureLifecycleEvent,
  createSession,
  endSession,
  startSession,
  updateSessionTitle,
} from './session';

describe('Session model', () => {
  const createdAt = new Date('2026-10-30T00:00:00.000Z');

  it('creates a ready session with ISO timestamps and unset lifecycle times', () => {
    expect(createSession('session-1', 'Planning', createdAt)).toEqual({
      id: 'session-1',
      title: 'Planning',
      status: 'ready',
      captureState: 'idle',
      createdAt: '2026-10-30T00:00:00.000Z',
      startedAt: null,
      endedAt: null,
      pausedAt: null,
      resumedAt: null,
      contextPanel: {
        sources: [
          { id: 'screen-context', label: 'Screen context', type: 'screen', enabled: false },
        ],
      },
    });
  });

  it('updates titles immutably', () => {
    const original = createSession('session-1', 'Planning', createdAt);
    const updated = updateSessionTitle(original, 'Design review');

    expect(updated).not.toBe(original);
    expect(updated.title).toBe('Design review');
    expect(original.title).toBe('Planning');
  });

  it('starts and ends sessions with immutable lifecycle updates', () => {
    const original = createSession('session-1', 'Planning', createdAt);
    const started = startSession(original, new Date('2026-10-30T00:05:00.000Z'));
    const ended = endSession(started, new Date('2026-10-30T00:10:00.000Z'));

    expect(started).not.toBe(original);
    expect(started).toMatchObject({
      status: 'active',
      startedAt: '2026-10-30T00:05:00.000Z',
      endedAt: null,
    });
    expect(ended).not.toBe(started);
    expect(ended).toMatchObject({
      status: 'ended',
      startedAt: '2026-10-30T00:05:00.000Z',
      endedAt: '2026-10-30T00:10:00.000Z',
    });
    expect(original).toMatchObject({ status: 'ready', startedAt: null, endedAt: null });
    expect(ended.captureState).toBe('idle');
    expect(ended.contextPanel.sources[0].enabled).toBe(false);
    expect(started.contextPanel.sources[0].enabled).toBe(false);
  });

  it('updates capture state and pause/resume timestamps from lifecycle events', () => {
    const original = createSession('session-1', 'Planning', createdAt);
    const ready = applyCaptureLifecycleEvent(original, { type: 'ready' }, createdAt);
    expect(ready).toMatchObject({ ok: true, session: { captureState: 'ready' } });
    if (!ready.ok) return;

    const started = applyCaptureLifecycleEvent(ready.session, { type: 'started' }, createdAt);
    expect(started).toMatchObject({ ok: true, session: { captureState: 'capturing' } });
    if (!started.ok) return;

    const pausedAt = new Date('2026-10-30T00:05:00.000Z');
    const paused = applyCaptureLifecycleEvent(started.session, { type: 'paused' }, pausedAt);
    expect(paused).toMatchObject({
      ok: true,
      session: { captureState: 'paused', pausedAt: pausedAt.toISOString(), resumedAt: null },
    });
    if (!paused.ok) return;

    const resumedAt = new Date('2026-10-30T00:06:00.000Z');
    const resumed = applyCaptureLifecycleEvent(paused.session, { type: 'resumed' }, resumedAt);
    expect(resumed).toMatchObject({
      ok: true,
      session: {
        captureState: 'capturing',
        pausedAt: pausedAt.toISOString(),
        resumedAt: resumedAt.toISOString(),
      },
    });
    expect(original).toMatchObject({
      captureState: 'idle',
      pausedAt: null,
      resumedAt: null,
    });
  });

  it('rejects capture events that do not match the current lifecycle state', () => {
    const original = createSession('session-1', 'Planning', createdAt);

    expect(applyCaptureLifecycleEvent(original, { type: 'paused' }, createdAt)).toEqual({
      ok: false,
      state: 'idle',
      event: 'paused',
    });
  });
});
