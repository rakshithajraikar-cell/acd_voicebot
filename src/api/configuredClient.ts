import { createApiClient } from './client';
import type { ApiClientConfiguration, MockApiScenario } from './client';

type ClientEnvironment = Readonly<{
  VITE_API_CLIENT_MODE?: string;
  VITE_API_BASE_URL?: string;
  VITE_API_MOCK_SCENARIO?: string;
}>;

function isMockScenario(value: string): value is MockApiScenario {
  return (
    value === 'success' ||
    value === 'session-not-found' ||
    value === 'server-error' ||
    value === 'network-failure'
  );
}

export function resolveApiClientConfiguration(
  environment: ClientEnvironment,
): ApiClientConfiguration {
  const mode = environment.VITE_API_CLIENT_MODE ?? 'mock';
  if (mode === 'http') {
    return { mode, baseUrl: environment.VITE_API_BASE_URL };
  }
  if (mode !== 'mock') {
    throw new Error(`Unsupported VITE_API_CLIENT_MODE: ${mode}`);
  }

  const configuredScenario = environment.VITE_API_MOCK_SCENARIO ?? 'success';
  if (!isMockScenario(configuredScenario)) {
    throw new Error(`Unsupported VITE_API_MOCK_SCENARIO: ${configuredScenario}`);
  }
  return { mode, scenario: configuredScenario };
}

export const apiClientConfiguration = resolveApiClientConfiguration(import.meta.env);
export const apiClient = createApiClient(apiClientConfiguration);
