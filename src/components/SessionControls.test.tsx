import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { createSession } from '../models/session';
import { SessionControls } from './SessionControls';

describe('SessionControls', () => {
  const callbacks = {
    onStart: vi.fn(),
    onEnd: vi.fn(),
    onSessionEnded: vi.fn(),
    requestState: 'idle' as const,
    loadingAction: null,
    error: null,
  };

  it('shows text status and disables lifecycle actions when no session exists', () => {
    render(<SessionControls {...callbacks} session={null} />);

    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('No session');
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    expect(screen.queryByLabelText('Session timestamps')).not.toBeInTheDocument();
  });

  it('disables Start for an active session and includes its timestamps', () => {
    const activeSession = {
      ...createSession('active', 'Active sample', new Date('2026-10-30T00:00:00.000Z')),
      status: 'active' as const,
      startedAt: '2026-10-30T00:05:00.000Z',
    };
    render(<SessionControls {...callbacks} session={activeSession} />);

    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active');
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeEnabled();
    expect(screen.getAllByRole('time')).toHaveLength(2);
  });
});
