"""Reusable PySide6 widget primitives."""
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QWidget,
    QScrollArea, QPushButton, QSlider, QLineEdit, QCheckBox,
    QComboBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from . import style as T


# MARK: typography --------------------------------------------------------

class H1(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "h1")


class H2(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "h2")


class Hint(QLabel):
    def __init__(self, text: str, parent=None, wrap: int = 0):
        super().__init__(text, parent)
        self.setProperty("class", "muted")
        if wrap:
            self.setWordWrap(True)
            self.setMaximumWidth(wrap)


class Warning(QLabel):
    def __init__(self, text: str, parent=None, wrap: int = 0):
        super().__init__(text, parent)
        self.setProperty("class", "warning")
        if wrap:
            self.setWordWrap(True)
            self.setMaximumWidth(wrap)


# MARK: surfaces ----------------------------------------------------------

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(T.PAD_SM, T.PAD_SM, T.PAD_SM, T.PAD_SM)
        self._layout.setSpacing(T.PAD_XS)

    def card_layout(self) -> QVBoxLayout:
        return self._layout


# MARK: buttons -----------------------------------------------------------

class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "primary")


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)


class DangerButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "danger")


class GhostButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("background: transparent;")


# MARK: nav button --------------------------------------------------------

class NavButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "nav")
        self.setProperty("active", "false")
        self.setCursor(Qt.PointingHandCursor)

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


# MARK: form layout -------------------------------------------------------

