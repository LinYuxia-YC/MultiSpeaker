"""Layout sanity checks: clipping, overflow, tiny hit targets."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui import theme
from app.ui.main_window import MainWindow

app = QApplication([])
app.setStyle("Fusion")
app.setFont(theme.base_font(9.5))
app.setStyleSheet(theme.build_qss())
print("font family:", theme.font_family())

for size in ((1240, 800), (1040, 690), (1500, 950)):
    w = MainWindow()
    w.resize(*size)
    w.show()
    for _ in range(6):
        app.processEvents()

    print(f"\n=== window {size[0]}x{size[1]} ===")
    issues = []
    for child in w.findChildren(QWidget):
        if not child.isVisible() or child.width() <= 0:
            continue
        par = child.parentWidget()
        if par is None:
            continue
        # overflow beyond parent
        tl = child.mapTo(par, QPoint(0, 0))
        if tl.x() + child.width() > par.width() + 1 or tl.y() + child.height() > par.height() + 1:
            issues.append(f"OVERFLOW {child.__class__.__name__} {child.objectName() or ''} "
                          f"at {tl.x()},{tl.y()} {child.width()}x{child.height()} in "
                          f"{par.__class__.__name__} {par.width()}x{par.height()}")
        # clipped text
        if isinstance(child, QLabel) and child.text() and not child.wordWrap():
            need = child.fontMetrics().horizontalAdvance(child.text()) + 4
            if need > child.width() + 1 and child.text() not in ("", "M", "S"):
                issues.append(f"TEXTCLIP {child.text()[:30]!r} need~{need} has {child.width()}")
    for line in issues[:20]:
        print(" ", line)
    if not issues:
        print("  no layout issues detected")

    # key widget visibility
    for name in ("btn_play", "wave", "vol", "btn_pick", "list_stack", "status"):
        obj = getattr(w, name, None)
        if obj is not None:
            print(f"  {name:12s} {obj.width():4d}x{obj.height():3d} visible={obj.isVisible()}")
    w.close()
