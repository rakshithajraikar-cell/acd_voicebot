import {
  createSession as createSessionModel,
  endSession as endSessionModel,
  startSession as startSessionModel,
  updateSessionTitle,
} from '../models/session';
import type { Session } from '../models/session';

export type SessionServiceError = Readonly<{
  code: 'not-found' | 'invalid-state' | 'invalid-title';
  message: string;
}>;

export type SessionServiceResult<T> =
  Readonly<{ ok: true; data: T }> | Readonly<{ ok: false; error: SessionServiceError }>;

export type SessionService = Readonly<{
  initialSession: Session | null;
  createSession(
    title: string,
    id?: string,
    createdAt?: Date,
  ): Promise<SessionServiceResult<Session>>;
  startSession(sessionId: string, startedAt?: Date): Promise<SessionServiceResult<Session>>;
  endSession(sessionId: string, endedAt?: Date): Promise<SessionServiceResult<Session>>;
  renameSession(sessionId: string, title: string): SessionServiceResult<Session>;
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
    return { ok: true, data: updatedSession };
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

    const updatedSession = endSessionModel(session, endedAt);
    sessions.set(sessionId, updatedSession);
    await delay();
    return { ok: true, data: updatedSession };
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

  return { initialSession, createSession, startSession, endSession, renameSession };
}
