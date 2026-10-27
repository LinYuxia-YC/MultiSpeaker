# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Custom painted widgets for MultiSpeaker."""
from __future__ import annotations

from typing import List, Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme

# Segoe MDL2 Assets glyphs ---------------------------------------------------
G_PLAY = "\uE768"
G_PAUSE = "\uE769"
G_STOP = "\uE71A"
G_PREV = "\uE892"
G_NEXT = "\uE893"
G_REFRESH = "\uE72C"
G_SETTINGS = "\uE713"
G_ADD = "\uE710"
G_DELETE = "\uE74D"
G_VOLUME = "\uE767"
G_MUTE = "\uE74F"
G_REPEAT = "\uE8EE"
G_MUSIC = "\uE8D6"
G_FOLDER = "\uE8B7"
G_CLOSE = "\uE711"
G_SPEAKER = "\uE7F5"
G_CHEVRON = "\uE70D"


def make_icon_button(glyph: str, size: int = 34, tooltip: str = "", font_px: int = 13) -> QToolButton:
    """创建统一风格的图标按钮（无焦点，避免空格误触）。"""
    btn = QToolButton()
    btn.setText(glyph)
    btn.setFont(theme.icon_font(font_px))
    btn.setFixedSize(size, size)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.setFocusPolicy(Qt.NoFocus)
    return btn


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        """单行文本标签：宽度不足时自动省略。"""
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802
        """设置完整文本（实际绘制时按宽度省略）。"""
        self._full = text or ""
        super().setText(self._full)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        """按当前宽度绘制省略后的文本。"""
        p = QPainter(self)
        p.setFont(self.font())
        fm = QFontMetrics(self.font())
        text = fm.elidedText(self._full, Qt.ElideRight, max(0, self.width() - 2))
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(self.rect(), int(self.alignment()), text)


class StatusDot(QWidget):
    def __init__(self, parent=None):
        """设备/系统状态小圆点。"""
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = QColor(theme.TEXT_FAINT)

    def set_color(self, color: str) -> None:
        """设置圆点颜色（灰=空闲，绿=播放，红=错误）。"""
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        """绘制带柔光的状态点。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        glow = QColor(self._color)
        glow.setAlpha(45)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 0, 10, 10))
        p.setBrush(self._color)
        p.drawEllipse(QRectF(2.5, 2.5, 5, 5))


class RoundCheck(QWidget):
    """Custom rounded checkbox (avoids image resources)."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        """自绘圆角复选框（不依赖图片资源）。"""
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = checked

    def isChecked(self) -> bool:  # noqa: N802
        """是否已勾选。"""
        return self._checked

    def setChecked(self, value: bool) -> None:  # noqa: N802
        """设置勾选状态（不触发信号）。"""
        if self._checked != value:
            self._checked = value
            self.update()

    def mousePressEvent(self, event):  # noqa: N802
        """点击切换勾选并发出信号。"""
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self._checked)

    def paintEvent(self, event):  # noqa: N802
        """绘制圆角框与对勾。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1.5, 1.5, 17, 17)
        if self._checked:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.ACCENT))
            p.drawRoundedRect(r, 5, 5)
            pen = QPen(QColor("#061020"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            path = QPainterPath(QPointF(5.4, 10.2))
            path.lineTo(8.4, 13.2)
            path.lineTo(14.4, 6.8)
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor("#3A4C63"), 1.6))
            p.setBrush(QColor("#0E151E"))
            p.drawRoundedRect(r, 5, 5)


