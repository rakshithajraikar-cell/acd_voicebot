export type TranscriptEvent =
  | Readonly<{
      type: 'user';
      id: string;
      timestamp: string;
      speaker: 'You';
      text: string;
    }>
  | Readonly<{
      type: 'assistant';
      id: string;
      timestamp: string;
      speaker: 'Co-Pilot';
      text: string;
    }>
  | Readonly<{
      type: 'system';
      id: string;
      timestamp: string;
      speaker: 'System';
      text: string;
    }>;

export type DemoWorkspace = {
  sessionName: string;
  transcript: TranscriptEvent[];
};
