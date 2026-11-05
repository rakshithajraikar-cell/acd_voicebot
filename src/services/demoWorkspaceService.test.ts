import { describe, expect, it } from 'vitest';
import { getDemoWorkspace } from './demoWorkspaceService';

describe('mock demo workspace service', () => {
  it('returns the typed local transcript fixture', async () => {
    const result = await getDemoWorkspace();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.sessionName).toBe('Product design review');
      expect(result.data.transcript).toHaveLength(10);
      expect(result.data.transcript[0]).toMatchObject({
        type: 'system',
        text: 'Session started.',
      });
      expect(
        result.data.transcript.some((event) =>
          /screen context|screen capture|screen contents/i.test(event.text),
        ),
      ).toBe(false);
      result.data.transcript.forEach((event) => {
        expect(event).not.toHaveProperty('contextSources');
        expect(event).not.toHaveProperty('screenContext');
      });
    }
  });

  it('returns a visible mock failure result when requested', async () => {
    await expect(getDemoWorkspace({ simulateError: true })).resolves.toEqual({
      ok: false,
      error: {
        message: 'The demo API could not load this session. Try again.',
        code: 'MOCK_FAILURE',
      },
    });
  });
});
