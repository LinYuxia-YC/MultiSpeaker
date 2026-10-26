import sys
from pathlib import Path, time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import SettingsDialog
app = QApplication([]); app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
d = SettingsDialog("all", False, "tray")
d.show()
for _ in range(6): app.processEvents(); time.sleep(0.02)
d.grab().save(r"I:\DSHwork\MultiSpeaker\build\settings_dialog.png")
print("saved", d.size().width(), "x", d.size().height())
