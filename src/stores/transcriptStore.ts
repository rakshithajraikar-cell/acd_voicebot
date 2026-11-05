import type { TranscriptEvent } from '../types';

export function upsertTranscriptEvent(
  events: readonly TranscriptEvent[],
  incomingEvent: TranscriptEvent,
): TranscriptEvent[] {
  const existingIndex = events.findIndex((event) => event.segmentId === incomingEvent.segmentId);
  if (existingIndex === -1) {
    return [...events, incomingEvent];
  }

  const existingEvent = events[existingIndex];
  if (existingEvent.isFinal && !incomingEvent.isFinal) {
    return [...events];
  }

  const incrementsRevision = !incomingEvent.isFinal || existingEvent.text !== incomingEvent.text;
  const { confidence: incomingConfidence, ...eventWithoutConfidence } = incomingEvent;
  const updatedEvent: TranscriptEvent = {
    ...eventWithoutConfidence,
    ...(incomingConfidence !== undefined
      ? { confidence: incomingConfidence }
      : existingEvent.confidence !== undefined
        ? { confidence: existingEvent.confidence }
        : {}),
    revision: incrementsRevision
      ? Math.max(existingEvent.revision + 1, incomingEvent.revision)
      : existingEvent.revision,
    ...(incrementsRevision
      ? { revisedAt: incomingEvent.revisedAt ?? incomingEvent.timestamp }
      : existingEvent.revisedAt
        ? { revisedAt: existingEvent.revisedAt }
        : {}),
  };
  const updatedEvents = events.filter((event) => event.segmentId !== incomingEvent.segmentId);
  updatedEvents.splice(existingIndex, 0, updatedEvent);
  return updatedEvents;
}
