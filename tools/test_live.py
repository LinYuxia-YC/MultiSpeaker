"""Headless test of the system-audio (virtual cable) relay."""
import sys
from pathlib import Path
import threading
import time

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.live import find_cable_capture
from app.ui import theme
from app.ui.main_window import MainWindow

from PySide6.QtWidgets import QApplication

RATE = 48000
DUR = 8.0
t = np.arange(int(RATE * DUR)) / RATE
env = np.minimum(1.0, np.minimum(t / 0.05, (DUR - t) / 0.05))
left = 0.25 * np.sin(2 * np.pi * 440 * t) * env
right = 0.25 * np.sin(2 * np.pi * 880 * t) * env
tone = np.stack([left, right], axis=1).astype(np.float32)

devices = list(sd.query_devices())
cable_render = next(
    i for i, d in enumerate(devices)
    if "MultiSpeaker" in d["name"] and int(d.get("max_output_channels", 0)) >= 2
)
print("cable render device:", cable_render, devices[cable_render]["name"])
print("cable capture:", find_cable_capture())


def play():
    try:
        with sd.OutputStream(device=cable_render, samplerate=RATE, channels=2,
                             dtype="float32", blocksize=1024) as s:
            s.write(tone)
    except Exception as exc:
        print("play error:", exc)


threading.Thread(target=play, daemon=True).start()
time.sleep(0.3)

app = QApplication([])
app.setStyle("Fusion")
app.setFont(theme.base_font(9.5))
app.setStyleSheet(theme.build_qss())
w = MainWindow()
w.resize(1240, 800)
w.show()


def pump(seconds, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)
        if until and until():
            return True
    return False


pump(0.5)
keys = [k for k in w.cards if "MultiSpeaker" not in k and "CABLE" not in k]
for k in keys[:2]:
    w.cards[k].set_checked(True)
    w._on_card_toggled(k, True)
print("outputs:", [k for k, c in w.cards.items() if c.is_checked()])

w._toggle_system_audio()
pump(2.0)
print("sys_active:", w._sys_active, "running:", w.engine.running,
      "cable:", w._cable)
print("input peaks:", None if w.engine.live_source is None else
      (round(w.engine.live_source.peak_l, 3), round(w.engine.live_source.peak_r, 3)))
print("device peaks:", {k: (round(v[0], 3), round(v[1], 3)) for k, v in w.engine.peaks().items()})
print("status:", w.status.text(), "|", w.sys_state.text(), "|", w.sys_source.text())
print("stats:", w.engine.device_stats())
w.grab().save(r"I:\DSHwork\MultiSpeaker\build\ui_sysaudio.png")

pump(1.5)
print("after 3.5s peaks:", {k: (round(v[0], 3), round(v[1], 3)) for k, v in w.engine.peaks().items()})
print("input:", None if w.engine.live_source is None else
      (round(w.engine.live_source.peak_l, 3), round(w.engine.live_source.peak_r, 3)))

w._stop_system_audio()
pump(0.5)
print("stopped: active=", w._sys_active, "running=", w.engine.running,
      "player enabled=", w.btn_play.isEnabled())
w.close()
