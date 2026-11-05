import { useEffect, useRef, useState } from 'react';
import {
  Check,
  CircleAlert,
  CircleHelp,
  LoaderCircle,
  LockKeyhole,
  Mic,
  MicOff,
  ShieldCheck,
} from 'lucide-react';
import { useMicrophonePermission } from '../hooks/useMicrophonePermission';
import type { MicrophonePermissionState } from '../services/microphonePermissionService';

const permissionCopy: Record<
  MicrophonePermissionState['status'],
  Readonly<{
    icon: typeof Mic;
    title: string;
    detail: string;
    guidance: string;
  }>
> = {
  'not-requested': {
    icon: Mic,
    title: 'Mock microphone is off',
    detail: 'No audio device is connected to this demo.',
    guidance: 'Select Enable mock microphone to simulate microphone readiness.',
  },
  requesting: {
    icon: LoaderCircle,
    title: 'Preparing mock microphone',
    detail: 'The local demo is updating its simulated microphone state.',
    guidance: 'No browser prompt or device access is involved.',
  },
  granted: {
    icon: Check,
    title: 'Mock microphone ready',
    detail: 'Microphone readiness is simulated locally.',
    guidance: 'No browser permission is requested and no audio is captured or transmitted.',
  },
  denied: {
    icon: CircleAlert,
    title: 'Microphone access denied',
    detail: 'The browser denied the microphone permission request.',
    guidance: 'This local mock state can be reset by refreshing the demo.',
  },
  unavailable: {
    icon: CircleHelp,
    title: 'Microphone access unsupported',
    detail: 'This browser does not provide the microphone access API.',
    guidance: 'Microphone access is not required for this mock demo.',
  },
  error: {
    icon: CircleAlert,
    title: 'Microphone request failed',
    detail: 'An unexpected error occurred while requesting microphone access.',
    guidance: 'Try again to reset the local mock microphone state.',
  },
};

function isFailureState(
  state: MicrophonePermissionState,
): state is Extract<MicrophonePermissionState, { reason: string }> {
  return 'reason' in state;
}

export function MicrophonePanel() {
  const { state, requestPermission } = useMicrophonePermission();
  const previousStatus = useRef(state.status);
  const requestButtonRef = useRef<HTMLButtonElement>(null);
  const permissionStatusRef = useRef<HTMLDivElement>(null);
  const shouldFocusPermissionStatus = useRef(false);
  const [statusAnnouncement, setStatusAnnouncement] = useState('');
  const [errorAnnouncement, setErrorAnnouncement] = useState('');
  const isFailure = isFailureState(state);
  const canRetry = state.status === 'denied' || state.status === 'error';
  const showControl = state.status !== 'granted' && state.status !== 'unavailable';
  const copy = permissionCopy[state.status];
  const StatusIcon = copy.icon;
  const detail = isFailure ? state.message : copy.detail;

  useEffect(() => {
    if (previousStatus.current === state.status) {
      return;
    }

    setStatusAnnouncement(
      state.status === 'requesting'
        ? 'Preparing mock microphone.'
        : state.status === 'granted'
          ? 'Microphone ready.'
          : state.status === 'unavailable'
            ? 'Microphone unavailable.'
            : '',
    );
    setErrorAnnouncement(
      state.status === 'denied'
        ? `Microphone denied. ${detail}`
        : state.status === 'error'
          ? `Microphone request failed. ${detail}`
          : '',
    );
    if (state.status === 'requesting' && shouldFocusPermissionStatus.current) {
      permissionStatusRef.current?.focus();
      shouldFocusPermissionStatus.current = false;
    }
    previousStatus.current = state.status;
  }, [detail, state.status]);

  return (
    <section
      className="panel microphone-panel"
      aria-labelledby="microphone-heading"
      aria-busy={state.status === 'requesting'}
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">VOICE INPUT</p>
          <h2 id="microphone-heading">Your microphone</h2>
        </div>
        <span className={`permission-icon permission-${state.status}`} aria-hidden="true">
          {state.status === 'denied' || state.status === 'error' ? (
            <MicOff size={17} />
          ) : (
            <StatusIcon size={17} />
          )}
        </span>
      </div>
      <div className={`permission-card permission-card-${state.status}`}>
        <div
          ref={permissionStatusRef}
          className="permission-copy"
          aria-live="off"
          aria-atomic="true"
          aria-busy={state.status === 'requesting'}
          tabIndex={-1}
        >
          <strong className={`permission-title permission-title-${state.status}`}>
            <StatusIcon size={15} aria-hidden="true" />
            {copy.title}
          </strong>
          <span>{detail}</span>
          <span id="microphone-next-step">{copy.guidance}</span>
        </div>
        {showControl && (
          <button
            ref={requestButtonRef}
            className="button button-mic"
            type="button"
            aria-busy={state.status === 'requesting'}
            aria-describedby="microphone-next-step microphone-privacy-disclosure"
            aria-label={
              state.status === 'requesting'
                ? 'Preparing mock microphone'
                : canRetry
                  ? 'Try again: mock microphone'
                  : 'Enable mock microphone'
            }
            onClick={() => {
              shouldFocusPermissionStatus.current =
                document.activeElement === requestButtonRef.current;
              void requestPermission();
            }}
            disabled={state.status === 'requesting'}
          >
            {state.status === 'requesting' ? (
              <LoaderCircle className="loading-spinner" size={14} aria-hidden="true" />
            ) : (
              <Mic size={14} aria-hidden="true" />
            )}
            {state.status === 'requesting'
              ? 'Working…'
              : canRetry
                ? 'Try again'
                : 'Enable mock microphone'}
          </button>
        )}
      </div>
      <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
        {statusAnnouncement}
      </div>
      {errorAnnouncement && (
        <div className="visually-hidden" role="alert" aria-live="assertive" aria-atomic="true">
          {errorAnnouncement}
        </div>
      )}
      <div className="privacy-note" id="microphone-privacy-disclosure">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          This demo does not request browser microphone permission, record audio, or transmit audio.
        </span>
        <LockKeyhole size={12} aria-hidden="true" />
      </div>
    </section>
  );
}
