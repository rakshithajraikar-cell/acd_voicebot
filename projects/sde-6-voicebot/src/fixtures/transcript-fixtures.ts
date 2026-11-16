import type { AudioChunkInput } from "../contracts/transcript.js";

/**
 * Creates a synthetic raw audio byte buffer for testing.
 * Generates deterministic bytes so repeated calls produce bitwise-identical results.
 */
export function generateSyntheticAudioBytes(durationMs: number, sampleRate: number = 16000): Uint8Array {
  const numSamples = Math.floor((durationMs / 1000) * sampleRate);
  const bytes = new Uint8Array(numSamples * 2); // 16-bit PCM mono
  for (let i = 0; i < numSamples; i++) {
    // Generate a simple deterministic sine-like wave pattern
    const val = Math.floor(Math.sin(i / 10) * 10000);
    bytes[i * 2] = val & 0xff;
    bytes[i * 2 + 1] = (val >> 8) & 0xff;
  }
  return bytes;
}

/**
 * Standard synthetic audio chunks representing a live 3-stage user utterance:
 * Utterance: "Academic voicebot system ready. Start session now."
 */
export const SYNTHETIC_AUDIO_FIXTURES: AudioChunkInput[] = [
  {
    chunk_id: "chunk-fix-001",
    sequence_number: 0,
    session_id: "session-fixture-001",
    correlation_id: "corr-chunk-001",
    timestamp_ms: 0,
    duration_ms: 800,
    sample_rate: 16000,
    channels: 1,
    data: "academic_voicebot_system_part1",
    is_speech: true,
  },
  {
    chunk_id: "chunk-fix-002",
    sequence_number: 1,
    session_id: "session-fixture-001",
    correlation_id: "corr-chunk-002",
    timestamp_ms: 800,
    duration_ms: 800,
    sample_rate: 16000,
    channels: 1,
    data: "ready_start_session_part2",
    is_speech: true,
  },
  {
    chunk_id: "chunk-fix-003",
    sequence_number: 2,
    session_id: "session-fixture-001",
    correlation_id: "corr-chunk-003",
    timestamp_ms: 1600,
    duration_ms: 600,
    sample_rate: 16000,
    channels: 1,
    data: "now_final_part3",
    is_speech: true,
  },
];

/**
 * Edge Case Fixtures: Silence, Noisy, and Fault-Injection Chunks
 */
export const EDGE_CASE_FIXTURES = {
  silenceChunk: {
    chunk_id: "chunk-edge-silence",
    sequence_number: 99,
    session_id: "session-fixture-001",
    correlation_id: "corr-silence",
    timestamp_ms: 3000,
    duration_ms: 500,
    sample_rate: 16000,
    channels: 1,
    data: "silence_buffer",
    is_speech: false,
  } as AudioChunkInput,

  errorTriggerChunk: {
    chunk_id: "chunk-edge-error",
    sequence_number: 100,
    session_id: "session-fixture-001",
    correlation_id: "corr-error-trigger",
    timestamp_ms: 3500,
    duration_ms: 500,
    sample_rate: 16000,
    channels: 1,
    data: "__TRIGGER_PROVIDER_ERROR__",
    is_speech: true,
  } as AudioChunkInput,
};
