import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MicrophonePanel } from './MicrophonePanel';
import * as microphonePermissionService from '../services/microphonePermissionService';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('mock microphone panel', () => {
  it('explains that the microphone is simulated and needs no browser permission', () => {
    const getUserMedia = vi.fn();
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal('navigator', testNavigator);
    render(<MicrophonePanel />);

    expect(screen.getByText('Mock microphone is off')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enable mock microphone' })).toBeEnabled();
    expect(
      screen.getByText(
        'This demo does not request browser microphone permission, record audio, or transmit audio.',
      ),
    ).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it('announces simulated readiness without opening a device', async () => {
    const user = userEvent.setup();
    const getUserMedia = vi.fn();
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal('navigator', testNavigator);
    render(<MicrophonePanel />);

    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toBeEmptyDOMElement();
    await user.click(screen.getByRole('button', { name: 'Enable mock microphone' }));
    expect(screen.getByText('Preparing mock microphone').closest('.permission-copy')).toHaveFocus();

    expect(await screen.findByText('Mock microphone ready')).toBeInTheDocument();
    await waitFor(() => expect(status).toHaveTextContent('Microphone ready.'));
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it('shows an accessible loading state while simulated readiness is pending', async () => {
    const getUserMedia = vi.fn();
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal('navigator', testNavigator);
    render(<MicrophonePanel />);

    const enableButton = screen.getByRole('button', { name: 'Enable mock microphone' });
    fireEvent.click(enableButton);
    fireEvent.click(enableButton);

    const panel = screen.getByRole('region', { name: 'Your microphone' });
    expect(panel).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Preparing mock microphone')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preparing mock microphone' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Preparing mock microphone' })).toHaveTextContent(
      'Working…',
    );
    expect(screen.getByRole('button', { name: 'Preparing mock microphone' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(
      screen
        .getByRole('button', { name: 'Preparing mock microphone' })
        .querySelector('.loading-spinner'),
    ).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText('Mock microphone ready')).toBeInTheDocument());
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it('announces microphone denial assertively only after the permission state changes', async () => {
    const user = userEvent.setup();
    vi.spyOn(microphonePermissionService, 'createMicrophonePermissionService').mockReturnValue({
      requestPermission: vi.fn(async () => ({
        status: 'denied' as const,
        reason: 'permission-denied' as const,
        message: 'Microphone access was denied.',
      })),
    });
    render(<MicrophonePanel />);

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Enable mock microphone' }));

    const alert = await screen.findByRole('alert');
    await waitFor(() =>
      expect(alert).toHaveTextContent('Microphone denied. Microphone access was denied.'),
    );
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(screen.getByText('Microphone access denied')).toBeInTheDocument();
  });
});
