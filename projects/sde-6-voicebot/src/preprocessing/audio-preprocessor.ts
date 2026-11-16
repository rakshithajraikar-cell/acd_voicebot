import type { AudioChunkInput } from "../contracts/transcript.js";
import type { ErrorEnvelope } from "../contracts/common.js";

export interface PreprocessorOptions {
  /**
   * Target sample rate in Hz (default: 16000 Hz, standard for speech recognition)
   */
  targetSampleRate?: number;
  /**
   * Target peak amplitude between 0.1 and 1.0 (default: 0.95 to prevent clipping)
   */
  targetPeakAmplitude?: number;
  /**
   * Whether to remove DC bias offset from signal (default: true)
   */
  removeDcOffset?: boolean;
}

export type PreprocessResult =
  | { success: true; processedChunk: AudioChunkInput }
  | { success: false; error: ErrorEnvelope };

/**
 * AudioPreprocessor
 *
 * Preprocessing pipeline for incoming audio chunks:
 * 1. Validation: Rejects empty or corrupt audio payloads.
 * 2. Channel Downmixing: Converts stereo (2-channel) to mono (1-channel).
 * 3. Resampling: Converts 8kHz, 44.1kHz, 48kHz to standard 16kHz.
 * 4. DC Offset Removal: Eliminates microphone bias / drift.
 * 5. Peak Amplitude Normalization: Scales audio to optimal dynamic range without clipping.
 */
export class AudioPreprocessor {
  readonly targetSampleRate: number;
  readonly targetPeakAmplitude: number;
  readonly removeDcOffset: boolean;

  constructor(options?: PreprocessorOptions) {
    this.targetSampleRate = options?.targetSampleRate ?? 16000;
    this.targetPeakAmplitude = options?.targetPeakAmplitude ?? 0.95;
    this.removeDcOffset = options?.removeDcOffset ?? true;
  }

  /**
   * Preprocesses an incoming AudioChunkInput.
   */
  process(chunk: AudioChunkInput): PreprocessResult {
    try {
      const rawData = chunk.data;

      // 1. Guard against empty audio data (string or Uint8Array)
      if (
        !rawData ||
        (typeof rawData === "string" && rawData.trim().length === 0) ||
        (rawData instanceof Uint8Array && rawData.byteLength === 0)
      ) {
        return {
          success: false,
          error: {
            code: "AUDIO_CHUNK_EMPTY",
            message_safe_for_user: "Received an empty audio chunk with no sample data.",
            retryable: false,
            correlation_id: chunk.correlation_id,
            details_redacted: { chunk_id: chunk.chunk_id },
          },
        };
      }

      // If data is a string fixture / trigger token, preserve token metadata for mock provider
      if (typeof rawData === "string") {
        return {
          success: true,
          processedChunk: {
            ...chunk,
            sample_rate: this.targetSampleRate,
            channels: 1,
          },
        };
      }

      // 2. Decode Uint8Array PCM samples into Float32Array in range [-1.0, 1.0]
      let samples = this.decodePcm16ToFloat32(rawData);
      if (samples.length === 0) {
        return {
          success: false,
          error: {
            code: "AUDIO_DECODE_FAILED",
            message_safe_for_user: "Failed to decode audio chunk samples into numeric PCM array.",
            retryable: false,
            correlation_id: chunk.correlation_id,
            details_redacted: { chunk_id: chunk.chunk_id },
          },
        };
      }

      // 3. Downmix stereo to mono if 2 channels
      if (chunk.channels === 2) {
        samples = this.downmixStereoToMono(samples);
      }

      // 4. Remove DC offset bias if enabled
      if (this.removeDcOffset) {
        samples = this.removeDcBias(samples);
      }

      // 5. Amplitude Normalization
      samples = this.normalizeAmplitude(samples, this.targetPeakAmplitude);

      // 6. Resample to target rate if needed
      if (chunk.sample_rate !== this.targetSampleRate) {
        samples = this.resample(samples, chunk.sample_rate, this.targetSampleRate);
      }

      // 7. Encode back to Uint8Array 16-bit PCM little-endian
      const processedBuffer = this.encodeToPcm16(samples);

      const processedChunk: AudioChunkInput = {
        ...chunk,
        sample_rate: this.targetSampleRate,
        channels: 1,
        data: processedBuffer,
      };

      return { success: true, processedChunk };
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      return {
        success: false,
        error: {
          code: "PREPROCESSING_ERROR",
          message_safe_for_user: "An error occurred during audio chunk preprocessing.",
          retryable: false,
          correlation_id: chunk.correlation_id,
          details_redacted: { reason: errorMessage, chunk_id: chunk.chunk_id },
        },
      };
    }
  }

