import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { createDefaultContextPanel } from '../models/session';
import type { ContextSource } from '../models/session';
import { ContextSourcesPanel } from './ContextSourcesPanel';

describe('ContextSourcesPanel', () => {
  it('lists source labels and types with accessible switch controls', () => {
    const sources: ContextSource[] = [
      { id: 'screen', label: 'Screen context', type: 'screen', enabled: false },
      { id: 'agenda', label: 'Meeting agenda', type: 'file', enabled: true },
      { id: 'notes', label: 'Session notes', type: 'note', enabled: false },
      { id: 'other', label: 'Other source', type: 'other', enabled: false },
    ];
    render(<ContextSourcesPanel sources={sources} onToggleSource={vi.fn()} />);

    const panel = screen.getByRole('region', { name: 'Context & Sources' });
    expect(panel).toBeInTheDocument();
    for (const [label, type] of [
      ['Screen context', 'Screen source'],
      ['Meeting agenda', 'File source'],
      ['Session notes', 'Note source'],
      ['Other source', 'Other source'],
    ]) {
      const source = within(panel).getByRole('switch', { name: label });
      expect(source).toBeInTheDocument();
      expect(source.closest('li')).toHaveTextContent(type);
    }
    expect(within(panel).getByRole('switch', { name: 'Screen context' })).not.toBeChecked();
    expect(within(panel).getByRole('switch', { name: 'Meeting agenda' })).toBeChecked();
    expect(within(panel).getByRole('status')).toHaveTextContent(
      'Screen context is off — nothing from your screen is shared.',
    );
    expect(within(panel).getByText('Not shared')).toBeInTheDocument();
    expect(within(panel).getByRole('switch', { name: 'Screen context' })).toHaveAttribute(
      'aria-describedby',
      'screen-sharing-state',
    );
  });

  it('supports keyboard toggling and reports the explicit source state change', async () => {
    const user = userEvent.setup();
    const onToggleSource = vi.fn();
    render(
      <ContextSourcesPanel
        sources={createDefaultContextPanel().sources}
        onToggleSource={onToggleSource}
      />,
    );
    const screenSwitch = screen.getByRole('switch', { name: 'Screen context' });

    await user.tab();
    expect(screenSwitch).toHaveFocus();
    expect(screenSwitch).toHaveAttribute('aria-checked', 'false');
    await user.keyboard(' ');

    expect(onToggleSource).toHaveBeenCalledWith('screen-context', true);
  });

  it('shows an accessible empty state when no sources are available', () => {
    render(<ContextSourcesPanel sources={[]} onToggleSource={vi.fn()} />);

    expect(screen.getByRole('status')).toHaveTextContent(
      'No context sources are available for this session.',
    );
  });
});
