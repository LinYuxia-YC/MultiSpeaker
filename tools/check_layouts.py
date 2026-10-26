import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import MainWindow
app = QApplication([]); app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
w = MainWindow(); w.show()
def pump(sec, until=None):
    end=time.time()+sec
    while time.time()<end:
        app.processEvents(); time.sleep(0.01)
        if until and until(): return True
    return False
pump(0.4)
for label, path in (("stereo mp3", r"I:\Music\U盘音乐\ray((left 超かぐや姫!＆right Leo_need星乃一歌 × 初音ミク)Stereo audio Version.mp3"),
                    ("5.1 wav", r"I:\DSHwork\MultiSpeaker\build\surround51.wav")):
    w.track=None
    w._load_path(path, autoplay=False)
    pump(20, until=lambda: w.track is not None)
    print(f"{label}: badge={w.btn_mono.text()!r} fmt={w.badge_fmt.text()!r} mono={w.engine.effective_mono()}")
w.close()
