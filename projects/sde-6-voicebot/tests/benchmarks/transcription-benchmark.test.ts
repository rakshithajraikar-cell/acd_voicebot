import { describe, it, expect } from "vitest";
import { runTranscriptionBenchmark } from "../../src/benchmarks/transcription-benchmark.js";

describe("Transcription Latency Benchmark Suite", () => {
  it("runs the benchmark across multi-rate synthetic fixtures and records metrics", async () => {
    const report = await runTranscriptionBenchmark({
      chunkCount: 20,
      sampleRates: [8000, 16000, 44100, 48000],
      writeReportFile: false,
      silent: true,
    });

    // Verify report structure
    expect(report.totalChunksProcessed).toBe(20);
    expect(report.sampleRatesTested).toEqual([8000, 16000, 44100, 48000]);
    expect(report.timestamp).toBeDefined();

    // Verify statistical percentiles are ordered correctly: min <= p50 <= p90 <= p95 <= p99 <= max
    const { endToEndMs, preprocessingMs, transcriptionMs, accumulationMs } = report.metrics;

    expect(endToEndMs.count).toBe(20);
    expect(endToEndMs.minMs).toBeGreaterThanOrEqual(0);
    expect(endToEndMs.p50Ms).toBeGreaterThanOrEqual(endToEndMs.minMs);
    expect(endToEndMs.p95Ms).toBeGreaterThanOrEqual(endToEndMs.p50Ms);
    expect(endToEndMs.p99Ms).toBeGreaterThanOrEqual(endToEndMs.p95Ms);
    expect(endToEndMs.maxMs).toBeGreaterThanOrEqual(endToEndMs.p99Ms);

    // Verify breakdown stages exist and have valid counts
    expect(preprocessingMs.count).toBe(20);
    expect(transcriptionMs.count).toBe(20);
    expect(accumulationMs.count).toBe(20);

    // Verify throughput metrics
    expect(endToEndMs.throughputChunksPerSec).toBeGreaterThan(0);
    expect(endToEndMs.realTimeFactor).toBeGreaterThan(0);

    // Verify summary table is generated
    expect(report.summaryTableMarkdown).toContain("| Audio Preprocessing |");
    expect(report.summaryTableMarkdown).toContain("| Mock STT Adapter |");
    expect(report.summaryTableMarkdown).toContain("| **End-to-End Pipeline** |");
  });

  it("handles empty or single chunk gracefully without division by zero", async () => {
    const report = await runTranscriptionBenchmark({
      chunkCount: 1,
      sampleRates: [16000],
      writeReportFile: false,
      silent: true,
    });

    expect(report.totalChunksProcessed).toBe(1);
    expect(report.metrics.endToEndMs.count).toBe(1);
    expect(report.metrics.endToEndMs.p50Ms).toBeGreaterThanOrEqual(0);
  });
});
