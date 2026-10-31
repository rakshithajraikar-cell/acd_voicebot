import { useRef, useState } from 'react';
import {
  createMicrophonePermissionService,
  type MicrophonePermissionState,
} from '../services/microphonePermissionService';

/**
 * Owns microphone permission state transitions for the React UI.
 */
export function useMicrophonePermission() {
  const [service] = useState(() => createMicrophonePermissionService());
  const [state, setState] = useState<MicrophonePermissionState>({ status: 'not-requested' });
  const requestInProgress = useRef(false);

  async function requestPermission(): Promise<void> {
    if (requestInProgress.current || state.status === 'granted') {
      return;
    }

    requestInProgress.current = true;
    setState({ status: 'requesting' });
    try {
      setState(await service.requestPermission());
    } finally {
      requestInProgress.current = false;
    }
  }

  return { state, requestPermission } as const;
}
