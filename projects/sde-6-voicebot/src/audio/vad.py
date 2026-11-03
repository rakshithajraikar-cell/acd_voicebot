"""Voice Activity Detection (VAD) Interface & Energy Classifier (SDE 6 - W1 - Days 10–11).

Provides:
- VADResult: Typed result of speech detection for an AudioChunk.
- VoiceActivityDetector: Abstract contract for VAD engines.
- EnergyVAD: Deterministic energy/RMS-based VAD with configurable energy threshold,
  minimum speech duration (to reject short noise spikes), and hangover smoothing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
import struct
from typing import Optional

from src.audio.schemas import AudioChunk, AudioError


@dataclass(frozen=True)
class VADResult:
    """Detection results for a single processed AudioChunk.

    Attributes:
        is_speech: True if speech activity is actively confirmed.
        confidence: Speech confidence score between 0.0 and 1.0.
        energy_rms: Normalized Root Mean Square energy (0.0 to 1.0).
        speech_duration_ms: Cumulative speech segment duration in ms.
        state: State label ('SPEECH', 'SILENCE', 'HANGOVER').
    """
    is_speech: bool
    confidence: float
    energy_rms: float
    speech_duration_ms: float
    state: str


class VoiceActivityDetector(ABC):
    """Abstract interface for voice activity detection."""

    @abstractmethod
    def process_chunk(self, chunk: AudioChunk) -> VADResult:
        """Process an AudioChunk and classify it as speech or non-speech."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal accumulator state for a new session."""
        pass


class EnergyVAD(VoiceActivityDetector):
    """Deterministic, energy-based voice activity detector with noise filtering.

    Parameters:
        energy_threshold: Normalized RMS threshold (0.0 to 1.0) above which a frame is candidate speech.
        min_speech_duration_ms: Minimum continuous audio energy required before declaring speech.
                                Rejects brief impulsive noise spikes like microphone clicks.
        hangover_duration_ms: Duration in ms to continue declaring speech after energy drops below threshold.
                              Smooths brief pauses between syllables and words.
    """

    def __init__(
        self,
        energy_threshold: float = 0.05,
        min_speech_duration_ms: float = 60.0,
        hangover_duration_ms: float = 100.0,
    ) -> None:
        if not (0.0 <= energy_threshold <= 1.0):
            raise AudioError(
                code="INVALID_VAD_THRESHOLD",
                message_safe_for_user=f"VAD energy threshold must be in range [0.0, 1.0], got {energy_threshold}",
            )
        if min_speech_duration_ms < 0 or hangover_duration_ms < 0:
            raise AudioError(
                code="INVALID_VAD_DURATION",
                message_safe_for_user="VAD durations must be non-negative.",
            )

        self.energy_threshold: float = energy_threshold
        self.min_speech_duration_ms: float = min_speech_duration_ms
        self.hangover_duration_ms: float = hangover_duration_ms

        # Internal state
        self._consecutive_energy_duration_ms: float = 0.0
        self._current_hangover_ms: float = 0.0
        self._total_speech_duration_ms: float = 0.0
        self._is_in_speech: bool = False

    def reset(self) -> None:
        """Reset internal tracking state."""
        self._consecutive_energy_duration_ms = 0.0
        self._current_hangover_ms = 0.0
        self._total_speech_duration_ms = 0.0
        self._is_in_speech = False

    @staticmethod
    def calculate_chunk_rms(chunk: AudioChunk) -> float:
        """Calculate normalized RMS energy [0.0, 1.0] from 16-bit PCM payload."""
        if chunk.is_empty:
            return 0.0

        sample_count = len(chunk.payload) // 2
        if sample_count == 0:
            return 0.0

        samples = struct.unpack(f"<{sample_count}h", chunk.payload)
        sum_sq = sum(s * s for s in samples)
        mean_sq = sum_sq / sample_count
        rms_val = math.sqrt(mean_sq)
        return min(1.0, rms_val / 32768.0)

    def process_chunk(self, chunk: AudioChunk) -> VADResult:
        """Analyze chunk energy and return deterministic VAD classification."""
        rms = self.calculate_chunk_rms(chunk)
        chunk_dur = chunk.duration_ms
        is_above_threshold = rms >= self.energy_threshold

        if is_above_threshold:
            self._consecutive_energy_duration_ms += chunk_dur
            self._current_hangover_ms = self.hangover_duration_ms

            if self._consecutive_energy_duration_ms >= self.min_speech_duration_ms:
                self._is_in_speech = True
                self._total_speech_duration_ms += chunk_dur
                confidence = min(1.0, 0.6 + (rms - self.energy_threshold) * 2.0)
                state = "SPEECH"
            else:
                # Potential speech candidate, but still below minimum speech duration (filtering noise)
                confidence = 0.4
                state = "CANDIDATE_NOISE_CHECK"
        else:
            self._consecutive_energy_duration_ms = 0.0

            if self._is_in_speech and self._current_hangover_ms > 0:
                # In hangover period
                self._current_hangover_ms -= chunk_dur
                self._total_speech_duration_ms += chunk_dur
                confidence = 0.5
                state = "HANGOVER"
            else:
                # Pure silence
                self._is_in_speech = False
                confidence = max(0.0, 1.0 - (rms / max(0.001, self.energy_threshold)))
                state = "SILENCE"

        return VADResult(
            is_speech=self._is_in_speech,
            confidence=round(confidence, 3),
            energy_rms=round(rms, 4),
            speech_duration_ms=round(self._total_speech_duration_ms, 2),
            state=state,
        )
