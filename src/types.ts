export type TranscriptEvent =
  | Readonly<{
      type: 'user';
      id: string;
      segmentId: string;
      isFinal: boolean;
      revision: number;
      revisedAt?: string;
      timestamp: string;
      speaker: 'You';
      text: string;
      confidence?: number;
    }>
  | Readonly<{
      type: 'assistant';
      id: string;
      segmentId: string;
      isFinal: boolean;
      revision: number;
      revisedAt?: string;
      timestamp: string;
      speaker: 'Co-Pilot';
      text: string;
      confidence?: number;
    }>
  | Readonly<{
      type: 'system';
      id: string;
      segmentId: string;
      isFinal: boolean;
      revision: number;
      revisedAt?: string;
      timestamp: string;
      speaker: 'System';
      text: string;
      confidence?: number;
    }>;

export type DemoWorkspace = {
  sessionName: string;
  transcript: TranscriptEvent[];
};