class LevelMeter(QWidget):
    """Segmented stereo peak meter (left row = L, right row = R)."""

    SEGMENTS = 16

    def __init__(self, channels: int = 2, parent=None):
        """分段式 L/R 电平表。"""
        super().__init__(parent)
        self.channels = 1 if channels < 2 else 2
        self._l = 0.0
        self._r = 0.0
        self.setFixedSize(104, 12 if self.channels == 1 else 24)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_levels(self, left: float, right: float) -> None:
        """更新左右声道电平（0..1）。"""
        self._l = max(0.0, min(1.0, left))
        self._r = max(0.0, min(1.0, right))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        """绘制分段电平（绿→黄→红）。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        n = self.SEGMENTS
        gap = 2.0
        seg_w = (self.width() - gap * (n - 1)) / n
        h = 8.0 if self.channels == 2 else 9.0
        rows = [(0.0, self._l)]
        if self.channels == 2:
            rows.append((h + 8.0, self._r))
        for y, val in rows:
            lit = val ** 0.55 * n
            for i in range(n):
                x = i * (seg_w + gap)
                rect = QRectF(x, y, seg_w, h)
                frac = i / (n - 1)
                if i < int(lit):
                    if frac < 0.6:
                        color = QColor(theme.GREEN)
                    elif frac < 0.82:
                        color = QColor(theme.YELLOW)
                    else:
                        color = QColor(theme.RED)
                else:
                    color = QColor("#22303F")
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(rect, 1.5, 1.5)


class WaveSlider(QWidget):
    """Waveform progress bar with click/drag seeking."""

    seekRequested = Signal(float)

    def __init__(self, parent=None):
        """波形进度条：显示峰值并支持点击/拖动跳转。"""
        super().__init__(parent)
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self._peaks = np.zeros(0, np.float32)
        self._progress = 0.0
        self._enabled = False

    def set_peaks(self, peaks: Optional[np.ndarray]) -> None:
        """设置波形峰值数组。"""
        self._peaks = np.asarray(peaks, np.float32) if peaks is not None else np.zeros(0, np.float32)
        self._enabled = self._peaks.size > 0
        self.update()

    def set_progress(self, value: float) -> None:
        """设置播放进度（0..1）。"""
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._progress) > 0.0005:
            self._progress = value
            self.update()

    def _seek_at(self, x: float) -> None:
        """把横坐标换算为进度并发出跳转信号。"""
        if not self._enabled:
            return
        ratio = max(0.0, min(1.0, x / max(1.0, self.width())))
        self.seekRequested.emit(ratio)

    def mousePressEvent(self, event):  # noqa: N802
        """按下即跳转。"""
        if event.button() == Qt.LeftButton:
            self._seek_at(event.position().x())

    def mouseMoveEvent(self, event):  # noqa: N802
        """按住拖动连续跳转。"""
        if event.buttons() & Qt.LeftButton:
            self._seek_at(event.position().x())

    def paintEvent(self, event):  # noqa: N802
        """绘制波形（已播放部分高亮）与播放头。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mid = h / 2.0
        n = self._peaks.size

        if n == 0:
            pen = QPen(QColor("#2A3A4F"), 1.0, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(0, mid), QPointF(w, mid))
            return

        step = max(1, n // max(1, int(w)))
        bars = []
        for x in range(int(w)):
            i0 = int(x / max(1, w) * n)
            i1 = max(i0 + 1, int((x + 1) / max(1, w) * n))
            amp = float(self._peaks[i0:i1].max()) if i1 > i0 else 0.0
            bars.append(amp)

        played_x = self._progress * w
        for x, amp in enumerate(bars):
            amp = min(1.0, amp * 1.15)
            bh = max(2.0, amp * (h - 6))
            color = QColor(theme.ACCENT) if x <= played_x else QColor("#34465C")
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, mid - bh / 2, 1.0, bh), 0.5, 0.5)

        # playhead
        px = played_x
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E9F0F8"))
        p.drawRoundedRect(QRectF(px - 1.5, 2, 3, h - 4), 1.5, 1.5)


