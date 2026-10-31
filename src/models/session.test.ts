import { describe, expect, it } from 'vitest';
import { createSession, endSession, startSession, updateSessionTitle } from './session';

describe('Session model', () => {
  const createdAt = new Date('2026-10-30T00:00:00.000Z');

  it('creates a ready session with ISO timestamps and unset lifecycle times', () => {
    expect(createSession('session-1', 'Planning', createdAt)).toEqual({
      id: 'session-1',
      title: 'Planning',
      status: 'ready',
      createdAt: '2026-10-30T00:00:00.000Z',
      startedAt: null,
      endedAt: null,
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
  });
});
