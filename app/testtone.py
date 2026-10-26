"""Built-in stereo test signal (left -> right -> both)."""
from __future__ import annotations

import numpy as np

from .decode import DecodedTrack


def make_stereo_test(rate: int = 48000) -> DecodedTrack:
    """6 s signal: 1.5 s left only, 1.5 s right only, then a stereo chord."""
    dur = 6.0
    n = int(rate * dur)
    t = np.arange(n, dtype=np.float64) / rate
    left = np.zeros(n, np.float64)
    right = np.zeros(n, np.float64)

    # 0.0-1.5 s: left channel only (A4 440 Hz)
    seg = (t >= 0.10) & (t < 1.60)
    left[seg] = 0.22 * np.sin(2 * np.pi * 440.0 * t[seg])
    # 1.7-3.2 s: right channel only (E5 659.25 Hz)
    seg = (t >= 1.70) & (t < 3.20)
    right[seg] = 0.22 * np.sin(2 * np.pi * 659.25 * t[seg])
    # 3.3-5.7 s: both channels, different notes -> obvious stereo image
    seg = (t >= 3.30) & (t < 5.70)
    left[seg] = 0.20 * np.sin(2 * np.pi * 523.25 * t[seg])
    right[seg] = 0.20 * np.sin(2 * np.pi * 783.99 * t[seg])

    # 12 ms cosine fades on every active region to avoid clicks
    for arr in (left, right):
        active = np.abs(arr) > 0
        idx = np.flatnonzero(np.diff(np.r_[0, active.astype(int), 0]))
        for start, end in zip(idx[::2], idx[1::2]):
            m = min(int(0.012 * rate), (end - start) // 2)
            if m > 1:
                ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, m))
                arr[start:start + m] *= ramp
                arr[end - m:end] *= ramp[::-1]

    data = np.stack([left, right], axis=1).astype(np.float32)
    peaks = np.zeros(600, np.float32)
    step = max(1, n // 600)
    amp = np.abs(data).max(axis=1)
    for i in range(600):
        chunk = amp[i * step:(i + 1) * step]
        peaks[i] = float(chunk.max()) if chunk.size else 0.0

    return DecodedTrack(
        path="",
        data=np.ascontiguousarray(data),
        rate=rate,
        duration=dur,
        title="声道测试信号",
        artist="左声道 → 右声道 → 双声道",
        album="MultiSpeaker",
        peaks=peaks,
        source_channels=2,
    )
