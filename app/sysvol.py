# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Windows endpoint volume control (IAudioEndpointVolume via pycaw)."""
from __future__ import annotations

import warnings
from typing import Dict, Optional

warnings.filterwarnings("ignore", category=UserWarning, module="pycaw")

try:
    from pycaw.utils import AudioUtilities

    _HAS_PYCAW = True
except Exception:  # pragma: no cover
    AudioUtilities = None
    _HAS_PYCAW = False


class SystemVolume:
    """Maps endpoint friendly names to their IAudioEndpointVolume interface."""

    def __init__(self) -> None:
        """建立端点名称 → IAudioEndpointVolume 映射；依赖缺失时自动降级。"""
        self.available = False
        self._map: Dict[str, object] = {}
        self.refresh()

    def refresh(self) -> None:
        """重新枚举渲染端点并缓存各自的 IAudioEndpointVolume。"""
        self._map.clear()
        if not _HAS_PYCAW:
            self.available = False
            return
        try:
            devices = list(AudioUtilities.GetAllDevices())
        except Exception:
            self.available = False
            return
        for dev in devices:
            try:
                volume = dev.EndpointVolume
                if volume is None:
                    continue
                name = str(dev.FriendlyName)
                # first working endpoint wins (EnumAudioEndpoints order)
                self._map.setdefault(name, volume)
            except Exception:
                continue
        self.available = bool(self._map)

    def has(self, name: str) -> bool:
        """该端点是否可控制系统音量。"""
        return name in self._map

    def get(self, name: str) -> Optional[float]:
        """读取端点主音量（0..1 标量）；失败返回 None。"""
        vol = self._map.get(name)
        if vol is None:
            return None
        try:
            return max(0.0, min(1.0, float(vol.GetMasterVolumeLevelScalar())))
        except Exception:
            return None

    def set(self, name: str, scalar: float) -> bool:
        """设置端点主音量；成功返回 True。"""
        vol = self._map.get(name)
        if vol is None:
            return False
        try:
            vol.SetMasterVolumeLevelScalar(float(max(0.0, min(1.0, scalar))), None)
            return True
        except Exception:
            return False

    def get_mute(self, name: str) -> Optional[bool]:
        """读取端点静音状态；失败返回 None。"""
        vol = self._map.get(name)
        if vol is None:
            return None
        try:
            return bool(vol.GetMute())
        except Exception:
            return None

    def set_mute(self, name: str, muted: bool) -> bool:
        """设置端点静音；成功返回 True。"""
        vol = self._map.get(name)
        if vol is None:
            return False
        try:
            vol.SetMute(1 if muted else 0, None)
            return True
        except Exception:
            return False
