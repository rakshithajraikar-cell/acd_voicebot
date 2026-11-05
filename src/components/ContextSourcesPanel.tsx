import { FileText, Monitor, MoreHorizontal, StickyNote } from 'lucide-react';
import type { ContextSource } from '../models/session';

type ContextSourcesPanelProps = Readonly<{
  sources: readonly ContextSource[];
  onToggleSource: (sourceId: string, enabled: boolean) => void;
}>;

const sourceTypeLabels: Record<ContextSource['type'], string> = {
  screen: 'Screen',
  file: 'File',
  note: 'Note',
  other: 'Other',
};

function SourceTypeIcon({ type }: { type: ContextSource['type'] }) {
  if (type === 'screen') return <Monitor size={14} aria-hidden="true" />;
  if (type === 'file') return <FileText size={14} aria-hidden="true" />;
  if (type === 'note') return <StickyNote size={14} aria-hidden="true" />;
  return <MoreHorizontal size={14} aria-hidden="true" />;
}

export function ContextSourcesPanel({ sources, onToggleSource }: ContextSourcesPanelProps) {
  return (
    <section className="panel context-panel" aria-labelledby="context-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">SESSION CONTEXT</p>
          <h2 id="context-heading">Context &amp; Sources</h2>
        </div>
      </div>
      <p className="panel-description">
        Choose which sources are available to this session. Screen context starts off and only turns
        on when you choose.
      </p>
      {sources.length > 0 ? (
        <ul className="context-source-list">
          {sources.map((source) => (
            <li
              className={`context-source${source.type === 'screen' && source.enabled ? ' context-source-screen-enabled' : ''}`}
              key={source.id}
            >
              <span className={`context-source-icon context-source-icon-${source.type}`}>
                <SourceTypeIcon type={source.type} />
              </span>
              <span className="context-source-copy">
                <span className="context-source-label">{source.label}</span>
                <span className="context-source-type">{sourceTypeLabels[source.type]} source</span>
                {source.type === 'screen' && (
                  <span
                    id={`${source.id}-sharing-state`}
                    className="context-source-sharing-state"
                    role="status"
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    {source.enabled
                      ? 'Screen context is on — enabled for this session.'
                      : 'Screen context is off — nothing from your screen is shared.'}
                  </span>
                )}
              </span>
              <label className="context-switch">
                <input
                  type="checkbox"
                  role="switch"
                  aria-label={source.label}
                  aria-describedby={
                    source.type === 'screen' ? `${source.id}-sharing-state` : undefined
                  }
                  aria-checked={source.enabled}
                  checked={source.enabled}
                  onChange={(event) => onToggleSource(source.id, event.currentTarget.checked)}
                />
                <span className="context-switch-track" aria-hidden="true">
                  <span className="context-switch-thumb" />
                </span>
                <span className="context-switch-state">{source.enabled ? 'On' : 'Off'}</span>
              </label>
              {source.type === 'screen' && !source.enabled && (
                <span className="context-source-not-shared">Not shared</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="context-empty" role="status">
          No context sources are available for this session.
        </p>
      )}
    </section>
  );
}
