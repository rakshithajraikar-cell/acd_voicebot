import { useRef, useState } from 'react';
import {
  createSession as createSessionModel,
  endSession as endSessionModel,
  startSession as startSessionModel,
} from '../models/session';
import type { Session } from '../models/session';
import { createMockSessionService } from '../services/sessionService';
import type { SessionServiceError, SessionServiceResult } from '../services/sessionService';

export type SessionRequestState = 'idle' | 'loading' | 'success' | 'error';
export type SessionLoadingAction = 'create' | 'start' | 'end' | null;

/**
 * Owns session service state and lifecycle actions for the UI.
 */
export function useMockSession(
  initialSession: Session | null = createSessionModel('session-demo', 'Product design review'),
) {
  const [service] = useState(() => createMockSessionService({ initialSession }));
  const [session, setSession] = useState<Session | null>(service.initialSession);
  const [requestState, setRequestState] = useState<SessionRequestState>('idle');
  const [loadingAction, setLoadingAction] = useState<SessionLoadingAction>(null);
  const [error, setError] = useState<SessionServiceError | null>(null);
  const requestInProgress = useRef(false);

  async function perform(
    action: Exclude<SessionLoadingAction, null>,
    operation: () => Promise<SessionServiceResult<Session>>,
    optimisticSession: Session | null,
  ): Promise<SessionServiceResult<Session> | null> {
    if (requestInProgress.current) {
      return null;
    }

    const previousSession = session;
    requestInProgress.current = true;
    setRequestState('loading');
    setLoadingAction(action);
    setError(null);
    setSession(optimisticSession);

    try {
      const result = await operation();
      if (!result.ok) {
        setSession(previousSession);
        setRequestState('error');
        setError(result.error);
        return result;
      }

      setSession(result.data);
      setRequestState('success');
      return result;
    } finally {
      requestInProgress.current = false;
      setLoadingAction(null);
    }
  }

  async function createSession(): Promise<SessionServiceResult<Session> | null> {
    const createdAt = new Date();
    const id = globalThis.crypto.randomUUID();
    const optimisticSession = createSessionModel(id, 'Untitled session', createdAt);
    return perform(
      'create',
      () => service.createSession(optimisticSession.title, id, createdAt),
      optimisticSession,
    );
  }

  async function startSession(): Promise<SessionServiceResult<Session> | null> {
    if (!session || session.status !== 'ready') {
      return null;
    }

    const startedAt = new Date();
    const optimisticSession = startSessionModel(session, startedAt);
    return perform('start', () => service.startSession(session.id, startedAt), optimisticSession);
  }

  async function endSession(): Promise<SessionServiceResult<Session> | null> {
    if (!session || session.status !== 'active') {
      return null;
    }

    const endedAt = new Date();
    const optimisticSession = endSessionModel(session, endedAt);
    return perform('end', () => service.endSession(session.id, endedAt), optimisticSession);
  }

  function renameSession(title: string): SessionServiceResult<Session> {
    if (!session) {
      const missingSession: SessionServiceResult<Session> = {
        ok: false,
        error: { code: 'not-found', message: 'This session could not be found.' },
      };
      setError(missingSession.error);
      setRequestState('error');
      return missingSession;
    }

    const result = service.renameSession(session.id, title);
    if (result.ok) {
      setSession(result.data);
      setError(null);
      if (requestState === 'error') {
        setRequestState('idle');
      }
    } else {
      setError(result.error);
      setRequestState('error');
    }
    return result;
  }

  return {
    session,
    requestState,
    loadingAction,
    error,
    isLoading: requestState === 'loading',
    createSession,
    startSession,
    endSession,
    renameSession,
  } as const;
}
