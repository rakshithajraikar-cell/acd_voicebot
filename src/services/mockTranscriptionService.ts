import { mockTranscriptionFixture } from '../fixtures/mockTranscription';
import type { TranscriptEvent } from '../types';

const transcriptUpdates = [
  { text: 'I would like to plan', isFinal: false },
  { text: 'I would like to plan a small team workshop', isFinal: false },
  { text: 'I would like to plan a small team workshop for next week', isFinal: false },
  { text: 'I would like to plan a small team workshop for next week.', isFinal: true },
] as const;

const updateIntervalMs = 1400;
let nextSegmentNumber = 1;

export function startMockTranscription(
  onEvent: (event: TranscriptEvent) => void,
  fixture: Readonly<{ confidence?: number }> = mockTranscriptionFixture,
): () => void {
  const segmentId = `mock-live-segment-${nextSegmentNumber}`;
  nextSegmentNumber += 1;
  let updateIndex = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  function emitNextUpdate(): void {
    if (stopped) return;

    const update = transcriptUpdates[updateIndex];
    const timestamp = new Date().toISOString();
    onEvent({
      type: 'user',
      id: `${segmentId}-revision-${updateIndex + 1}`,
      segmentId,
      isFinal: update.isFinal,
      revision: updateIndex + 1,
      ...(updateIndex > 0 ? { revisedAt: timestamp } : {}),
      timestamp,
      speaker: 'You',
      text: update.text,
      ...(fixture.confidence !== undefined ? { confidence: fixture.confidence } : {}),
    });

    updateIndex += 1;
    if (updateIndex < transcriptUpdates.length) {
      timer = setTimeout(emitNextUpdate, updateIntervalMs);
    }
  }

  emitNextUpdate();

  return () => {
    stopped = true;
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  };
}
