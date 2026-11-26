# Device Troubleshooting Guide

This guide helps developers diagnose and resolve common audio‑device issues encountered when working with the **sde‑6‑voicebot** audio pipeline.

## 1. Listing Available Devices
```bash
python -c "from src.audio.device import MockAudioDeviceAdapter; print([d.name for d in MockAudioDeviceAdapter().list_devices()])"
```
The command prints a list of mock devices (default, studio, offline). For a real environment replace `MockAudioDeviceAdapter` with the appropriate platform adapter.

## 2. Common Failure Scenarios
| Symptom | Likely Cause | Steps to Resolve |
|--------|--------------|------------------|
| `DeviceNotFound` | Wrong `device_id` passed to `select_device` | Verify the ID using the list command above. |
| `DeviceUnavailable` | Physical device unplugged or driver failure | Re‑connect the device, ensure OS recognizes it, then restart the controller. |
| `NoAudioDevicesAvailable` | All devices are offline or permissions denied | Check OS audio settings, grant microphone permission, or use the mock adapter. |
| Permission errors (`PermissionState.DENIED`) | User denied microphone access | Re‑run the permission request flow or adjust OS privacy settings. |

## 3. Recovery Workflow
When a device loss is detected, the `DeviceRecoveryManager` automatically:
1. Emits a `DeviceLost` event.
2. Starts an exponential back‑off retry (1 s → 2 s → 4 s … up to the configured max).
3. Attempts to switch to an available fallback device.
4. Emits a `DeviceRecovered` event on success.

You can monitor this flow via the event stream:
```python
controller.event_emitter.subscribe(lambda e: print(e))
```

## 4. Debugging Tips
- **Enable verbose logging** by setting the environment variable `AUDIO_LOG_LEVEL=DEBUG` before running the demo.
- **Check buffer state**: `controller.buffer.get_stats()` shows current size and drop counts.
- **Inspect lifecycle state**: `controller.lifecycle.state` should be `recording`, `paused` or `stopped`.

## 5. Regeneration of Mock Devices
If you need a custom set of mock devices (e.g., to simulate a permanently offline mic), instantiate the adapter with `custom_devices`:
```python
from src.audio.device import AudioDevice, MockAudioDeviceAdapter, PermissionState

device = AudioDevice(
    device_id="my-offline-mic",
    name="My Offline Mic",
    is_default=False,
    supported_sample_rates=[16000],
    supported_channels=[1],
    is_available=False,
)
adapter = MockAudioDeviceAdapter(custom_devices=[device])
```

---
*Keep this file under `docs/` and reference it from the README.*
