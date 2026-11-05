import { useRef, useState } from 'react';
import {
  createSession as createSessionModel,
  endSession as endSessionModel,
  startSession as startSessionModel,
} from '../models/session';
import type { CaptureLifecycleEvent, Session } from '../models/session';
import {
  createMockCaptureService,
  type MockCaptureService,
  type CaptureActionPending,
  type CaptureActionResult,
} from '../services/mockCaptureService';
import { createMockSessionService } from '../services/sessionService';
import type { SessionServiceError, SessionServiceResult } from '../services/sessionService';
import { useNetworkStatus } from './useNetworkStatus';

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
  const { networkStatus, setNetworkStatus } = useNetworkStatus(service.setNetworkStatus);
  const [requestState, setRequestState] = useState<SessionRequestState>('idle');
  const [loadingAction, setLoadingAction] = useState<SessionLoadingAction>(null);
  const [failedAction, setFailedAction] = useState<SessionLoadingAction>(null);
  const [error, setError] = useState<SessionServiceError | null>(null);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [captureActionPending, setCaptureActionPending] = useState<CaptureActionPending>(null);
  const requestInProgress = useRef(false);
  const captureActionPendingRef = useRef<CaptureActionPending>(null);
  const captureServiceRef = useRef<MockCaptureService | null>(null);
  const sessionIdRef = useRef(session?.id ?? null);
  const captureSessionRef = useRef(session);
  sessionIdRef.current = session?.id ?? null;

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
        setFailedAction(action);
        setError(result.error);
        return result;
      }

      setSession(result.data);
      setRequestState('success');
      setFailedAction(null);
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
    if (
      !session ||
      (session.status !== 'ready' &&
        !(session.status === 'active' && session.captureState === 'idle')) ||
      requestInProgress.current ||
      captureActionPendingRef.current !== null
    ) {
      return null;
    }

    sessionIdRef.current = session.id;
    const startedSession =
      session.status === 'ready'
        ? await perform(
            'start',
            () => service.startSession(session.id),
            startSessionModel(session, new Date()),
          )
        : { ok: true as const, data: session };
    if (!startedSession?.ok) return startedSession;

    setPendingCaptureAction('starting');
    const captureResult = await getCaptureService().start();
    if (!captureResult.ok) setPendingCaptureAction(null);
    setCaptureError(captureResult.ok ? null : captureResult.message);
    return startedSession;
  }

  async function endSession(): Promise<SessionServiceResult<Session> | null> {
    if (
      !session ||
      session.status !== 'active' ||
      requestInProgress.current ||
      captureActionPendingRef.current === 'stopping'
    ) {
      return null;
    }

    if (session.captureState !== 'ended' && session.captureState !== 'idle') {
      setPendingCaptureAction('stopping');
      const captureResult = await getCaptureService().stop();
      setPendingCaptureAction(null);
      if (!captureResult.ok) {
        setCaptureError(captureResult.message);
        return {
          ok: false,
          error: { code: 'invalid-state', message: captureResult.message },
        };
      }
    }

    const endedAt = new Date();
    const currentSession =
      captureSessionRef.current?.id === session.id ? captureSessionRef.current : session;
    const optimisticSession = endSessionModel(currentSession, endedAt);
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
      setFailedAction(null);
      setError(null);
      setRequestState((current) => (current === 'error' ? 'idle' : current));
    } else {
      setFailedAction(null);
      setError(result.error);
      setRequestState('error');
    }
    return result;
  }

  function setContextSourceEnabled(
    sourceId: string,
    enabled: boolean,
  ): SessionServiceResult<Session> {
    if (!session) {
      const missingSession: SessionServiceResult<Session> = {
        ok: false,
        error: { code: 'not-found', message: 'This session could not be found.' },
      };
      setError(missingSession.error);
      setRequestState('error');
      return missingSession;
    }

    const result = service.setContextSourceEnabled(session.id, sourceId, enabled);
    if (result.ok) {
      setSession(result.data);
      setError(null);
      setRequestState((current) => (current === 'error' ? 'idle' : current));
    } else {
      setFailedAction(null);
      setError(result.error);
      setRequestState('error');
    }
    return result;
  }

  /** Apply only lifecycle events emitted by the capture service, never button intent. */
  function recordCaptureEvent(event: CaptureLifecycleEvent): SessionServiceResult<Session> {
    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      const missingSession: SessionServiceResult<Session> = {
        ok: false,
        error: { code: 'not-found', message: 'This session could not be found.' },
      };
      setError(missingSession.error);
      setRequestState('error');
      return missingSession;
    }

    const result = service.recordCaptureEvent(sessionId, event);
    if (result.ok) {
      captureSessionRef.current = result.data;
      setSession(result.data);
      setError(null);
      if (event.type === 'started' || event.type === 'paused' || event.type === 'resumed') {
        setPendingCaptureAction(null);
      } else if (event.type === 'ended' && captureActionPendingRef.current !== 'stopping') {
        setPendingCaptureAction(null);
      }
      setRequestState((current) => (current === 'error' ? 'idle' : current));
    } else {
      setFailedAction(null);
      setError(result.error);
      setRequestState('error');
    }
    return result;
  }

  function getCaptureService(): MockCaptureService {
    captureServiceRef.current ??= createMockCaptureService((event) => {
      recordCaptureEvent(event);
    });
    return captureServiceRef.current;
  }

  function setPendingCaptureAction(action: CaptureActionPending): void {
    captureActionPendingRef.current = action;
    setCaptureActionPending(action);
  }

  function updateCaptureActionResult(result: CaptureActionResult): CaptureActionResult {
    setCaptureError(result.ok ? null : result.message);
    return result;
  }

  function pauseCapture(): CaptureActionResult {
    if (captureActionPendingRef.current !== null) {
      return updateCaptureActionResult({
        ok: false,
        message: 'A microphone capture transition is already in progress.',
      });
    }

    setPendingCaptureAction('pausing');
    const result = getCaptureService().pause();
    if (!result.ok) setPendingCaptureAction(null);
    return updateCaptureActionResult(result);
  }

  function resumeCapture(): CaptureActionResult {
    if (captureActionPendingRef.current !== null) {
      return updateCaptureActionResult({
        ok: false,
        message: 'A microphone capture transition is already in progress.',
      });
    }

    setPendingCaptureAction('resuming');
    const result = getCaptureService().resume();
    if (!result.ok) setPendingCaptureAction(null);
    return updateCaptureActionResult(result);
  }

  function retryFailedAction(): void {
    if (!failedAction || requestInProgress.current || networkStatus === 'offline') {
      return;
    }

    if (failedAction === 'create') void createSession();
    else if (failedAction === 'start') void startSession();
    else if (failedAction === 'end') void endSession();
  }

  return {
    session,
    networkStatus,
    setNetworkStatus,
    requestState,
    loadingAction,
    failedAction,
    error,
    captureError,
    captureActionPending,
    isLoading: requestState === 'loading',
    createSession,
    startSession,
    endSession,
    pauseCapture,
    resumeCapture,
    renameSession,
    setContextSourceEnabled,
    retryFailedAction,
  } as const;
}
