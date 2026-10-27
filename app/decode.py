# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Audio file decoding (FFmpeg via PyAV) -> float32 stereo PCM."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np

try:  # PyAV is the primary decoder
    import av

    _HAS_AV = True
except Exception:  # pragma: no cover
    av = None
    _HAS_AV = False


AUDIO_EXTS = {
    ".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac",
    ".wma", ".aiff", ".aif", ".ape", ".alac", ".mp4", ".mkv", ".mov",
    ".webm", ".ts", ".m4b", ".caf", ".amr", ".ac3", ".dts",
}


@dataclass
class DecodedTrack:
    path: str
    data: np.ndarray  # (frames, 2) float32
    rate: int
    duration: float
    title: str
    artist: str = ""
    album: str = ""
    peaks: np.ndarray = field(default_factory=lambda: np.zeros(0, np.float32))
    source_channels: int = 2
    source_layout: str = "stereo"

    @property
    def frames(self) -> int:
        """总采样帧数。"""
        return int(self.data.shape[0])

    @property
    def nbytes(self) -> int:
        """PCM 数据占用字节数。"""
        return int(self.data.nbytes)


class DecodeError(Exception):
    pass


def _frame_to_array(frame) -> np.ndarray:
    """Convert a decoded float32 frame to an (n, channels) array."""
    arr = frame.to_ndarray()
    channels = int(frame.layout.nb_channels)
    if frame.format.is_planar:
        data = arr.T if arr.ndim == 2 else arr.reshape(-1, 1)
    else:
        data = arr.reshape(-1, channels)
    return np.ascontiguousarray(data, dtype=np.float32)


def _make_peaks(data: np.ndarray, buckets: int = 1200) -> np.ndarray:
    """为波形进度条生成固定数量的峰值（按块取绝对值最大）。"""
    n = data.shape[0]
    if n == 0:
        return np.zeros(buckets, np.float32)
    step = max(1, n // buckets)
    usable = (n // step) * step
    if usable < step:
        return np.zeros(buckets, np.float32)
    block = data[:usable].reshape(-1, step, data.shape[1])
    amp = np.abs(block).max(axis=(1, 2))
    if amp.size < buckets:
        amp = np.pad(amp, (0, buckets - amp.size))
    return np.ascontiguousarray(amp[:buckets].astype(np.float32))


def decode_track(
    path: str,
    progress: Optional[Callable[[float], None]] = None,
    max_seconds: float = 3 * 3600,
) -> DecodedTrack:
    """Decode any FFmpeg-supported media file to stereo float32 PCM."""
    if not _HAS_AV:
        raise DecodeError("缺少 PyAV 解码组件")
    p = Path(path)
    if not p.exists():
        raise DecodeError(f"文件不存在: {p}")

    try:
        container = av.open(str(p))
    except Exception as exc:
        raise DecodeError(f"无法打开文件: {exc}") from exc

    try:
        streams = [s for s in container.streams if s.type == "audio"]
        if not streams:
            raise DecodeError("文件中没有音频轨道")
        stream = streams[0]
        src_rate = int(stream.rate or 48000)
        src_channels = int(stream.channels or 2)
        total = float(stream.duration * stream.time_base) if stream.duration else 0.0

        raw_layout = (stream.layout.name or "").lower() if stream.layout else ""
        if raw_layout in ("mono", "stereo", "5.1", "7.1"):
            layout = raw_layout
        elif src_channels == 1:
            layout = "mono"
        elif src_channels == 2:
            layout = "stereo"
        elif src_channels >= 8:
            layout = "7.1"
        elif src_channels >= 6:
            layout = "5.1"
        else:
            layout = "stereo"
        if layout == "mono" and src_channels > 1:
            layout = "stereo"

        resampler = av.AudioResampler(format="flt", layout=layout, rate=src_rate)
        chunks: List[np.ndarray] = []
        total_frames = 0

        def flush():
            """冲刷重采样器并收集尾部残留帧。"""
            nonlocal total_frames
            try:
                frames = resampler.resample(None)
            except Exception:
                frames = []
            if frames is None:
                frames = []
            if not isinstance(frames, (list, tuple)):
                frames = [frames]
            for fr in frames:
                if fr is None:
                    continue
                a = _frame_to_array(fr)
                chunks.append(a)
                total_frames += a.shape[0]

        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                a = _frame_to_array(rf)
                chunks.append(a)
                total_frames += a.shape[0]
            if total_frames > max_seconds * src_rate:
                raise DecodeError("音频过长（超过 3 小时）")
            if progress and total > 0:
                try:
                    progress(min(0.99, max(0.0, float(frame.pts or 0) * stream.time_base / total)))
                except Exception:
                    pass
        flush()

        if not chunks:
            raise DecodeError("解码结果为空")

        data = np.concatenate(chunks, axis=0)
        del chunks
        data = np.ascontiguousarray(data, dtype=np.float32)
        if progress:
            progress(1.0)

        meta = {}
        try:
            meta = {str(k).lower(): str(v) for k, v in (container.metadata or {}).items()}
        except Exception:
            pass
        title = meta.get("title") or p.stem
        artist = meta.get("artist") or meta.get("album_artist") or ""
        album = meta.get("album") or ""
        duration = data.shape[0] / float(src_rate)

        return DecodedTrack(
            path=str(p),
            data=data,
            rate=src_rate,
            duration=duration,
            title=title,
            artist=artist,
            album=album,
            peaks=_make_peaks(data),
            source_channels=int(data.shape[1]),
            source_layout=layout,
        )
    finally:
        try:
            container.close()
        except Exception:
            pass
