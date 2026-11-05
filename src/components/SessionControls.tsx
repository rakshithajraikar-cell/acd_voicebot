import { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Circle,
  LoaderCircle,
  Mic,
  Pause,
  Play,
  RefreshCw,
  Square,
} from 'lucide-react';
import type { Session } from '../models/session';
import type { SessionServiceError } from '../services/sessionService';
import type { CaptureActionPending, CaptureActionResult } from '../services/mockCaptureService';
import type { NetworkStatus } from '../services/sessionService';
import type { SessionLoadingAction, SessionRequestState } from '../hooks/useMockSession';

type SessionControlsProps = {
  session: Session | null;
  onStart: () => void;
  onPauseCapture: () => CaptureActionResult;
  onResumeCapture: () => CaptureActionResult;
  onEnd: () => void;
  requestState: SessionRequestState;
  loadingAction: SessionLoadingAction;
  failedAction: SessionLoadingAction;
  error: SessionServiceError | null;
  captureError: string | null;
  captureActionPending: CaptureActionPending;
  networkStatus: NetworkStatus;
  onRetry: () => void;
  onSessionEnded: () => void;
};

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function SessionControls({
  session,
  onStart,
  onPauseCapture,
  onResumeCapture,
  onEnd,
  requestState,
  loadingAction,
  failedAction,
  error,
  captureError,
  captureActionPending,
  networkStatus,
  onRetry,
  onSessionEnded,
}: SessionControlsProps) {
  const endButtonRef = useRef<HTMLButtonElement>(null);
  const previousLoadingAction = useRef<SessionLoadingAction>(null);
  const previousError = useRef(error);
  const previousCaptureError = useRef(captureError);
  const sessionErrorRef = useRef<HTMLDivElement>(null);
  const retryButtonRef = useRef<HTMLButtonElement>(null);
  const captureErrorRef = useRef<HTMLSpanElement>(null);
  const pauseButtonRef = useRef<HTMLButtonElement>(null);
  const resumeButtonRef = useRef<HTMLButtonElement>(null);
  const captureFocusIntent = useRef<'pause' | 'resume' | null>(null);
  const previousCaptureState = useRef(session?.captureState ?? 'idle');
  const [captureAnnouncement, setCaptureAnnouncement] = useState('');
  const isLoading = requestState === 'loading';
  const isStarting = loadingAction === 'start';
  const isEnding = loadingAction === 'end';
  const isCapturePending = captureActionPending !== null;
  const status = session?.status ?? 'none';
  const statusLabel =
    status === 'none'
      ? 'No session'
      : status === 'active'
        ? 'Active'
        : status === 'ended'
          ? 'Ended'
          : 'Ready';
  const StatusIcon = status === 'active' || status === 'ended' ? CheckCircle2 : Circle;
  const timestampEntries = session
    ? [
        ['Created', session.createdAt],
        ...(session.startedAt ? [['Started', session.startedAt]] : []),
        ...(session.endedAt ? [['Ended', session.endedAt]] : []),
      ]
    : [];
  const canStart =
    session?.status === 'ready' ||
    (session?.status === 'active' && session.captureState === 'idle');
  const canEnd = session?.status === 'active';
  const isOffline = networkStatus === 'offline';
  const captureState = session?.captureState ?? 'idle';
  const canPauseCapture = captureState === 'capturing';
  const canResumeCapture = captureState === 'paused';
  const isCaptureTransitionPending = captureActionPending !== null;
  const captureStatus =
    captureState === 'capturing'
      ? 'capturing'
      : captureState === 'paused'
        ? 'paused'
        : captureState === 'ended'
          ? 'ended'
          : 'ready';
  const CaptureStatusIcon =
    captureStatus === 'capturing'
      ? Mic
      : captureStatus === 'paused'
        ? Pause
        : captureStatus === 'ended'
          ? Square
          : CheckCircle2;
  const captureStatusLabel =
    captureStatus === 'capturing'
      ? 'Capturing'
      : captureStatus === 'paused'
        ? 'Paused'
        : captureStatus === 'ended'
          ? 'Ended'
          : 'Ready';

  useEffect(() => {
    if (error && error !== previousError.current) {
      if (failedAction && !isOffline) {
        retryButtonRef.current?.focus();
      } else {
        sessionErrorRef.current?.focus();
      }
    }
    previousError.current = error;
  }, [error, failedAction, isOffline]);

  useEffect(() => {
    if (captureError && captureError !== previousCaptureError.current) {
      captureErrorRef.current?.focus();
    }
    previousCaptureError.current = captureError;
  }, [captureError]);

  useEffect(() => {
    const previousState = previousCaptureState.current;
    if (previousState !== captureState) {
      if (captureState === 'capturing') {
        setCaptureAnnouncement(
          previousState === 'paused' ? 'Capture resumed.' : 'Capture started.',
        );
      } else if (captureState === 'paused') {
        setCaptureAnnouncement('Capture paused.');
      } else if (captureState === 'ended') {
        setCaptureAnnouncement('Capture ended.');
      }
    }

    if (
      previousState === 'capturing' &&
      captureState === 'paused' &&
      captureFocusIntent.current === 'pause'
    ) {
      resumeButtonRef.current?.focus();
      captureFocusIntent.current = null;
    } else if (
      previousState === 'paused' &&
      captureState === 'capturing' &&
      captureFocusIntent.current === 'resume'
    ) {
      pauseButtonRef.current?.focus();
      captureFocusIntent.current = null;
    }
    previousCaptureState.current = captureState;
  }, [captureState]);

  useEffect(() => {
    if (loadingAction) {
      previousLoadingAction.current = loadingAction;
      return;
    }

    if (requestState !== 'success' || !previousLoadingAction.current) {
      return;
    }

    const completedAction = previousLoadingAction.current;
    previousLoadingAction.current = null;
    if (completedAction === 'start') {
      endButtonRef.current?.focus();
    } else if (completedAction === 'end') {
      onSessionEnded();
    }
  }, [loadingAction, onSessionEnded, requestState]);

  return (
    <section
      className="session-controls"
      aria-label="Session controls"
      aria-busy={isLoading || isCapturePending}
    >
      {(isLoading || isCapturePending) && (
        <div
          className="session-loading-announcement"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <LoaderCircle className="loading-spinner" size={15} aria-hidden="true" />
          <span>
            {loadingAction === 'create'
              ? 'Creating session…'
              : loadingAction === 'start'
                ? 'Starting session…'
                : loadingAction === 'end'
                  ? 'Ending session…'
                  : captureActionPending === 'starting'
                    ? 'Preparing capture…'
                    : captureActionPending === 'stopping'
                      ? 'Stopping capture…'
                      : captureActionPending === 'pausing'
                        ? 'Pausing capture…'
                        : captureActionPending === 'resuming'
                          ? 'Resuming capture…'
                          : 'Working…'}
          </span>
        </div>
      )}
      <div className={`session-status status-${status}`} role="status" aria-label="Session status">
        <StatusIcon size={15} aria-hidden="true" />
        <span>{statusLabel}</span>
      </div>
      {timestampEntries.length > 0 && (
        <dl className="session-timestamps" aria-label="Session timestamps">
          {timestampEntries.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>
                <time dateTime={value}>{formatTimestamp(value)}</time>
              </dd>
            </div>
          ))}
        </dl>
      )}
      {error && (
        <div
          ref={sessionErrorRef}
          className="session-error"
          role="alert"
          aria-live="assertive"
          tabIndex={-1}
        >
          <p>
            {failedAction === 'create'
              ? 'Couldn’t create session.'
              : failedAction === 'start'
                ? 'Couldn’t start session.'
                : failedAction === 'end'
                  ? 'Couldn’t end session.'
                  : 'Session request failed.'}{' '}
            {error.message}
          </p>
          {failedAction && (
            <button
              ref={retryButtonRef}
              className="button button-primary"
              type="button"
              aria-label="Retry session request"
              onClick={onRetry}
              disabled={isLoading || isOffline}
            >
              <RefreshCw size={14} aria-hidden="true" />
              Retry
            </button>
          )}
        </div>
      )}
      <div
        className={`capture-status-indicator capture-status-${captureStatus}`}
        role="status"
        aria-live="off"
        aria-atomic="true"
        aria-label="Capture status"
      >
        <CaptureStatusIcon size={18} aria-hidden="true" />
        <strong>{captureStatusLabel}</strong>
      </div>
      <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
        {captureAnnouncement}
      </div>
      {captureError && (
        <span ref={captureErrorRef} role="alert" aria-live="assertive" tabIndex={-1}>
          {captureError}
        </span>
      )}
      <p className="session-capture-disclosure" id="session-capture-disclosure">
        The demo does not save or transmit microphone audio.
      </p>
      <div className="session-actions">
        <button
          className="button button-primary"
          type="button"
          aria-label="Start session"
          aria-describedby="session-capture-disclosure"
          aria-busy={isStarting || captureActionPending === 'starting'}
          onClick={onStart}
          disabled={
            !canStart ||
            isLoading ||
            isOffline ||
            captureActionPending === 'starting' ||
            captureActionPending === 'stopping'
          }
        >
          {isStarting || captureActionPending === 'starting' ? (
            <LoaderCircle className="loading-spinner" size={15} aria-hidden="true" />
          ) : (
            <Play size={15} fill="currentColor" aria-hidden="true" />
          )}
          {isStarting ? 'Starting…' : 'Start'}
        </button>
        <button
          ref={pauseButtonRef}
          className="button button-outline"
          type="button"
          aria-label="Pause microphone capture"
          aria-busy={captureActionPending === 'pausing'}
          onClick={() => {
            captureFocusIntent.current = 'pause';
            onPauseCapture();
          }}
          disabled={!canPauseCapture || isLoading || isOffline || isCaptureTransitionPending}
        >
          <Pause size={15} aria-hidden="true" />
          Pause
        </button>
        <button
          ref={resumeButtonRef}
          className="button button-outline"
          type="button"
          aria-label="Resume microphone capture"
          aria-busy={captureActionPending === 'resuming'}
          onClick={() => {
            captureFocusIntent.current = 'resume';
            onResumeCapture();
          }}
          disabled={!canResumeCapture || isLoading || isOffline || isCaptureTransitionPending}
        >
          <Play size={15} aria-hidden="true" />
          Resume
        </button>
        <button
          ref={endButtonRef}
          className="button button-danger"
          type="button"
          aria-label="End or stop session"
          aria-busy={isEnding || captureActionPending === 'stopping'}
          onClick={onEnd}
          disabled={
            !canEnd ||
            isLoading ||
            isOffline ||
            captureActionPending === 'starting' ||
            captureActionPending === 'stopping'
          }
        >
          {isEnding || captureActionPending === 'stopping' ? (
            <LoaderCircle className="loading-spinner" size={14} aria-hidden="true" />
          ) : (
            <Square size={14} aria-hidden="true" />
          )}
          {captureActionPending === 'stopping' ? 'Stopping…' : isEnding ? 'Ending…' : 'End / Stop'}
        </button>
      </div>
    </section>
  );
}
