"""Visual theme for MultiSpeaker (dark, high-contrast, Windows 10/11 friendly)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

BG = "#0A0E14"
BG_GRAD = "#0C121B"
HEADER = "#0B1119"
PANEL = "#10161F"
CARD = "#151D28"
CARD_HOVER = "#1A2431"
CARD_ACTIVE = "#16212F"
BORDER = "#1E2A3A"
BORDER_SOFT = "#182231"
TEXT = "#E9F0F8"
TEXT_DIM = "#8A9AB0"
TEXT_FAINT = "#5D6B7E"
ACCENT = "#4C8DFF"
ACCENT_HOVER = "#6AA0FF"
ACCENT_DARK = "#2B5DB8"
GREEN = "#37D39B"
YELLOW = "#F5C451"
RED = "#FF6B6B"
TRACK = "#223044"


def font_family() -> str:
    families = set(QFontDatabase.families())
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"):
        if name in families:
            return name
    return "Segoe UI"


def base_font(size: float = 9.5, weight: int = QFont.Normal) -> QFont:
    f = QFont(font_family())
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def icon_font(size: int = 12) -> QFont:
    f = QFont("Segoe MDL2 Assets")
    f.setPixelSize(size)
    return f


def build_qss() -> str:
    fam = font_family()
    return f"""
* {{
    font-family: "{fam}";
    outline: none;
}}
QWidget {{
    color: {TEXT};
    font-size: 9.5pt;
}}
QMainWindow, #Root {{
    background: {BG};
}}
#Header {{
    background: {HEADER};
    border-bottom: 1px solid {BORDER_SOFT};
}}
#StatusBar {{
    background: {HEADER};
    border-top: 1px solid {BORDER_SOFT};
}}
#BrandTitle {{
    font-size: 14pt;
    font-weight: 600;
    color: {TEXT};
}}
#BrandSub {{
    font-size: 8.5pt;
    color: {TEXT_DIM};
}}
#SectionTitle {{
    font-size: 10.5pt;
    font-weight: 600;
    color: {TEXT};
}}
#Dim {{
    color: {TEXT_DIM};
}}
#Faint {{
    color: {TEXT_FAINT};
    font-size: 8.5pt;
}}
#Panel {{
    background: {PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 14px;
}}
#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
#Card[active="true"] {{
    background: {CARD_ACTIVE};
    border: 1px solid {ACCENT};
}}
#Card[error="true"] {{
    border: 1px solid {RED};
}}
#CardName {{
    font-size: 10pt;
    font-weight: 600;
    color: {TEXT};
}}
#CardMeta {{
    font-size: 8pt;
    color: {TEXT_FAINT};
}}
#Badge {{
    background: {ACCENT_DARK};
    color: #DCE9FF;
    border-radius: 6px;
    padding: 1px 6px;
    font-size: 7.5pt;
}}
#BadgeDim {{
    background: #1B2634;
    color: {TEXT_DIM};
    border-radius: 6px;
    padding: 1px 6px;
    font-size: 7.5pt;
}}
#BadgeBtn {{
    background: #1B2634;
    color: {TEXT_DIM};
    border: none;
    border-radius: 6px;
    padding: 1px 7px;
    font-size: 7.5pt;
}}
#BadgeBtn:hover {{
    background: #223044;
    color: {TEXT};
}}
#BadgeBtn:checked {{
    background: {YELLOW};
    color: #201700;
    font-weight: 600;
}}
#ErrorText {{
    color: {RED};
    font-size: 8pt;
}}
QPushButton {{
    background: #1A2431;
    border: 1px solid #26364A;
    border-radius: 8px;
    padding: 6px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: #213044;
    border: 1px solid #32465F;
}}
QPushButton:pressed {{
    background: #182433;
}}
QPushButton:disabled {{
    color: #4E5B6C;
    background: #141C27;
    border: 1px solid #1D2836;
}}
QPushButton#Accent {{
    background: {ACCENT};
    color: #061020;
    font-weight: 600;
    border: none;
    padding: 7px 16px;
}}
QPushButton#Accent:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: {TEXT_DIM};
    padding: 4px 8px;
}}
QPushButton#Ghost:hover {{
    color: {TEXT};
    background: #18222F;
}}
QPushButton#Ghost:checked {{
    color: {ACCENT};
    background: #16202E;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 4px;
    color: {TEXT_DIM};
}}
QToolButton:hover {{
    background: #1B2634;
    color: {TEXT};
}}
QToolButton:pressed {{
    background: #141D29;
}}
QToolButton:checked {{
    color: {ACCENT};
    background: #172335;
}}
QToolButton#PlayMain {{
    background: {ACCENT};
    border-radius: 26px;
    color: #061020;
}}
QToolButton#PlayMain:hover {{
    background: {ACCENT_HOVER};
}}
QToolButton#PlayMain:disabled {{
    background: #1E2A38;
    color: #4E5B6C;
}}
QToolButton#Tiny {{
    background: #1A2431;
    border: 1px solid #26364A;
    border-radius: 5px;
    color: {TEXT_DIM};
    font-size: 8pt;
    font-weight: 600;
    padding: 0px;
}}
QToolButton#Tiny:hover {{
    color: {TEXT};
    border: 1px solid #32465F;
}}
QToolButton#Tiny:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #061020;
}}
QToolButton#TinySolo:checked {{
    background: {YELLOW};
    border: 1px solid {YELLOW};
    color: #201700;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {TRACK};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    background: #E9F0F8;
    border: 1px solid #B9C8DC;
}}
QSlider::handle:horizontal:hover {{
    background: #FFFFFF;
    border: 1px solid {ACCENT};
}}
QSlider::groove:horizontal:disabled {{
    background: #1A2330;
}}
QSlider::sub-page:horizontal:disabled {{
    background: #2B3A4F;
}}
QSlider::handle:horizontal:disabled {{
    background: #3A4859;
    border: 1px solid #3A4859;
}}
QSpinBox {{
    background: #0E151E;
    border: 1px solid #26364A;
    border-radius: 6px;
    padding: 2px 4px;
    color: {TEXT};
    font-size: 8.5pt;
    selection-background-color: {ACCENT};
}}
QSpinBox:hover {{
    border: 1px solid #32465F;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 12px;
    background: #1A2431;
    border: none;
}}
QSpinBox::up-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}
QSpinBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2A3A4F;
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3A4E68;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background: transparent;
    border-radius: 8px;
    padding: 6px 8px;
    margin: 2px 2px;
    color: {TEXT_DIM};
}}
QListWidget::item:hover {{
    background: #18222F;
    color: {TEXT};
}}
QListWidget::item:selected {{
    background: #172335;
    color: {TEXT};
    border: 1px solid #2B4A78;
}}
QToolTip {{
    background: #1B2634;
    color: {TEXT};
    border: 1px solid #32465F;
    border-radius: 6px;
    padding: 5px 8px;
}}
QDialog {{
    background: {BG};
}}
QMessageBox {{
    background: {PANEL};
}}
QMenu {{
    background: #121A24;
    border: 1px solid #26364A;
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: #1C2A3B;
}}
"""