  /**
   * Decodes Uint8Array (16-bit PCM) into float samples [-1.0, 1.0].
   */
  private decodePcm16ToFloat32(data: Uint8Array): Float32Array {
    const numSamples = Math.floor(data.byteLength / 2);
    const floatSamples = new Float32Array(numSamples);
    const dataView = new DataView(data.buffer, data.byteOffset, data.byteLength);

    for (let i = 0; i < numSamples; i++) {
      const int16 = dataView.getInt16(i * 2, true);
      floatSamples[i] = int16 / 32768;
    }
    return floatSamples;
  }

  /**
   * Downmixes interleaved stereo samples to single-channel mono.
   */
  private downmixStereoToMono(stereoSamples: Float32Array): Float32Array {
    const monoLength = Math.floor(stereoSamples.length / 2);
    const mono = new Float32Array(monoLength);
    for (let i = 0; i < monoLength; i++) {
      const left = stereoSamples[i * 2];
      const right = stereoSamples[i * 2 + 1];
      mono[i] = (left + right) / 2;
    }
    return mono;
  }

  /**
   * Removes DC bias by subtracting mean amplitude across all samples.
   */
  private removeDcBias(samples: Float32Array): Float32Array {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i];
    }
    const mean = sum / samples.length;

    const zeroMean = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      zeroMean[i] = samples[i] - mean;
    }
    return zeroMean;
  }

  /**
   * Scales samples to match target peak amplitude, avoiding clipping.
   */
  private normalizeAmplitude(samples: Float32Array, targetPeak: number): Float32Array {
    let peak = 0;
    for (let i = 0; i < samples.length; i++) {
      const abs = Math.abs(samples[i]);
      if (abs > peak) {
        peak = abs;
      }
    }

    if (peak === 0 || peak === targetPeak) {
      return samples;
    }

    const scale = targetPeak / peak;
    const normalized = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      normalized[i] = Math.max(-1.0, Math.min(1.0, samples[i] * scale));
    }
    return normalized;
  }

  /**
   * Resamples PCM samples between arbitrary sample rates using linear interpolation.
   */
  private resample(
    samples: Float32Array,
    fromRate: number,
    toRate: number
  ): Float32Array {
    if (fromRate === toRate || samples.length === 0) {
      return samples;
    }

    const ratio = toRate / fromRate;
    const newLength = Math.round(samples.length * ratio);
    const result = new Float32Array(newLength);

    for (let i = 0; i < newLength; i++) {
      const originalIndex = i / ratio;
      const indexFloor = Math.floor(originalIndex);
      const indexCeil = Math.min(samples.length - 1, indexFloor + 1);
      const fraction = originalIndex - indexFloor;

      result[i] = samples[indexFloor] * (1 - fraction) + samples[indexCeil] * fraction;
    }

    return result;
  }

  /**
   * Encodes float samples [-1.0, 1.0] back to 16-bit PCM little-endian byte buffer.
   */
  private encodeToPcm16(samples: Float32Array): Uint8Array {
    const bytes = new Uint8Array(samples.length * 2);
    const view = new DataView(bytes.buffer);

    for (let i = 0; i < samples.length; i++) {
      const clamped = Math.max(-1.0, Math.min(1.0, samples[i]));
      const int16 = clamped < 0 ? Math.round(clamped * 32768) : Math.round(clamped * 32767);
      view.setInt16(i * 2, int16, true);
    }

    return bytes;
  }
}
