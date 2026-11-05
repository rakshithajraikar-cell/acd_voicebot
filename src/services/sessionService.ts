import {
  createSession as createSessionModel,
  applyCaptureLifecycleEvent,
  endSession as endSessionModel,
  startSession as startSessionModel,
  updateSessionTitle,
} from '../models/session';
import type { CaptureLifecycleEvent, ContextSource, Session } from '../models/session';

export type SessionServiceError = Readonly<{
  code: 'not-found' | 'invalid-state' | 'invalid-title';
  message: string;
}>;

export type SessionServiceResult<T> =
  Readonly<{ ok: true; data: T }> | Readonly<{ ok: false; error: SessionServiceError }>;

export type NetworkStatus = 'online' | 'offline';

export type SessionService = Readonly<{
  initialSession: Session | null;
  networkStatus: NetworkStatus;
  createSession(
    title: string,
    id?: string,
    createdAt?: Date,
  ): Promise<SessionServiceResult<Session>>;
  startSession(sessionId: string, startedAt?: Date): Promise<SessionServiceResult<Session>>;
  endSession(sessionId: string, endedAt?: Date): Promise<SessionServiceResult<Session>>;
  recordCaptureEvent(
    sessionId: string,
    event: CaptureLifecycleEvent,
    occurredAt?: Date,
  ): SessionServiceResult<Session>;
  renameSession(sessionId: string, title: string): SessionServiceResult<Session>;
  setContextSourceEnabled(
    sessionId: string,
    sourceId: string,
    enabled: boolean,
  ): SessionServiceResult<Session>;
  getEnabledContextSources(sessionId: string): SessionServiceResult<readonly ContextSource[]>;
  setNetworkStatus(status: NetworkStatus): void;
}>;

type MockSessionServiceOptions = Readonly<{
  initialSession?: Session | null;
  latencyMs?: number;
  createId?: () => string;
  now?: () => Date;
}>;

const serviceError = (code: SessionServiceError['code'], message: string) => ({
  ok: false as const,
  error: { code, message },
});

/**
 * Creates a local in-memory session service with simulated asynchronous operations.
 */
export function createMockSessionService({
  initialSession = null,
  latencyMs = 180,
  createId = () => globalThis.crypto.randomUUID(),
  now = () => new Date(),
}: MockSessionServiceOptions): SessionService {
  const sessions = new Map<string, Session>();
  let networkStatus: NetworkStatus = 'online';
  if (initialSession) {
    sessions.set(initialSession.id, initialSession);
  }

  function delay(): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, latencyMs));
  }

  async function createSession(
    title: string,
    id = createId(),
    createdAt = now(),
  ): Promise<SessionServiceResult<Session>> {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      return serviceError('invalid-title', 'Enter a title before creating a session.');
    }

    const session = createSessionModel(id, trimmedTitle, createdAt);
    sessions.set(session.id, session);
    await delay();
    return { ok: true, data: session };
  }

  async function startSession(
    sessionId: string,
    startedAt = now(),
  ): Promise<SessionServiceResult<Session>> {
    const session = sessions.get(sessionId);
    if (!session) {
      return serviceError('not-found', 'This session could not be found.');
    }
    if (session.status !== 'ready') {
      return serviceError('invalid-state', `A ${session.status} session cannot be started.`);
    }

    const updatedSession = startSessionModel(session, startedAt);
    sessions.set(sessionId, updatedSession);
    await delay();
    return { ok: true, data: sessions.get(sessionId) ?? updatedSession };
  }

  async function endSession(
    sessionId: string,
    endedAt = now(),
  ): Promise<SessionServiceResult<Session>> {
    const session = sessions.get(sessionId);
    if (!session) {
      return serviceError('not-found', 'This session could not be found.');
    }
    if (session.status !== 'active') {
      return serviceError('invalid-state', 'Only an active session can be ended.');
    }
    if (session.captureState !== 'idle' && session.captureState !== 'ended') {
      return serviceError(
        'invalid-state',
        'Stop microphone capture and wait for its ended event before ending the session.',
      );
    }

    const updatedSession = endSessionModel(session, endedAt);
    sessions.set(sessionId, updatedSession);
    await delay();
    return { ok: true, data: updatedSession };
  }

  function recordCaptureEvent(
    sessionId: string,
    event: CaptureLifecycleEvent,
    occurredAt = now(),
  ): SessionServiceResult<Session> {
    const session = sessions.get(sessionId);
    if (!session) {
      return serviceError('not-found', 'This session could not be found.');
    }

    const transition = applyCaptureLifecycleEvent(session, event, occurredAt);
    if (!transition.ok) {
      return serviceError(
        'invalid-state',
        `Capture cannot transition from ${transition.state} to ${event.type}.`,
      );
    }

    sessions.set(sessionId, transition.session);
    return { ok: true, data: transition.session };
  }

  function renameSession(sessionId: string, title: string): SessionServiceResult<Session> {
    const session = sessions.get(sessionId);
    if (!session) {
      return serviceError('not-found', 'This session could not be found.');
    }
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      return serviceError('invalid-title', 'Enter a title before renaming a session.');
    }

    const updatedSession = updateSessionTitle(session, trimmedTitle);
    sessions.set(sessionId, updatedSession);
    return { ok: true, data: updatedSession };
  }

  function setContextSourceEnabled(
    sessionId: string,
    sourceId: string,
    enabled: boolean,
  ): SessionServiceResult<Session> {
    const session = sessions.get(sessionId);
    if (!session) {
      return serviceError('not-found', 'This session could not be found.');
    }

    const source = session.contextPanel.sources.find((item) => item.id === sourceId);
    if (!source) {
      return serviceError('not-found', 'This context source could not be found.');
    }

    const updatedSource: ContextSource = { ...source, enabled };
    const updatedSession: Session = {
      ...session,
      contextPanel: {
        ...session.contextPanel,
        sources: session.contextPanel.sources.map((item) =>
          item.id === sourceId ? updatedSource : item,
        ),
      },
    };
    sessions.set(sessionId, updatedSession);
    return { ok: true, data: updatedSession };
  }

  function getEnabledContextSources(
    sessionId: string,
  ): SessionServiceResult<readonly ContextSource[]> {
    const session = sessions.get(sessionId);
    if (!session) {
      return serviceError('not-found', 'This session could not be found.');
    }

    return {
      ok: true,
      data: session.contextPanel.sources.filter((source) => source.enabled),
    };
  }

  function setNetworkStatus(status: NetworkStatus): void {
    networkStatus = status;
  }

  return {
    initialSession,
    get networkStatus() {
      return networkStatus;
    },
    createSession,
    startSession,
    endSession,
    recordCaptureEvent,
    renameSession,
    setContextSourceEnabled,
    getEnabledContextSources,
    setNetworkStatus,
  };
}
