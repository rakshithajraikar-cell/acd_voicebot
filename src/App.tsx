import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Headphones,
  LoaderCircle,
  Plus,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import type { ApiClient } from './api/client';
import { apiClient, apiClientConfiguration } from './api/configuredClient';
import { apiRouteOverview } from './api/routeOverview';
import { AppShell } from './components/AppShell';
import { MicrophonePanel } from './components/MicrophonePanel';
import { SessionControls } from './components/SessionControls';
import { TranscriptTimeline } from './components/TranscriptTimeline';
import { useMockSession } from './hooks/useMockSession';
import type { Session } from './models/session';
import { getDemoWorkspace } from './services/demoWorkspaceService';
import type { HealthCheckResponse, SessionRetrievalResponse } from './api/contracts';
import type { TranscriptEvent } from './types';

type ApiLoadState =
  | Readonly<{ status: 'idle' }>
  | Readonly<{ status: 'loading' }>
  | Readonly<{
      status: 'success';
      session: SessionRetrievalResponse;
      health: HealthCheckResponse;
    }>
  | Readonly<{ status: 'error'; message: string }>;

function formatApiResponse(response: unknown): string {
  return JSON.stringify(response, null, 2) ?? String(response);
}

type AppProps = Readonly<{
  client?: ApiClient;
}>;

