"""Headless UI audit: geometry, interaction, screenshots and ASCII preview."""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.ui import theme
from app.ui.main_window import MainWindow

app = QApplication([])
app.setStyle("Fusion")
app.setFont(theme.base_font(9.5))
app.setStyleSheet(theme.build_qss())

w = MainWindow()
w.resize(1240, 800)
w.show()
for _ in range(8):
    app.processEvents()


def pump(seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


print("window:", w.size().width(), "x", w.size().height())
for name in ("title", "subtitle", "wave", "btn_play", "cover", "vol", "list", "scroll"):
    obj = getattr(w, name, None)
    if obj is not None:
        g = obj.geometry()
        print(f"  {name:10s} {g.x():4d},{g.y():4d} {g.width():4d}x{g.height():3d}")

print(f"\ndevice cards: {len(w.cards)}")
for key, card in w.cards.items():
    g = card.geometry()
    kids = {c.__class__.__name__ + ":" + (c.text() if hasattr(c, "text") else ""): c.geometry()
            for c in card.findChildren(QWidget) if c.parent() is card}
    name_w = card.name.width()
    print(f"  {key[:26]:26s} {g.width()}x{g.height()} checked={card.is_checked()} name_w={name_w}")

# ---------- interaction: play test tone on two endpoints ----------
keys = list(w.cards.keys())
for k in keys[:2]:
    w.cards[k].set_checked(True)
    w._on_card_toggled(k, True)
print("\nselected:", [k for k, c in w.cards.items() if c.is_checked()])

w._play_test()
pump(2.2)
peaks = w.engine.peaks()
print("after play: running=", w.engine.running, "pos=", round(w.engine.position(), 2),
      "icon=", repr(w.btn_play.text()), "peaks=",
      {k: (round(v[0], 3), round(v[1], 3)) for k, v in peaks.items()})
print("status:", w.status.text(), "|", w.header_state.text())
print("badge:", w.badge_sync.text(), "| wave prog:", round(w.wave._progress, 3))
w.grab().save(r"I:\DSHwork\MultiSpeaker\build\ui_playing.png")

w.engine.pause()
pump(0.4)
print("paused:", w.engine.paused, "icon=", repr(w.btn_play.text()), "status:", w.header_state.text())
w.engine.resume()
pump(0.4)
w.engine.seek(1.0)
pump(0.5)
print("after seek pos=", round(w.engine.position(), 2))
w.engine.stop()
pump(0.5)
print("stopped: running=", w.engine.running, "pos=", round(w.engine.position(), 2),
      "icon=", repr(w.btn_play.text()))
for k in keys[:2]:
    w.cards[k].set_checked(False)
    w._on_card_toggled(k, False)

pump(0.2)
w.grab().save(r"I:\DSHwork\MultiSpeaker\build\ui_audit.png")

# ---------- ASCII preview from the PNG ----------
img = Image.open(r"I:\DSHwork\MultiSpeaker\build\ui_audit.png").convert("L")
a = np.asarray(img, dtype=np.float32)
H, W = a.shape
cols, rows = 150, 52
chars = " .:-=+*#%@"
print("\n--- preview ---")
for r in range(rows):
    line = []
    for c in range(cols):
        y0, y1 = int(r * H / rows), int((r + 1) * H / rows)
        x0, x1 = int(c * W / cols), int((c + 1) * W / cols)
        block = a[y0:max(y0 + 1, y1), x0:max(x0 + 1, x1)]
        v = float(block.max()) if block.size else 0.0
        line.append(chars[min(9, int(v / 25.6))])
    print("".join(line))
