"""Channel layout helpers: map a source layout onto a device's channel count."""
from __future__ import annotations

from typing import List

import numpy as np

# Windows / WAVE default channel order for a given channel count.
DEVICE_ORDER = {
    1: ["M"],
    2: ["FL", "FR"],
    3: ["FL", "FR", "FC"],
    4: ["FL", "FR", "BL", "BR"],
    5: ["FL", "FR", "FC", "BL", "BR"],
    6: ["FL", "FR", "FC", "LFE", "BL", "BR"],
    7: ["FL", "FR", "FC", "LFE", "BC", "SL", "SR"],
    8: ["FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"],
}

LAYOUT_ORDER = {
    "mono": ["M"],
    "stereo": ["FL", "FR"],
    "2.1": ["FL", "FR", "LFE"],
    "3.0": ["FL", "FR", "FC"],
    "4.0": ["FL", "FR", "BL", "BR"],
    "quad": ["FL", "FR", "BL", "BR"],
    "5.0": ["FL", "FR", "FC", "BL", "BR"],
    "5.1": ["FL", "FR", "FC", "LFE", "BL", "BR"],
    "5.1(side)": ["FL", "FR", "FC", "LFE", "SL", "SR"],
    "6.1": ["FL", "FR", "FC", "LFE", "BC", "SL", "SR"],
    "7.1": ["FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"],
    "7.1(wide)": ["FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"],
}

SIDE_OF = {"BL": "SL", "BR": "SR", "SL": "BL", "SR": "BR"}

FRONT_GAIN = 1.0
CENTER_GAIN = 0.7071
SURROUND_GAIN = 0.7071


def source_names(layout: str, channels: int) -> List[str]:
    names = LAYOUT_ORDER.get((layout or "").lower())
    if names and len(names) == channels:
        return list(names)
    if channels in DEVICE_ORDER:
        return list(DEVICE_ORDER[channels])
    # unknown: treat extra channels as front-ish and keep the first ones
    base = DEVICE_ORDER[8]
    return base[:channels] if channels <= 8 else base + ["M"] * (channels - 8)


def build_matrix(src_names: List[str], dev_channels: int, channel_mode: str = "all") -> np.ndarray:
    """Return (src_channels, dev_channels) float32 gain matrix."""
    dev_names = DEVICE_ORDER.get(dev_channels, DEVICE_ORDER[8][:dev_channels])
    m = np.zeros((len(src_names), len(dev_names)), np.float32)
    idx = {name: i for i, name in enumerate(dev_names)}

    if src_names == ["M"]:
        # mono fills every speaker; LFE stays quiet
        for j, name in enumerate(dev_names):
            if name == "LFE":
                continue
            m[0, j] = 1.0 if name in ("FL", "FR") else (0.5 if name == "FC" else SURROUND_GAIN)
        return m

    direct = {"FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR", "BC"}
    for i, name in enumerate(src_names):
        if name in idx:
            m[i, idx[name]] = 1.0

    for i, name in enumerate(src_names):
        if name in idx or name == "LFE":
            continue
        if name == "FC":
            for t in ("FL", "FR"):
                if t in idx:
                    m[i, idx[t]] += CENTER_GAIN
        elif name in SIDE_OF:
            alt = SIDE_OF[name]
            if alt in idx:
                m[i, idx[alt]] += SURROUND_GAIN
            else:
                front = "FL" if name in ("BL", "SL", "BC") else "FR"
                if front in idx:
                    m[i, idx[front]] += SURROUND_GAIN
        elif name in ("FL", "FR") and name not in idx:
            if name == "FL" and "FC" in idx:
                m[i, idx["FC"]] += 1.0
            elif name == "FR" and "FC" in idx:
                m[i, idx["FC"]] += 1.0

    # stereo source onto a surround device: spread to the rear pair / centre
    if src_names == ["FL", "FR"] and dev_channels > 2 and channel_mode != "front":
        fl, fr = m[0].copy(), m[1].copy()
        if "FC" in idx:
            m[0, idx["FC"]] = 0.25
            m[1, idx["FC"]] = 0.25
        for side_name, src_row in (("BL", 0), ("BR", 1), ("SL", 0), ("SR", 1)):
            if side_name in idx:
                m[src_row, idx[side_name]] = SURROUND_GAIN
    return m


def downmix_to_stereo(block: np.ndarray, src_names: List[str]) -> np.ndarray:
    """Standard 5.1/7.1 -> stereo fold-down."""
    if block.shape[1] <= 2:
        return block[:, :2]
    m = build_matrix(src_names, 2, "front")
    out = block @ m
    # avoid clipping when many channels fold into two
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0.98:
        out *= 0.98 / peak
    return out.astype(np.float32, copy=False)


def downmix_to_mono(block: np.ndarray, src_names: List[str]) -> np.ndarray:
    if block.shape[1] == 1:
        return block[:, :1]
    if block.shape[1] == 2:
        return block.mean(axis=1, keepdims=True, dtype=np.float32)
    weights = np.array(
        [1.0 if n in ("FL", "FR") else (0.7071 if n != "LFE" else 0.0) for n in src_names],
        dtype=np.float32,
    )
    total = float(weights.sum()) or 1.0
    return ((block @ weights) / total).astype(np.float32).reshape(-1, 1)
