# W2 Speech-to-Text: Latency Benchmark Results

Recorded on: `2026-11-27T06:12:32.569Z`  
Environment: Node `v24.11.1` (`win32` `x64`)  
Workstream: **W2 — Speech-to-Text (SDE 6, Pavithra P)**  

---

## 1. Executive Summary

- **Total Chunks Benchmarked**: 120
- **Sample Rates Tested**: 8000, 16000, 44100, 48000 Hz
- **End-to-End Median Latency (p50)**: **0.205 ms**
- **End-to-End 95th Percentile (p95)**: **1.182 ms**
- **End-to-End 99th Percentile (p99)**: **1.628 ms**
- **Throughput**: **2574.59 chunks/sec**
- **Real-Time Factor (RTF)**: **257.46x** (Processing faster than real-time audio)

---

## 2. Granular Latency Breakdown

| Pipeline Stage | Samples | Min (ms) | Mean (ms) | p50 / Median (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Audio Preprocessing | 120 | 0.055 | 0.177 | 0.121 | 0.298 | 0.547 | 1.374 | 1.386 |
| Mock STT Adapter | 120 | 0.037 | 0.132 | 0.055 | 0.16 | 0.213 | 0.915 | 5.837 |
| Segment Accumulator | 120 | 0.026 | 0.078 | 0.033 | 0.108 | 0.189 | 1.166 | 1.245 |
| **End-to-End Pipeline** | **120** | **0.121** | **0.388** | **0.205** | **0.708** | **1.182** | **1.628** | **8.046** |

---

## 3. SLA Compliance Assessment

| Metric | Target SLA | Measured Value | Compliance Status |
|---|---|---|:---:|
| **Median Latency (p50)** | < 15.0 ms | 0.205 ms | **MET** |
| **95th Percentile (p95)** | < 30.0 ms | 1.182 ms | **MET** |
| **99th Percentile (p99)** | < 50.0 ms | 1.628 ms | **MET** |
| **Real-Time Processing** | > 1.0x RTF | 257.46x RTF | **MET** |

*All benchmarks executed deterministically in offline mock mode without paid external credentials.*
