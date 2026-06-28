"""Logs tab: level cycler, pause toggle, clear, scrolling log view."""
import logging

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from PySide6.QtGui import QTextCharFormat, QColor, QFont

from .. import style as T

def t(s: str) -> str: return s
from .. import components as W

log = logging.getLogger("dhe")

LOG_LEVELS = ("WARNING", "INFO", "DEBUG")
DEFAULT_LOG_LEVEL = "INFO"
MAX_LINES = 2000

LEVEL_COLORS = {
    "DEBUG": T.TEXT_FAINT,
    "INFO": "#d4d4d4",
    "WARNING": T.YELLOW,
    "ERROR": T.RED,
    "CRITICAL": "#ffffff",
}


class LogsTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._level_idx = LOG_LEVELS.index(DEFAULT_LOG_LEVEL)
        self._paused = False
        self._line_count = 0
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.PAD_SM)

        layout.addWidget(W.PageHeader(t("Logs"), t("Live application output.")))

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(T.PAD_SM)

        self.btn_level = W.SecondaryButton(self.level_name.lower())
        self.btn_level.clicked.connect(self.cycle_level)
        toolbar.addWidget(self.btn_level)

        self.btn_pause = W.SecondaryButton(f"{T.ICON['pause']}  {t('pause')}")
        self.btn_pause.clicked.connect(self.toggle_pause)
        toolbar.addWidget(self.btn_pause)

        clear_btn = W.SecondaryButton(f"{T.ICON['clear']}  {t('clear')}")
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Log text area
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(MAX_LINES)
        font = QFont("Consolas", 10)
        self.text.setFont(font)
        layout.addWidget(self.text, 1)

    @property
    def level_name(self) -> str:
        return LOG_LEVELS[self._level_idx]

    @property
    def level(self) -> int:
        return getattr(logging, self.level_name)

    def write(self, level: str, msg: str) -> None:
        color = LEVEL_COLORS.get(level, "#d4d4d4")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self.text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(msg + "\n", fmt)
        if not self._paused:
            self.text.ensureCursorVisible()

    def clear(self) -> None:
        self.text.clear()
        self._line_count = 0

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self.btn_pause.setText(f"{T.ICON['play']}  {t('resume')}")
        else:
            self.btn_pause.setText(f"{T.ICON['pause']}  {t('pause')}")

    def cycle_level(self) -> None:
        self._level_idx = (self._level_idx + 1) % len(LOG_LEVELS)
        self.btn_level.setText(self.level_name.lower())
        root_logger = logging.getLogger()
        root_logger.setLevel(self.level)
        log.info("Log level: %s", self.level_name)
