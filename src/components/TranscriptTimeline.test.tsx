import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TranscriptTimeline } from './TranscriptTimeline';
import type { TranscriptEvent } from '../types';

const events: TranscriptEvent[] = [
  {
    type: 'assistant',
    id: 'assistant-b',
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'Co-Pilot',
    text: 'Assistant event B',
  },
  {
    type: 'system',
    id: 'system-a',
    timestamp: '2026-10-30T10:41:00.000Z',
    speaker: 'System',
    text: 'Session started.',
  },
  {
    type: 'user',
    id: 'user-a',
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'You',
    text: 'User event',
  },
  {
    type: 'assistant',
    id: 'assistant-a',
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'Co-Pilot',
    text: 'Assistant event A',
  },
];

describe('TranscriptTimeline', () => {
  it('shows a friendly empty state when there are no events', () => {
    render(<TranscriptTimeline events={[]} />);

    expect(screen.getByRole('status')).toHaveTextContent('No transcript yet');
    expect(screen.getByRole('status')).toHaveTextContent(
      'Start a session to see events here, or explore the sample conversation.',
    );
    expect(
      screen.queryByRole('region', { name: 'Conversation transcript' }),
    ).not.toBeInTheDocument();
  });

  it('sorts events by timestamp and id without mutating its input', () => {
    const originalOrder = events.map((event) => event.id);
    render(<TranscriptTimeline events={events} />);

    const region = screen.getByRole('region', { name: 'Conversation transcript' });
    expect(region).toHaveAttribute('tabIndex', '0');
    const items = within(region).getAllByRole('listitem');
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining('Session started.'),
      expect.stringContaining('Assistant event A'),
      expect.stringContaining('Assistant event B'),
      expect.stringContaining('You'),
    ]);
    expect(events.map((event) => event.id)).toEqual(originalOrder);
  });

  it('shows speaker labels, readable timestamps, and distinct event styles', () => {
    render(<TranscriptTimeline events={events} />);

    const items = within(
      screen.getByRole('region', { name: 'Conversation transcript' }),
    ).getAllByRole('listitem');
    expect(items[0]).toHaveClass('transcript-system');
    expect(items[0]).toHaveTextContent('System');
    expect(items[0].querySelector('time')).toHaveAttribute('dateTime', events[1].timestamp);
    expect(items[1]).toHaveClass('transcript-assistant');
    expect(items[1]).toHaveTextContent('Assistant');
    expect(items[1].querySelector('time')).toHaveAttribute('dateTime', events[3].timestamp);
    expect(items[1].querySelector('time')?.textContent).toMatch(/\d{1,2}:\d{2}/);
    expect(items[1].querySelector('time')?.textContent).not.toBe(events[3].timestamp);
    expect(items[3]).toHaveClass('transcript-user');
    expect(items[3]).toHaveTextContent('You');
  });
});
