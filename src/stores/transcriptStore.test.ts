import { describe, expect, it } from 'vitest';
import { upsertTranscriptEvent } from './transcriptStore';
import type { TranscriptEvent } from '../types';

const existingEvents: TranscriptEvent[] = [
  {
    type: 'user',
    id: 'user-1',
    segmentId: 'segment-1',
    isFinal: false,
    revision: 1,
    timestamp: '2026-11-04T08:00:00.000Z',
    speaker: 'You',
    text: 'Schedule the',
  },
  {
    type: 'system',
    id: 'system-1',
    segmentId: 'system-1',
    isFinal: true,
    revision: 1,
    timestamp: '2026-11-04T08:00:01.000Z',
    speaker: 'System',
    text: 'Session started.',
  },
];

describe('upsertTranscriptEvent', () => {
  it('updates an interim segment in its existing position without duplicating it', () => {
    const updatedEvent: TranscriptEvent = {
      ...existingEvents[0],
      id: 'user-1-revision-2',
      revision: 2,
      revisedAt: '2026-11-04T08:00:02.000Z',
      text: 'Schedule the design review',
      timestamp: '2026-11-04T08:00:02.000Z',
    };

    const result = upsertTranscriptEvent(existingEvents, updatedEvent);

    expect(result).toHaveLength(existingEvents.length);
    expect(result[0]).toEqual(updatedEvent);
    expect(result[0].revision).toBe(2);
    expect(result[0].revisedAt).toBe(updatedEvent.revisedAt);
    expect(result[1]).toEqual(existingEvents[1]);
    expect(result.filter((event) => event.segmentId === 'segment-1')).toHaveLength(1);
    expect(existingEvents[0].text).toBe('Schedule the');
  });

  it('replaces an interim segment with its final version in the same position', () => {
    const finalEvent: TranscriptEvent = {
      type: 'user',
      id: 'user-1-final',
      segmentId: 'segment-1',
      isFinal: true,
      revision: 2,
      revisedAt: '2026-11-04T08:00:03.000Z',
      timestamp: '2026-11-04T08:00:03.000Z',
      speaker: 'You',
      text: 'Schedule the design review tomorrow.',
    };

    const result = upsertTranscriptEvent(existingEvents, finalEvent);

    expect(result).toHaveLength(existingEvents.length);
    expect(result[0]).toEqual(finalEvent);
    expect(result[0].isFinal).toBe(true);
    expect(result[0].timestamp).toBe(finalEvent.timestamp);
    expect(result[0].revision).toBe(2);
    expect(result[0].revisedAt).toBe(finalEvent.revisedAt);
    expect(result[0].text).toBe(finalEvent.text);
    expect(result[1]).toEqual(existingEvents[1]);
    expect(result.filter((event) => event.segmentId === 'segment-1')).toHaveLength(1);
    expect(existingEvents[0].isFinal).toBe(false);
    expect(existingEvents[0].text).toBe('Schedule the');
  });

  it('appends a final event when no matching segment exists', () => {
    const finalEvent: TranscriptEvent = {
      type: 'user',
      id: 'user-new-final',
      segmentId: 'new-segment',
      isFinal: true,
      revision: 1,
      timestamp: '2026-11-04T08:00:03.000Z',
      speaker: 'You',
      text: 'A new finalized segment.',
    };

    const result = upsertTranscriptEvent(existingEvents, finalEvent);

    expect(result).toEqual([...existingEvents, finalEvent]);
    expect(result).toHaveLength(existingEvents.length + 1);
  });

  it('does not replace a final segment with a late interim update', () => {
    const finalEvent: TranscriptEvent = {
      ...existingEvents[0],
      isFinal: true,
      revision: 2,
      revisedAt: '2026-11-04T08:00:02.000Z',
      text: 'Final transcript.',
    };
    const lateInterim: TranscriptEvent = {
      ...existingEvents[0],
      id: 'late-interim',
      revision: 2,
      text: 'Stale interim text.',
    };

    const result = upsertTranscriptEvent([finalEvent, existingEvents[1]], lateInterim);

    expect(result[0]).toEqual(finalEvent);
    expect(result.filter((event) => event.segmentId === 'segment-1')).toHaveLength(1);
  });

  it('updates revised final text in place and increments its revision', () => {
    const finalEvent: TranscriptEvent = {
      ...existingEvents[0],
      isFinal: true,
      revision: 2,
      revisedAt: '2026-11-04T08:00:02.000Z',
      timestamp: '2026-11-04T08:00:02.000Z',
      text: 'Schedule the design review.',
    };
    const revisedFinal: TranscriptEvent = {
      ...finalEvent,
      id: 'user-1-final-revision-2',
      revision: 3,
      revisedAt: '2026-11-04T08:00:04.000Z',
      timestamp: '2026-11-04T08:00:04.000Z',
      text: 'Schedule the design review tomorrow.',
    };

    const result = upsertTranscriptEvent([finalEvent, existingEvents[1]], revisedFinal);

    expect(result).toHaveLength(existingEvents.length);
    expect(result[0]).toEqual(revisedFinal);
    expect(result[0].segmentId).toBe(finalEvent.segmentId);
    expect(result[0].revision).toBe(3);
    expect(result[0].revisedAt).toBe(revisedFinal.revisedAt);
    expect(result.filter((event) => event.segmentId === finalEvent.segmentId)).toHaveLength(1);
    expect(result[1]).toEqual(existingEvents[1]);
  });

  it('keeps the revision when finalization does not change the text', () => {
    const finalEvent: TranscriptEvent = {
      ...existingEvents[0],
      isFinal: true,
      revision: 2,
      revisedAt: '2026-11-04T08:00:02.000Z',
    };
    const finalizedWithoutTextChange: TranscriptEvent = {
      ...finalEvent,
      id: 'user-1-final',
      revision: 3,
      revisedAt: '2026-11-04T08:00:03.000Z',
      timestamp: '2026-11-04T08:00:03.000Z',
    };

    const result = upsertTranscriptEvent([finalEvent], finalizedWithoutTextChange);

    expect(result).toHaveLength(1);
    expect(result[0].revision).toBe(2);
    expect(result[0].revisedAt).toBe(finalEvent.revisedAt);
  });

  it('preserves confidence through interim revisions and finalization unless an update supplies a new value', () => {
    const initial: TranscriptEvent = {
      ...existingEvents[0],
      confidence: 0.94,
    };
    const interimRevision: TranscriptEvent = {
      ...initial,
      id: 'user-interim-revision',
      text: 'Schedule the design review',
      timestamp: '2026-11-04T08:00:02.000Z',
      confidence: undefined,
    };
    const finalWithoutConfidence: TranscriptEvent = {
      ...interimRevision,
      id: 'user-final',
      isFinal: true,
      text: 'Schedule the design review tomorrow.',
      timestamp: '2026-11-04T08:00:03.000Z',
    };
    const finalWithUpdatedConfidence: TranscriptEvent = {
      ...finalWithoutConfidence,
      id: 'user-final-confidence-update',
      text: 'Schedule the design review tomorrow at 10.',
      timestamp: '2026-11-04T08:00:04.000Z',
      confidence: 0.88,
    };

    const afterInterim = upsertTranscriptEvent([initial], interimRevision);
    expect(afterInterim).toHaveLength(1);
    expect(afterInterim[0].confidence).toBe(0.94);

    const afterFinal = upsertTranscriptEvent(afterInterim, finalWithoutConfidence);
    expect(afterFinal).toHaveLength(1);
    expect(afterFinal[0].confidence).toBe(0.94);

    const afterExplicitUpdate = upsertTranscriptEvent(afterFinal, finalWithUpdatedConfidence);
    expect(afterExplicitUpdate).toHaveLength(1);
    expect(afterExplicitUpdate[0].confidence).toBe(0.88);
    expect(afterExplicitUpdate[0].segmentId).toBe(initial.segmentId);
  });

  it('does not add confidence to an unscored segment during interim or final updates', () => {
    const initial: TranscriptEvent = {
      ...existingEvents[0],
      confidence: undefined,
    };
    const interim: TranscriptEvent = {
      ...initial,
      id: 'unscored-interim-revision',
      text: 'Schedule the design review',
    };
    const final: TranscriptEvent = {
      ...interim,
      id: 'unscored-final',
      isFinal: true,
      text: 'Schedule the design review tomorrow.',
    };

    const afterInterim = upsertTranscriptEvent([initial], interim);
    const afterFinal = upsertTranscriptEvent(afterInterim, final);

    expect(afterInterim).toHaveLength(1);
    expect(afterFinal).toHaveLength(1);
    expect(afterFinal[0].confidence).toBeUndefined();
    expect(afterFinal[0]).not.toHaveProperty('confidence');
  });
});
