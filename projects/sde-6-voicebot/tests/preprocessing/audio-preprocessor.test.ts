import { describe, it, expect } from "vitest";
import { AudioPreprocessor } from "../../src/preprocessing/audio-preprocessor.js";
import type { AudioChunkInput } from "../../src/contracts/transcript.js";

describe("W2 Audio Preprocessor (Resampling & Normalization)", () => {
  const preprocessor = new AudioPreprocessor({ targetSampleRate: 16000, targetPeakAmplitude: 0.95 });

  it("should resample 48000Hz input audio down to 16000Hz", () => {
    // Generate 100ms at 48000Hz = 4800 samples = 9600 bytes
    const numSamples48k = 4800;
    const pcm48k = new Uint8Array(numSamples48k * 2);
    const view = new DataView(pcm48k.buffer);
    for (let i = 0; i < numSamples48k; i++) {
      view.setInt16(i * 2, Math.round(Math.sin(i / 10) * 16000), true);
    }

    const chunk48k: AudioChunkInput = {
      chunk_id: "chunk-48k",
      sequence_number: 0,
      session_id: "sess-prep-1",
      correlation_id: "corr-prep-1",
      timestamp_ms: 0,
      duration_ms: 100,
      sample_rate: 48000,
      channels: 1,
      data: pcm48k,
      is_speech: true,
    };

    const result = preprocessor.process(chunk48k);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.processedChunk.sample_rate).toBe(16000);
      expect(result.processedChunk.channels).toBe(1);
      // 100ms at 16000Hz = 1600 samples = 3200 bytes
      const processedBytes = result.processedChunk.data as Uint8Array;
      const processedSamples = processedBytes.byteLength / 2;
      expect(processedSamples).toBe(1600);
    }
  });

  it("should resample 8000Hz input audio up to 16000Hz", () => {
    // 100ms at 8000Hz = 800 samples = 1600 bytes
    const numSamples8k = 800;
    const pcm8k = new Uint8Array(numSamples8k * 2);
    const view = new DataView(pcm8k.buffer);
    for (let i = 0; i < numSamples8k; i++) {
      view.setInt16(i * 2, Math.round(Math.sin(i / 5) * 10000), true);
    }

    const chunk8k: AudioChunkInput = {
      chunk_id: "chunk-8k",
      sequence_number: 1,
      session_id: "sess-prep-1",
      correlation_id: "corr-prep-2",
      timestamp_ms: 100,
      duration_ms: 100,
      sample_rate: 8000,
      channels: 1,
      data: pcm8k,
      is_speech: true,
    };

    const result = preprocessor.process(chunk8k);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.processedChunk.sample_rate).toBe(16000);
      const processedBytes = result.processedChunk.data as Uint8Array;
      const processedSamples = processedBytes.byteLength / 2;
      expect(processedSamples).toBe(1600);
    }
  });

  it("should normalize quiet audio to target peak amplitude", () => {
    // Quiet audio: max amplitude is only 3276 (approx 0.1 peak)
    const samples = 1600;
    const pcm = new Uint8Array(samples * 2);
    const view = new DataView(pcm.buffer);
    for (let i = 0; i < samples; i++) {
      view.setInt16(i * 2, Math.round(Math.sin(i / 10) * 3276), true);
    }

    const quietChunk: AudioChunkInput = {
      chunk_id: "chunk-quiet",
      sequence_number: 0,
      session_id: "sess-prep-1",
      correlation_id: "corr-quiet",
      timestamp_ms: 0,
      duration_ms: 100,
      sample_rate: 16000,
      channels: 1,
      data: pcm,
      is_speech: true,
    };

    const result = preprocessor.process(quietChunk);
    expect(result.success).toBe(true);
    if (result.success) {
      const processedBytes = result.processedChunk.data as Uint8Array;
      const pView = new DataView(processedBytes.buffer);
      let maxAbs = 0;
      for (let i = 0; i < samples; i++) {
        const val = Math.abs(pView.getInt16(i * 2, true));
        if (val > maxAbs) maxAbs = val;
      }
      // Target peak is 0.95 * 32767 = 31128
      expect(maxAbs).toBeGreaterThanOrEqual(31000);
      expect(maxAbs).toBeLessThanOrEqual(32767);
    }
  });

  it("should downmix stereo 2-channel audio to mono 1-channel", () => {
    // 100 samples stereo = 200 samples total = 400 bytes
    const stereoSamples = 200;
    const pcm = new Uint8Array(stereoSamples * 2);
    const view = new DataView(pcm.buffer);
    for (let i = 0; i < stereoSamples; i++) {
      view.setInt16(i * 2, 10000, true);
    }

    const stereoChunk: AudioChunkInput = {
      chunk_id: "chunk-stereo",
      sequence_number: 0,
      session_id: "sess-prep-1",
      correlation_id: "corr-stereo",
      timestamp_ms: 0,
      duration_ms: 100,
      sample_rate: 16000,
      channels: 2,
      data: pcm,
      is_speech: true,
    };

    const result = preprocessor.process(stereoChunk);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.processedChunk.channels).toBe(1);
    }
  });

  it("should reject empty audio data with clean ErrorEnvelope", () => {
    const emptyChunk: AudioChunkInput = {
      chunk_id: "chunk-empty-data",
      sequence_number: 0,
      session_id: "sess-prep-1",
      correlation_id: "corr-empty",
      timestamp_ms: 0,
      duration_ms: 100,
      sample_rate: 16000,
      channels: 1,
      data: new Uint8Array(0),
      is_speech: true,
    };

    const result = preprocessor.process(emptyChunk);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.code).toBe("AUDIO_CHUNK_EMPTY");
      expect(result.error.retryable).toBe(false);
    }
  });
});

