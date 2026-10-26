import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import SettingsDialog
app = QApplication([])
app.setStyle("Fusion")
app.setFont(theme.base_font(9.5))
app.setStyleSheet(theme.build_qss())
d = SettingsDialog("all", False, "tray", False)
d.show()
for _ in range(8):
    app.processEvents()
    time.sleep(0.02)
d.grab().save(str(ROOT / "build" / "settings_dialog.png"))
print("saved", d.size().width(), "x", d.size().height())
