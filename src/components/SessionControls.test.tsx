import { cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createSession } from '../models/session';
import { useMockSession } from '../hooks/useMockSession';
import { SessionControls } from './SessionControls';

afterEach(cleanup);

describe('SessionControls', () => {
  const callbacks = {
    onStart: vi.fn(),
    onPauseCapture: vi.fn(() => ({ ok: true as const })),
    onResumeCapture: vi.fn(() => ({ ok: true as const })),
    onEnd: vi.fn(),
    onSessionEnded: vi.fn(),
    onRetry: vi.fn(),
    requestState: 'idle' as const,
    loadingAction: null,
    failedAction: null,
    error: null,
    captureError: null,
    captureActionPending: null,
    networkStatus: 'online' as const,
  };

  it('shows text status and disables lifecycle actions when no session exists', () => {
    render(<SessionControls {...callbacks} session={null} />);

    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('No session');
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Ready$/);
    expect(screen.queryByLabelText('Session timestamps')).not.toBeInTheDocument();
  });

  it('allows capture retry for an active idle session and includes its timestamps', () => {
    const activeSession = {
      ...createSession('active', 'Active sample', new Date('2026-10-30T00:00:00.000Z')),
      status: 'active' as const,
      startedAt: '2026-10-30T00:05:00.000Z',
    };
    render(<SessionControls {...callbacks} session={activeSession} />);

    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active');
    expect(screen.getByRole('button', { name: 'Start session' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();
    expect(screen.getAllByRole('time')).toHaveLength(2);
  });

  it('enables only the capture action valid for the actual capture state', () => {
    const capturingSession = {
      ...createSession('active', 'Active sample'),
      status: 'active' as const,
      captureState: 'capturing' as const,
    };
    const { rerender } = render(<SessionControls {...callbacks} session={capturingSession} />);

    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();
    const captureStatus = screen.getByRole('status', { name: 'Capture status' });
    expect(captureStatus).toHaveTextContent(/^Capturing$/);
    expect(captureStatus).toHaveAttribute('aria-live', 'off');
    expect(captureStatus).toHaveAttribute('aria-atomic', 'true');
    expect(captureStatus).toHaveClass('capture-status-indicator', 'capture-status-capturing');

    rerender(
      <SessionControls
        {...callbacks}
        session={{
          ...capturingSession,
          captureState: 'paused',
          pausedAt: new Date().toISOString(),
        }}
      />,
    );

    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeEnabled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Paused$/);
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveClass(
      'capture-status-paused',
    );
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeEnabled();
  });

  it('announces capture start, pause, and resume once for each state transition', async () => {
    function Harness() {
      const controller = useMockSession();
      return (
        <SessionControls
          session={controller.session}
          onStart={() => void controller.startSession()}
          onPauseCapture={controller.pauseCapture}
          onResumeCapture={controller.resumeCapture}
          onEnd={() => void controller.endSession()}
          requestState={controller.requestState}
          loadingAction={controller.loadingAction}
          failedAction={controller.failedAction}
          error={controller.error}
          captureError={controller.captureError}
          captureActionPending={controller.captureActionPending}
          networkStatus={controller.networkStatus}
          onRetry={controller.retryFailedAction}
          onSessionEnded={() => undefined}
        />
      );
    }

    const user = userEvent.setup();
    render(<Harness />);
    const announcement = screen.getByRole('status', { name: '' });
    expect(announcement).toHaveAttribute('aria-live', 'polite');
    expect(announcement).toBeEmptyDOMElement();

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() => expect(announcement).toHaveTextContent('Capture started.'));

    await user.click(screen.getByRole('button', { name: 'Pause microphone capture' }));
    await waitFor(() => expect(announcement).toHaveTextContent('Capture paused.'));

    await user.click(screen.getByRole('button', { name: 'Resume microphone capture' }));
    await waitFor(() => expect(announcement).toHaveTextContent('Capture resumed.'));
  });

  it('labels capture as Ready while idle and Ended when capture has ended', () => {
    const session = createSession('session-ready', 'Ready sample');
    const { rerender } = render(<SessionControls {...callbacks} session={session} />);

    const captureStatus = screen.getByRole('status', { name: 'Capture status' });
    expect(captureStatus).toHaveTextContent(/^Ready$/);
    expect(captureStatus.querySelector('svg')).toBeInTheDocument();

    rerender(<SessionControls {...callbacks} session={{ ...session, captureState: 'ended' }} />);

    expect(captureStatus).toHaveTextContent(/^Ended$/);
    expect(captureStatus.querySelector('svg')).toBeInTheDocument();
    expect(captureStatus).toHaveClass('capture-status-ended');
  });

  it('disables session and capture actions while offline', () => {
    const capturingSession = {
      ...createSession('active', 'Active sample'),
      status: 'active' as const,
      captureState: 'capturing' as const,
    };
    render(<SessionControls {...callbacks} session={capturingSession} networkStatus="offline" />);

    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
  });

  it('disables capture controls while a browser transition is pending', () => {
    const capturingSession = {
      ...createSession('active', 'Active sample'),
      status: 'active' as const,
      captureState: 'capturing' as const,
    };
    render(
      <SessionControls {...callbacks} session={capturingSession} captureActionPending="pausing" />,
    );

    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
  });

  it('announces request failures and lets keyboard users retry them', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<SessionControls {...callbacks} session={null} />);
    rerender(
      <SessionControls
        {...callbacks}
        session={null}
        requestState="error"
        failedAction="create"
        error={{ code: 'invalid-state', message: 'Please try again.' }}
      />,
    );

    expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Couldn’t create session. Please try again.',
    );
    const retry = screen.getByRole('button', { name: 'Retry session request' });
    expect(retry).toHaveClass('button-primary');
    expect(retry).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(callbacks.onRetry).toHaveBeenCalledOnce();
  });

  it('announces capture errors and moves focus to the error message', () => {
    const activeSession = {
      ...createSession('active', 'Active sample'),
      status: 'active' as const,
      captureState: 'capturing' as const,
    };
    const { rerender } = render(<SessionControls {...callbacks} session={activeSession} />);
    rerender(
      <SessionControls
        {...callbacks}
        session={activeSession}
        captureError="Capture could not be paused."
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(alert).toHaveFocus();
  });

  it('delegates Pause and Resume to the capture controller', async () => {
    const user = userEvent.setup();
    const capturingSession = {
      ...createSession('active', 'Active sample'),
      status: 'active' as const,
      captureState: 'capturing' as const,
    };
    render(<SessionControls {...callbacks} session={capturingSession} />);

    await user.click(screen.getByRole('button', { name: 'Pause microphone capture' }));

    expect(callbacks.onPauseCapture).toHaveBeenCalledOnce();
    expect(callbacks.onResumeCapture).not.toHaveBeenCalled();
  });

  it('runs the mock capture state machine with keyboard-operable controls', async () => {
    function Harness() {
      const controller = useMockSession();
      return (
        <SessionControls
          session={controller.session}
          onStart={() => void controller.startSession()}
          onPauseCapture={controller.pauseCapture}
          onResumeCapture={controller.resumeCapture}
          onEnd={() => void controller.endSession()}
          requestState={controller.requestState}
          loadingAction={controller.loadingAction}
          failedAction={controller.failedAction}
          error={controller.error}
          captureError={controller.captureError}
          captureActionPending={controller.captureActionPending}
          networkStatus={controller.networkStatus}
          onRetry={controller.retryFailedAction}
          onSessionEnded={() => undefined}
        />
      );
    }

    const user = userEvent.setup();
    render(<Harness />);
    const captureStatus = screen.getByRole('status', { name: 'Capture status' });
    const startButton = screen.getByRole('button', { name: 'Start session' });
    const pauseButton = screen.getByRole('button', { name: 'Pause microphone capture' });
    const resumeButton = screen.getByRole('button', { name: 'Resume microphone capture' });
    const endButton = screen.getByRole('button', { name: 'End or stop session' });

    expect(captureStatus).toHaveTextContent(/^Ready$/);
    expect(pauseButton).toBeDisabled();
    expect(resumeButton).toBeDisabled();
    await user.tab();
    expect(startButton).toHaveFocus();
    await user.keyboard('{Enter}');

    await waitFor(() => expect(captureStatus).toHaveTextContent(/^Capturing$/));
    expect(startButton).toBeDisabled();
    expect(pauseButton).toBeEnabled();
    expect(resumeButton).toBeDisabled();
    expect(endButton).toBeEnabled();

    pauseButton.focus();
    await user.keyboard('{Enter}');

    await waitFor(() => expect(captureStatus).toHaveTextContent(/^Paused$/));
    expect(pauseButton).toBeDisabled();
    expect(resumeButton).toBeEnabled();
    expect(endButton).toBeEnabled();
    expect(resumeButton).toHaveFocus();

    await user.keyboard('{Enter}');

    await waitFor(() => expect(captureStatus).toHaveTextContent(/^Capturing$/));
    expect(pauseButton).toBeEnabled();
    expect(resumeButton).toBeDisabled();
    expect(pauseButton).toHaveFocus();
  });
});
