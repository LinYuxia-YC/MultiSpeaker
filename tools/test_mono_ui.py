import sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import MainWindow, SettingsDialog
app = QApplication([]); app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
w = MainWindow(); w.resize(1240, 800); w.show()
for _ in range(4): app.processEvents()
print("default mono:", w.engine.mono_mix, "| btn:", w.btn_mono.text(), "| checked:", w.btn_mono.isChecked())
w._apply_mono(True, save=True, announce=True)
print("after on  :", w.engine.mono_mix, "| btn:", w.btn_mono.text(), "| checked:", w.btn_mono.isChecked(),
      "| setting:", w.settings.value("mono_mix"), "| status:", w.status.text())
d = SettingsDialog("all", False, "tray", True)
print("dialog cb_mono default:", d.cb_mono.isChecked())
d.cb_mono.setChecked(False); d._accept(); print("dialog accepted mono:", d.mono)
w._apply_mono(False, save=True, announce=True)
print("after off :", w.engine.mono_mix, "| btn:", w.btn_mono.text(), "| setting:", w.settings.value("mono_mix"))
w.close()