class FieldRow(QWidget):
    """A row with a label column and a control area."""
    LABEL_W = 320

    def __init__(self, label: str, hint: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(T.PAD_MD)

        label_col = QVBoxLayout()
        label_col.setSpacing(2)
        lbl = QLabel(label)
        lbl.setFixedWidth(self.LABEL_W)
        label_col.addWidget(lbl)
        if hint:
            h = Hint(hint, wrap=self.LABEL_W)
            label_col.addWidget(h)
        layout.addLayout(label_col)

        self.controls = QWidget()
        self.controls_layout = QHBoxLayout(self.controls)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(T.PAD_SM)
        layout.addWidget(self.controls, 1)


# MARK: pill / chip -------------------------------------------------------

class Pill(QFrame):
    def __init__(self, label: str = "", prefix: str = "", dot_color: str = None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "pill")
        self.setFixedHeight(26)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.setSpacing(6)

        self._dot = None
        if dot_color:
            self._dot = QLabel(T.ICON["dot"])
            self._dot.setStyleSheet(f"color: {dot_color}; font-size: 10px;")
            layout.addWidget(self._dot)

        if prefix:
            p = QLabel(prefix)
            p.setStyleSheet(f"color: {T.TEXT_FAINT}; font-size: {T.FS_TINY}px; font-weight: bold;")
            layout.addWidget(p)

        self._label = QLabel(label)
        self._label.setStyleSheet(f"font-size: {T.FS_SMALL}px; font-weight: bold;")
        layout.addWidget(self._label)

    def set_label(self, text: str):
        self._label.setText(text)

    def set_dot_color(self, color: str):
        if self._dot:
            self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")

    def set(self, label: str = None, dot_color: str = None):
        if label is not None:
            self.set_label(label)
        if dot_color is not None:
            self.set_dot_color(dot_color)


# MARK: scroll area -------------------------------------------------------

class ScrollArea(QScrollArea):
    """Vertical scroll area with smooth scrolling."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(T.PAD_MD)
        self._layout.addStretch()
        self.setWidget(self._content)

    def content_layout(self) -> QVBoxLayout:
        return self._layout

    def add_widget(self, w: QWidget):
        self._layout.insertWidget(self._layout.count() - 1, w)

    def clear_content(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# MARK: page header -------------------------------------------------------

class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, T.PAD_MD)
        layout.setSpacing(T.PAD_XS)
        layout.addWidget(H1(title))
        if subtitle:
            layout.addWidget(Hint(subtitle))


# MARK: float slider -------------------------------------------------------

class FloatSlider(QWidget):
    """Slider + entry that emits float values."""
    valueChanged = Signal(float)

    def __init__(self, lo: float = 0, hi: float = 300, steps: int = 300, *,
                 suffix: str = "%", decimals: int = 0, parent=None):
        super().__init__(parent)
        self._lo = lo
        self._hi = hi
        self._steps = steps
        self._suffix = suffix
        self._decimals = decimals
        self._suppress = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.PAD_SM)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, steps)
        self._slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self._slider, 1)

        self._entry = QLineEdit()
        self._entry.setFixedWidth(70)
        self._entry.setAlignment(Qt.AlignCenter)
        self._entry.returnPressed.connect(self._on_entry)
        layout.addWidget(self._entry)

    def _format(self, value: float) -> str:
        return f"{value:.{self._decimals}f}{self._suffix}"

    def _on_slider(self, tick: int):
        if self._suppress:
            return
        value = self._lo + (self._hi - self._lo) * tick / self._steps
        self._entry.setText(self._format(value))
        self.valueChanged.emit(value)

    def _on_entry(self):
        text = self._entry.text()
        if self._suffix:
            text = text.replace(self._suffix, "")
        text = text.strip()
        try:
            value = float(text)
            value = max(self._lo, min(self._hi, value))
            tick = int((value - self._lo) / (self._hi - self._lo) * self._steps)
            self._suppress = True
            self._slider.setValue(tick)
            self._suppress = False
            self._entry.setText(self._format(value))
            self.valueChanged.emit(value)
        except ValueError:
            pass

    def set_value(self, value: float):
        value = max(self._lo, min(self._hi, value))
        tick = int((value - self._lo) / (self._hi - self._lo) * self._steps)
        self._suppress = True
        self._slider.setValue(tick)
        self._suppress = False
        self._entry.setText(self._format(value))

    def value(self) -> float:
        tick = self._slider.value()
        return self._lo + (self._hi - self._lo) * tick / self._steps


# MARK: toggle switch -------------------------------------------------------

class ToggleSwitch(QWidget):
    """Custom painted toggle switch with clear ON/OFF distinction."""
    toggled = Signal(bool)

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout
        from PySide6.QtCore import QSize
        self._checked = False
        self._text = text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._track = _ToggleTrack(self)
        self._track.clicked.connect(self._toggle)
        layout.addWidget(self._track)

        if text:
            lbl = QLabel(text)
            layout.addWidget(lbl)
        layout.addStretch()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._track.update()
            self.toggled.emit(checked)

    def blockSignals(self, block: bool):
        super().blockSignals(block)
        self._track.blockSignals(block)

    def _toggle(self):
        self._checked = not self._checked
        self._track.update()
        if not self.signalsBlocked():
            self.toggled.emit(self._checked)


class _ToggleTrack(QWidget):
    """The painted track+knob of the toggle switch."""
    clicked = Signal()

    def __init__(self, parent: ToggleSwitch):
        super().__init__(parent)
        self._parent_switch = parent
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QPen
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        checked = self._parent_switch.isChecked()
        w, h = self.width(), self.height()
        radius = h / 2

        # Track
        if checked:
            track_color = QColor(T.ACCENT)
        else:
            track_color = QColor(T.BG_HOVER)
        p.setPen(Qt.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # Border for OFF state
        if not checked:
            p.setPen(QPen(QColor(T.BG_ACTIVE), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius - 1, radius - 1)

        # Knob
        knob_r = h - 6
        if checked:
            knob_x = w - knob_r - 3
            knob_color = QColor("#ffffff")
        else:
            knob_x = 3
            knob_color = QColor(T.TEXT_MUTED)
        p.setPen(Qt.NoPen)
        p.setBrush(knob_color)
        p.drawEllipse(QRectF(knob_x, 3, knob_r, knob_r))

        # ON/OFF text
        p.setPen(QColor("#ffffff" if checked else T.TEXT_FAINT))
        from PySide6.QtGui import QFont
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        if checked:
            p.drawText(QRectF(4, 0, w / 2, h), Qt.AlignCenter, "ON")
        else:
            p.drawText(QRectF(w / 2, 0, w / 2 - 2, h), Qt.AlignCenter, "OFF")

        p.end()

    def mousePressEvent(self, event):
        self.clicked.emit()


# MARK: collapsible section ------------------------------------------------

class CollapsibleSection(QWidget):
    """Accordion-style section: click header to expand/collapse content."""

    def __init__(self, title: str, expanded: bool = False, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self._header = QPushButton()
        self._header.setProperty("class", "accordion-header")
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # Content container
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(T.GAP_SM, T.GAP_SM, T.GAP_SM, T.GAP_MD)
        self._content_layout.setSpacing(T.GAP_XS)
        layout.addWidget(self._content)

        self._title = title
        self._update_header()
        self._content.setVisible(expanded)

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_header()

    def _update_header(self):
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._header.setText(f" {arrow}  {self._title}")

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def add_widget(self, w: QWidget):
        self._content_layout.addWidget(w)

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self._content.setVisible(expanded)
        self._update_header()


# MARK: trigger gauge (live monitor) ----------------------------------------

class TriggerGauge(QWidget):
    """Horizontal bar showing trigger force level: label + bar + value."""

    def __init__(self, label: str = "L2", parent=None):
        super().__init__(parent)
        self._value = 0
        self._max = 255

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(T.GAP_SM)

        self._label = QLabel(label)
        self._label.setFixedWidth(28)
        self._label.setProperty("class", "h2")
        layout.addWidget(self._label)

        self._bar = _GaugeBar(self)
        layout.addWidget(self._bar, 1)

        self._val_label = QLabel("0")
        self._val_label.setFixedWidth(36)
        self._val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._val_label.setProperty("class", "muted")
        layout.addWidget(self._val_label)

    def set_value(self, value: int):
        self._value = max(0, min(self._max, int(value)))
        self._val_label.setText(str(self._value))
        self._bar.update()

    def value(self) -> int:
        return self._value


class _GaugeBar(QWidget):
    """Painted bar for TriggerGauge."""
    def __init__(self, gauge: TriggerGauge):
        super().__init__(gauge)
        self._gauge = gauge
        self.setFixedHeight(16)
        self.setMinimumWidth(80)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2

        # Background track
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.SURFACE_INPUT))
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # Fill bar
        ratio = self._gauge._value / max(1, self._gauge._max)
        fill_w = max(0, w * ratio)
        if fill_w > 0:
            color = T.PRIMARY if ratio < 0.8 else (T.WARNING if ratio < 0.95 else T.DESTRUCTIVE)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(0, 0, fill_w, h), radius, radius)
        p.end()


# MARK: bus level (haptic monitor) ------------------------------------------

class BusLevel(QWidget):
    """Compact horizontal level indicator: name + 4-segment bar."""

    def __init__(self, label: str = "Surface", parent=None):
        super().__init__(parent)
        self._level = 0.0  # 0..1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(T.GAP_SM)

        self._label = QLabel(label)
        self._label.setFixedWidth(56)
        self._label.setProperty("class", "muted")
        layout.addWidget(self._label)

        self._segments = _SegmentBar(self)
        layout.addWidget(self._segments, 1)

    def set_level(self, level: float):
        self._level = max(0.0, min(1.0, float(level)))
        self._segments.update()


class _SegmentBar(QWidget):
    """4-segment painted bar for BusLevel."""
    SEGMENTS = 8

    def __init__(self, bus: BusLevel):
        super().__init__(bus)
        self._bus = bus
        self.setFixedHeight(10)
        self.setMinimumWidth(60)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = self.SEGMENTS
        gap = 2
        seg_w = (w - gap * (n - 1)) / n
        active = int(self._bus._level * n + 0.5)

        for i in range(n):
            x = i * (seg_w + gap)
            if i < active:
                color = T.PRIMARY if i < n * 0.7 else (T.WARNING if i < n * 0.9 else T.DESTRUCTIVE)
            else:
                color = T.SURFACE_INPUT
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, 0, seg_w, h), 2, 2)
        p.end()


# MARK: info row (live data) ------------------------------------------------

class InfoRow(QWidget):
    """Simple key: value display row for live monitor."""
    def __init__(self, label: str, value: str = "-", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(T.GAP_SM)

        lbl = QLabel(label)
        lbl.setProperty("class", "muted")
        lbl.setFixedWidth(56)
        layout.addWidget(lbl)

        self._value = QLabel(value)
        layout.addWidget(self._value, 1)

    def set_value(self, text: str):
        self._value.setText(text)

