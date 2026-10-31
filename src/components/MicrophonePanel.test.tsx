import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MicrophonePanel } from './MicrophonePanel';

function stubMediaDevices(mediaDevices: object | undefined) {
  const testNavigator = Object.create(navigator) as Navigator;
  Object.defineProperty(testNavigator, 'mediaDevices', {
    configurable: true,
    value: mediaDevices,
  });
  vi.stubGlobal('navigator', testNavigator);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('microphone permission states', () => {
  it('starts in a clear, user-controlled prompt state', () => {
    const getUserMedia = vi.fn();
    stubMediaDevices({ getUserMedia });
    render(<MicrophonePanel />);

    expect(screen.getByText('Microphone is off')).toBeInTheDocument();
    const enableButton = screen.getByRole('button', { name: 'Enable microphone' });
    expect(enableButton).toBeEnabled();
    expect(
      screen.getByText(
        'To use this feature, your browser will ask for microphone access. This week’s mock flow does not record, upload, or transmit audio.',
      ),
    ).toBeInTheDocument();
    expect(enableButton).toHaveAttribute(
      'aria-describedby',
      'microphone-next-step microphone-privacy-disclosure',
    );
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it('reports when microphone access is unavailable', async () => {
    const user = userEvent.setup();
    stubMediaDevices(undefined);
    render(<MicrophonePanel />);

    await user.click(screen.getByRole('button', { name: 'Enable microphone' }));

    expect(screen.getByRole('status')).toHaveTextContent('Microphone access unsupported');
    expect(
      screen.getByText('Use a supported browser with microphone access enabled.'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Try again: microphone permission' }),
    ).not.toBeInTheDocument();
  });

  it('explains when permission is denied', async () => {
    const user = userEvent.setup();
    stubMediaDevices({
      getUserMedia: vi
        .fn()
        .mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError')),
    });
    render(<MicrophonePanel />);

    await user.click(screen.getByRole('button', { name: 'Enable microphone' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Microphone access denied');
    expect(
      screen.getByText('Allow microphone access in your browser site permissions, then try again.'),
    ).toBeInTheDocument();
  });

  it('stops the stream immediately after permission is granted', async () => {
    const user = userEvent.setup();
    const stop = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop }],
    });
    stubMediaDevices({
      getUserMedia,
    });
    render(<MicrophonePanel />);

    expect(getUserMedia).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Enable microphone' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Microphone access granted');
    expect(getUserMedia).toHaveBeenCalledOnce();
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(stop).toHaveBeenCalledOnce();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(
      screen.getByText(
        'To use this feature, your browser will ask for microphone access. This week’s mock flow does not record, upload, or transmit audio.',
      ),
    ).toBeInTheDocument();
  });

  it('shows requesting state while waiting for the browser permission result', async () => {
    let resolveRequest!: (stream: MediaStream) => void;
    stubMediaDevices({
      getUserMedia: vi.fn(
        () =>
          new Promise<MediaStream>((resolve) => {
            resolveRequest = resolve;
          }),
      ),
    });
    render(<MicrophonePanel />);

    fireEvent.click(screen.getByRole('button', { name: 'Enable microphone' }));

    expect(screen.getByRole('status')).toHaveTextContent('Waiting for permission');
    expect(screen.getByRole('button', { name: 'Requesting microphone permission' })).toBeDisabled();

    resolveRequest({ getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream);
    expect(await screen.findByRole('status')).toHaveTextContent('Microphone access granted');
  });

  it('preserves an unexpected failure reason as a readable error message', async () => {
    const user = userEvent.setup();
    stubMediaDevices({
      getUserMedia: vi.fn().mockRejectedValue(new Error('Audio device initialization failed.')),
    });
    render(<MicrophonePanel />);

    await user.click(screen.getByRole('button', { name: 'Enable microphone' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Microphone request failed');
    expect(screen.getByText('Audio device initialization failed.')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Try again. If the problem continues, check browser permissions and your microphone.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try again: microphone permission' })).toBeEnabled();
  });
});
