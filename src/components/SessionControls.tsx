import { useEffect, useRef } from 'react';
import { CheckCircle2, Circle, Play, Square } from 'lucide-react';
import type { Session } from '../models/session';
import type { SessionServiceError } from '../services/sessionService';
import type { SessionLoadingAction, SessionRequestState } from '../hooks/useMockSession';

type SessionControlsProps = {
  session: Session | null;
  onStart: () => void;
  onEnd: () => void;
  requestState: SessionRequestState;
  loadingAction: SessionLoadingAction;
  error: SessionServiceError | null;
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
  onEnd,
  requestState,
  loadingAction,
  error,
  onSessionEnded,
}: SessionControlsProps) {
  const endButtonRef = useRef<HTMLButtonElement>(null);
  const previousLoadingAction = useRef<SessionLoadingAction>(null);
  const isLoading = requestState === 'loading';
  const isStarting = loadingAction === 'start';
  const isEnding = loadingAction === 'end';
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
  const canStart = session?.status === 'ready';
  const canEnd = session?.status === 'active';

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
    <section className="session-controls" aria-label="Session controls" aria-busy={isLoading}>
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
      {error && <span role="alert">{error.message}</span>}
      <div className="session-actions">
        <button
          className="button button-primary"
          type="button"
          aria-label="Start session"
          aria-busy={isStarting}
          onClick={onStart}
          disabled={!canStart || isLoading}
        >
          <Play size={15} fill="currentColor" aria-hidden="true" />
          {isStarting ? 'Starting…' : 'Start'}
        </button>
        <button
          ref={endButtonRef}
          className="button button-danger"
          type="button"
          aria-label="End or stop session"
          aria-busy={isEnding}
          onClick={onEnd}
          disabled={!canEnd || isLoading}
        >
          <Square size={14} aria-hidden="true" />
          {isEnding ? 'Ending…' : 'End / Stop'}
        </button>
      </div>
    </section>
  );
}
