import { describe, expect, it, vi } from 'vitest';
import { createMicrophonePermissionService } from './microphonePermissionService';

describe('microphone permission service', () => {
  it('reports unavailable when microphone access is unsupported', async () => {
    const service = createMicrophonePermissionService();

    await expect(service.requestPermission()).resolves.toMatchObject({
      status: 'unavailable',
      reason: 'unsupported',
    });
  });

  it('reports unavailable when getUserMedia is missing', async () => {
    const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { mediaDevices: {} },
    });

    try {
      await expect(createMicrophonePermissionService().requestPermission()).resolves.toMatchObject({
        status: 'unavailable',
        reason: 'unsupported',
      });
    } finally {
      if (navigatorDescriptor) {
        Object.defineProperty(globalThis, 'navigator', navigatorDescriptor);
      } else {
        Reflect.deleteProperty(globalThis, 'navigator');
      }
    }
  });

  it.each([
    ['NotAllowedError', 'denied', 'permission-denied'],
    ['NotFoundError', 'error', 'unexpected'],
    ['NotReadableError', 'error', 'unexpected'],
    ['SecurityError', 'error', 'unexpected'],
    ['UnknownError', 'error', 'unexpected'],
  ] as const)(
    'maps %s into a typed %s state',
    async (errorName, expectedStatus, expectedReason) => {
      const getUserMedia = vi.fn(async () => {
        throw Object.assign(new Error('Browser permission failure.'), { name: errorName });
      });
      const service = createMicrophonePermissionService({ getUserMedia });

      await expect(service.requestPermission()).resolves.toMatchObject({
        status: expectedStatus,
        reason: expectedReason,
        message: expect.any(String),
      });
    },
  );

  it('sets granted only after getUserMedia resolves', async () => {
    const getUserMedia = vi.fn(async () => ({
      getTracks: () => [{ stop: vi.fn() }],
    }));
    const service = createMicrophonePermissionService({ getUserMedia });

    await expect(service.requestPermission()).resolves.toEqual({ status: 'granted' });
    expect(getUserMedia).toHaveBeenCalledOnce();
  });
});
