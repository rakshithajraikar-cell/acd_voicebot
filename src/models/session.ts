/**
 * Lifecycle states for a session.
 */
export type SessionStatus = 'ready' | 'active' | 'ended';

export type CaptureState = 'idle' | 'ready' | 'capturing' | 'paused' | 'ended';

export type ContextSource = Readonly<{
  id: string;
  label: string;
  type: 'screen' | 'file' | 'note' | 'other';
  enabled: boolean;
}>;

export type ContextPanelState = Readonly<{
  sources: readonly ContextSource[];
}>;

export type CaptureLifecycleEvent =
  | Readonly<{ type: 'ready' }>
  | Readonly<{ type: 'started' }>
  | Readonly<{ type: 'paused' }>
  | Readonly<{ type: 'resumed' }>
  | Readonly<{ type: 'ended' }>;

export type CaptureTransitionResult =
  | Readonly<{ ok: true; session: Session }>
  | Readonly<{
      ok: false;
      state: CaptureState;
      event: CaptureLifecycleEvent['type'];
    }>;

/**
 * Immutable local model for one Co-Pilot session.
 */
export type Session = Readonly<{
  /** Stable identifier for this session. */
  id: string;
  /** Human-readable session title. */
  title: string;
  /** Current lifecycle state. */
  status: SessionStatus;
  /** State reported by the capture lifecycle, independent of session status. */
  captureState: CaptureState;
  /** Creation time as an ISO 8601 timestamp. */
  createdAt: string;
  /** Start time as an ISO 8601 timestamp, or null before the session starts. */
  startedAt: string | null;
  /** End time as an ISO 8601 timestamp, or null until the session ends. */
  endedAt: string | null;
  /** Most recent time the capture entered the paused state. */
  pausedAt: string | null;
  /** Most recent time capture resumed after being paused. */
  resumedAt: string | null;
  /** Context sources and their explicit user-controlled enabled state. */
  contextPanel: ContextPanelState;
}>;

export function createDefaultContextPanel(): ContextPanelState {
  return {
    sources: [{ id: 'screen-context', label: 'Screen context', type: 'screen', enabled: false }],
  };
}

const captureTransitions: Readonly<Record<CaptureState, readonly CaptureLifecycleEvent['type'][]>> =
  {
    idle: ['ready', 'ended'],
    ready: ['started', 'ended'],
    capturing: ['paused', 'ended'],
    paused: ['resumed', 'ended'],
    ended: [],
  };

export function applyCaptureLifecycleEvent(
  session: Session,
  event: CaptureLifecycleEvent,
  occurredAt = new Date(),
): CaptureTransitionResult {
  if (!captureTransitions[session.captureState].includes(event.type)) {
    return { ok: false, state: session.captureState, event: event.type };
  }

  const timestamp = occurredAt.toISOString();
  const captureState: CaptureState =
    event.type === 'ready'
      ? 'ready'
      : event.type === 'started' || event.type === 'resumed'
        ? 'capturing'
        : event.type === 'paused'
          ? 'paused'
          : 'ended';

  return {
    ok: true,
    session: {
      ...session,
      captureState,
      pausedAt: event.type === 'paused' ? timestamp : session.pausedAt,
      resumedAt: event.type === 'resumed' ? timestamp : session.resumedAt,
    },
  };
}

/**
 * Creates a ready session without making any network requests.
 *
 * @param id Stable identifier assigned by the caller.
 * @param title Human-readable title for the session.
 * @param createdAt Creation time; defaults to the current time.
 */
export function createSession(id: string, title: string, createdAt = new Date()): Session {
  return {
    id,
    title,
    status: 'ready',
    captureState: 'idle',
    createdAt: createdAt.toISOString(),
    startedAt: null,
    endedAt: null,
    pausedAt: null,
    resumedAt: null,
    contextPanel: createDefaultContextPanel(),
  };
}

/**
 * Returns a new session value marked active, leaving the input unchanged.
 *
 * @param session Session to start.
 * @param startedAt Start time; defaults to the current time.
 */
export function startSession(session: Session, startedAt = new Date()): Session {
  return {
    ...session,
    status: 'active',
    startedAt: startedAt.toISOString(),
    endedAt: null,
  };
}

/**
 * Returns a new session value with an updated title, leaving the input unchanged.
 *
 * @param session Session to update.
 * @param title New human-readable title.
 */
export function updateSessionTitle(session: Session, title: string): Session {
  return { ...session, title };
}

/**
 * Returns a new session value marked ended, leaving the input unchanged.
 *
 * @param session Session to end.
 * @param endedAt End time; defaults to the current time.
 */
export function endSession(session: Session, endedAt = new Date()): Session {
  return {
    ...session,
    status: 'ended',
    endedAt: endedAt.toISOString(),
  };
}
