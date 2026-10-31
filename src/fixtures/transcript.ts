import type { TranscriptEvent } from '../types';

export const transcriptFixture: TranscriptEvent[] = [
  {
    type: 'system',
    id: 'event-1',
    timestamp: '2026-10-30T10:42:00.000Z',
    speaker: 'System',
    text: 'Session started.',
  },
  {
    type: 'user',
    id: 'event-2',
    timestamp: '2026-10-30T10:42:18.000Z',
    speaker: 'You',
    text: 'Help me prepare a clear agenda for our product design review.',
  },
  {
    type: 'assistant',
    id: 'event-3',
    timestamp: '2026-10-30T10:42:34.000Z',
    speaker: 'Co-Pilot',
    text: 'Absolutely. We can shape it around goals, key decisions, and next steps.',
  },
  {
    type: 'assistant',
    id: 'event-4',
    timestamp: '2026-10-30T10:42:41.000Z',
    speaker: 'Co-Pilot',
    text: 'What should the team leave the meeting aligned on?',
  },
  {
    type: 'user',
    id: 'event-5',
    timestamp: '2026-10-30T10:43:02.000Z',
    speaker: 'You',
    text: 'The onboarding flow and the first-run experience.',
  },
  {
    type: 'assistant',
    id: 'event-6',
    timestamp: '2026-10-30T10:43:20.000Z',
    speaker: 'Co-Pilot',
    text: 'Got it. I’ll keep the agenda focused on those two areas.',
  },
  {
    type: 'user',
    id: 'event-7',
    timestamp: '2026-10-30T10:43:36.000Z',
    speaker: 'You',
    text: 'We also need to leave with clear owners for follow-up work.',
  },
  {
    type: 'assistant',
    id: 'event-8',
    timestamp: '2026-10-30T10:43:55.000Z',
    speaker: 'Co-Pilot',
    text: 'I’ll add an action-items section with an owner and due date for each decision.',
  },
  {
    type: 'user',
    id: 'event-9',
    timestamp: '2026-10-30T10:44:12.000Z',
    speaker: 'You',
    text: 'That sounds good. Keep the meeting to 45 minutes.',
  },
  {
    type: 'assistant',
    id: 'event-10',
    timestamp: '2026-10-30T10:44:30.000Z',
    speaker: 'Co-Pilot',
    text: 'Here’s a focused 45-minute agenda: goals, onboarding, first-run experience, decisions, and owners.',
  },
];
