import sys
from pathlib import Path, time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import MainWindow

app = QApplication([])
app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
w = MainWindow(); w.resize(1240, 800); w.show()
def pump(sec, until=None):
    end = time.time()+sec
    while time.time() < end:
        app.processEvents(); time.sleep(0.01)
        if until and until(): return True
    return False
pump(0.4)
k = list(w.cards.keys())[0]
w.cards[k].set_checked(True); w._on_card_toggled(k, True)
w._load_path(r"I:\DSHwork\MultiSpeaker\build\media\tone.flac", autoplay=False)
ok = pump(15.0, until=lambda: w.track is not None)
print("loaded:", ok, w.track.duration if w.track else None)
w.title.setText("夜曲 · 立体声测试")
w.subtitle.setText("MultiSpeaker Test Suite · Stereo")
w.wave.set_progress(0.42)
w.time_now.setText("00:05")
w.time_total.setText("00:12")
w.badge_sync.setText("1 台同步")
pump(0.6)
w.grab().save(r"I:\DSHwork\MultiSpeaker\build\ui_current.png")
print("saved")
w.close()
