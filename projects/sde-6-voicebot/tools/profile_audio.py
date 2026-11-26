import time
import argparse
import tracemalloc
from src.audio.controller import AudioPipelineController
from src.audio.mock_source import MockMicrophoneSource

def run_profile(iterations: int, chunk_duration_ms: float):
    # Warm‑up
    controller = AudioPipelineController(chunk_duration_ms=chunk_duration_ms)
    controller.start()
    # Warm‑up loop (few frames)
    for _ in range(5):
        controller.capture_step()
    controller.stop()

    # Profiling
    latencies = []
    tracemalloc.start()
    for i in range(iterations):
        start = time.perf_counter()
        ctrl = AudioPipelineController(chunk_duration_ms=chunk_duration_ms)
        ctrl.start()
        ctrl.capture_step()
        ctrl.stop()
        end = time.perf_counter()
        latencies.append((end - start) * 1000.0)  # ms
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    avg_latency = sum(latencies) / len(latencies)
    print(f"Avg frame latency: {avg_latency:.2f} ms")
    print(f"Peak memory usage: {peak / (1024 * 1024):.2f} MiB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile audio pipeline latency and memory.")
    parser.add_argument("--iterations", type=int, default=500, help="Number of iterations to run.")
    parser.add_argument("--chunk-duration", type=float, default=20.0, help="Chunk duration in ms.")
    args = parser.parse_args()
    run_profile(args.iterations, args.chunk_duration)
