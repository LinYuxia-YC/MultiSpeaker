import sys, time
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import theme
from app.ui.main_window import MainWindow
from app.sysvol import SystemVolume

sv = SystemVolume()
orig = {}
for key, dev in ((k, d) for k, d in []):
    pass
app = QApplication([]); app.setStyle("Fusion"); app.setFont(theme.base_font(9.5)); app.setStyleSheet(theme.build_qss())
w = MainWindow(); w.show()
for _ in range(4): app.processEvents()

names = [d.name for d in w.devices]
for n in names:
    orig[n] = (sv.get(n), sv.get_mute(n))
print("system now:", {k: (round(v[0],2) if v[0] is not None else None, v[1]) for k,v in orig.items()})
print("cards:", [(w.by_key[k].name, c.volume.value(), c.btn_mute.isChecked()) for k,c in w.cards.items()][:4])

key = list(w.cards.keys())[0]
name = w.by_key[key].name
w.cards[key].volume.setValue(30)
app.processEvents()
print(f"set card {name} -> 30% | system: {sv.get(name):.3f} | card: {w.cards[key].volume.value()}")
w.cards[key].btn_mute.setChecked(True)
app.processEvents()
print("mute -> system mute:", sv.get_mute(name))
w.cards[key].btn_mute.setChecked(False)
app.processEvents()
print("unmute -> system mute:", sv.get_mute(name))

# restore
for n,(v,m) in orig.items():
    if v is not None: sv.set(n, v)
    if m is not None: sv.set_mute(n, m)
print("restored")
w.close()