class CoverArt(QWidget):
    """Album-art placeholder with an equaliser motif."""

    def __init__(self, size: int = 78, parent=None):
        """封面占位控件（空状态显示 +，有曲目显示律动条）。"""
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._active = False
        self._empty = True

    def set_state(self, has_track: bool, playing: bool) -> None:
        """更新是否有曲目 / 是否正在播放。"""
        self._empty = not has_track
        self._active = playing
        self.update()

    def paintEvent(self, event):  # noqa: N802
        """绘制渐变封面与占位图形。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        if self._empty:
            grad.setColorAt(0.0, QColor("#16202C"))
            grad.setColorAt(1.0, QColor("#101823"))
        else:
            grad.setColorAt(0.0, QColor("#2B63B8"))
            grad.setColorAt(1.0, QColor("#7A4CD6"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(r, 14, 14)

        if self._empty:
            p.setPen(QPen(QColor("#4E5F75"), 1.4, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(4, 4, -4, -4), 11, 11)
            p.setPen(QPen(QColor("#6C8099"), 1.6, Qt.SolidLine, Qt.RoundCap))
            cx, cy = r.center().x(), r.center().y() - 2
            p.drawLine(QPointF(cx - 8, cy), QPointF(cx + 8, cy))
            p.drawLine(QPointF(cx, cy - 8), QPointF(cx, cy + 8))
        else:
            heights = [0.34, 0.6, 0.85, 0.52, 0.72]
            bw = 6.0
            gap = 5.0
            total = len(heights) * bw + (len(heights) - 1) * gap
            x0 = r.center().x() - total / 2
            base = r.center().y() + 20
            alpha = 235 if self._active else 150
            for i, hf in enumerate(heights):
                bh = hf * 44
                p.setBrush(QColor(255, 255, 255, alpha))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(x0 + i * (bw + gap), base - bh, bw, bh), 3, 3)


class DeviceCard(QFrame):
    """One output endpoint row."""

    toggled = Signal(str, bool)
    volumeChanged = Signal(str, float)
    muteToggled = Signal(str, bool)
    soloToggled = Signal(str, bool)
    delayChanged = Signal(str, int)

    def __init__(self, device, checked: bool = False, parent=None):
        """设备卡片：勾选、名称、声道信息、音量、静音/独奏、延迟、电平表。"""
        super().__init__(parent)
        self.device = device
        self.key = device.key
        self.setObjectName("Card")
        self.setProperty("active", "true" if checked else "false")
        self.setProperty("error", "false")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        # ---- row 0: checkbox + name + badges
        row0 = QHBoxLayout()
        row0.setSpacing(8)
        self.check = RoundCheck(checked)
        self.check.toggled.connect(self._on_check)
        row0.addWidget(self.check, 0, Qt.AlignVCenter)

        self.name = ElidedLabel(device.short)
        self.name.setObjectName("CardName")
        self.name.setToolTip(device.name)
        self.name.setMinimumWidth(60)
        row0.addWidget(self.name, 1)

        if device.is_default:
            b = QLabel("默认")
            b.setObjectName("Badge")
            row0.addWidget(b, 0, Qt.AlignVCenter)
        self.meta = QLabel("")
        self.meta.setObjectName("BadgeDim")
        row0.addWidget(self.meta, 0, Qt.AlignVCenter)
        root.addLayout(row0)

        # ---- row 1: meter + volume + mute/solo
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.meter = LevelMeter(device.channels)
        row1.addWidget(self.meter, 0, Qt.AlignVCenter)

        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setFixedHeight(16)
        self.volume.setToolTip("该设备音量")
        self.volume.valueChanged.connect(self._on_volume)
        row1.addWidget(self.volume, 1)

        self.pct = QLabel("100%")
        self.pct.setObjectName("Faint")
        self.pct.setFixedWidth(32)
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row1.addWidget(self.pct, 0, Qt.AlignVCenter)

        self.btn_mute = QToolButton()
        self.btn_mute.setText("M")
        self.btn_mute.setObjectName("Tiny")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedSize(22, 20)
        self.btn_mute.setToolTip("静音此设备")
        self.btn_mute.setCursor(Qt.PointingHandCursor)
        self.btn_mute.toggled.connect(lambda v: self.muteToggled.emit(self.key, v))
        row1.addWidget(self.btn_mute, 0, Qt.AlignVCenter)

        self.btn_solo = QToolButton()
        self.btn_solo.setText("S")
        self.btn_solo.setObjectName("TinySolo")
        self.btn_solo.setCheckable(True)
        self.btn_solo.setFixedSize(22, 20)
        self.btn_solo.setToolTip("独奏：只听这一台设备")
        self.btn_solo.setCursor(Qt.PointingHandCursor)
        self.btn_solo.toggled.connect(self._on_solo)
        row1.addWidget(self.btn_solo, 0, Qt.AlignVCenter)
        root.addLayout(row1)

        # ---- row 2: delay calibration
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.status = StatusDot()
        row2.addWidget(self.status, 0, Qt.AlignVCenter)
        lbl = QLabel("延迟补偿")
        lbl.setObjectName("Faint")
        row2.addWidget(lbl)
        self.delay = QSpinBox()
        self.delay.setRange(-300, 300)
        self.delay.setSingleStep(5)
        self.delay.setValue(0)
        self.delay.setSuffix(" ms")
        self.delay.setFixedWidth(74)
        self.delay.setToolTip("正值 = 这台设备相对其他设备更晚出声（用于对齐蓝牙音箱等）")
        self.delay.valueChanged.connect(lambda v: self.delayChanged.emit(self.key, v))
        row2.addWidget(self.delay)
        row2.addStretch(1)
        self.hint = ElidedLabel("")
        self.hint.setObjectName("Faint")
        self.hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.hint.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 8pt;")
        row2.addWidget(self.hint, 1)
        root.addLayout(row2)

        self.set_checked(checked)
        self.set_meta(device)

    # ------------------------------------------------------------------ state
    def set_meta(self, device) -> None:
        """刷新「声道数 · 采样率」徽章。"""
        ch = device.channels
        if ch == 1:
            ch_txt = "单声道"
        elif ch == 2:
            ch_txt = "立体声"
        else:
            ch_txt = f"{ch} 声道"
        self.meta.setText(f"{ch_txt} · {device.rate / 1000:.1f}k")

    def set_checked(self, value: bool) -> None:
        """设置勾选外观（高亮边框）。"""
        self.check.setChecked(value)
        self.setProperty("active", "true" if value else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def is_checked(self) -> bool:
        """是否已勾选。"""
        return self.check.isChecked()

    def set_error(self, message: str) -> None:
        """显示打开失败的红色提示。"""
        self.setProperty("error", "true" if message else "false")
        self.status.set_color(theme.RED if message else theme.TEXT_FAINT)
        if message:
            self.hint.setText(message)
            self.hint.setStyleSheet(f"color: {theme.RED}; font-size: 8pt;")
        else:
            self.hint.setText("")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_levels(self, left: float, right: float) -> None:
        """更新该设备的 L/R 电平表。"""
        self.meter.set_levels(left, right)

    def set_playing(self, playing: bool) -> None:
        """更新状态点（播放中为绿色）。"""
        if self.property("error") != "true":
            self.status.set_color(theme.GREEN if playing else theme.TEXT_FAINT)

    def set_gain_ui(self, gain: float) -> None:
        """不触发信号地更新音量滑杆与百分比。"""
        self.volume.blockSignals(True)
        self.volume.setValue(int(round(gain * 100)))
        self.volume.blockSignals(False)
        self.pct.setText(f"{int(round(gain * 100))}%")

    def set_sys_volume(self, on: bool) -> None:
        """标记该滑杆控制的是系统端点音量。"""
        self._sys_volume = bool(on)
        tip = ("系统音量：拖动会同步修改 Windows 中该播放设备的音量"
               if on else "软件音量（未匹配到系统端点，仅作用于本程序）")
        self.volume.setToolTip(tip)
        self.pct.setToolTip(tip)

    def set_muted_ui(self, muted: bool) -> None:
        """不触发信号地更新静音按钮。"""
        self.btn_mute.blockSignals(True)
        self.btn_mute.setChecked(muted)
        self.btn_mute.blockSignals(False)

    def set_solo_ui(self, solo: bool) -> None:
        """不触发信号地更新独奏按钮。"""
        self.btn_solo.blockSignals(True)
        self.btn_solo.setChecked(solo)
        self.btn_solo.blockSignals(False)

    def set_delay_ui(self, ms: int) -> None:
        """不触发信号地更新延迟补偿数值。"""
        self.delay.blockSignals(True)
        self.delay.setValue(int(ms))
        self.delay.blockSignals(False)

    # ------------------------------------------------------------------ slots
    def _on_check(self, value: bool) -> None:
        """勾选变化：刷新外观并通知主窗口。"""
        self.setProperty("active", "true" if value else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.toggled.emit(self.key, value)

    def _on_volume(self, value: int) -> None:
        """音量滑杆变化：更新百分比并通知主窗口。"""
        self.pct.setText(f"{value}%")
        self.volumeChanged.emit(self.key, value / 100.0)

    def _on_solo(self, value: bool) -> None:
        """独奏按钮变化。"""
        self.soloToggled.emit(self.key, value)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        """双击卡片等效于切换勾选。"""
        self.check.setChecked(not self.check.isChecked())
        self._on_check(self.check.isChecked())

