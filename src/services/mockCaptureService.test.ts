import { describe, expect, it, vi } from 'vitest';
import { createMockCaptureService } from './mockCaptureService';

describe('mock capture service', () => {
  it('emits lifecycle events for start, pause, resume, and stop', async () => {
    const onEvent = vi.fn();
    const service = createMockCaptureService(onEvent);

    await expect(service.start()).resolves.toEqual({ ok: true });
    expect(service.pause()).toEqual({ ok: true });
    expect(service.resume()).toEqual({ ok: true });
    await expect(service.stop()).resolves.toEqual({ ok: true });

    expect(onEvent.mock.calls.map(([event]) => event.type)).toEqual([
      'ready',
      'started',
      'paused',
      'resumed',
      'ended',
    ]);
  });

  it('rejects invalid and duplicate transitions without emitting lifecycle events', async () => {
    const onEvent = vi.fn();
    const service = createMockCaptureService(onEvent);

    expect(service.pause()).toMatchObject({ ok: false });
    expect(service.resume()).toMatchObject({ ok: false });
    await service.start();
    expect(await service.start()).toMatchObject({ ok: false });
    expect(service.pause()).toEqual({ ok: true });
    expect(service.pause()).toMatchObject({ ok: false });
    expect(service.resume()).toEqual({ ok: true });
    await service.stop();
    expect(service.resume()).toMatchObject({ ok: false });
    expect(onEvent.mock.calls.map(([event]) => event.type)).toEqual([
      'ready',
      'started',
      'paused',
      'resumed',
      'ended',
    ]);
  });
});
