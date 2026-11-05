import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ToolApprovalDemo } from './ToolApprovalDemo';

describe('ToolApprovalDemo', () => {
  it.each([
    ['Approve', 'Approved in mock mode. No tool was executed.'],
    ['Deny', 'Denied in mock mode. No tool was executed.'],
  ])(
    'supports keyboard-only %s and returns focus to the request control',
    async (action, result) => {
      const user = userEvent.setup();
      render(<ToolApprovalDemo />);

      await user.tab();
      const trigger = screen.getByRole('button', { name: 'Trigger mock tool call' });
      expect(trigger).toHaveFocus();
      await user.keyboard('{Enter}');

      expect(screen.getByRole('group', { name: 'Tool approval request' })).toHaveTextContent(
        'Awaiting your decision.',
      );
      await user.tab();
      expect(screen.getByRole('button', { name: 'Approve' })).toHaveFocus();
      if (action === 'Deny') {
        await user.tab();
        expect(screen.getByRole('button', { name: 'Deny' })).toHaveFocus();
      }
      await user.keyboard(' ');

      const status = await screen.findByRole('status', { name: 'Tool approval result' });
      await waitFor(() => expect(status).toHaveTextContent(result));
      expect(trigger).toHaveFocus();
      expect(screen.queryByRole('button', { name: action })).not.toBeInTheDocument();
      expect(status.querySelector('svg')).toBeInTheDocument();
    },
  );
});
