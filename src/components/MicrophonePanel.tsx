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
    title: 'Microphone is off',
    detail: 'Microphone permission has not been requested.',
    guidance: 'Select Enable microphone when you are ready for your browser to ask for access.',
  },
  requesting: {
    icon: LoaderCircle,
    title: 'Waiting for permission',
    detail: 'Your browser is waiting for a permission decision.',
    guidance:
      'Choose Allow in the browser prompt. If it is not visible, check your browser settings.',
  },
  granted: {
    icon: Check,
    title: 'Microphone access granted',
    detail: 'Your browser confirmed microphone access.',
    guidance: 'This mock flow does not record, upload, or transmit audio.',
  },
  denied: {
    icon: CircleAlert,
    title: 'Microphone access denied',
    detail: 'The browser denied the microphone permission request.',
    guidance: 'Allow microphone access in your browser site permissions, then try again.',
  },
  unavailable: {
    icon: CircleHelp,
    title: 'Microphone access unsupported',
    detail: 'This browser does not provide the microphone access API.',
    guidance: 'Use a supported browser with microphone access enabled.',
  },
  error: {
    icon: CircleAlert,
    title: 'Microphone request failed',
    detail: 'An unexpected error occurred while requesting microphone access.',
    guidance: 'Try again. If the problem continues, check browser permissions and your microphone.',
  },
};

function isFailureState(
  state: MicrophonePermissionState,
): state is Extract<MicrophonePermissionState, { reason: string }> {
  return 'reason' in state;
}

export function MicrophonePanel() {
  const { state, requestPermission } = useMicrophonePermission();
  const isFailure = isFailureState(state);
  const canRetry = state.status === 'denied' || state.status === 'error';
  const showControl = state.status !== 'granted' && state.status !== 'unavailable';
  const copy = permissionCopy[state.status];
  const StatusIcon = copy.icon;
  const detail = isFailure ? state.message : copy.detail;

  return (
    <section className="panel microphone-panel" aria-labelledby="microphone-heading">
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
          className="permission-copy"
          role="status"
          aria-live="polite"
          aria-atomic="true"
          aria-busy={state.status === 'requesting'}
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
            className="button button-mic"
            type="button"
            aria-describedby="microphone-next-step microphone-privacy-disclosure"
            aria-label={
              state.status === 'requesting'
                ? 'Requesting microphone permission'
                : canRetry
                  ? 'Try again: microphone permission'
                  : 'Enable microphone'
            }
            onClick={requestPermission}
            disabled={state.status === 'requesting'}
          >
            <Mic size={14} aria-hidden="true" />
            {state.status === 'requesting'
              ? 'Requesting…'
              : canRetry
                ? 'Try again'
                : 'Enable microphone'}
          </button>
        )}
      </div>
      <div className="privacy-note" id="microphone-privacy-disclosure">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>
          To use this feature, your browser will ask for microphone access. This week’s mock flow
          does not record, upload, or transmit audio.
        </span>
        <LockKeyhole size={12} aria-hidden="true" />
      </div>
    </section>
  );
}
