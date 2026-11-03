"""Audio Device Selection and Permission Adapter (SDE 6 - W1 - Days 8–9).

This module defines:
- PermissionState: Lifecycle states for audio hardware access permissions.
- AudioDevice: Strongly typed representation of an audio input endpoint.
- AudioDeviceAdapter: Abstract provider interface for hardware independence.
- MockAudioDeviceAdapter: Deterministic mock implementation handling device selection,
  permission grants, denials, and unsupported configuration errors cleanly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from src.audio.schemas import AudioError, AudioFormat


class PermissionState(str, Enum):
    """Permission state for microphone capture."""
    GRANTED = "granted"
    DENIED = "denied"
    PROMPT = "prompt"


@dataclass(frozen=True)
class AudioDevice:
    """Metadata describing an audio input capture device.

    Attributes:
        device_id: Unique hardware or logical identifier.
        name: Human-readable device label.
        is_default: Whether this is the system default input device.
        supported_sample_rates: List of sample rates supported by hardware in Hz.
        supported_channels: Channels supported (e.g. [1, 2]).
        is_available: Whether device is currently plugged in and functional.
    """
    device_id: str
    name: str
    is_default: bool = False
    supported_sample_rates: List[int] = field(default_factory=lambda: [16000, 44100, 48000])
    supported_channels: List[int] = field(default_factory=lambda: [1, 2])
    is_available: bool = True

    def supports_format(self, audio_format: AudioFormat) -> bool:
        """Check if this device can capture in the requested AudioFormat."""
        return (
            self.is_available
            and audio_format.sample_rate_hz in self.supported_sample_rates
            and audio_format.channels in self.supported_channels
        )


class AudioDeviceAdapter(ABC):
    """Abstract interface defining audio input device discovery and permission handling."""

    @abstractmethod
    def list_devices(self) -> List[AudioDevice]:
        """List all discovered audio input devices."""
        pass

    @abstractmethod
    def get_default_device(self) -> AudioDevice:
        """Get the default audio input device."""
        pass

    @abstractmethod
    def select_device(self, device_id: str) -> AudioDevice:
        """Select an active capture device by its ID."""
        pass

    @abstractmethod
    def get_permission_state(self) -> PermissionState:
        """Query current microphone permission state without prompting."""
        pass

    @abstractmethod
    def request_permission(self) -> PermissionState:
        """Prompt or request user microphone capture permission."""
        pass

    @abstractmethod
    def validate_device_for_format(self, device_id: str, audio_format: AudioFormat) -> None:
        """Validate that selected device has permissions and supports the audio format."""
        pass


class MockAudioDeviceAdapter(AudioDeviceAdapter):
    """Deterministic mock audio device adapter for tests and local mock mode.

    Simulates hardware device enumeration, selection, permission grants,
    and denial states without accessing physical system hardware.
    """

    def __init__(
        self,
        permission_state: PermissionState = PermissionState.GRANTED,
        custom_devices: Optional[List[AudioDevice]] = None,
    ) -> None:
        self._permission_state: PermissionState = permission_state
        self._devices: Dict[str, AudioDevice] = {}
        self._selected_device_id: Optional[str] = None

        if custom_devices:
            for dev in custom_devices:
                self._devices[dev.device_id] = dev
        else:
            self._init_default_mock_devices()

        default_dev = self.get_default_device()
        self._selected_device_id = default_dev.device_id

    def _init_default_mock_devices(self) -> None:
        """Initialize standard mock devices (default mic, studio mic, offline mic)."""
        dev_default = AudioDevice(
            device_id="mock-mic-default",
            name="Mock Default Internal Microphone",
            is_default=True,
            supported_sample_rates=[8000, 16000, 24000, 44100, 48000],
            supported_channels=[1, 2],
            is_available=True,
        )
        dev_studio = AudioDevice(
            device_id="mock-mic-studio",
            name="Mock Studio Pro USB Microphone",
            is_default=False,
            supported_sample_rates=[16000, 44100, 48000],
            supported_channels=[1, 2],
            is_available=True,
        )
        dev_offline = AudioDevice(
            device_id="mock-mic-offline",
            name="Mock Disconnected Headset Mic",
            is_default=False,
            supported_sample_rates=[16000],
            supported_channels=[1],
            is_available=False,
        )
        self._devices = {
            dev_default.device_id: dev_default,
            dev_studio.device_id: dev_studio,
            dev_offline.device_id: dev_offline,
        }

    def list_devices(self) -> List[AudioDevice]:
        """Return all configured mock devices."""
        return list(self._devices.values())

    def get_default_device(self) -> AudioDevice:
        """Return the default mock device."""
        for dev in self._devices.values():
            if dev.is_default and dev.is_available:
                return dev
        # Fallback to first available
        for dev in self._devices.values():
            if dev.is_available:
                return dev
        raise AudioError(
            code="NO_AUDIO_DEVICES_AVAILABLE",
            message_safe_for_user="No audio input devices are available.",
        )

    def select_device(self, device_id: str) -> AudioDevice:
        """Select a device by ID or raise AudioError if not found or offline."""
        if device_id not in self._devices:
            raise AudioError(
                code="DEVICE_NOT_FOUND",
                message_safe_for_user=f"Audio device '{device_id}' does not exist.",
                details={"device_id": device_id},
            )

        device = self._devices[device_id]
        if not device.is_available:
            raise AudioError(
                code="DEVICE_UNAVAILABLE",
                message_safe_for_user=f"Audio device '{device.name}' is currently unavailable or disconnected.",
                details={"device_id": device_id, "name": device.name},
            )

        self._selected_device_id = device_id
        return device

    @property
    def selected_device(self) -> AudioDevice:
        """Return currently selected AudioDevice."""
        if not self._selected_device_id or self._selected_device_id not in self._devices:
            return self.get_default_device()
        return self._devices[self._selected_device_id]

    def get_permission_state(self) -> PermissionState:
        """Return mock permission state."""
        return self._permission_state

    def set_permission_state(self, state: PermissionState) -> None:
        """Test helper to simulate user granting or denying permission."""
        self._permission_state = state

    def request_permission(self) -> PermissionState:
        """Simulate permission request prompt. If prompt, defaults to granted."""
        if self._permission_state == PermissionState.PROMPT:
            self._permission_state = PermissionState.GRANTED
        return self._permission_state

    def validate_device_for_format(self, device_id: str, audio_format: AudioFormat) -> None:
        """Verify permission state and format support without crashing.

        Raises:
            AudioError: With PERMISSION_DENIED if access is denied.
            AudioError: With UNSUPPORTED_DEVICE_FORMAT if the device cannot handle the format.
        """
        # Check permissions
        if self._permission_state == PermissionState.DENIED:
            raise AudioError(
                code="PERMISSION_DENIED",
                message_safe_for_user="Microphone access was denied by user or system policy.",
                details={"permission_state": self._permission_state.value},
            )

        device = self.select_device(device_id)

        # Check sample rate support
        if audio_format.sample_rate_hz not in device.supported_sample_rates:
            raise AudioError(
                code="UNSUPPORTED_DEVICE_FORMAT",
                message_safe_for_user=(
                    f"Device '{device.name}' does not support sample rate {audio_format.sample_rate_hz} Hz. "
                    f"Supported rates: {device.supported_sample_rates}"
                ),
                details={
                    "device_id": device_id,
                    "requested_rate": audio_format.sample_rate_hz,
                    "supported_rates": device.supported_sample_rates,
                },
            )

        # Check channels support
        if audio_format.channels not in device.supported_channels:
            raise AudioError(
                code="UNSUPPORTED_DEVICE_FORMAT",
                message_safe_for_user=(
                    f"Device '{device.name}' does not support {audio_format.channels} channel(s). "
                    f"Supported channels: {device.supported_channels}"
                ),
                details={
                    "device_id": device_id,
                    "requested_channels": audio_format.channels,
                    "supported_channels": device.supported_channels,
                },
            )
