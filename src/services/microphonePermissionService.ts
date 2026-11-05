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

/**
 * Creates a permission-state simulator that never requests access to a physical device.
 */
export function createMicrophonePermissionService(): MicrophonePermissionService {
  async function requestPermission(): Promise<MicrophonePermissionResult> {
    await new Promise<void>((resolve) => setTimeout(resolve, 180));
    return { status: 'granted' };
  }

  return { requestPermission };
}
