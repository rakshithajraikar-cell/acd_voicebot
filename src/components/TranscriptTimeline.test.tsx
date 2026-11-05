import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TranscriptTimeline } from './TranscriptTimeline';
import { upsertTranscriptEvent } from '../stores/transcriptStore';
import { transcriptFixture } from '../fixtures/transcript';
import type { TranscriptEvent } from '../types';

const events: TranscriptEvent[] = [
  {
    type: 'assistant',
    id: 'assistant-b',
    segmentId: 'assistant-b',
    isFinal: true,
    revision: 1,
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'Co-Pilot',
    text: 'Assistant event B',
  },
  {
    type: 'system',
    id: 'system-a',
    segmentId: 'system-a',
    isFinal: true,
    revision: 1,
    timestamp: '2026-10-30T10:41:00.000Z',
    speaker: 'System',
    text: 'Session started.',
  },
  {
    type: 'user',
    id: 'user-a',
    segmentId: 'user-a',
    isFinal: true,
    revision: 1,
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'You',
    text: 'User event',
  },
  {
    type: 'assistant',
    id: 'assistant-a',
    segmentId: 'assistant-a',
    isFinal: true,
    revision: 1,
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'Co-Pilot',
    text: 'Assistant event A',
  },
];

afterEach(() => {
  vi.useRealTimers();
});

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

  it('makes the transcript region keyboard reachable', async () => {
    const user = userEvent.setup();
    render(<TranscriptTimeline events={events} />);

    await user.tab();

    expect(screen.getByRole('region', { name: 'Conversation transcript' })).toHaveFocus();
  });

  it('shows speaker labels, readable timestamps, and distinct event styles', () => {
    render(<TranscriptTimeline events={events} />);

    const items = within(
      screen.getByRole('region', { name: 'Conversation transcript' }),
    ).getAllByRole('listitem');
    expect(items).toHaveLength(events.length);
    items.forEach((item) => {
      expect(
        item.querySelector('.timeline-notice-speaker, .transcript-meta strong'),
      ).toHaveTextContent(/^(You|Assistant|System)$/);
      const timestamp = item.querySelector('time');
      expect(timestamp).toBeInTheDocument();
      expect(timestamp).toHaveAttribute('dateTime');
      expect(timestamp).not.toHaveTextContent(/^\d{4}-\d{2}-\d{2}T/);
      expect(within(item).queryByText(/Confidence:/)).not.toBeInTheDocument();
    });
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

  it('updates interim text in place and debounces polite announcements until speech pauses', () => {
    vi.useFakeTimers();
    const interim: TranscriptEvent = {
      type: 'user',
      id: 'user-interim',
      segmentId: 'live-user-segment',
      isFinal: false,
      revision: 1,
      timestamp: '2026-10-30T10:42:00.000Z',
      speaker: 'You',
      text: 'Schedule the design',
    };
    const final: TranscriptEvent = {
      ...interim,
      id: 'user-final',
      isFinal: true,
      revision: 2,
      text: 'Schedule the design review tomorrow.',
    };
    let transcript = upsertTranscriptEvent([], interim);
    const { rerender } = render(<TranscriptTimeline events={transcript} />);
    const region = screen.getByRole('region', { name: 'Conversation transcript' });
    const interimRow = within(region).getByRole('listitem');
    const announcement = screen.getByRole('status', { name: 'Transcript updates' });
    expect(interimRow).toHaveAttribute('data-segment-id', 'live-user-segment');
    expect(interimRow).toHaveAttribute('data-final', 'false');
    expect(interimRow).toHaveClass('transcript-item-interim');
    expect(within(interimRow).getByText('Listening · interim')).toBeInTheDocument();
    expect(within(interimRow).getByText('You')).toBeInTheDocument();
    expect(within(interimRow).getByRole('time')).toHaveAttribute('dateTime', interim.timestamp);
    expect(within(interimRow).getByRole('time')).not.toHaveTextContent(interim.timestamp);
    const interimDisplayTime = within(interimRow).getByRole('time').textContent;
    expect(announcement).toHaveAttribute('aria-live', 'polite');
    expect(announcement).toHaveAttribute('aria-atomic', 'true');

    const revisedInterim = {
      ...interim,
      id: 'user-interim-revision',
      text: 'Schedule the design review',
    };
    transcript = upsertTranscriptEvent(transcript, revisedInterim);
    rerender(<TranscriptTimeline events={transcript} />);
    expect(within(region).getByRole('listitem')).toBe(interimRow);
    expect(interimRow).toHaveAttribute('data-revision', '2');
    expect(interimRow).toHaveTextContent('Schedule the design review');
    expect(announcement).toBeEmptyDOMElement();

    act(() => vi.advanceTimersByTime(600));
    const latestInterim = {
      ...revisedInterim,
      id: 'user-interim-revision-2',
      text: 'Schedule the design review tomorrow',
    };
    transcript = upsertTranscriptEvent(transcript, latestInterim);
    rerender(<TranscriptTimeline events={transcript} />);
    expect(within(region).getAllByRole('listitem')).toHaveLength(1);
    expect(interimRow).toHaveAttribute('data-revision', '3');
    act(() => vi.advanceTimersByTime(799));
    expect(announcement).toBeEmptyDOMElement();
    act(() => vi.advanceTimersByTime(1));
    expect(announcement).toHaveTextContent(
      'You, transcript revised: Schedule the design review tomorrow',
    );

    const finalEvent = {
      ...final,
      id: 'user-final',
      timestamp: '2026-10-30T10:43:05.000Z',
      text: 'Schedule the design review tomorrow.',
    };
    transcript = upsertTranscriptEvent(transcript, finalEvent);
    rerender(<TranscriptTimeline events={transcript} />);

    const finalRows = within(region).getAllByRole('listitem');
    expect(finalRows).toHaveLength(1);
    expect(finalRows[0]).toBe(interimRow);
    expect(finalRows[0]).toHaveAttribute('data-final', 'true');
    expect(finalRows[0]).toHaveAttribute('data-revision', '4');
    expect(finalRows[0]).not.toHaveClass('transcript-item-interim');
    expect(finalRows[0]).toHaveTextContent('Schedule the design review tomorrow.');
    expect(within(finalRows[0]).getByText('Revised')).toBeInTheDocument();
    expect(within(finalRows[0]).getByText('Revised').querySelector('svg')).toHaveAttribute(
      'aria-hidden',
      'true',
    );
    expect(within(finalRows[0]).queryByText('Listening · interim')).not.toBeInTheDocument();
    expect(within(finalRows[0]).getByText('You')).toBeInTheDocument();
    expect(within(finalRows[0]).getByRole('time')).toHaveAttribute(
      'dateTime',
      finalEvent.timestamp,
    );
    expect(within(finalRows[0]).getByRole('time')).not.toHaveTextContent(finalEvent.timestamp);
    expect(within(finalRows[0]).getByRole('time').textContent).not.toBe(interimDisplayTime);
    expect(announcement).toHaveTextContent(
      'You, transcript revised: Schedule the design review tomorrow.',
    );
  });

  it('marks a revised final segment and announces its updated text politely', () => {
    const originalFinal: TranscriptEvent = {
      type: 'user',
      id: 'final-original',
      segmentId: 'final-revision-segment',
      isFinal: true,
      revision: 1,
      timestamp: '2026-10-30T10:42:00.000Z',
      speaker: 'You',
      text: 'Schedule the design review.',
    };
    const revisedFinalInput: TranscriptEvent = {
      ...originalFinal,
      id: 'final-revised',
      timestamp: '2026-10-30T10:43:00.000Z',
      text: 'Schedule the design review for tomorrow.',
    };
    const { rerender } = render(<TranscriptTimeline events={[originalFinal]} />);
    const region = screen.getByRole('region', { name: 'Conversation transcript' });
    const originalRow = within(region).getByRole('listitem');
    const announcement = screen.getByRole('status', { name: 'Transcript updates' });

    const updatedFinals = upsertTranscriptEvent([originalFinal], revisedFinalInput);
    const updatedFinal = updatedFinals[0];
    if (!updatedFinal) throw new Error('Revised transcript segment was not returned.');
    rerender(<TranscriptTimeline events={[updatedFinal]} />);

    const updatedRow = within(region).getByRole('listitem');
    expect(updatedRow).toBe(originalRow);
    expect(updatedRow).toHaveAttribute('data-revision', '2');
    expect(updatedFinal.revision).toBe(originalFinal.revision + 1);
    expect(updatedFinal.revisedAt).toBe(revisedFinalInput.timestamp);
    expect(within(region).getAllByRole('listitem')).toHaveLength(1);
    expect(updatedRow).toHaveTextContent('Schedule the design review for tomorrow.');
    expect(within(updatedRow).getByText('Revised')).toBeInTheDocument();
    expect(announcement).toHaveAttribute('aria-live', 'polite');
    expect(announcement).toHaveTextContent(
      'You, transcript revised: Schedule the design review for tomorrow.',
    );
  });

  it('renders supplied confidence separately from revision state and hides absent values', () => {
    const withConfidence: TranscriptEvent = {
      type: 'user',
      id: 'confident-segment',
      segmentId: 'confident-segment',
      isFinal: true,
      revision: 2,
      revisedAt: '2026-10-30T10:43:00.000Z',
      timestamp: '2026-10-30T10:43:00.000Z',
      speaker: 'You',
      text: 'Schedule the design review for tomorrow.',
      confidence: 0.92,
    };
    const withoutConfidence: TranscriptEvent = {
      ...withConfidence,
      id: 'no-confidence-segment',
      segmentId: 'no-confidence-segment',
      revision: 1,
      revisedAt: undefined,
      text: 'No confidence value was supplied.',
      confidence: undefined,
    };
    render(<TranscriptTimeline events={[withConfidence, withoutConfidence]} />);

    const region = screen.getByRole('region', { name: 'Conversation transcript' });
    const [revisedRow, plainRow] = within(region).getAllByRole('listitem');
    expect(within(revisedRow).getByText('Mock demo confidence: 92%')).toBeInTheDocument();
    expect(within(revisedRow).getByLabelText('Mock demo confidence: 92%')).toBeInTheDocument();
    expect(within(revisedRow).getByText('Revised')).toBeInTheDocument();
    expect(within(plainRow).queryByText(/Mock demo confidence:/)).not.toBeInTheDocument();
    expect(within(plainRow).queryByText('Revised')).not.toBeInTheDocument();
  });

  it('keeps one visible confidence label through interim, revised, and final updates', () => {
    const initial: TranscriptEvent = {
      type: 'user',
      id: 'confidence-interim',
      segmentId: 'confidence-transition',
      isFinal: false,
      revision: 1,
      timestamp: '2026-10-30T10:42:00.000Z',
      speaker: 'You',
      text: 'Schedule the',
      confidence: 0.94,
    };
    const revision: TranscriptEvent = {
      ...initial,
      id: 'confidence-revision',
      revision: 2,
      revisedAt: '2026-10-30T10:42:01.000Z',
      timestamp: '2026-10-30T10:42:01.000Z',
      text: 'Schedule the design review',
      confidence: undefined,
    };
    const final: TranscriptEvent = {
      ...revision,
      id: 'confidence-final',
      revision: 3,
      isFinal: true,
      revisedAt: '2026-10-30T10:42:02.000Z',
      timestamp: '2026-10-30T10:42:02.000Z',
      text: 'Schedule the design review tomorrow.',
    };
    let transcript = upsertTranscriptEvent([], initial);
    const { rerender } = render(<TranscriptTimeline events={transcript} />);
    const region = screen.getByRole('region', { name: 'Conversation transcript' });
    const row = within(region).getByRole('listitem');
    const expectOneConfidence = () => {
      expect(within(row).getAllByText('Mock demo confidence: 94%')).toHaveLength(1);
      expect(within(region).getAllByRole('listitem')).toHaveLength(1);
    };
    expectOneConfidence();

    transcript = upsertTranscriptEvent(transcript, revision);
    rerender(<TranscriptTimeline events={transcript} />);
    expect(within(region).getByRole('listitem')).toBe(row);
    expectOneConfidence();

    transcript = upsertTranscriptEvent(transcript, final);
    rerender(<TranscriptTimeline events={transcript} />);
    expect(within(region).getByRole('listitem')).toBe(row);
    expect(row).toHaveAttribute('data-final', 'true');
    expectOneConfidence();
  });

  it('shows only confidence values explicitly supplied by the mock transcript fixture', () => {
    render(<TranscriptTimeline events={transcriptFixture} />);
    const region = screen.getByRole('region', { name: 'Conversation transcript' });
    const confidenceLabels = within(region).getAllByText(/Mock demo confidence:/);

    expect(confidenceLabels.map((label) => label.textContent)).toEqual([
      'Mock demo confidence: 94%',
      'Mock demo confidence: 88%',
      'Mock demo confidence: 91%',
    ]);
    expect(within(region).getAllByRole('listitem')).toHaveLength(transcriptFixture.length);
    within(region)
      .getAllByRole('listitem')
      .filter((item) => !item.textContent?.includes('Mock demo confidence:'))
      .forEach((item) => expect(within(item).queryByText(/confidence/i)).not.toBeInTheDocument());
  });
});
