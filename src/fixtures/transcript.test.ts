import { describe, expect, it } from 'vitest';
import { transcriptFixture } from './transcript';

describe('transcript fixture', () => {
  it('contains 8–12 typed, timestamped events in chronological order', () => {
    expect(transcriptFixture.length).toBeGreaterThanOrEqual(8);
    expect(transcriptFixture.length).toBeLessThanOrEqual(12);
    expect(new Set(transcriptFixture.map((event) => event.id)).size).toBe(transcriptFixture.length);
    expect(new Set(transcriptFixture.map((event) => event.segmentId)).size).toBe(
      transcriptFixture.length,
    );

    const timestamps = transcriptFixture.map((event) => Date.parse(event.timestamp));
    expect(timestamps.every(Number.isFinite)).toBe(true);
    expect(timestamps).toEqual([...timestamps].sort((a, b) => a - b));

    transcriptFixture.forEach((event) => {
      expect(event.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/);
      expect(event.speaker).toBeTruthy();
      expect(event.text).toBeTruthy();
      expect(typeof event.isFinal).toBe('boolean');
    });

    expect(transcriptFixture).toContainEqual(
      expect.objectContaining({
        type: 'system',
        speaker: 'System',
        text: 'Session started.',
      }),
    );
    expect(new Set(transcriptFixture.map((event) => event.type))).toEqual(
      new Set(['user', 'assistant', 'system']),
    );
  });

  it('labels only selected segments with clearly illustrative mock confidence values', () => {
    expect(
      transcriptFixture
        .filter((event) => event.confidence !== undefined)
        .map(({ segmentId, confidence }) => ({ segmentId, confidence })),
    ).toEqual([
      { segmentId: 'event-2', confidence: 0.94 },
      { segmentId: 'event-3', confidence: 0.88 },
      { segmentId: 'event-5', confidence: 0.91 },
    ]);
    expect(transcriptFixture.some((event) => event.confidence === undefined)).toBe(true);
  });
});
