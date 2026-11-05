import { useEffect, useRef, useState } from 'react';
import { AudioLines, Bot, Gauge, PencilLine, UserRound } from 'lucide-react';
import type { TranscriptEvent } from '../types';

type TranscriptTimelineProps = {
  events: TranscriptEvent[];
};

function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(timestamp));
}

function SpeakerIcon({ type }: { type: TranscriptEvent['type'] }) {
  if (type === 'user') return <UserRound size={15} aria-hidden="true" />;
  if (type === 'assistant') return <Bot size={15} aria-hidden="true" />;
  return <AudioLines size={14} aria-hidden="true" />;
}

function getSpeakerLabel(type: TranscriptEvent['type']): string {
  if (type === 'user') return 'You';
  if (type === 'assistant') return 'Assistant';
  return 'System';
}

function RevisedLabel() {
  return (
    <span className="transcript-revised-label">
      <PencilLine size={10} aria-hidden="true" />
      Revised
    </span>
  );
}

function ConfidenceLabel({ confidence }: { confidence: number }) {
  const percentage = Math.round(confidence * 100);

  return (
    <span
      className="transcript-confidence-label"
      aria-label={`Mock demo confidence: ${percentage}%`}
    >
      <Gauge size={10} aria-hidden="true" />
      Mock demo confidence: {percentage}%
    </span>
  );
}

function compareEvents(a: TranscriptEvent, b: TranscriptEvent): number {
  const timestampDifference = Date.parse(a.timestamp) - Date.parse(b.timestamp);
  if (timestampDifference !== 0) return timestampDifference;
  if (a.id < b.id) return -1;
  if (a.id > b.id) return 1;
  return 0;
}

export function TranscriptTimeline({ events }: TranscriptTimelineProps) {
  const timelineRef = useRef<HTMLDivElement>(null);
  const previousEventsRef = useRef(events);
  const hasMountedRef = useRef(false);
  const announcementTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [announcement, setAnnouncement] = useState('');

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true;
      previousEventsRef.current = events;
      return;
    }

    const previousEventsBySegment = new Map(
      previousEventsRef.current.map((event) => [event.segmentId, event]),
    );
    const changedEvents = events.filter((event) => {
      const previousEvent = previousEventsBySegment.get(event.segmentId);
      return (
        !previousEvent ||
        previousEvent.text !== event.text ||
        previousEvent.isFinal !== event.isFinal ||
        previousEvent.revision !== event.revision ||
        previousEvent.revisedAt !== event.revisedAt
      );
    });
    previousEventsRef.current = events;

    if (changedEvents.length > 0) {
      const sortedChangedEvents = [...changedEvents].sort(compareEvents);
      const latestChangedEvent = sortedChangedEvents[sortedChangedEvents.length - 1];
      if (announcementTimerRef.current !== null) {
        clearTimeout(announcementTimerRef.current);
        announcementTimerRef.current = null;
      }

      const speakerLabel = getSpeakerLabel(latestChangedEvent.type);
      const previousEvent = previousEventsBySegment.get(latestChangedEvent.segmentId);
      const isRevision =
        previousEvent !== undefined &&
        (latestChangedEvent.revision > previousEvent.revision ||
          latestChangedEvent.revisedAt !== previousEvent.revisedAt);
      const updateAnnouncement = isRevision
        ? `${speakerLabel}, transcript revised: ${latestChangedEvent.text}`
        : latestChangedEvent.isFinal
          ? `${speakerLabel}: ${latestChangedEvent.text}`
          : `${speakerLabel}, interim transcript: ${latestChangedEvent.text}`;

      if (latestChangedEvent.isFinal) {
        setAnnouncement(updateAnnouncement);
      } else {
        announcementTimerRef.current = setTimeout(() => {
          setAnnouncement(updateAnnouncement);
          announcementTimerRef.current = null;
        }, 800);
      }
    }
  }, [events]);

  useEffect(() => {
    const timeline = timelineRef.current;
    if (timeline) {
      if (typeof timeline.scrollTo === 'function') {
        timeline.scrollTo({ top: timeline.scrollHeight, behavior: 'smooth' });
      } else {
        timeline.scrollTop = timeline.scrollHeight;
      }
    }
  }, [events]);

  useEffect(
    () => () => {
      if (announcementTimerRef.current !== null) {
        clearTimeout(announcementTimerRef.current);
      }
    },
    [],
  );

  if (events.length === 0) {
    return (
      <div className="empty-transcript" role="status">
        <span className="empty-icon">
          <AudioLines size={20} aria-hidden="true" />
        </span>
        <strong>No transcript yet</strong>
        <span>Start a session to see events here, or explore the sample conversation.</span>
      </div>
    );
  }

  const sortedEvents = [...events].sort(compareEvents);

  return (
    <>
      <div
        className="visually-hidden"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        aria-label="Transcript updates"
      >
        {announcement}
      </div>
      <div
        ref={timelineRef}
        className="transcript-scroll-region"
        role="region"
        aria-label="Conversation transcript"
        tabIndex={0}
      >
        <ol className="transcript-list">
          {sortedEvents.map((event) => (
            <li
              className={`transcript-item transcript-${event.type}${event.isFinal ? '' : ' transcript-item-interim'}`}
              key={event.segmentId}
              data-segment-id={event.segmentId}
              data-final={event.isFinal}
              data-revision={event.revision}
            >
              {event.type === 'system' ? (
                <div className="timeline-notice">
                  <span className="timeline-notice-icon">
                    <SpeakerIcon type={event.type} />
                  </span>
                  <span className="timeline-notice-speaker">{getSpeakerLabel(event.type)}</span>
                  <span className="timeline-notice-text">{event.text}</span>
                  {(event.revision > 1 || event.revisedAt) && <RevisedLabel />}
                  {event.confidence !== undefined && (
                    <ConfidenceLabel confidence={event.confidence} />
                  )}
                  <time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time>
                </div>
              ) : (
                <>
                  <span
                    className={`speaker-avatar speaker-${event.speaker.toLowerCase().replace('-', '')}`}
                  >
                    <SpeakerIcon type={event.type} />
                  </span>
                  <div className="transcript-content">
                    <div className="transcript-meta">
                      <strong>{getSpeakerLabel(event.type)}</strong>
                      <time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time>
                      {event.type === 'assistant' && <span className="assistant-tag">AI</span>}
                      {(event.revision > 1 || event.revisedAt) && <RevisedLabel />}
                      {event.confidence !== undefined && (
                        <ConfidenceLabel confidence={event.confidence} />
                      )}
                      {!event.isFinal && (
                        <span className="transcript-interim-label">Listening · interim</span>
                      )}
                    </div>
                    <p>{event.text}</p>
                  </div>
                </>
              )}
            </li>
          ))}
        </ol>
      </div>
    </>
  );
}
