import type { CaptureLifecycleEvent, CaptureState } from '../models/session';

export type CaptureActionPending = 'starting' | 'pausing' | 'resuming' | 'stopping' | null;

export type CaptureActionResult = Readonly<{ ok: true }> | Readonly<{ ok: false; message: string }>;

export type MockCaptureService = Readonly<{
  start(): Promise<CaptureActionResult>;
  pause(): CaptureActionResult;
  resume(): CaptureActionResult;
  stop(): Promise<CaptureActionResult>;
}>;

const success: CaptureActionResult = { ok: true };

function failure(message: string): CaptureActionResult {
  return { ok: false, message };
}

/**
 * Simulates capture lifecycle events locally without accessing a microphone or network.
 */
export function createMockCaptureService(
  onEvent: (event: CaptureLifecycleEvent) => void,
): MockCaptureService {
  let state: CaptureState = 'idle';

  async function start(): Promise<CaptureActionResult> {
    if (state !== 'idle') {
      return failure(`Capture cannot start while ${state}.`);
    }

    state = 'ready';
    onEvent({ type: 'ready' });
    state = 'capturing';
    onEvent({ type: 'started' });
    return success;
  }

  function pause(): CaptureActionResult {
    if (state !== 'capturing') {
      return failure('Capture can only be paused while capturing.');
    }

    state = 'paused';
    onEvent({ type: 'paused' });
    return success;
  }

  function resume(): CaptureActionResult {
    if (state !== 'paused') {
      return failure('Capture can only be resumed while paused.');
    }

    state = 'capturing';
    onEvent({ type: 'resumed' });
    return success;
  }

  async function stop(): Promise<CaptureActionResult> {
    if (state === 'ended') {
      return failure('Capture has already ended.');
    }

    state = 'ended';
    onEvent({ type: 'ended' });
    return success;
  }

  return { start, pause, resume, stop };
}
