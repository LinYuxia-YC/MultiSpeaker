"""Live capture source: reads a virtual cable's output into a ring buffer."""
from __future__ import annotations

import time
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd


CABLE_HINTS = (
    "cable output", "vb-audio", "voicemeeter", "virtual audio cable",
    "virtual cable", "scream", "line 1",
)


def find_cable_capture() -> Optional[Tuple[int, str, int]]:
    """Locate a virtual-cable capture endpoint (index, name, rate)."""
    found = []
    try:
        devices = list(sd.query_devices())
        hostapis = list(sd.query_hostapis())
    except Exception:
        return None
    for i, d in enumerate(devices):
        try:
            if int(d.get("max_input_channels", 0)) < 2:
                continue
        except Exception:
            continue
        name = str(d.get("name", ""))
        low = name.lower()
        if any(h in low for h in CABLE_HINTS):
            rate = int(round(float(d.get("default_samplerate", 48000) or 48000)))
            try:
                host = str(hostapis[int(d["hostapi"])].get("name", "")).lower()
            except Exception:
                host = ""
            wasapi = 0 if "wasapi" in host else 1
            is_cable_out = 0 if "cable output" in low else 1
            found.append((wasapi, is_cable_out, i, name, rate))
    if not found:
        return None
    found.sort()
    _, _, idx, name, rate = found[0]
    return idx, name, rate


class LiveSource:
    """Ring buffer fed by a WASAPI input stream (the virtual cable's output)."""

    def __init__(self, device: int, rate: int, seconds: float = 2.0):
        self.rate = int(rate)
        self.cap = max(4096, int(self.rate * seconds))
        self.ring = np.zeros((self.cap, 2), np.float32)
        self.write = 0
        self.peak_l = 0.0
        self.peak_r = 0.0
        self.xruns = 0
        self.error = ""
        self.running = False
        self.stream = None
        self._device = int(device)

    def start(self) -> None:
        self.stream = sd.InputStream(
            device=self._device,
            samplerate=self.rate,
            channels=2,
            dtype="float32",
            blocksize=0,
            latency="low",
            callback=self._callback,
        )
        self.stream.start()
        self.running = True

    def stop(self) -> None:
        self.running = False
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        try:
            if status and getattr(status, "input_overflow", False):
                self.xruns += 1
            if frames <= 0:
                return
            n = self.write % self.cap
            if n + frames <= self.cap:
                self.ring[n:n + frames] = indata
            else:
                first = self.cap - n
                self.ring[n:] = indata[:first]
                self.ring[: frames - first] = indata[first:]
            self.write += frames
            self.peak_l = max(self.peak_l * 0.8, float(np.abs(indata[:, 0]).max()))
            self.peak_r = max(self.peak_r * 0.8, float(np.abs(indata[:, 1]).max()))
        except Exception as exc:  # pragma: no cover
            self.error = f"{type(exc).__name__}: {exc}"

    def read(self, start: float, frames: int, step: float) -> np.ndarray:
        idx = np.floor(start + step * np.arange(frames, dtype=np.float64)).astype(np.int64)
        return self.ring[idx % self.cap]

    def wait_ready(self, seconds: float = 1.5) -> bool:
        need = int(self.rate * 0.08)
        t0 = time.perf_counter()
        while self.write < need:
            if time.perf_counter() - t0 > seconds:
                return False
            time.sleep(0.01)
        return True
