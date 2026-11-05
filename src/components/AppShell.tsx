import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  AudioLines,
  CircleAlert,
  Command,
  LoaderCircle,
  Plus,
  Settings2,
  Sparkles,
} from 'lucide-react';
import type { NetworkStatus } from '../services/sessionService';

type AppShellProps = {
  children: ReactNode;
  onNewSession: () => void;
  isSessionLoading: boolean;
  isCreatingSession: boolean;
  networkStatus: NetworkStatus;
};

export function AppShell({
  children,
  onNewSession,
  isSessionLoading,
  isCreatingSession,
  networkStatus,
}: AppShellProps) {
  const previousNetworkStatus = useRef(networkStatus);
  const [networkAnnouncement, setNetworkAnnouncement] = useState('');

  useEffect(() => {
    if (previousNetworkStatus.current !== networkStatus) {
      setNetworkAnnouncement(
        networkStatus === 'online' ? 'Connection restored. Session actions are available.' : '',
      );
      previousNetworkStatus.current = networkStatus;
    }
  }, [networkStatus]);

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        aria-label="Skip to main content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById('main-content')?.focus();
        }}
      >
        Skip to main content
      </a>
      <aside className="sidebar" aria-label="Workspace sidebar">
        <a className="brand" href="#main-content" aria-label="Academia home">
          <span className="brand-mark" aria-hidden="true">
            <AudioLines size={20} strokeWidth={2.2} aria-hidden="true" />
          </span>
          <span className="brand-copy">
            <strong>academia</strong>
            <span>AI CO-PILOT</span>
          </span>
        </a>

        <button
          className="new-session-button"
          type="button"
          aria-label="New session"
          aria-busy={isCreatingSession}
          aria-live="polite"
          onClick={onNewSession}
          disabled={isSessionLoading}
        >
          {isCreatingSession ? (
            <LoaderCircle className="loading-spinner" size={16} aria-hidden="true" />
          ) : (
            <Plus size={16} aria-hidden="true" />
          )}
          <span>{isCreatingSession ? 'Creating…' : 'New Session'}</span>
          <span className="shortcut">
            <Command size={12} aria-hidden="true" /> K
          </span>
        </button>

        <nav className="nav-section" aria-label="Workspace navigation">
          <p className="nav-label">WORKSPACE</p>
          <a
            className="nav-link active"
            href="#main-content"
            aria-label="Co-Pilot workspace"
            aria-current="page"
          >
            <Sparkles size={17} aria-hidden="true" />
            <span>Co-Pilot</span>
            <span className="nav-indicator" />
          </a>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="note-icon">
              <Sparkles size={15} aria-hidden="true" />
            </span>
            <p>
              <strong>A little more focus.</strong>
              <br />
              Your ideas, in good company.
            </p>
          </div>
          <div className="profile-button">
            <span className="avatar" aria-hidden="true">
              SA
            </span>
            <span className="profile-name">
              <strong>Shivani A.</strong>
              <small>Personal workspace</small>
            </span>
            <Settings2 size={16} aria-hidden="true" />
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar" aria-busy={isCreatingSession}>
          <div
            className={`mock-mode-banner${networkStatus === 'offline' ? ' mock-mode-banner-offline' : ''}`}
          >
            <div
              className="visually-hidden"
              role="status"
              aria-live="polite"
              aria-atomic="true"
              aria-label="Network recovery"
            >
              {networkAnnouncement}
            </div>
            <div className="mock-mode-status" role="status" aria-label="Mock mode status">
              <span className="mock-mode-indicator" aria-hidden="true" />
              <strong>MOCK MODE</strong>
              <span>Mock data is in use — no AI service is connected.</span>
            </div>
            {isCreatingSession && (
              <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
                Creating session…
              </div>
            )}
            {networkStatus === 'offline' && (
              <div
                className="offline-status"
                role="status"
                aria-live="polite"
                aria-atomic="true"
                aria-label="Network status"
              >
                <CircleAlert size={14} aria-hidden="true" />
                <strong>Offline</strong>
                <span>
                  You’re offline. Session actions will resume when the connection returns.
                </span>
              </div>
            )}
          </div>
          <div className="topbar-content">
            <div className="topbar-mobile-brand">
              <span className="brand-mark" aria-hidden="true">
                <AudioLines size={18} aria-hidden="true" />
              </span>
              <strong>academia</strong>
            </div>
            <div className="breadcrumbs">
              <span>Workspace</span>
              <span className="breadcrumb-slash">/</span>
              <strong>Co-Pilot</strong>
            </div>
          </div>
        </header>
        {children}
        <footer className="page-footer">
          <span>
            ACADEMIA AI CO-PILOT <span className="footer-dot">·</span> WEEK 1 PREVIEW
          </span>
          <span>Built for thoughtful work</span>
        </footer>
      </div>
    </div>
  );
}
