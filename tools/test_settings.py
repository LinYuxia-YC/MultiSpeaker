import sys
import time, subprocess, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import SettingsDialog
app = QApplication([]); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
d = SettingsDialog("all", True, "exit")
print("autostart checked:", d.cb_autostart.isChecked(), "close=exit:", d.rb_exit.isChecked(), "tray radio:", d.rb_tray.isChecked())
d2 = SettingsDialog("front", False, "tray")
print("autostart checked:", d2.cb_autostart.isChecked(), "close=tray:", d2.rb_tray.isChecked(), "front:", d2.rb_front.isChecked())
