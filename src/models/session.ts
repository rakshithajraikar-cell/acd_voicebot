/**
 * Lifecycle states for a session.
 */
export type SessionStatus = 'ready' | 'active' | 'ended';

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
  /** Creation time as an ISO 8601 timestamp. */
  createdAt: string;
  /** Start time as an ISO 8601 timestamp, or null before the session starts. */
  startedAt: string | null;
  /** End time as an ISO 8601 timestamp, or null until the session ends. */
  endedAt: string | null;
}>;

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
    createdAt: createdAt.toISOString(),
    startedAt: null,
    endedAt: null,
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
