import type { AudioChunkInput } from "../contracts/transcript.js";
import { createSyntheticChunk } from "./transcript-fixtures.js";

/**
 * Regression Fixtures Suite
 *
 * Dedicated collection of challenging edge-case audio streams used in CI
 * and regression testing to prevent regression bugs in production.
 */
export interface RegressionFixtureSet {
  multiRateSequence: AudioChunkInput[];
  silenceSequence: AudioChunkInput[];
  clippedAudioSequence: AudioChunkInput[];
  outOfOrderSequence: AudioChunkInput[];
  gapSequence: AudioChunkInput[];
  revisionBurstSequence: AudioChunkInput[];
  quotaTriggerSequence: AudioChunkInput[];
}

/**
 * Generates an audio buffer with clipped amplitudes (+2.0 and -2.0)
 */
function createClippedAudioData(sampleCount = 1600): Uint8Array {
  const pcm = new Float32Array(sampleCount);
  for (let i = 0; i < sampleCount; i++) {
    // Generate clipped square/sine waveform
    pcm[i] = Math.sin((i / 16) * Math.PI) > 0 ? 2.5 : -2.5;
  }
  return new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
}

/**
 * Generates a pure silence audio buffer
 */
function createSilenceAudioData(sampleCount = 1600): Uint8Array {
  const pcm = new Float32Array(sampleCount);
  pcm.fill(0.0);
  return new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
}

/**
 * Builds the complete regression fixture dataset
 */
export function createRegressionFixtureSet(
  sessionId = "regression-test-session"
): RegressionFixtureSet {
  // 1. Multi-rate sequence (8kHz, 16kHz, 44.1kHz, 48kHz)
  const rates = [8000, 16000, 44100, 48000];
  const multiRateSequence: AudioChunkInput[] = rates.map((rate, idx) =>
    createSyntheticChunk({
      chunkId: `reg-rate-${idx}`,
      sequenceNumber: idx,
      sampleRate: rate,
      startTimeMs: idx * 100,
      durationMs: 100,
      sessionId,
      testPhraseToken: `multi-rate speech at ${rate}Hz`,
    })
  );

  // 2. Pure silence sequence
  const silenceSequence: AudioChunkInput[] = [0, 1, 2].map((idx) =>
    createSyntheticChunk({
      chunkId: `reg-silence-${idx}`,
      sequenceNumber: idx,
      sampleRate: 16000,
      startTimeMs: idx * 100,
      durationMs: 100,
      sessionId,
      data: createSilenceAudioData(1600),
      isSpeech: false,
    })
  );

  // 3. Clipped audio sequence
  const clippedAudioSequence: AudioChunkInput[] = [0, 1].map((idx) =>
    createSyntheticChunk({
      chunkId: `reg-clipped-${idx}`,
      sequenceNumber: idx,
      sampleRate: 16000,
      startTimeMs: idx * 100,
      durationMs: 100,
      sessionId,
      data: createClippedAudioData(1600),
      isSpeech: true,
    })
  );

  // 4. Out-of-order sequence (intended order: [2, 0, 3, 1])
  const naturalOrder: AudioChunkInput[] = [0, 1, 2, 3].map((seq) =>
    createSyntheticChunk({
      chunkId: `reg-ooo-${seq}`,
      sequenceNumber: seq,
      sampleRate: 16000,
      startTimeMs: seq * 100,
      durationMs: 100,
      sessionId,
      testPhraseToken: `word_${seq}`,
    })
  );
  const outOfOrderSequence: AudioChunkInput[] = [
    naturalOrder[2],
    naturalOrder[0],
    naturalOrder[3],
    naturalOrder[1],
  ];

  // 5. Gap sequence (missing chunk 2: [0, 1, 3, 4])
  const gapSequence: AudioChunkInput[] = [0, 1, 3, 4].map((seq) =>
    createSyntheticChunk({
      chunkId: `reg-gap-${seq}`,
      sequenceNumber: seq,
      sampleRate: 16000,
      startTimeMs: seq * 100,
      durationMs: 100,
      sessionId,
      testPhraseToken: `gap_token_${seq}`,
    })
  );

  // 6. Revision burst sequence
  const revisionBurstSequence: AudioChunkInput[] = [0, 1, 2].map((idx) =>
    createSyntheticChunk({
      chunkId: `reg-rev-${idx}`,
      sequenceNumber: idx,
      sampleRate: 16000,
      startTimeMs: idx * 100,
      durationMs: 100,
      sessionId,
      testPhraseToken: `recognize speech segment ${idx}`,
    })
  );

  // 7. Quota error trigger sequence
  const quotaTriggerSequence: AudioChunkInput[] = [
    createSyntheticChunk({
      chunkId: "reg-quota-0",
      sequenceNumber: 0,
      sampleRate: 16000,
      startTimeMs: 0,
      durationMs: 100,
      sessionId,
      testPhraseToken: "valid initial chunk",
    }),
    createSyntheticChunk({
      chunkId: "reg-quota-1",
      sequenceNumber: 1,
      sampleRate: 16000,
      startTimeMs: 100,
      durationMs: 100,
      sessionId,
      testPhraseToken: "__TRIGGER_PROVIDER_ERROR__",
    }),
    createSyntheticChunk({
      chunkId: "reg-quota-2",
      sequenceNumber: 2,
      sampleRate: 16000,
      startTimeMs: 200,
      durationMs: 100,
      sessionId,
      testPhraseToken: "subsequent recovering chunk",
    }),
  ];

  return {
    multiRateSequence,
    silenceSequence,
    clippedAudioSequence,
    outOfOrderSequence,
    gapSequence,
    revisionBurstSequence,
    quotaTriggerSequence,
  };
}
