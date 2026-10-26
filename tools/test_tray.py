import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from app.ui import theme
from app.ui.main_window import MainWindow
from app.autostart import is_enabled, set_enabled, startup_command

app = QApplication([])
app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
app.setQuitOnLastWindowClosed(False)
w = MainWindow()
w.resize(1240, 800); w.show()
for _ in range(4): app.processEvents()

print("tray available:", QSystemTrayIcon.isSystemTrayAvailable(), "tray:", w.tray is not None)
print("close_action:", w._close_action)
if w.tray:
    print("menu:", [a.text() for a in w._tray_menu.actions() if not a.isSeparator()])
w._close_action = "tray"
w.close()
for _ in range(3): app.processEvents()
print("after close(tray): visible=", w.isVisible())
w.show_from_tray()
for _ in range(3): app.processEvents()
print("after tray open: visible=", w.isVisible())
print("startup command:", startup_command())
set_enabled(True); print("autostart enabled:", is_enabled())
set_enabled(False); print("autostart disabled:", is_enabled())
print("registry clean:", not is_enabled())
w._quitting = True
w.close()
print("done")
