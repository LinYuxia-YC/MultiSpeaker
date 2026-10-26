"""End-to-end GUI flow test: load files, play, meters, auto-advance."""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from PySide6.QtWidgets import QApplication

from app.ui import theme
from app.ui.main_window import MainWindow

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


media = r"I:\DSHwork\MultiSpeaker\build\media"
w._add_files([media + r"\tone.mp3", media + r"\tone.flac"], autoplay=False)
print("playlist:", len(w.playlist), "items:", w.list.count())

keys = list(w.cards.keys())
for k in keys[:2]:
    w.cards[k].set_checked(True)
    w._on_card_toggled(k, True)

w._play_index(0)
ok = pump(8.0, until=lambda: w.track is not None and w.engine.running)
print("loaded+playing:", ok, "title:", w.title._full, "running:", w.engine.running,
      "rate:", w.track.rate if w.track else None)
pump(1.5)
print("pos:", round(w.engine.position(), 2), "peaks:",
      {k: (round(v[0], 3), round(v[1], 3)) for k, v in w.engine.peaks().items()})
print("status:", w.status.text(), "| badge:", w.badge_sync.text())
print("time labels:", w.time_now.text(), "/", w.time_total.text(), "| wave:", round(w.wave._progress, 3))
w.grab().save(r"I:\DSHwork\MultiSpeaker\build\ui_flow.png")

# seek close to the end -> auto advance
dur = w.track.duration
w._seek_ratio((dur - 1.2) / dur)
print("seeking to", round(dur - 1.2, 2))
advanced = pump(6.0, until=lambda: w.current_index == 1 and w.track is not None
                and w.engine.running and w.engine.position() < 3)
print("auto-advance:", advanced, "index:", w.current_index, "title:", w.title._full,
      "running:", w.engine.running)

w.engine.pause()
pump(0.3)
print("paused:", w.engine.paused, "status:", w.header_state.text())
w.engine.resume()
pump(0.4)
print("resumed, pos:", round(w.engine.position(), 2))

w._stop()
pump(0.4)
print("stopped:", w.engine.running, "pos:", round(w.engine.position(), 2), "time:", w.time_now.text())

# device add/remove while playing
w._play_index(1)
pump(4.0, until=lambda: w.engine.running)
if w.engine.running:
    k3 = keys[2]
    w.cards[k3].set_checked(True)
    w._on_card_toggled(k3, True)
    pump(0.8)
    print("devices while playing:", len(w.engine.workers), "errors:",
          {k: c.property("error") for k, c in w.cards.items() if c.property("error") == "true"})
    w.engine.stop()
    pump(0.2)

img = Image.open(r"I:\DSHwork\MultiSpeaker\build\ui_flow.png")
print("screenshot:", img.size)
w.close()
