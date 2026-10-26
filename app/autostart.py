"""Auto-start registration (HKCU\\...\\Run)."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MultiSpeaker"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    root = Path(__file__).resolve().parents[1]
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    return f'"{exe}" "{root / "main.py"}" --tray'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
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
