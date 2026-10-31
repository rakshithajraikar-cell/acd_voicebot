/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_CLIENT_MODE?: 'mock' | 'http';
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_MOCK_SCENARIO?:
    | 'success'
    | 'session-not-found'
    | 'server-error'
    | 'network-failure';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
