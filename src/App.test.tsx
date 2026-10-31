import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MockApiClient, type ApiClient } from './api/client';
import { apiRouteOverview } from './api/routeOverview';
import App from './App';

afterEach(() => {
  vi.unstubAllGlobals();
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
    screen
      .getAllByRole('button', { name: 'New session' })
      .forEach((button) => expect(button).toBeDisabled());
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
    await user.keyboard('{Enter}');
    expect(await screen.findByRole('status', { name: 'Session status' })).toHaveTextContent(
      'Active',
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

  it('does not request microphone access on page load or session creation', async () => {
    const user = userEvent.setup();
    const getUserMedia = vi.fn();
    const testNavigator = Object.create(navigator) as Navigator;
    Object.defineProperty(testNavigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal('navigator', testNavigator);

    render(<App />);
    expect(getUserMedia).not.toHaveBeenCalled();

    await user.click(screen.getAllByRole('button', { name: 'New session' })[0]);
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Untitled session' }),
    ).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it('places every enabled link and button in the keyboard tab order', async () => {
    const user = userEvent.setup();
    render(<App />);

    const controls = Array.from(
      document.querySelectorAll<HTMLAnchorElement | HTMLButtonElement>(
        'a[href], button:not(:disabled)',
      ),
    );
    const visited = new Set<Element>();
    for (let index = 0; index < controls.length; index += 1) {
      await user.tab();
      visited.add(document.activeElement as Element);
    }

    expect(visited.size).toBe(controls.length);
    controls.forEach((control) => expect(visited.has(control)).toBe(true));
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

  it('ends a session immediately and disables invalid actions', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'End or stop session' })).toBeEnabled(),
    );
    await user.click(screen.getByRole('button', { name: 'End or stop session' }));
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
    expect(screen.getByRole('region', { name: 'Session response' })).toHaveTextContent(
      'session-001',
    );
    expect(screen.getByRole('region', { name: 'Health response' })).toHaveTextContent(
      'healthy',
    );
    const items = Array.from(conversation.querySelectorAll('li'));
    expect(items).toHaveLength(10);
    expect(items[0]).toHaveTextContent('Session started.');
    expect(items[1]).toHaveTextContent('Help me prepare a clear agenda');
    expect(items[9]).toHaveTextContent('Here’s a focused 45-minute agenda');
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

  it('shows mock client errors and retry guidance without success-shaped data', async () => {
    const user = userEvent.setup();
    render(<App client={new MockApiClient({ scenario: 'server-error' })} />);

    await user.click(screen.getByRole('button', { name: 'Start session' }));
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Session status' })).toHaveTextContent('Active'),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('The mock server failed.');
    expect(
      screen.getByText('Check the connection or mock scenario, then retry the session load.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Session response' })).not.toBeInTheDocument();

    const retry = screen.getByRole('button', {
      name: 'Retry loading mock session (local data)',
    });
    expect(retry).toBeEnabled();
    await user.click(retry);
    expect(await screen.findByRole('alert')).toHaveTextContent('The mock server failed.');
    expect(screen.queryByRole('region', { name: 'Health response' })).not.toBeInTheDocument();
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
    expect(loadingStatus.closest('[aria-busy="true"]')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load mock session (local data)' })).toBeDisabled();
    expect(screen.queryByRole('region', { name: 'Session response' })).not.toBeInTheDocument();

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
