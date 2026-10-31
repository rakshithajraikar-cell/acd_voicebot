import { useEffect, useRef } from 'react';
import { AudioLines, Bot, UserRound } from 'lucide-react';
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

function compareEvents(a: TranscriptEvent, b: TranscriptEvent): number {
  const timestampDifference = Date.parse(a.timestamp) - Date.parse(b.timestamp);
  if (timestampDifference !== 0) return timestampDifference;
  if (a.id < b.id) return -1;
  if (a.id > b.id) return 1;
  return 0;
}

export function TranscriptTimeline({ events }: TranscriptTimelineProps) {
  const timelineRef = useRef<HTMLDivElement>(null);

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
    <div
      ref={timelineRef}
      className="transcript-scroll-region"
      role="region"
      aria-label="Conversation transcript"
      tabIndex={0}
    >
      <ol className="transcript-list">
        {sortedEvents.map((event) => (
          <li className={`transcript-item transcript-${event.type}`} key={event.id}>
            {event.type === 'system' ? (
              <div className="timeline-notice">
                <span className="timeline-notice-icon">
                  <SpeakerIcon type={event.type} />
                </span>
                <span className="timeline-notice-speaker">{getSpeakerLabel(event.type)}</span>
                <span className="timeline-notice-text">{event.text}</span>
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
                  </div>
                  <p>{event.text}</p>
                </div>
              </>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
