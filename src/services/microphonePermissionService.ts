export type MicrophonePermissionFailureReason = 'unsupported' | 'permission-denied' | 'unexpected';

export type MicrophonePermissionState =
  | Readonly<{ status: 'not-requested' }>
  | Readonly<{ status: 'requesting' }>
  | Readonly<{ status: 'granted' }>
  | Readonly<{
      status: 'denied';
      reason: 'permission-denied';
      message: string;
    }>
  | Readonly<{
      status: 'unavailable';
      reason: 'unsupported';
      message: string;
    }>
  | Readonly<{
      status: 'error';
      reason: 'unexpected';
      message: string;
    }>;

export type MicrophonePermissionResult = Exclude<
  MicrophonePermissionState,
  { status: 'not-requested' } | { status: 'requesting' }
>;

export type MicrophonePermissionService = Readonly<{
  requestPermission(): Promise<MicrophonePermissionResult>;
}>;

type MicrophonePermissionServiceOptions = Readonly<{
  getUserMedia?: (constraints: MediaStreamConstraints) => Promise<MicrophoneStream>;
}>;

type MicrophoneStream = Readonly<{
  getTracks(): readonly Readonly<{ stop(): void }>[];
}>;

function getErrorName(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'name' in error) {
    return typeof error.name === 'string' ? error.name : undefined;
  }
  return undefined;
}

function getErrorMessage(error: unknown): string | undefined {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return undefined;
}

function mapPermissionError(error: unknown): MicrophonePermissionResult {
  const errorName = getErrorName(error);
  if (errorName === 'NotAllowedError') {
    return {
      status: 'denied',
      reason: 'permission-denied',
      message: 'Microphone access was denied. Allow it in browser settings, then try again.',
    };
  }
  return {
    status: 'error',
    reason: 'unexpected',
    message: getErrorMessage(error) ?? 'An unexpected error occurred while requesting access.',
  };
}

/**
 * Creates a local browser-permission service; any acquired audio stream is stopped immediately.
 */
export function createMicrophonePermissionService(
  options: MicrophonePermissionServiceOptions = {},
): MicrophonePermissionService {
  async function requestPermission(): Promise<MicrophonePermissionResult> {
    const mediaDevices = typeof navigator !== 'undefined' ? navigator.mediaDevices : undefined;
    const browserGetUserMedia = mediaDevices?.getUserMedia;
    const getUserMedia =
      options.getUserMedia ??
      (typeof browserGetUserMedia === 'function'
        ? browserGetUserMedia.bind(mediaDevices)
        : undefined);
    if (!getUserMedia) {
      return {
        status: 'unavailable',
        reason: 'unsupported',
        message: 'This browser does not provide the microphone access API.',
      };
    }

    let stream: MicrophoneStream;
    try {
      stream = await getUserMedia({ audio: true });
    } catch (error) {
      return mapPermissionError(error);
    }

    try {
      for (const track of stream.getTracks()) {
        try {
          track.stop();
        } catch (error) {
          console.error('Failed to stop a microphone track after permission was granted.', error);
        }
      }
    } catch (error) {
      console.error('Failed to retrieve microphone tracks after permission was granted.', error);
    }
    return { status: 'granted' };
  }

  return { requestPermission };
}
