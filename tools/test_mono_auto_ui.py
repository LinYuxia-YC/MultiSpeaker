import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import MainWindow, SettingsDialog
import numpy as np
from app.decode import DecodedTrack

app = QApplication([]); app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
w = MainWindow(); w.resize(1240, 800); w.show()
for _ in range(4): app.processEvents()

def track(ch):
    t = np.arange(48000)/48000.0
    d = np.stack([0.2*np.sin(2*np.pi*440*t), 0.2*np.sin(2*np.pi*880*t)], axis=1).astype(np.float32)
    return DecodedTrack(path="", data=d, rate=48000, duration=1.0, title="t", source_channels=ch)

print("default mode:", w._mono_mode, "| btn:", w.btn_mono.text(), "| engine:", w.engine.mono_mix)
w.track = track(2); w.engine.set_track(w.track); w._refresh_mono_ui()
print("2ch:", w.btn_mono.text(), "| engine:", w.engine.mono_mix)
w.track = track(6); w.engine.set_track(w.track); w._refresh_mono_ui()
print("6ch:", w.btn_mono.text(), "| engine:", w.engine.mono_mix)
w._set_mono_mode("mono")
print("force mono:", w.btn_mono.text(), "| engine:", w.engine.mono_mix, "| setting:", w.settings.value("mono_mode"))
w._set_mono_mode("stereo")
print("force stereo:", w.btn_mono.text(), "| engine:", w.engine.mono_mix)
w._set_mono_mode("auto")
print("auto again:", w.btn_mono.text(), "| engine:", w.engine.mono_mix)
d = SettingsDialog("all", False, "tray", "auto"); print("dialog auto:", d.rb_mono_auto.isChecked())
d.rb_mono_stereo.setChecked(True); d._accept(); print("dialog ->", d.mono_mode)
w.close()