function App({ client = apiClient }: AppProps) {
  const newSessionButtonRef = useRef<HTMLButtonElement>(null);
  const focusNewSession = useCallback(() => newSessionButtonRef.current?.focus(), []);
  const {
    session,
    requestState,
    loadingAction,
    error: sessionError,
    isLoading: isSessionLoading,
    createSession,
    startSession,
    endSession,
    renameSession,
  } = useMockSession();
  const createTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [events, setEvents] = useState<TranscriptEvent[]>([]);
  const [apiState, setApiState] = useState<ApiLoadState>({ status: 'idle' });

  useEffect(() => {
    if (loadingAction || !createTriggerRef.current) {
      return;
    }

    createTriggerRef.current.focus();
    createTriggerRef.current = null;
  }, [loadingAction]);

  async function loadWorkspace(
    options: Readonly<{
      renameCurrentSession?: boolean;
      sessionStatus?: Session['status'];
    }> = {},
  ) {
    const activeStatus = options.sessionStatus ?? session?.status;
    if (activeStatus !== 'active' && activeStatus !== 'ended') {
      return;
    }

    setApiState({ status: 'loading' });
    setEvents([]);
    const sessionId = session?.id;
    if (!sessionId) {
      setApiState({
        status: 'error',
        message: 'No session is available to load. Create a session and try again.',
      });
      return;
    }

    try {
      const sessionResponse = await client.getSession({ session_id: sessionId });
      const healthResponse = await client.healthCheck();
      const result = await getDemoWorkspace();
      if (!result.ok) {
        setApiState({ status: 'error', message: result.error.message });
        return;
      }

      if (options.renameCurrentSession ?? true) {
        const renameResult = renameSession(result.data.sessionName);
        if (!renameResult.ok) {
          setApiState({ status: 'error', message: renameResult.error.message });
          return;
        }
      }

      setEvents(result.data.transcript);
      setApiState({
        status: 'success',
        session: sessionResponse,
        health: healthResponse,
      });
    } catch (error) {
      setApiState({
        status: 'error',
        message:
          error instanceof Error && error.message.trim()
            ? error.message
            : 'An unexpected error occurred while loading the session.',
      });
    }
  }

  async function handleStartSession() {
    const result = await startSession();
    if (result?.ok) {
      await loadWorkspace({
        renameCurrentSession: false,
        sessionStatus: result.data.status,
      });
    }
  }

  async function handleCreateSession() {
    const trigger =
      document.activeElement instanceof HTMLButtonElement ? document.activeElement : null;
    createTriggerRef.current = trigger;
    const result = await createSession();
    if (!result?.ok) {
      return;
    }
    setEvents([]);
    setApiState({ status: 'idle' });
  }

  return (
    <AppShell
      onNewSession={handleCreateSession}
      isSessionLoading={isSessionLoading}
      isCreatingSession={loadingAction === 'create'}
    >
      <main className="main-content" id="main-content" tabIndex={-1}>
        <div className="page-heading">
          <div>
            <div className="page-kicker">
              <span className="kicker-line" /> YOUR THINKING PARTNER
            </div>
            <h1>
              Good ideas start
              <br className="mobile-break" /> with a conversation.
            </h1>
            <p className="page-description">
              A thoughtful space to think out loud, untangle ideas, and find your next step.
            </p>
          </div>
          <button
            ref={newSessionButtonRef}
            className="button button-new-session"
            type="button"
            aria-label="New session"
            aria-busy={loadingAction === 'create'}
            onClick={handleCreateSession}
            disabled={isSessionLoading}
          >
            <Plus size={16} aria-hidden="true" />
            {loadingAction === 'create' ? 'Creating…' : 'New Session'}
          </button>
        </div>

        <div className="content-grid">
          <section className="conversation-column" aria-label="Co-Pilot session">
            <div className="conversation-card">
              <div className="conversation-header">
                <div className="session-title-group">
                  <span className="session-art">
                    <Sparkles size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <p className="eyebrow">CURRENT SESSION</p>
                    <h2>{session?.title ?? 'No session selected'}</h2>
                  </div>
                </div>
                <SessionControls
                  session={session}
                  onStart={handleStartSession}
                  onEnd={endSession}
                  requestState={requestState}
                  loadingAction={loadingAction}
                  error={sessionError}
                  onSessionEnded={focusNewSession}
                />
              </div>

              <div className="transcript-toolbar">
                <div className="transcript-heading">
                  <h3>Conversation</h3>
                  <span className="event-count">
                    {events.length} {events.length === 1 ? 'moment' : 'moments'}
                  </span>
                </div>
                <div className="transcript-tools">
                  <span className="live-indicator">
                    <span aria-hidden="true" /> MOCK SESSION
                  </span>
                </div>
              </div>

              <TranscriptTimeline
                events={session?.status === 'active' || session?.status === 'ended' ? events : []}
              />

              {events.length === 0 && (
                <div className="conversation-empty-action">
                  <button
                    className="button button-primary"
                    type="button"
                    aria-label="Explore sample conversation (local mock data)"
                    onClick={() => loadWorkspace()}
                    disabled={session?.status !== 'active' && session?.status !== 'ended'}
                  >
                    <Sparkles size={15} aria-hidden="true" /> Explore sample conversation
                  </button>
                  <span>Uses local fixture data only</span>
                </div>
              )}

              {events.length > 0 && (
                <div className="composer">
                  <button
                    className="composer-add"
                    type="button"
                    disabled
                    aria-label="Add attachment (not available in demo)"
                  >
                    <Plus size={17} aria-hidden="true" />
                  </button>
                  <span className="composer-placeholder">
                    Your message will appear here in a future version…
                  </span>
                  <button
                    className="composer-send"
                    type="button"
                    disabled
                    aria-label="Send message (not available in demo)"
                  >
                    <ArrowUpRight size={17} aria-hidden="true" />
                  </button>
                </div>
              )}
              {events.length > 0 && (
                <p className="composer-footnote">
                  <span className="inline-lock" aria-hidden="true">
                    ●
                  </span>{' '}
                  Your conversation stays in this local demo.
                </p>
              )}
            </div>

            <div className="bottom-hint">
              <span>
                <Clock3 size={14} aria-hidden="true" /> A calm pace. Your call.
              </span>
              <span>
                Mock-first, by design <ArrowUpRight size={13} aria-hidden="true" />
              </span>
            </div>
          </section>

          <aside className="right-rail" aria-label="Session tools">
            <MicrophonePanel />
            <section className="panel api-panel" aria-labelledby="api-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">FOUNDATION</p>
                  <h2 id="api-heading">Demo API</h2>
                </div>
                <span className="api-shield">
                  <CheckCircle2 size={16} aria-hidden="true" />
                </span>
              </div>
              <p className="panel-description">
                {apiClientConfiguration.mode === 'mock'
                  ? 'Typed client, local mock response. No server connection.'
                  : 'Typed client using the configured HTTP API.'}
              </p>
              <div
                className={`api-feedback api-${apiState.status}`}
                role={apiState.status === 'error' ? 'alert' : 'status'}
                aria-live={apiState.status === 'error' ? 'assertive' : 'polite'}
                aria-busy={apiState.status === 'loading'}
              >
                {apiState.status === 'loading' ? (
                  <>
                    <LoaderCircle
                      className="api-loading-spinner"
                      size={15}
                      aria-hidden="true"
                    />
                    <span>Loading session details and health status…</span>
                  </>
                ) : (
                  <>
                    <span className="api-feedback-dot" aria-hidden="true" />
                    <span>
                      {apiState.status === 'error'
                        ? apiState.message
                        : apiState.status === 'success'
                          ? 'Session details loaded successfully. Health check passed.'
                          : session?.status === 'ready'
                            ? 'Start the session to load its sample transcript.'
                            : 'Session data is ready to load.'}
                    </span>
                  </>
                )}
              </div>
              {apiState.status === 'error' && (
                <p className="api-retry-guidance">
                  Check the connection or mock scenario, then retry the session load.
                </p>
              )}
              {apiState.status === 'success' && (
                <div className="api-response-details">
                  <section className="api-session-details" aria-labelledby="api-session-details">
                    <h3 id="api-session-details">Session response</h3>
                    <pre>{formatApiResponse(apiState.session)}</pre>
                  </section>
                  <section className="api-session-details" aria-labelledby="api-health-details">
                    <h3 id="api-health-details">Health response</h3>
                    <pre>{formatApiResponse(apiState.health)}</pre>
                  </section>
                </div>
              )}
              <div className="api-actions">
                <button
                  className="button button-outline"
                  type="button"
                  aria-label={
                    apiState.status === 'error'
                      ? 'Retry loading mock session (local data)'
                      : 'Load mock session (local data)'
                  }
                  onClick={() => loadWorkspace()}
                  disabled={
                    apiState.status === 'loading' ||
                    (session?.status !== 'active' && session?.status !== 'ended')
                  }
                >
                  <RefreshCw size={14} aria-hidden="true" />
                  {apiState.status === 'loading'
                    ? 'Loading…'
                    : apiState.status === 'error'
                      ? 'Retry session load'
                      : 'Load mock session'}
                </button>
              </div>
            </section>
            <section className="panel api-overview" aria-labelledby="api-overview-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">REFERENCE</p>
                  <h2 id="api-overview-heading">API overview</h2>
                </div>
              </div>
              <p className="panel-description">
                Contract capability routes. Methods, paths, and schemas require backend
                validation before implementation.
              </p>
              <ul className="api-route-list">
                {apiRouteOverview.map((route) => (
                  <li key={route}>
                    <span>{route}</span>
                    <span className="api-route-status">proposed — pending backend validation</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="privacy-card">
              <span className="privacy-card-icon">
                <Headphones size={17} aria-hidden="true" />
              </span>
              <div>
                <strong>Designed around you</strong>
                <p>
                  Your voice and choices stay in your hands. This preview uses sample data only.
                </p>
              </div>
            </section>
          </aside>
        </div>
      </main>
    </AppShell>
  );
}

export default App;
