import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MockApiClient, type ApiClient } from './api/client';
import { apiRouteOverview } from './api/routeOverview';
import App from './App';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Week 1 app shell', () => {
  it('lists every API contract capability as pending backend validation', () => {
    render(<App />);

    const overview = screen.getByRole('region', { name: 'API overview' });
    expect(apiRouteOverview).toHaveLength(8);
    for (const route of apiRouteOverview) {
      expect(overview).toHaveTextContent(route);
    }
    expect(overview.querySelectorAll('.api-route-status')).toHaveLength(8);
    expect(overview).toHaveTextContent('proposed — pending backend validation');
    expect(
      within(screen.getByRole('region', { name: 'Demo API' })).getByText('Ready'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback svg'),
    ).toBeInTheDocument();
  });

  it('lets keyboard users skip directly to main content', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.tab();
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveFocus();

    await user.keyboard('{Enter}');
    expect(screen.getByRole('main')).toHaveFocus();
  });

  it('keeps navigation controls in a predictable keyboard tab order', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.tab();
    await user.tab();
    expect(screen.getByRole('link', { name: 'Academia home' })).toHaveFocus();

    await user.tab();
    expect(screen.getAllByRole('button', { name: 'New session' })[0]).toHaveFocus();

    await user.tab();
    expect(screen.getByRole('link', { name: 'Co-Pilot workspace' })).toHaveFocus();
  });

  it('lets keyboard users create and start a mock session', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.tab();
    await user.tab();
    await user.tab();
    expect(screen.getAllByRole('button', { name: 'New session' })[0]).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(screen.getAllByRole('button', { name: 'New session' })).toHaveLength(2);
    screen
      .getAllByRole('button', { name: 'New session' })
      .forEach((button) => expect(button).toBeDisabled());
    expect(screen.getAllByRole('button', { name: 'New session' })[0]).toHaveAttribute(
      'aria-busy',
      'true',
    );
    const creationAnnouncements = screen
      .getAllByRole('status')
      .filter((status) => status.textContent?.includes('Creating session'));
    expect(creationAnnouncements.length).toBeGreaterThan(0);
    creationAnnouncements.forEach((announcement) =>
      expect(announcement).toHaveAttribute('aria-live', 'polite'),
    );
    expect(screen.getByRole('heading', { level: 2, name: 'Untitled session' })).toBeInTheDocument();
    expect(screen.getAllByText('Creating session…')).toHaveLength(2);
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Untitled session' }),
    ).toBeInTheDocument();
    await waitFor(() =>
      screen
        .getAllByRole('button', { name: 'New session' })
        .forEach((button) => expect(button).toBeEnabled()),
    );
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: 'New session' })[0]).toHaveFocus(),
    );

    await user.tab();
    await user.tab();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Start session' })).toHaveFocus();
    await user.keyboard(' ');
    expect(await screen.findByRole('status', { name: 'Session status' })).toHaveTextContent(
      'Active',
    );
    expect(screen.getByText('Starting session…')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Session controls' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(
      screen
        .getByRole('region', { name: 'Session controls' })
        .querySelector('.session-loading-announcement'),
    ).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('button', { name: 'Start session' })).toHaveTextContent('Starting…');
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Start session' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'End or stop session' })).toHaveFocus(),
    );
    await user.keyboard('{Enter}');
    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Ended');
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: 'New session' })[1]).toHaveFocus(),
    );
  });

  it('runs the capture flow without microphone access or network requests', async () => {
    const user = userEvent.setup();
    const getUserMedia = vi.fn();
    const fetch = vi.fn();
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'onLine', {
      configurable: true,
      value: true,
    });
    Object.defineProperty(testNavigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal('navigator', testNavigator);
    vi.stubGlobal('fetch', fetch);

    render(<App />);
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();

    await user.click(screen.getAllByRole('button', { name: 'New session' })[0]);
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Untitled session' }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Start session' })).toBeEnabled(),
    );

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(
        /^Capturing$/,
      ),
    );
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Pause microphone capture' }));
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Paused$/);
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Resume microphone capture' }));
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();

    expect(getUserMedia).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('visits every enabled tab stop, activates the context switch with Space, and leaves the final stop', async () => {
    const user = userEvent.setup();
    render(<App />);

    const controls = Array.from(
      document.querySelectorAll<HTMLElement>(
        'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
      ),
    );
    const lastControl = controls[controls.length - 1];
    const screenContextSwitch = screen.getByRole('switch', { name: 'Screen context' });
    const visited = new Set<Element>();
    for (let index = 0; index < controls.length; index += 1) {
      await user.tab();
      visited.add(document.activeElement as Element);
      if (document.activeElement === screenContextSwitch) {
        await user.keyboard(' ');
        expect(screenContextSwitch).toBeChecked();
        await user.keyboard(' ');
        expect(screenContextSwitch).not.toBeChecked();
      }
    }

    expect(visited.size).toBe(controls.length);
    controls.forEach((control) => expect(visited.has(control)).toBe(true));
    expect(visited.has(screenContextSwitch)).toBe(true);

    await user.tab();
    expect(document.activeElement).not.toBe(lastControl);
  });

  it('gives every button and link an explicit accessible label', () => {
    render(<App />);

    const controls = document.querySelectorAll('button, a');
    expect(controls.length).toBeGreaterThan(0);
    controls.forEach((control) => {
      expect(control).toHaveAttribute('aria-label');
      expect(control.getAttribute('aria-label')).not.toBe('');
    });
  });

  it('uses semantic landmarks and a clear page heading hierarchy', () => {
    render(<App />);

    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Workspace navigation' })).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    expect(screen.getByRole('banner')).toHaveClass('topbar');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Good ideas start with a conversation.',
    );
    expect(
      screen.getByRole('heading', { level: 2, name: 'Product design review' }),
    ).toBeInTheDocument();
  });

  it('shows mock mode and starts a session', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText('MOCK MODE')).toBeInTheDocument();
    expect(
      screen.getByText('Mock data is in use — no AI service is connected.'),
    ).toBeInTheDocument();
    const mockStatus = screen.getByRole('status', { name: 'Mock mode status' });
    expect(mockStatus).toHaveTextContent('MOCK MODE');
    expect(mockStatus).toHaveTextContent('Mock data is in use — no AI service is connected.');

    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Ready');
    expect(screen.getByRole('time')).toHaveAttribute('dateTime', expect.stringMatching(/Z$/));
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Start session' }));
    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active');
    expect(screen.getByRole('region', { name: 'Session controls' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'End or stop session' })).toBeEnabled(),
    );
    expect(screen.getByLabelText('Session timestamps').querySelectorAll('time')).toHaveLength(2);
    expect(screen.getByRole('status', { name: 'Mock mode status' })).toBeInTheDocument();
    expect(screen.getByText('MOCK SESSION')).toBeInTheDocument();
  });

  it('keeps screen context off through session start until the user explicitly enables it', async () => {
    const user = userEvent.setup();
    render(<App />);

    const contextPanel = screen.getByRole('region', { name: 'Context & Sources' });
    const screenSwitch = within(contextPanel).getByRole('switch', { name: 'Screen context' });
    expect(screenSwitch).not.toBeChecked();
    expect(screenSwitch).toHaveAttribute('aria-checked', 'false');
    expect(within(contextPanel).getByRole('status')).toHaveTextContent(
      'Screen context is off — nothing from your screen is shared.',
    );
    expect(within(contextPanel).getByText('Not shared')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(
        /^Capturing$/,
      ),
    );
    expect(screenSwitch).not.toBeChecked();
    expect(screenSwitch).toHaveAttribute('aria-checked', 'false');
    expect(within(contextPanel).getByText('Not shared')).toBeInTheDocument();
    expect(within(contextPanel).getByRole('status')).toHaveTextContent(
      'Screen context is off — nothing from your screen is shared.',
    );
    const transcript = screen.getByRole('region', { name: 'Conversation transcript' });
    within(transcript)
      .getAllByRole('listitem')
      .forEach((item) => {
        expect(item).not.toHaveTextContent(/screen context|screen capture|screen contents/i);
        expect(item).not.toHaveAttribute('data-screen-context');
      });

    await user.click(screenSwitch);
    expect(screenSwitch).toBeChecked();
    expect(screenSwitch).toHaveAttribute('aria-checked', 'true');
    expect(within(contextPanel).getByText('On')).toBeInTheDocument();
    expect(within(contextPanel).getByRole('status')).toHaveTextContent(
      'Screen context is on — enabled for this session.',
    );

    await user.click(screenSwitch);
    expect(screenSwitch).not.toBeChecked();
    expect(screenSwitch).toHaveAttribute('aria-checked', 'false');
    expect(within(contextPanel).getByText('Off')).toBeInTheDocument();
    expect(within(contextPanel).getByRole('status')).toHaveTextContent(
      'Screen context is off — nothing from your screen is shared.',
    );
  });

  it('ends a session immediately and disables invalid actions', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'End or stop session' })).toBeEnabled(),
    );
    await user.click(screen.getByRole('button', { name: 'End or stop session' }));
    expect(screen.getByText('Ending session…')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(screen.getByRole('button', { name: 'End or stop session' })).toHaveTextContent(
      'Ending…',
    );
    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Ended');
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    expect(screen.getByLabelText('Session timestamps').querySelectorAll('time')).toHaveLength(3);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows fixture events only for active or ended sessions', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText('No transcript yet')).toBeInTheDocument();
    expect(
      screen.queryByRole('region', { name: 'Conversation transcript' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Explore sample conversation (local mock data)' }),
    ).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Load mock session (local data)' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Start session' }));

    const conversation = await screen.findByRole('region', { name: 'Conversation transcript' });
    expect(
      await screen.findByText('Session details loaded successfully. Health check passed.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Success')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Session response' })).toHaveTextContent(
      'session-001',
    );
    expect(screen.getByRole('region', { name: 'Health response' })).toHaveTextContent('healthy');
    const items = Array.from(conversation.querySelectorAll('li'));
    expect(items).toHaveLength(11);
    expect(items[0]).toHaveTextContent('Session started.');
    expect(items[1]).toHaveTextContent('Help me prepare a clear agenda');
    expect(items[9]).toHaveTextContent('Here’s a focused 45-minute agenda');
    expect(within(items[1]).getByText('Mock demo confidence: 94%')).toBeInTheDocument();
    expect(within(items[2]).getByText('Mock demo confidence: 88%')).toBeInTheDocument();
    expect(within(items[4]).getByText('Mock demo confidence: 91%')).toBeInTheDocument();
    items.forEach((item, index) => {
      if (![1, 2, 4, 10].includes(index)) {
        expect(within(item).queryByText(/confidence/i)).not.toBeInTheDocument();
      }
    });
    expect(items[10]).toHaveAttribute('data-final', 'false');
    expect(items[10]).toHaveTextContent('I would like to plan');
    expect(within(items[10]).getAllByText('Mock demo confidence: 94%')).toHaveLength(1);
    const timestamps = Array.from(conversation.querySelectorAll('time')).map((time) =>
      Date.parse(time.dateTime),
    );
    expect(timestamps).toEqual([...timestamps].sort((a, b) => a - b));

    await user.click(screen.getByRole('button', { name: 'End or stop session' }));
    expect(screen.getByRole('region', { name: 'Conversation transcript' })).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: 'New session' })[0]).toBeEnabled(),
    );
    await user.click(screen.getAllByRole('button', { name: 'New session' })[0]);
    expect(await screen.findByText('No transcript yet')).toBeInTheDocument();
    expect(
      screen.queryByRole('region', { name: 'Conversation transcript' }),
    ).not.toBeInTheDocument();
  });

  it('streams interim transcript updates into one segment and finalizes it on session start', async () => {
    const user = userEvent.setup();
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    const transcript = await screen.findByRole('region', { name: 'Conversation transcript' });
    const liveSegment = await within(transcript).findByText('I would like to plan');
    const segmentRow = liveSegment.closest('li');
    expect(segmentRow).not.toBeNull();
    if (!segmentRow) throw new Error('Mock transcript segment row was not rendered.');
    const segmentId = segmentRow.getAttribute('data-segment-id');
    expect(segmentId).toMatch(/^mock-live-segment-\d+$/);
    expect(segmentRow).toHaveAttribute('data-final', 'false');
    expect(within(segmentRow).getByText('Listening · interim')).toBeInTheDocument();
    expect(within(segmentRow).getAllByText('Mock demo confidence: 94%')).toHaveLength(1);

    await screen.findByText('I would like to plan a small team workshop', {}, { timeout: 5000 });
    expect(within(transcript).getAllByRole('listitem')).toHaveLength(11);
    expect(segmentRow).toHaveTextContent('I would like to plan a small team workshop');
    expect(segmentRow).toHaveAttribute('data-final', 'false');
    expect(within(segmentRow).getAllByText('Mock demo confidence: 94%')).toHaveLength(1);

    await screen.findByText(
      'I would like to plan a small team workshop for next week',
      {},
      { timeout: 5000 },
    );
    expect(within(transcript).getAllByRole('listitem')).toHaveLength(11);
    expect(segmentRow).toHaveTextContent(
      'I would like to plan a small team workshop for next week',
    );
    expect(within(segmentRow).getAllByText('Mock demo confidence: 94%')).toHaveLength(1);

    await screen.findByText(
      'I would like to plan a small team workshop for next week.',
      {},
      {
        timeout: 5000,
      },
    );
    expect(within(transcript).getAllByRole('listitem')).toHaveLength(11);
    expect(segmentRow).toHaveAttribute('data-final', 'true');
    expect(within(segmentRow).getAllByText('Mock demo confidence: 94%')).toHaveLength(1);
    expect(segmentRow).toHaveTextContent(
      'I would like to plan a small team workshop for next week.',
    );
    expect(segmentRow).toHaveAttribute('data-segment-id', segmentId);
    expect(within(segmentRow).queryByText('Listening · interim')).not.toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Transcript updates' })).toHaveTextContent(
      'You, transcript revised: I would like to plan a small team workshop for next week.',
    );
    expect(fetch).not.toHaveBeenCalled();
  }, 12000);

  it('shows mock client errors with an accessible retry and no success-shaped data', async () => {
    const user = userEvent.setup();
    render(<App client={new MockApiClient({ scenario: 'server-error' })} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active'),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Couldn’t load session. The mock server failed.',
    );
    expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive');
    expect(screen.queryByRole('status', { name: 'Network status' })).not.toBeInTheDocument();
    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback'),
    ).toHaveClass('api-error');
    expect(screen.getByText('Request failed')).toBeInTheDocument();
    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback svg'),
    ).toBeInTheDocument();
    expect(screen.getByText('Your previous session data is still available.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Session response' })).not.toBeInTheDocument();

    const retry = screen.getByRole('button', { name: 'Retry session load' });
    expect(retry).toHaveTextContent('Retry');
    expect(retry).toHaveClass('button-primary');
    expect(retry).toBeEnabled();
    expect(retry).toHaveFocus();
    await user.click(retry);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Couldn’t load session. The mock server failed.',
    );
    expect(screen.queryByRole('region', { name: 'Health response' })).not.toBeInTheDocument();
  });

  it('recovers from a transient API error with keyboard activation', async () => {
    const user = userEvent.setup();
    render(<App client={new MockApiClient({ scenario: 'transient-error' })} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Couldn’t load session. Temporary mock server failure.');
    const retry = screen.getByRole('button', { name: 'Retry session load' });
    expect(retry).toHaveFocus();

    await user.keyboard('{Enter}');
    expect(
      await screen.findByText('Session details loaded successfully. Health check passed.'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Demo API' })).getByText('Success'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('retries a failed request from the keyboard and restores the active session', async () => {
    const user = userEvent.setup();
    let requestCount = 0;
    let resolveRetry: (value: unknown) => void = () => {
      throw new Error('Retry resolver was not initialized.');
    };
    const client: ApiClient = {
      getSession: vi.fn(() => {
        requestCount += 1;
        if (requestCount === 1) return Promise.reject(new Error('Temporary service failure.'));
        return new Promise((resolve) => {
          resolveRetry = resolve;
        });
      }),
      healthCheck: vi.fn(async () => ({ status: 'healthy' })),
    };
    render(<App client={client} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Couldn’t load session. Temporary service failure.');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    const retry = screen.getByRole('button', { name: 'Retry session load' });
    expect(retry).toHaveFocus();
    expect(retry).toBeEnabled();

    await user.keyboard('{Enter}');
    await waitFor(() => expect(client.getSession).toHaveBeenCalledTimes(2));
    const loadingStatus = screen.getByText('Loading session details and health status…');
    expect(
      within(screen.getByRole('region', { name: 'Demo API' })).getByText('Loading'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback svg'),
    ).toBeInTheDocument();
    expect(loadingStatus.closest('[role="status"]')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('region', { name: 'Demo API' })).toHaveAttribute('aria-busy', 'true');
    const loadingButton = screen.getByRole('button', { name: 'Load mock session (local data)' });
    expect(loadingButton).toBeDisabled();
    expect(loadingButton).toHaveAttribute('aria-busy', 'true');
    await user.keyboard('{Enter}');
    await user.click(loadingButton);
    expect(client.getSession).toHaveBeenCalledTimes(2);

    resolveRetry({ id: 'session-recovered', status: 'active' });
    expect(
      await screen.findByText('Session details loaded successfully. Health check passed.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Session response' })).toHaveTextContent(
      'session-recovered',
    );
    expect(screen.getByRole('region', { name: 'Conversation transcript' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeEnabled();
  });

  it('preserves the displayed transcript when a later session request fails', async () => {
    const user = userEvent.setup();
    let requestCount = 0;
    const client: ApiClient = {
      async getSession() {
        requestCount += 1;
        if (requestCount === 2) throw new Error('The follow-up request failed.');
        return { id: 'mock-session' };
      },
      async healthCheck() {
        return { status: 'healthy' };
      },
    };
    render(<App client={client} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    expect(
      await screen.findByRole('region', { name: 'Conversation transcript' }),
    ).toBeInTheDocument();
    const transcriptText =
      screen.getByRole('region', { name: 'Conversation transcript' }).textContent ?? '';
    expect(transcriptText).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Load mock session (local data)' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Couldn’t load session. The follow-up request failed.',
    );
    expect(screen.getByRole('region', { name: 'Session response' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Conversation transcript' })).toHaveTextContent(
      transcriptText,
    );
  });

  it('shows network failure as offline, not as a generic API error', async () => {
    const user = userEvent.setup();
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(<App client={new MockApiClient({ scenario: 'network-failure' })} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));

    const apiPanel = screen.getByRole('region', { name: 'Demo API' });
    expect(
      await screen.findByText(
        'Network unavailable. Local demo data remains available; network-backed data needs a connection.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Network status' })).toHaveTextContent(
      'You’re offline. Session actions will resume when the connection returns.',
    );
    expect(screen.getByRole('status', { name: 'Network status' })).toHaveAttribute(
      'aria-live',
      'polite',
    );
    expect(apiPanel.querySelector('.api-feedback')).toHaveClass('api-offline');
    expect(apiPanel.querySelector('.api-feedback')).toHaveAttribute('role', 'status');
    expect(within(apiPanel).getByText('Offline')).toBeInTheDocument();
    expect(apiPanel.querySelector('.api-feedback svg')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load mock session (local data)' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'End or stop session' })).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);

    act(() => window.dispatchEvent(new Event('online')));
    expect(screen.getByRole('status', { name: 'Network recovery' })).toHaveTextContent(
      'Connection restored. Session actions are available.',
    );
    expect(apiPanel.querySelector('.api-feedback')).not.toHaveClass('api-offline');
    expect(screen.getByText('Session data is ready to load.')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeEnabled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('updates network status from browser events without making network calls', async () => {
    const user = userEvent.setup();
    const fetch = vi.fn();
    let isOnline = true;
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'onLine', {
      configurable: true,
      get: () => isOnline,
    });
    vi.stubGlobal('navigator', testNavigator);
    vi.stubGlobal('fetch', fetch);
    render(<App />);

    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback'),
    ).not.toHaveClass('api-offline');
    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(
        /^Capturing$/,
      ),
    );

    isOnline = false;
    act(() => window.dispatchEvent(new Event('offline')));
    expect(
      await screen.findByText(
        'Network unavailable. Local demo data remains available; network-backed data needs a connection.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback'),
    ).toHaveClass('api-offline');
    expect(screen.getByRole('status', { name: 'Network status' })).toHaveTextContent('Offline');
    expect(screen.getByRole('status', { name: 'Network status' })).toHaveTextContent(
      'You’re offline. Session actions will resume when the connection returns.',
    );
    expect(screen.getByRole('button', { name: 'Start session' })).toBeDisabled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();

    isOnline = true;
    act(() => window.dispatchEvent(new Event('online')));
    expect(screen.getByRole('status', { name: 'Network recovery' })).toHaveTextContent(
      'Connection restored. Session actions are available.',
    );
    expect(screen.getByRole('status', { name: 'Network recovery' })).toHaveAttribute(
      'aria-live',
      'polite',
    );
    expect(
      screen.getByRole('region', { name: 'Demo API' }).querySelector('.api-feedback'),
    ).not.toHaveClass('api-offline');
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Capturing$/);
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeEnabled();
  });

  it('restores a paused capture state when connectivity returns', async () => {
    const user = userEvent.setup();
    let isOnline = true;
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'onLine', {
      configurable: true,
      get: () => isOnline,
    });
    vi.stubGlobal('navigator', testNavigator);
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(
        /^Capturing$/,
      ),
    );
    await user.click(screen.getByRole('button', { name: 'Pause microphone capture' }));
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Paused$/);

    isOnline = false;
    act(() => window.dispatchEvent(new Event('offline')));
    expect(screen.getByRole('status', { name: 'Network status' })).toHaveAttribute(
      'aria-live',
      'polite',
    );
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeDisabled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Paused$/);

    isOnline = true;
    act(() => window.dispatchEvent(new Event('online')));
    expect(screen.getByRole('status', { name: 'Network recovery' })).toHaveTextContent(
      'Connection restored. Session actions are available.',
    );
    expect(screen.getByRole('button', { name: 'Resume microphone capture' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Pause microphone capture' })).toBeDisabled();
    expect(screen.getByRole('status', { name: 'Capture status' })).toHaveTextContent(/^Paused$/);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows an accessible loading state until the mock client resolves', async () => {
    const user = userEvent.setup();
    let resolveSession: (value: unknown) => void = () => {
      throw new Error('Session response resolver was not initialized.');
    };
    const sessionResponse = new Promise<unknown>((resolve) => {
      resolveSession = resolve;
    });
    const client: ApiClient = {
      getSession: vi.fn(() => sessionResponse),
      healthCheck: vi.fn(async () => ({ status: 'healthy' })),
    };
    render(<App client={client} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    const loadingStatus = await screen.findByText('Loading session details and health status…');
    expect(loadingStatus.closest('[role="status"]')).toHaveAttribute('aria-live', 'polite');
    expect(loadingStatus.closest('[aria-busy="true"]')).toBeInTheDocument();
    const apiPanel = screen.getByRole('region', { name: 'Demo API' });
    expect(apiPanel).toHaveAttribute('aria-busy', 'true');
    const loadButton = screen.getByRole('button', { name: 'Load mock session (local data)' });
    expect(loadButton).toBeDisabled();
    expect(loadButton).toHaveAttribute('aria-busy', 'true');
    expect(loadButton).toHaveTextContent('Loading…');
    expect(loadButton.querySelector('.loading-spinner')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Session response' })).not.toBeInTheDocument();
    await user.click(loadButton);
    expect(client.getSession).toHaveBeenCalledOnce();

    resolveSession({
      id: 'session-from-client',
      status: 'active',
    });
    expect(
      await screen.findByText('Session details loaded successfully. Health check passed.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Session response' })).toHaveTextContent(
      'session-from-client',
    );
    expect(client.getSession).toHaveBeenCalledWith({ session_id: expect.any(String) });
  });

  it('keeps API controls keyboard accessible on mobile and desktop', async () => {
    const user = userEvent.setup();

    for (const width of [375, 1440]) {
      window.innerWidth = width;
      window.dispatchEvent(new Event('resize'));
      const client: ApiClient = {
        getSession: vi.fn(async () => ({ id: `session-${width}`, status: 'active' })),
        healthCheck: vi.fn(async () => ({ status: 'healthy' })),
      };
      const { unmount } = render(<App client={client} />);

      await user.click(screen.getByRole('button', { name: 'Start session' }));
      await screen.findByText('Session details loaded successfully. Health check passed.');
      const loadButton = screen.getByRole('button', { name: 'Load mock session (local data)' });
      for (
        let tabCount = 0;
        tabCount < 40 && document.activeElement !== loadButton;
        tabCount += 1
      ) {
        await user.tab();
      }
      expect(loadButton).toHaveFocus();
      await user.keyboard('{Enter}');
      await waitFor(() => expect(client.getSession).toHaveBeenCalledTimes(2));
      expect(screen.getByRole('region', { name: 'API overview' })).toBeInTheDocument();
      unmount();
    }
  });
});
