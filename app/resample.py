# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""High quality sample-rate conversion helpers (soxr -> scipy -> linear)."""
from __future__ import annotations

from math import gcd
from typing import Optional

import numpy as np

try:
    import soxr  # type: ignore

    _HAS_SOXR = True
except Exception:  # pragma: no cover
    soxr = None
    _HAS_SOXR = False

try:
    from scipy.signal import resample_poly  # type: ignore

    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    resample_poly = None
    _HAS_SCIPY = False


def resample_stereo(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample (frames, channels) float32 audio.  Stereo layout is preserved."""
    if not data.size or src_rate == dst_rate:
        return data
    src_rate = int(src_rate)
    dst_rate = int(dst_rate)
    if _HAS_SOXR:
        try:
            out = soxr.resample(data, src_rate, dst_rate, quality="HQ")
            return np.ascontiguousarray(out, dtype=np.float32)
        except Exception:
            pass
    if _HAS_SCIPY:
        try:
            g = gcd(src_rate, dst_rate)
            out = resample_poly(data, dst_rate // g, src_rate // g, axis=0)
            return np.ascontiguousarray(out, dtype=np.float32)
        except Exception:
            pass
    n_out = int(round(data.shape[0] * dst_rate / src_rate))
    x_old = np.arange(data.shape[0], dtype=np.float64)
    x_new = np.linspace(0.0, data.shape[0] - 1, n_out, dtype=np.float64)
    out = np.empty((n_out, data.shape[1]), np.float32)
    for c in range(data.shape[1]):
        out[:, c] = np.interp(x_new, x_old, data[:, c]).astype(np.float32)
    return out


def backend_name() -> str:
    """返回当前可用的重采样后端名称（soxr/scipy/linear）。"""
    if _HAS_SOXR:
        return "soxr"
    if _HAS_SCIPY:
        return "scipy"
    return "linear"
