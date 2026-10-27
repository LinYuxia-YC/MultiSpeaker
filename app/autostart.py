# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Auto-start registration (HKCU\\...\\Run)."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MultiSpeaker"


def startup_command() -> str:
    """生成写入 Run 键的启动命令（打包后带 --tray 静默启动）。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    root = Path(__file__).resolve().parents[1]
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    return f'"{exe}" "{root / "main.py"}" --tray'


def is_enabled() -> bool:
    """检查当前用户是否已登记开机自启。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """写入或删除当前用户的开机自启项，返回最终状态。"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        return is_enabled()
    return is_enabled()
