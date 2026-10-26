"""MultiSpeaker main window."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..autostart import is_enabled as autostart_enabled
from ..autostart import set_enabled as autostart_set_enabled
from ..decode import AUDIO_EXTS, DecodedTrack, decode_track
from ..devices import AudioDevice, describe, list_output_devices
from ..engine import MultiSpeakerEngine
from ..live import LiveSource, find_cable_capture
from ..resample import backend_name
from ..testtone import make_stereo_test
from . import theme, widgets
from .widgets import (
    CoverArt,
    DeviceCard,
    ElidedLabel,
    LevelMeter,
    StatusDot,
    WaveSlider,
    make_icon_button,
)


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def resource_path(name: str) -> str:
    base = Path(getattr(__import__("sys"), "_MEIPASS", Path(__file__).resolve().parents[2]))
    for candidate in (base / "app" / "resources" / name, base / "resources" / name, base / name):
        if candidate.exists():
            return str(candidate)
    return ""


class Loader(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self) -> None:  # noqa: D401
        try:
            track = decode_track(self.path)
            self.loaded.emit(track)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(self, channel_mode: str, autostart: bool = False,
                 close_action: str = "tray", mono: str = "auto", parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(460)
        self.setModal(True)
        self.mono_mode = mono if mono in ("auto", "mono", "stereo") else "auto"
        self.channel_mode = channel_mode
        self.autostart = autostart
        self.close_action = "exit" if close_action == "exit" else "tray"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)

        title = QLabel("多声道设备分配")
        title.setObjectName("SectionTitle")
        lay.addWidget(title)
        hint = QLabel("对于 5.1 / 7.1 等环绕声设备，立体声如何分配：")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.rb_all = QRadioButton("全声道：前后左右每对扬声器都还原独立的 L / R")
        self.rb_front = QRadioButton("仅前置：只使用前置左右声道，其余静音")
        (self.rb_all if channel_mode != "front" else self.rb_front).setChecked(True)
        lay.addWidget(self.rb_all)
        lay.addWidget(self.rb_front)

        note = QLabel(
            "说明：立体声 L / R 始终独立传输，不会混成单声道。\n"
            "若觉得某台设备声音偏早或偏晚，可在设备卡片上调整「延迟补偿」。"
        )
        note.setObjectName("Faint")
        note.setWordWrap(True)
        lay.addWidget(note)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {theme.BORDER_SOFT};")
        lay.addWidget(line)

        out_title = QLabel("输出声道")
        out_title.setObjectName("SectionTitle")
        lay.addWidget(out_title)
        self.rb_mono_auto = QRadioButton("自动（默认）：单声道源合并；双声道 / 5.1 / 7.1 按原声道还原")
        self.rb_mono_mono = QRadioButton("总是单声道：L + R 取平均，送往所有声道")
        self.rb_mono_stereo = QRadioButton("总是立体声：左 / 右声道独立")
        { "auto": self.rb_mono_auto, "mono": self.rb_mono_mono,
          "stereo": self.rb_mono_stereo }.get(mono, self.rb_mono_auto).setChecked(True)
        lay.addWidget(self.rb_mono_auto)
        lay.addWidget(self.rb_mono_mono)
        lay.addWidget(self.rb_mono_stereo)
        mono_hint = QLabel(
            "「自动」：单声道音源铺满所有扬声器；双声道音乐保持 L/R；"
            "5.1 / 7.1 按对应声道还原（设备支持时）。"
        )
        mono_hint.setObjectName("Faint")
        mono_hint.setWordWrap(True)
        lay.addWidget(mono_hint)

        line2 = QFrame()
        line2.setFixedHeight(1)
        line2.setStyleSheet(f"background: {theme.BORDER_SOFT};")
        lay.addWidget(line2)

        start_title = QLabel("启动与关闭")
        start_title.setObjectName("SectionTitle")
        lay.addWidget(start_title)

        self.cb_autostart = QCheckBox("开机自动启动（登录后最小化到托盘）")
        self.cb_autostart.setChecked(bool(autostart))
        lay.addWidget(self.cb_autostart)

        close_hint = QLabel("点击窗口右上角关闭按钮时：")
        close_hint.setObjectName("Dim")
        lay.addWidget(close_hint)
        self.rb_tray = QRadioButton("最小化到托盘，音乐继续播放")
        self.rb_exit = QRadioButton("直接退出程序")
        (self.rb_tray if self.close_action == "tray" else self.rb_exit).setChecked(True)
        lay.addWidget(self.rb_tray)
        lay.addWidget(self.rb_exit)

        tray_note = QLabel("托盘图标：单击打开主界面，右键可「打开主界面」或「退出软件」。")
        tray_note.setObjectName("Faint")
        tray_note.setWordWrap(True)
        lay.addWidget(tray_note)
        lay.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        ok = QPushButton("保存")
        ok.setObjectName("Accent")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def _accept(self) -> None:
        self.channel_mode = "all" if self.rb_all.isChecked() else "front"
        self.close_action = "tray" if self.rb_tray.isChecked() else "exit"
        self.autostart = self.cb_autostart.isChecked()
        if self.rb_mono_mono.isChecked():
            self.mono_mode = "mono"
        elif self.rb_mono_stereo.isChecked():
            self.mono_mode = "stereo"
        else:
            self.mono_mode = "auto"
        self.accept()


class MainWindow(QWidget):
    def __init__(self, icon: Optional[QIcon] = None):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("MultiSpeaker · 多扬声器同步播放器")
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        self.resize(1240, 800)
        self.setMinimumSize(1040, 690)
        self.setAcceptDrops(True)

        self.engine = MultiSpeakerEngine()
        self.settings = QSettings("MultiSpeaker", "MultiSpeaker")
        self.devices: List[AudioDevice] = []
        self.by_key: Dict[str, AudioDevice] = {}
        self.cards: Dict[str, DeviceCard] = {}
        self.track: Optional[DecodedTrack] = None
        self.loader: Optional[Loader] = None
        self.playlist: List[str] = []
        self.current_index = -1
        self.repeat = False
        self.test_mode = False
        self._end_handled = False
        self._loading = False
        self._status_t = 0.0
        self._solo_key: Optional[str] = None
        self._sys_active = False
        self._sys_source = None
        self._cable = None
        self._mono_mode = "auto"
        self._quitting = False
        self._tray_hint = False
        self._close_action = str(self.settings.value("close_action", "tray"))
        self.tray = None

        self._build_ui()
        self._wire_shortcuts()
        self._restore_state()
        self._refresh_devices(first=True)
        self._detect_cable()
        self._init_tray(icon)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(16, 14, 16, 10)
        body_lay.setSpacing(14)
        body_lay.addWidget(self._build_device_panel(), 0)
        body_lay.addWidget(self._build_right_panel(), 1)
        root.addWidget(body, 1)
        root.addWidget(self._build_statusbar())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("Header")
        header.setFixedHeight(66)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(18, 0, 16, 0)
        lay.setSpacing(12)

        logo = QLabel()
        logo.setFixedSize(38, 38)
        path = resource_path("logo.png")
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        t1 = QLabel("MultiSpeaker")
        t1.setObjectName("BrandTitle")
        t2 = QLabel("多扬声器同步播放")
        t2.setObjectName("BrandSub")
        titles.addWidget(t1)
        titles.addWidget(t2)
        lay.addLayout(titles)
        lay.addStretch(1)

        self.header_dot = StatusDot()
        self.header_state = QLabel("就绪")
        self.header_state.setObjectName("Dim")
        lay.addWidget(self.header_dot)
        lay.addWidget(self.header_state)
        lay.addSpacing(8)

        self.btn_refresh = QPushButton("\uE72C")
        self.btn_refresh.setFont(theme.icon_font(12))
        self.btn_refresh.setToolTip("重新扫描音频设备")
        self.btn_refresh.setFixedSize(34, 30)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(lambda: self._refresh_devices())
        lay.addWidget(self.btn_refresh)

        self.btn_settings = QPushButton("\uE713")
        self.btn_settings.setFont(theme.icon_font(12))
        self.btn_settings.setToolTip("设置")
        self.btn_settings.setFixedSize(34, 30)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self._open_settings)
        lay.addWidget(self.btn_settings)
        return header

    def _build_device_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(474)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 12, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("输出设备")
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        self.dev_count = QLabel("0")
        self.dev_count.setObjectName("Badge")
        head.addWidget(self.dev_count)
        head.addStretch(1)
        self.btn_all = QPushButton("全选")
        self.btn_all.setObjectName("Ghost")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none = QPushButton("清空")
        self.btn_none.setObjectName("Ghost")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        head.addWidget(self.btn_all)
        head.addWidget(self.btn_none)
        lay.addLayout(head)

        sub = QLabel("勾选任意组合，声音会同步送往全部选中的扬声器")
        sub.setObjectName("Faint")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.card_host = QWidget()
        self.card_host.setObjectName("CardHost")
        self.card_host.setAutoFillBackground(True)
        pal = self.card_host.palette()
        pal.setColor(pal.ColorRole.Window, QColor(theme.PANEL))
        self.card_host.setPalette(pal)
        self.card_lay = QVBoxLayout(self.card_host)
        self.card_lay.setContentsMargins(0, 2, 4, 2)
        self.card_lay.setSpacing(8)
        self.card_lay.addStretch(1)
        self.scroll.setWidget(self.card_host)
        lay.addWidget(self.scroll, 1)

        foot = QLabel("每台设备独立音量 / 静音 / 独奏 / 延迟补偿")
        foot.setObjectName("Faint")
        lay.addWidget(foot)
        return panel

    def _build_right_panel(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(self._build_system_audio())
        lay.addWidget(self._build_player())
        lay.addWidget(self._build_playlist(), 1)
        return wrap

    def _build_system_audio(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("系统音频")
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        self.sys_dot = StatusDot()
        head.addWidget(self.sys_dot)
        self.sys_state = QLabel("未启用")
        self.sys_state.setObjectName("Dim")
        head.addWidget(self.sys_state)
        head.addStretch(1)

        self.btn_sound = QPushButton("打开声音设置")
        self.btn_sound.setObjectName("Ghost")
        self.btn_sound.clicked.connect(self._open_sound_settings)
        head.addWidget(self.btn_sound)

        self.btn_sys = QPushButton("开始转发")
        self.btn_sys.setObjectName("Accent")
        self.btn_sys.setMinimumWidth(96)
        self.btn_sys.clicked.connect(self._toggle_system_audio)
        head.addWidget(self.btn_sys)
        lay.addLayout(head)

        desc = QLabel(
            "把 Windows 默认输出设为「MultiSpeaker 组合输出」，所有程序的声音都会同步转发到左侧勾选的扬声器。"
        )
        desc.setObjectName("Faint")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.sys_meter = LevelMeter(2)
        row.addWidget(self.sys_meter, 0, Qt.AlignVCenter)
        self.sys_source = QLabel("正在检测虚拟声卡…")
        self.sys_source.setObjectName("Faint")
        row.addWidget(self.sys_source, 1)
        lay.addLayout(row)
        return card

    def _open_sound_settings(self) -> None:
        QDesktopServices.openUrl(QUrl("ms-settings:sound"))

    def _detect_cable(self) -> None:
        found = find_cable_capture()
        self._cable = found
        if found:
            self.sys_source.setText(f"输入：{found[1]} · {found[2] / 1000:.1f} kHz")
            self.sys_source.setToolTip(found[1])
            self.btn_sys.setEnabled(True)
        else:
            self.sys_source.setText("未检测到虚拟声卡（需要 VB-CABLE 或同类设备）")
            self.btn_sys.setEnabled(False)

    def _toggle_system_audio(self) -> None:
        if self._sys_active:
            self._stop_system_audio()
            return
        devices = self._selected_devices()
        if not devices:
            QMessageBox.information(self, "请选择设备", "请先在左侧勾选至少一个输出扬声器。")
            return
        self._detect_cable()
        if not self._cable:
            QMessageBox.warning(
                self,
                "没有虚拟声卡",
                "没有检测到虚拟声卡，无法把系统声音转发到多台扬声器。\n"
                "请安装 VB-CABLE（或 VoiceMeeter）后重试。",
            )
            return
        idx, name, rate = self._cable
        if self.engine.running:
            self.engine.stop(fade=False)
        source = LiveSource(idx, rate)
        errors = self.engine.start_live(devices, source, buffer_ms=80.0)
        if not self.engine.running:
            source.stop()
            self._set_status("系统音频转发启动失败：" + "；".join(errors))
            QMessageBox.warning(self, "启动失败", "\n".join(errors) or "无法打开虚拟声卡")
            return
        self._sys_active = True
        self._sys_source = source
        self._refresh_mono_ui()
        self.btn_sys.setText("停止转发")
        self.sys_dot.set_color(theme.GREEN)
        self.sys_state.setText("转发中")
        self._set_player_enabled(False)
        if errors:
            self._set_status("；".join(errors))
        else:
            self._set_status(f"系统音频转发中 · {len(devices)} 台设备")

    def _stop_system_audio(self) -> None:
        self._sys_active = False
        self._sys_source = None
        if self.engine.running:
            self.engine.stop(fade=False)
        self.btn_sys.setText("开始转发")
        self.sys_dot.set_color(theme.TEXT_FAINT)
        self.sys_state.setText("未启用")
        self.sys_meter.set_levels(0, 0)
        self._refresh_mono_ui()
        self._set_player_enabled(True)
        self._set_status("已停止系统音频转发")

    def _set_player_enabled(self, enabled: bool) -> None:
        for w in (self.btn_play, self.btn_prev, self.btn_next, self.btn_stop,
                  self.btn_repeat, self.btn_pick, self.wave):
            w.setEnabled(enabled)
        self.wave.setEnabled(enabled and self.track is not None)

    def _build_player(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(14)
        self.cover = CoverArt(78)
        top.addWidget(self.cover)
        info = QVBoxLayout()
        info.setSpacing(3)
        self.title = ElidedLabel("未载入音频")
        self.title.setStyleSheet(f"font-size: 15pt; font-weight: 600; color: {theme.TEXT};")
        self.subtitle = ElidedLabel("拖入音频文件，或点击下方「选择文件」")
        self.subtitle.setStyleSheet(f"font-size: 9pt; color: {theme.TEXT_DIM};")
        info.addWidget(self.title)
        info.addWidget(self.subtitle)
        badges = QHBoxLayout()
        badges.setSpacing(6)
        self.badge_fmt = QLabel("")
        self.badge_fmt.setObjectName("BadgeDim")
        self.badge_sync = QLabel("")
        self.badge_sync.setObjectName("Badge")
        badges.addWidget(self.badge_fmt)
        badges.addWidget(self.badge_sync)
        self.btn_mono = QPushButton("自动")
        self.btn_mono.setObjectName("BadgeBtn")
        self.btn_mono.setCursor(Qt.PointingHandCursor)
        self.btn_mono.setToolTip("点击选择：自动 / 总是单声道 / 总是立体声")
        self.btn_mono.clicked.connect(self._show_mono_menu)
        badges.addWidget(self.btn_mono)
        badges.addStretch(1)
        info.addLayout(badges)
        top.addLayout(info, 1)

        self.btn_pick = QPushButton("选择文件")
        self.btn_pick.setObjectName("Accent")
        self.btn_pick.clicked.connect(self._choose_files)
        top.addWidget(self.btn_pick, 0, Qt.AlignTop)
        lay.addLayout(top)

        self.wave = WaveSlider()
        self.wave.seekRequested.connect(self._seek_ratio)
        lay.addWidget(self.wave)

        times = QHBoxLayout()
        self.time_now = QLabel("00:00")
        self.time_now.setObjectName("Faint")
        self.time_total = QLabel("00:00")
        self.time_total.setObjectName("Faint")
        times.addWidget(self.time_now)
        times.addStretch(1)
        times.addWidget(self.time_total)
        lay.addLayout(times)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.btn_prev = make_icon_button(widgets.G_PREV, 34, "上一首")
        self.btn_stop = make_icon_button(widgets.G_STOP, 34, "停止")
        self.btn_next = make_icon_button(widgets.G_NEXT, 34, "下一首")
        self.btn_play = QToolButton()
        self.btn_play.setObjectName("PlayMain")
        self.btn_play.setText(widgets.G_PLAY)
        self.btn_play.setFont(theme.icon_font(20))
        self.btn_play.setFixedSize(52, 52)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setToolTip("播放 / 暂停 (空格)")
        self.btn_repeat = make_icon_button(widgets.G_REPEAT, 34, "单曲循环")
        self.btn_repeat.setCheckable(True)

        self.btn_prev.clicked.connect(lambda: self._step_track(-1))
        self.btn_next.clicked.connect(lambda: self._step_track(1))
        self.btn_stop.clicked.connect(self._stop)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_repeat.toggled.connect(self._set_repeat)

        controls.addWidget(self.btn_prev)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.btn_next)
        controls.addWidget(self.btn_repeat)
        controls.addSpacing(14)

        vol_icon = QLabel("\uE767")
        vol_icon.setFont(theme.icon_font(12))
        vol_icon.setStyleSheet(f"color: {theme.TEXT_DIM};")
        controls.addWidget(vol_icon)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(90)
        self.vol.setFixedWidth(140)
        self.vol.valueChanged.connect(self._on_master_volume)
        controls.addWidget(self.vol)
        self.vol_pct = QLabel("90%")
        self.vol_pct.setObjectName("Faint")
        self.vol_pct.setFixedWidth(36)
        controls.addWidget(self.vol_pct)
        controls.addStretch(1)
        self.btn_test = QPushButton("声道测试")
        self.btn_test.setToolTip("播放左右声道测试信号，检查每台设备是否独立")
        self.btn_test.clicked.connect(self._play_test)
        controls.addWidget(self.btn_test)
        lay.addLayout(controls)
        return card

    def _build_playlist(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("播放列表")
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        self.pl_count = QLabel("0 首")
        self.pl_count.setObjectName("Faint")
        head.addWidget(self.pl_count)
        head.addStretch(1)
        b_add = QPushButton("添加")
        b_add.setObjectName("Ghost")
        b_add.clicked.connect(self._choose_files)
        b_clear = QPushButton("清空")
        b_clear.setObjectName("Ghost")
        b_clear.clicked.connect(self._clear_playlist)
        head.addWidget(b_add)
        head.addWidget(b_clear)
        lay.addLayout(head)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.itemDoubleClicked.connect(self._on_item_activated)

        self.list_empty = QWidget()
        empty_lay = QVBoxLayout(self.list_empty)
        empty_lay.setContentsMargins(20, 20, 20, 20)
        empty_hint = QLabel("播放列表为空\n\n点击右上角「添加」，或把音频文件拖进窗口")
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_hint.setObjectName("Faint")
        empty_hint.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 9pt;")
        empty_lay.addWidget(empty_hint, 1)

        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.list)
        self.list_stack.addWidget(self.list_empty)
        self.list_stack.setCurrentIndex(1)
        lay.addWidget(self.list_stack, 1)

        foot = QLabel("支持 MP3 / FLAC / WAV / M4A / AAC / OGG / APE / WMA 等格式 · 可拖入窗口")
        foot.setObjectName("Faint")
        lay.addWidget(foot)
        return card

    def _build_statusbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(32)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 18, 0)
        self.status = QLabel("正在扫描音频设备…")
        self.status.setObjectName("Faint")
        lay.addWidget(self.status)
        lay.addStretch(1)
        self.status_right = QLabel("")
        self.status_right.setObjectName("Faint")
        lay.addWidget(self.status_right)
        return bar

    def _wire_shortcuts(self) -> None:
        self._shortcuts = []

        def add(seq, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(fn)
            self._shortcuts.append(sc)

        add(Qt.Key_Space, self._toggle_play)
        add("Ctrl+O", self._choose_files)
        add(Qt.Key_Left, lambda: self._nudge(-5))
        add(Qt.Key_Right, lambda: self._nudge(5))
        add(Qt.Key_Escape, self._stop)

    # -------------------------------------------------------------- devices
    def _refresh_devices(self, first: bool = False) -> None:
        selected = {k for k, c in self.cards.items() if c.is_checked()}
        if first:
            saved = self.settings.value("selected", [])
            if isinstance(saved, str):
                saved = [saved] if saved else []
            selected |= {str(s) for s in (saved or [])}
        previous = {k: c for k, c in self.cards.items()}
        try:
            devices = list_output_devices()
        except Exception as exc:
            self._set_status(f"设备扫描失败：{exc}")
            return

        self.devices = devices
        self.by_key = {d.key: d for d in devices}

        for key in list(self.cards.keys()):
            if key not in self.by_key:
                card = self.cards.pop(key)
                self.card_lay.removeWidget(card)
                card.deleteLater()
                selected.discard(key)

        for dev in devices:
            card = self.cards.get(dev.key)
            if card is None:
                card = DeviceCard(dev, checked=False)
                card.toggled.connect(self._on_card_toggled)
                card.volumeChanged.connect(self._on_card_volume)
                card.muteToggled.connect(self._on_card_mute)
                card.soloToggled.connect(self._on_card_solo)
                card.delayChanged.connect(self._on_card_delay)
                self.card_lay.insertWidget(self.card_lay.count() - 1, card)
                self.cards[dev.key] = card
                self._apply_saved_card(card)
                if dev.key in selected:
                    card.set_checked(True)
                elif first and not selected and dev.is_default:
                    card.set_checked(True)
                    selected.add(dev.key)
            else:
                card.set_meta(dev)

        self.dev_count.setText(str(len(devices)))
        if self.engine.running:
            wanted = [self.by_key[k] for k in selected if k in self.by_key]
            errors = self.engine.set_devices(wanted)
            for msg in errors:
                self._set_status(msg)
        self._set_status(
            f"已发现 {len(devices)} 个输出设备" + ("，勾选后开始同步播放" if devices else "，未找到可用扬声器")
        )
        self._refresh_play_state()

    def _apply_saved_card(self, card: DeviceCard) -> None:
        key = card.key
        gain = float(self.settings.value(f"gain/{key}", 1.0))
        delay = int(self.settings.value(f"delay/{key}", 0))
        muted = str(self.settings.value(f"mute/{key}", "false")).lower() == "true"
        card.set_gain_ui(gain)
        card.set_delay_ui(delay)
        card.set_muted_ui(muted)

    def _selected_devices(self) -> List[AudioDevice]:
        out = []
        for key, card in self.cards.items():
            if card.is_checked() and key in self.by_key:
                out.append(self.by_key[key])
        return out

    def _set_all(self, value: bool) -> None:
        for card in self.cards.values():
            if card.is_checked() != value:
                card.set_checked(value)
                self._on_card_toggled(card.key, value)

    def _on_card_toggled(self, key: str, checked: bool) -> None:
        card = self.cards.get(key)
        if card is None:
            return
        dev = self.by_key.get(key)
        if checked and dev is not None and self.engine.running:
            err = self.engine.add_device(dev)
            if err:
                card.set_checked(False)
                card.set_error(err)
                self._set_status(f"{dev.short} 无法打开：{err}")
                return
            card.set_error("")
            self.engine.set_gain(key, card.volume.value() / 100.0)
            self.engine.set_muted(key, card.btn_mute.isChecked())
            self.engine.set_delay(key, card.delay.value())
        elif not checked:
            self.engine.remove_device(key)
            card.set_error("")
            if self._solo_key == key:
                self._solo_key = None
                self.engine.set_solo(None)
                card.set_solo_ui(False)
        self._refresh_play_state()

    def _on_card_volume(self, key: str, gain: float) -> None:
        self.engine.set_gain(key, gain)

    def _on_card_mute(self, key: str, muted: bool) -> None:
        self.engine.set_muted(key, muted)
        self.settings.setValue(f"mute/{key}", "true" if muted else "false")

    def _on_card_delay(self, key: str, ms: int) -> None:
        self.engine.set_delay(key, ms)
        self.settings.setValue(f"delay/{key}", ms)

    def _on_card_solo(self, key: str, solo: bool) -> None:
        if solo:
            self._solo_key = key
            self.engine.set_solo(key)
            for other, card in self.cards.items():
                if other != key:
                    card.set_solo_ui(False)
        else:
            if self._solo_key == key:
                self._solo_key = None
                self.engine.set_solo(None)

    # ---------------------------------------------------------------- files
    def _choose_files(self) -> None:
        start_dir = str(self.settings.value("last_dir", str(Path.home())))
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择音频文件",
            start_dir,
            "音频文件 (*.mp3 *.flac *.wav *.m4a *.aac *.ogg *.opus *.wma *.aiff *.ape *.mp4 *.mkv *.webm);;所有文件 (*.*)",
        )
        if files:
            self.settings.setValue("last_dir", str(Path(files[0]).parent))
            self._add_files(files)

    def _add_files(self, paths: List[str], autoplay: bool = True) -> None:
        added = 0
        for p in paths:
            p = str(Path(p))
            if not Path(p).exists():
                continue
            if p in self.playlist:
                continue
            self.playlist.append(p)
            item = QListWidgetItem(self._item_text(len(self.playlist) - 1, p))
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            self.list.addItem(item)
            added += 1
        self.pl_count.setText(f"{len(self.playlist)} 首")
        self.list_stack.setCurrentIndex(0 if self.playlist else 1)
        if added and autoplay and not self.engine.running:
            self._play_index(0)

    def _item_text(self, index: int, path: str) -> str:
        name = Path(path).stem
        return f"{index + 1:02d}    {name}"

    def _clear_playlist(self) -> None:
        self.playlist.clear()
        self.list.clear()
        self.pl_count.setText("0 首")
        self.current_index = -1
        self.list_stack.setCurrentIndex(1)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path in self.playlist:
            self._play_index(self.playlist.index(path))

    def _play_index(self, index: int) -> None:
        if not (0 <= index < len(self.playlist)):
            return
        if self._sys_active:
            self._stop_system_audio()
        self.current_index = index
        self.test_mode = False
        self._end_handled = False
        if 0 <= index < self.list.count():
            self.list.setCurrentRow(index)
            self.list.scrollToItem(self.list.item(index))
        self._load_path(self.playlist[index], autoplay=True)

    def _step_track(self, delta: int) -> None:
        if not self.playlist:
            return
        idx = self.current_index + delta
        if idx < 0:
            idx = len(self.playlist) - 1
        if idx >= len(self.playlist):
            idx = 0
        self._play_index(idx)

    def _load_path(self, path: str, autoplay: bool = True) -> None:
        if self._loading:
            return
        if self.engine.running:
            self.engine.stop(fade=True)
        self._loading = True
        self._set_loading_ui(True, Path(path).name)
        self.loader = Loader(path, self)
        self.loader.loaded.connect(lambda t: self._on_loaded(t, autoplay))
        self.loader.failed.connect(self._on_load_failed)
        self.loader.start()

    def _set_loading_ui(self, loading: bool, name: str = "") -> None:
        if loading:
            self.title.setText("正在载入…")
            self.subtitle.setText(name)
            self.btn_play.setEnabled(False)
        else:
            self.btn_play.setEnabled(True)

    def _on_loaded(self, track: DecodedTrack, autoplay: bool) -> None:
        self._loading = False
        self._set_loading_ui(False)
        self.track = track
        self.engine.set_track(track)
        self._refresh_mono_ui()
        self.title.setText(track.title)
        parts = []
        if track.artist:
            parts.append(track.artist)
        if track.album:
            parts.append(track.album)
        self.subtitle.setText(" · ".join(parts) if parts else Path(track.path).name)
        self.badge_fmt.setText(f"{track.rate / 1000:.1f} kHz · {'单声道' if self.engine.effective_mono() else '立体声'}")
        self.badge_sync.setText("")
        self.wave.set_peaks(track.peaks)
        self.wave.set_progress(0.0)
        self.time_total.setText(fmt_time(track.duration))
        self.time_now.setText("00:00")
        self._end_handled = False
        self._refresh_mono_ui()
        self._update_play_icon()
        if autoplay:
            self._start_playback()

    def _on_load_failed(self, message: str) -> None:
        self._loading = False
        self._set_loading_ui(False)
        self._set_status(f"载入失败：{message}")
        QMessageBox.warning(self, "无法播放", message)

    # ------------------------------------------------------------- playback
    def _toggle_play(self) -> None:
        focus = QApplication.focusWidget()
        if isinstance(focus, (QSpinBox, QLineEdit)):
            return
        if self._sys_active:
            self._stop_system_audio()
            return
        if self.track is None:
            if self.playlist:
                self._play_index(max(0, self.current_index))
            else:
                self._choose_files()
            return
        if self.engine.running:
            if self.engine.paused:
                self.engine.resume()
                self._set_status("继续播放")
            else:
                self.engine.pause()
                self._set_status("已暂停")
        else:
            self._start_playback()
        self._update_play_icon()

    def _start_playback(self) -> None:
        if self._sys_active:
            self._stop_system_audio()
        devices = self._selected_devices()
        if not devices:
            QMessageBox.information(self, "请选择设备", "请先在左侧勾选至少一个输出设备。")
            return
        if self.track is not None and self.engine.track is not self.track:
            self.engine.set_track(self.track)
        for card in self.cards.values():
            card.set_error("")
        errors = self.engine.start(devices)
        for msg in errors:
            for key, dev in self.by_key.items():
                if msg.startswith(dev.short) and key in self.cards:
                    self.cards[key].set_error(msg.split(": ", 1)[-1])
        if not self.engine.running:
            self._set_status("无法开始播放")
            self._update_play_icon()
            return
        self.engine.set_master_gain(self.vol.value() / 100.0)
        self.engine.set_channel_mode(str(self.settings.value("channel_mode", "all")))
        for key, card in self.cards.items():
            if key in self.engine.workers:
                self.engine.set_gain(key, card.volume.value() / 100.0)
                self.engine.set_muted(key, card.btn_mute.isChecked())
                self.engine.set_delay(key, card.delay.value())
        if self._solo_key:
            self.engine.set_solo(self._solo_key)
        self._end_handled = False
        self._set_status(f"正在同步播放 · {len(devices)} 台设备")
        self._update_play_icon()

    def _stop(self) -> None:
        if self.engine.running:
            self.engine.stop()
        self.wave.set_progress(0.0)
        self.time_now.setText("00:00")
        self._set_status("已停止")
        self._update_play_icon()
        for card in self.cards.values():
            card.set_levels(0, 0)
            card.set_playing(False)

    def _nudge(self, seconds: int) -> None:
        if self.track is None:
            return
        self.engine.seek(max(0.0, self.engine.position() + seconds))

    def _seek_ratio(self, ratio: float) -> None:
        if self.track is None:
            return
        self.engine.seek(ratio * self.track.duration)
        self.wave.set_progress(ratio)
        self.time_now.setText(fmt_time(ratio * self.track.duration))
        self._end_handled = False

    def _set_repeat(self, value: bool) -> None:
        self.repeat = bool(value)

    def _on_master_volume(self, value: int) -> None:
        self.vol_pct.setText(f"{value}%")
        self.engine.set_master_gain(value / 100.0)
        self.settings.setValue("master_volume", value)

    # ------------------------------------------------------------------- mono
    def _show_mono_menu(self) -> None:
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        options = (
            ("auto", "自动：2 声道及以下合并，多声道保持原样"),
            ("mono", "总是单声道：L + R 取平均"),
            ("stereo", "总是立体声：左 / 右声道独立"),
        )
        for mode, label in options:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self._mono_mode == mode)
            act.triggered.connect(lambda _=False, m=mode: self._set_mono_mode(m))
            group.addAction(act)
        menu.exec(self.btn_mono.mapToGlobal(self.btn_mono.rect().bottomLeft()))

    def _set_mono_mode(self, mode: str, save: bool = True, announce: bool = True) -> None:
        self._mono_mode = mode if mode in ("auto", "mono", "stereo") else "auto"
        self.engine.set_mono_mode(self._mono_mode)
        if save:
            self.settings.setValue("mono_mode", self._mono_mode)
        self._refresh_mono_ui()
        if announce:
            self._set_status(
                {
                    "auto": "声道模式：自动（单声道源合并，双声道及以上还原）",
                    "mono": "声道模式：总是单声道（L + R 取平均）",
                    "stereo": "声道模式：总是立体声（L/R 独立）",
                }[self._mono_mode]
            )

    def _refresh_mono_ui(self) -> None:
        effective = bool(self.engine.effective_mono())
        if self._mono_mode == "auto":
            if effective:
                text = "自动 · 单声道"
            elif self.engine.source_channels <= 2:
                text = "自动 · 立体声"
            else:
                text = f"自动 · {self.engine.source_layout or str(self.engine.source_channels) + 'ch'}"
        elif self._mono_mode == "mono":
            text = "单声道"
        else:
            text = "立体声"
        self.btn_mono.setText(text)
        want = "true" if effective else "false"
        if self.btn_mono.property("mono") != want:
            self.btn_mono.setProperty("mono", want)
            self.btn_mono.style().unpolish(self.btn_mono)
            self.btn_mono.style().polish(self.btn_mono)
        labels = {"auto": "自动", "mono": "总是单声道", "stereo": "总是立体声"}
        self.btn_mono.setToolTip(
            f"当前输出：{'单声道（L+R 合并）' if effective else '立体声 / 原声道'}\n"
            f"音源：{self.engine.source_channels} 声道 · 模式：{labels[self._mono_mode]}\n"
            "点击可切换：自动 / 总是单声道 / 总是立体声"
        )
        if self.track is not None:
            if effective:
                kind = "单声道"
            elif self.engine.source_channels <= 2:
                kind = "立体声"
            else:
                kind = self.engine.source_layout or f"{self.engine.source_channels}ch"
            self.badge_fmt.setText(f"{self.track.rate / 1000:.1f} kHz · {kind}")

    def _play_test(self) -> None:
        if self._sys_active:
            self._stop_system_audio()
        self.engine.stop(fade=False)
        track = make_stereo_test(48000)
        self.track = track
        self.test_mode = True
        self.current_index = -1
        self.engine.set_track(track)
        self._refresh_mono_ui()
        self.title.setText(track.title)
        self.subtitle.setText(track.artist)
        self.badge_fmt.setText(f"48.0 kHz · {'单声道' if self.engine.effective_mono() else '立体声'}")
        self.wave.set_peaks(track.peaks)
        self.wave.set_progress(0.0)
        self.time_total.setText(fmt_time(track.duration))
        self.time_now.setText("00:00")
        self._end_handled = False
        self._start_playback()
        self._set_status("声道测试：先左声道，再右声道，最后双声道同时")

    def _update_play_icon(self) -> None:
        if self.engine.running and not self.engine.paused:
            self.btn_play.setText(widgets.G_PAUSE)
            self.cover.set_state(self.track is not None, True)
        else:
            self.btn_play.setText(widgets.G_PLAY)
            self.cover.set_state(self.track is not None, False)

    # ------------------------------------------------------------------ tick
    def _tick(self) -> None:
        running = self.engine.running
        if self._sys_active:
            src = self.engine.live_source
            if src is not None:
                self.sys_meter.set_levels(src.peak_l, src.peak_r)
        if running and self.track is not None and not self._sys_active:
            pos = self.engine.position()
            dur = self.track.duration or 1.0
            if not self.engine.paused:
                self.wave.set_progress(pos / dur)
                self.time_now.setText(fmt_time(pos))
        if not running:
            for card in self.cards.values():
                card.set_levels(0, 0)

        peaks = self.engine.peaks() if running else {}
        for key, card in self.cards.items():
            if key in peaks:
                l, r, ch = peaks[key]
                card.set_levels(l, r)
                card.set_playing(running and not self.engine.paused and card.is_checked())
            else:
                card.set_levels(0, 0)
                card.set_playing(False)

        if running and self.track is not None and not self.engine.paused and not self._end_handled:
            if self.engine.position() >= self.track.duration - 0.05:
                self._handle_end()

        now = time.time()
        if now - self._status_t > 0.4:
            self._status_t = now
            self._update_status_live()
        self._update_play_icon()

    def _handle_end(self) -> None:
        self._end_handled = True
        if self.repeat and self.track is not None:
            self.engine.seek(0.0)
            self._end_handled = False
            return
        if self.test_mode:
            self._stop()
            return
        if self.current_index + 1 < len(self.playlist):
            self._play_index(self.current_index + 1)
        else:
            self._stop()

    def _update_status_live(self) -> None:
        if self.engine.running:
            stats = self.engine.device_stats()
            n = len(stats)
            err = max((abs(s.get("err_ms", 0.0)) for s in stats.values()), default=0.0)
            xr = sum(s.get("xruns", 0) for s in stats.values())
            if self._sys_active:
                self._refresh_mono_ui()
                self.header_dot.set_color(theme.GREEN)
                self.header_state.setText("系统音频转发中")
                self.status.setText(f"系统音频转发中 · {n} 台设备" + (f" · 欠载 {xr}" if xr else ""))
                self.badge_sync.setText(f"{n} 台同步")
                src = self.engine.live_source
                if src is not None:
                    self.status_right.setText(f"系统音频 · {src.rate / 1000:.1f} kHz · {'单声道' if self.engine.effective_mono() else '立体声 L/R'}")
                else:
                    self.status_right.setText("系统音频")
                return
            if self.engine.paused:
                self.header_dot.set_color(theme.YELLOW)
                self.header_state.setText("已暂停")
                self.status.setText(f"已暂停 · {n} 台设备保持连接")
            else:
                self.header_dot.set_color(theme.GREEN)
                self.header_state.setText("同步播放中")
                self.status.setText(
                    f"正在同步 {n} 台设备 · 误差 {err:.1f} ms" + (f" · 欠载 {xr}" if xr else "")
                )
            self.badge_sync.setText(f"{n} 台同步")
            if self.track is not None:
                self.status_right.setText(f"{self.track.rate / 1000:.1f} kHz · {'单声道' if self.engine.effective_mono() else '立体声 L/R'}")
            else:
                self.status_right.setText("")
        else:
            self.header_dot.set_color(theme.TEXT_FAINT)
            self.header_state.setText("就绪")
            self.badge_sync.setText("")
            if self.track is not None:
                self.status_right.setText(f"{self.track.rate / 1000:.1f} kHz · {'单声道' if self.engine.effective_mono() else '立体声 L/R'}")
            else:
                self.status_right.setText("")

    def _refresh_play_state(self) -> None:
        self._update_play_icon()

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    # ---------------------------------------------------------------- events
    def _open_settings(self) -> None:
        dlg = SettingsDialog(
            str(self.settings.value("channel_mode", "all")),
            autostart_enabled(),
            self._close_action,
            self._mono_mode,
            self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.settings.setValue("channel_mode", dlg.channel_mode)
            self.engine.set_channel_mode(dlg.channel_mode)
            self._close_action = dlg.close_action
            self.settings.setValue("close_action", dlg.close_action)
            if dlg.mono_mode != self._mono_mode:
                self._set_mono_mode(dlg.mono_mode, save=True, announce=True)
            ok = autostart_set_enabled(dlg.autostart)
            self.settings.setValue("autostart", dlg.autostart)
            if ok != dlg.autostart:
                QMessageBox.warning(
                    self, "开机自启",
                    "无法写入开机启动项（注册表 Run 键被拒绝）。\n请以管理员身份运行或手动添加。",
                )
            self._set_status("设置已保存")

    # ------------------------------------------------------------------ tray
    def _init_tray(self, icon: Optional[QIcon]) -> None:
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            tray_icon = icon if (icon is not None and not icon.isNull()) else self.windowIcon()
            if tray_icon.isNull():
                tray_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
            self.tray = QSystemTrayIcon(tray_icon, self)
            self.tray.setToolTip("MultiSpeaker · 多扬声器同步播放器")
            menu = QMenu(self)
            act_open = menu.addAction("打开主界面")
            act_open.triggered.connect(self.show_from_tray)
            menu.addSeparator()
            act_quit = menu.addAction("退出 MultiSpeaker")
            act_quit.triggered.connect(self._quit_app)
            self._tray_menu = menu
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()
        except Exception:
            self.tray = None

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_from_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def start_hidden(self) -> None:
        if self.tray is not None:
            self.hide()

    def _quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        try:
            self._save_state()
            self.engine.shutdown()
        except Exception:
            pass
        finally:
            if self.tray is not None:
                self.tray.hide()
        QApplication.instance().quit()

    # ---------------------------------------------------------------- events
    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = url.toLocalFile()
                if os.path.isdir(p):
                    for root, _, names in os.walk(p):
                        for n in names:
                            if Path(n).suffix.lower() in AUDIO_EXTS:
                                files.append(os.path.join(root, n))
                elif Path(p).suffix.lower() in AUDIO_EXTS:
                    files.append(p)
        if files:
            self._add_files(sorted(files))
            event.acceptProposedAction()

    def closeEvent(self, event):  # noqa: N802
        if self._quitting:
            event.accept()
            return
        if self._close_action == "tray" and self.tray is not None:
            event.ignore()
            self.hide()
            if not self._tray_hint:
                self._tray_hint = True
                self.tray.showMessage(
                    "MultiSpeaker",
                    "已最小化到托盘，播放不会中断。\n单击托盘图标可重新打开，右键可退出。",
                    QSystemTrayIcon.Information,
                    3000,
                )
            return
        self._quitting = True
        try:
            self._save_state()
            self.engine.shutdown()
        except Exception:
            pass
        finally:
            if self.tray is not None:
                self.tray.hide()
        event.accept()
        QTimer.singleShot(0, QApplication.instance().quit)

    def _save_state(self) -> None:
        selected = [k for k, c in self.cards.items() if c.is_checked()]
        self.settings.setValue("selected", selected)
        for key, card in self.cards.items():
            self.settings.setValue(f"gain/{key}", card.volume.value() / 100.0)
            self.settings.setValue(f"delay/{key}", card.delay.value())
            self.settings.setValue(f"mute/{key}", "true" if card.btn_mute.isChecked() else "false")
        self.settings.setValue("master_volume", self.vol.value())
        self.settings.setValue("repeat", "true" if self.repeat else "false")
        self.settings.setValue("mono_mode", self._mono_mode)
        self.settings.setValue("playlist", self.playlist)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.sync()

    def _restore_state(self) -> None:
        geo = self.settings.value("geometry")
        if geo:
            try:
                self.restoreGeometry(geo)
            except Exception:
                pass
        vol = int(self.settings.value("master_volume", 90))
        self.vol.setValue(max(0, min(100, vol)))
        self.vol_pct.setText(f"{self.vol.value()}%")
        self.engine.set_master_gain(self.vol.value() / 100.0)
        self.engine.set_channel_mode(str(self.settings.value("channel_mode", "all")))
        self.repeat = str(self.settings.value("repeat", "false")).lower() == "true"
        self.btn_repeat.setChecked(self.repeat)
        self.wave.setEnabled(True)
        mode = str(self.settings.value("mono_mode", "")).lower()
        if mode not in ("auto", "mono", "stereo"):
            legacy = str(self.settings.value("mono_mix", "false")).lower() == "true"
            mode = "mono" if legacy else "auto"
        self._set_mono_mode(mode, save=False, announce=False)

        saved_pl = self.settings.value("playlist", [])
        if isinstance(saved_pl, str):
            saved_pl = [saved_pl] if saved_pl else []
        paths = [str(p) for p in (saved_pl or []) if Path(str(p)).exists()]
        if paths:
            self._add_files(paths, autoplay=False)
