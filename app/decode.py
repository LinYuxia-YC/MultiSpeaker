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

    @property
    def frames(self) -> int:
        return int(self.data.shape[0])

    @property
    def nbytes(self) -> int:
        return int(self.data.nbytes)


class DecodeError(Exception):
    pass


def _frame_to_stereo(frame) -> np.ndarray:
    """Convert a decoded float32 stereo frame to an (n, 2) array."""
    arr = frame.to_ndarray()
    if frame.format.is_planar:
        # (channels, samples)
        if arr.ndim == 2 and arr.shape[0] >= 2:
            arr = arr[:2].T
        else:
            arr = arr.reshape(-1, 1)
    else:
        # (1, samples * channels)
        arr = arr.reshape(-1, 2)
    if arr.shape[1] == 1:
        arr = np.repeat(arr, 2, axis=1)
    return np.ascontiguousarray(arr[:, :2], dtype=np.float32)


def _make_peaks(data: np.ndarray, buckets: int = 1200) -> np.ndarray:
    n = data.shape[0]
    if n == 0:
        return np.zeros(buckets, np.float32)
    step = max(1, n // buckets)
    usable = (n // step) * step
    if usable < step:
        return np.zeros(buckets, np.float32)
    block = data[:usable].reshape(-1, step, 2)
    amp = np.maximum(np.abs(block[:, :, 0]), np.abs(block[:, :, 1])).max(axis=1)
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

        resampler = av.AudioResampler(format="flt", layout="stereo", rate=src_rate)
        chunks: List[np.ndarray] = []
        total_frames = 0

        def flush():
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
                a = _frame_to_stereo(fr)
                chunks.append(a)
                total_frames += a.shape[0]

        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                a = _frame_to_stereo(rf)
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
            source_channels=src_channels,
        )
    finally:
        try:
            container.close()
        except Exception:
            pass
