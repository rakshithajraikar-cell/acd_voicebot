import { useRef, useState } from 'react';
import { CheckCircle2, CircleAlert, CircleX, ShieldCheck } from 'lucide-react';

type ToolDecision = 'pending' | 'approved' | 'denied' | null;

const decisionCopy: Record<Exclude<ToolDecision, null>, string> = {
  pending: 'Awaiting your decision.',
  approved: 'Approved in mock mode. No tool was executed.',
  denied: 'Denied in mock mode. No tool was executed.',
};

export function ToolApprovalDemo() {
  const [decision, setDecision] = useState<ToolDecision>(null);
  const requestButtonRef = useRef<HTMLButtonElement>(null);

  function decide(nextDecision: Exclude<ToolDecision, null>) {
    setDecision(nextDecision);
    requestButtonRef.current?.focus();
  }

  return (
    <section className="panel tool-approval-panel" aria-labelledby="tool-approval-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">LOCAL DEMO</p>
          <h2 id="tool-approval-heading">Tool approval</h2>
        </div>
        <span className="api-shield" aria-hidden="true">
          <ShieldCheck size={16} />
        </span>
      </div>
      <p className="panel-description">
        Approval flow preview only. This does not connect to or execute a tool.
      </p>
      <button
        ref={requestButtonRef}
        className="button button-outline"
        type="button"
        aria-label="Trigger mock tool call"
        onClick={() => {
          if (decision !== 'pending') {
            setDecision('pending');
          }
        }}
      >
        Trigger mock tool call
      </button>
      {decision && (
        <div
          className={`tool-approval-request tool-approval-${decision}`}
          role={decision === 'pending' ? 'group' : 'status'}
          aria-label={decision === 'pending' ? 'Tool approval request' : 'Tool approval result'}
          aria-live={decision === 'pending' ? undefined : 'polite'}
          aria-atomic="true"
        >
          <p>
            <strong>Mock request:</strong> Draft a meeting agenda
          </p>
          <p className="tool-approval-decision">
            {decision === 'approved' ? (
              <CheckCircle2 size={15} aria-hidden="true" />
            ) : decision === 'denied' ? (
              <CircleX size={15} aria-hidden="true" />
            ) : (
              <CircleAlert size={15} aria-hidden="true" />
            )}
            {decisionCopy[decision]}
          </p>
          {decision === 'pending' && (
            <div className="tool-approval-actions">
              <button
                className="button button-primary"
                type="button"
                onClick={() => decide('approved')}
              >
                Approve
              </button>
              <button
                className="button button-danger"
                type="button"
                onClick={() => decide('denied')}
              >
                Deny
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
