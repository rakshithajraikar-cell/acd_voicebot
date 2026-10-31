import { transcriptFixture } from '../fixtures/transcript';
import type { DemoWorkspace } from '../types';

export type DemoWorkspaceResult =
  | Readonly<{ ok: true; data: DemoWorkspace }>
  | Readonly<{ ok: false; error: { message: string; code: 'MOCK_FAILURE' } }>;

export type DemoWorkspaceRequest = Readonly<{
  simulateError?: boolean;
}>;

export async function getDemoWorkspace(
  request: DemoWorkspaceRequest = {},
): Promise<DemoWorkspaceResult> {
  if (request.simulateError) {
    return {
      ok: false,
      error: {
        message: 'The demo API could not load this session. Try again.',
        code: 'MOCK_FAILURE',
      },
    };
  }

  return {
    ok: true,
    data: {
      sessionName: 'Product design review',
      transcript: transcriptFixture,
    },
  };
}
