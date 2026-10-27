# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Windows audio endpoint discovery (WASAPI via PortAudio / sounddevice)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import sounddevice as sd


@dataclass
class AudioDevice:
    """A physical / virtual render endpoint we can play to."""

    index: int
    name: str
    hostapi: str
    channels: int
    rate: int
    latency: float  # default low output latency reported by PortAudio (seconds)
    is_default: bool = False
    key: str = ""
    display: str = ""
    note: str = ""

    @property
    def short(self) -> str:
        """用于界面显示的短名称（重名时带序号）。"""
        return self.display or self.name

    @property
    def is_wasapi(self) -> bool:
        """是否属于 WASAPI 主机 API。"""
        return "wasapi" in self.hostapi.lower()


def _clean_name(name: str) -> str:
    """规范化端点名称：去控制字符、压缩连续空白。"""
    name = name.replace("\x00", "").strip()
    return re.sub(r"\s+", " ", name)


# Endpoints that are themselves virtual cables must never be used as an output
# (that would feed the relay back into itself).
_VIRTUAL_OUT = (
    "cable input",
    "vb-audio",
    "voicemeeter",
    "virtual audio cable",
    "virtual cable",
    "multispeaker 组合输出",
    "scream",
)


def list_output_devices() -> List[AudioDevice]:
    """Enumerate render endpoints, preferring the WASAPI host API."""
    try:
        hostapis = list(sd.query_hostapis())
    except Exception:
        hostapis = []
    try:
        devices = list(sd.query_devices())
    except Exception:
        return []

    wasapi_ids = {
        i for i, h in enumerate(hostapis) if "wasapi" in str(h.get("name", "")).lower()
    }
    if not wasapi_ids:
        wasapi_ids = set(range(len(hostapis)))

    try:
        default_out = sd.default.device[0]
    except Exception:
        default_out = -1
    # Prefer the WASAPI host's own default endpoint (same as the Windows default).
    for i in sorted(wasapi_ids):
        try:
            wd = int(hostapis[i].get("default_output_device", -1))
        except Exception:
            wd = -1
        if wd >= 0:
            default_out = wd
            break

    result: List[AudioDevice] = []
    seen: Dict[str, int] = {}
    for idx, dev in enumerate(devices):
        if int(dev.get("max_output_channels", 0)) < 1:
            continue
        if int(dev.get("hostapi", -1)) not in wasapi_ids:
            continue
        name = _clean_name(str(dev.get("name", f"Device {idx}")))
        if any(h in name.lower() for h in _VIRTUAL_OUT):
            continue
        host = ""
        try:
            host = str(hostapis[int(dev["hostapi"])].get("name", ""))
        except Exception:
            pass
        seen[name] = seen.get(name, 0) + 1
        occ = seen[name]
        key = f"{name}#{occ}"
        display = name if occ == 1 else f"{name} (#{occ})"
        ch = int(dev.get("max_output_channels", 2))
        rate = int(round(float(dev.get("default_samplerate", 48000) or 48000)))
        lat = float(dev.get("default_low_output_latency", 0.0) or 0.0)
        result.append(
            AudioDevice(
                index=idx,
                name=name,
                hostapi=host,
                channels=max(1, min(ch, 8)),
                rate=rate,
                latency=lat,
                is_default=(idx == default_out),
                key=key,
                display=display,
            )
        )

    # Default device first, then keep enumeration order.
    result.sort(key=lambda d: (not d.is_default, d.index))
    return result


def device_by_key(devices: List[AudioDevice], key: str) -> Optional[AudioDevice]:
    """按稳定 key 在设备列表中查找端点。"""
    for d in devices:
        if d.key == key:
            return d
    return None


def describe(dev: AudioDevice) -> str:
    """生成「声道数 · 采样率」的展示文本。"""
    ch = "单声道" if dev.channels == 1 else f"{dev.channels} 声道"
    return f"{ch} · {dev.rate / 1000:.1f} kHz"
