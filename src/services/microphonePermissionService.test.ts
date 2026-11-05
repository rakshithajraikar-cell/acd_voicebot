import { describe, expect, it, vi } from 'vitest';
import { createMicrophonePermissionService } from './microphonePermissionService';

describe('mock microphone permission service', () => {
  it('simulates readiness without consulting browser media APIs', async () => {
    const getUserMedia = vi.fn();
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal('navigator', testNavigator);

    await expect(createMicrophonePermissionService().requestPermission()).resolves.toEqual({
      status: 'granted',
    });
    expect(getUserMedia).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
