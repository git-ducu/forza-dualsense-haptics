# -*- coding: utf-8 -*-
# ── UI Design Tokens ────────────────────────────────────────────────────────
#
# Single source of truth for all visual constants.

# ── Surface hierarchy ──
SURFACE_0 = "#0d1117"          # deepest background
SURFACE_1 = "#161b22"          # main content area
SURFACE_2 = "#1c2128"          # panels/cards
SURFACE_INPUT = "#0d1117"      # input fields
SURFACE_HOVER = "#272d36"      # hover state
SURFACE_ACTIVE = "#313840"     # pressed/active state

# ── Border ──
DIVIDER = "#21262d"

# ── Typography ──
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_HINT = "#6e7681"

# ── Brand ──
PRIMARY = "#3fb950"
PRIMARY_HOVER = "#2ea043"

# ── Semantic ──
POSITIVE = "#20a358"
WARNING = "#e8a62e"
DESTRUCTIVE = "#e5393d"
INFO = "#1c87f0"

# ── Spacing ──
GAP_XS = 4
GAP_SM = 8
GAP_MD = 16
GAP_LG = 24
GAP_XL = 32

# ── Layout ──
LIVE_PANEL_WIDTH = 260
TOOLBAR_HEIGHT = 40
LOG_DRAWER_HEIGHT = 120

# ── Font scale ──
FONT_XL = 18
FONT_LG = 14
FONT_MD = 12
FONT_SM = 11
FONT_XS = 10

# ── Page order ──
PAGE_ORDER = [
    ("live",    "Live"),
    ("tuning",  "Tuning"),
]

# ── Icon glyphs ──
ICON = {
    "overview":     "\U0001F3AE",
    "tuning":       "\u2699",
    "profiles":     "\U0001F4CB",
    "system":       "\U0001F5A5",
    "diagnostics":  "\U0001F527",
    "log":          "\U0001F4C4",
    "pause":        "\u23F8",
    "play":         "\u25B6",
    "clear":        "\U0001F5D1",
    "reload":       "\u21BB",
    "heart":        "\u2665",
    "dot":          "\u25CF",
    "x":            "\u2715",
    "warn":         "\u26A0",
    # legacy keys (kept for compat)
    "Dashboard":    "\U0001F3AE",
    "Profiles":     "\U0001F4CB",
    "Settings":     "\u2699",
    "System":       "\U0001F5A5",
    "Developer":    "\U0001F527",
}


def buildStylesheet() -> str:
    """Global QSS stylesheet for the application."""
    return f"""
QMainWindow, QWidget {{
    background-color: {SURFACE_1};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: {FONT_MD}px;
}}
QFrame[class="card"] {{
    background-color: {SURFACE_2};
    border-radius: 8px;
    padding: {GAP_SM}px;
}}
QFrame#live_panel {{
    background-color: {SURFACE_0};
    border-right: 1px solid {DIVIDER};
}}
QFrame#header {{
    background-color: {SURFACE_2};
    min-height: {TOOLBAR_HEIGHT}px;
    max-height: {TOOLBAR_HEIGHT}px;
}}
QPushButton {{
    background-color: {SURFACE_HOVER};
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: {FONT_MD}px;
}}
QPushButton:hover {{
    background-color: {SURFACE_ACTIVE};
}}
QPushButton[class="primary"] {{
    background-color: {PRIMARY};
    color: white;
    font-weight: bold;
}}
QPushButton[class="primary"]:hover {{
    background-color: {PRIMARY_HOVER};
}}
QPushButton[class="danger"] {{
    background-color: {DESTRUCTIVE};
    color: white;
    font-weight: bold;
}}
QPushButton[class="nav"] {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    text-align: left;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: {FONT_MD}px;
}}
QPushButton[class="nav"]:hover {{
    background-color: {SURFACE_HOVER};
}}
QPushButton[class="nav"][active="true"] {{
    background-color: {SURFACE_ACTIVE};
    color: {TEXT_PRIMARY};
}}
QLineEdit {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {SURFACE_HOVER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: {FONT_MD}px;
}}
QLineEdit:focus {{
    border-color: {PRIMARY};
}}
QSlider::groove:horizontal {{
    background: {SURFACE_INPUT};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {PRIMARY};
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {PRIMARY_HOVER};
}}
QSlider::sub-page:horizontal {{
    background: {PRIMARY};
    border-radius: 3px;
}}
QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 40px;
    height: 22px;
    border-radius: 11px;
    background-color: {SURFACE_HOVER};
    border: 2px solid {SURFACE_ACTIVE};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border: 2px solid {PRIMARY};
    image: none;
}}
QCheckBox::indicator:unchecked {{
    background-color: {SURFACE_INPUT};
    border: 2px solid {SURFACE_ACTIVE};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {SURFACE_2};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE_ACTIVE};
    min-height: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PRIMARY};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QComboBox {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {SURFACE_HOVER};
    border-radius: 4px;
    padding: 4px 8px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    selection-background-color: {PRIMARY};
}}
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QLabel[class="muted"] {{
    color: {TEXT_SECONDARY};
    font-size: {FONT_SM}px;
}}
QLabel[class="faint"] {{
    color: {TEXT_HINT};
    font-size: {FONT_XS}px;
}}
QLabel[class="h1"] {{
    font-size: {FONT_XL}px;
    font-weight: bold;
}}
QLabel[class="h2"] {{
    font-size: {FONT_LG}px;
    font-weight: bold;
}}
QLabel[class="warning"] {{
    color: {WARNING};
    font-size: {FONT_SM}px;
}}
QListWidget {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 4px 8px;
}}
QListWidget::item:selected {{
    background-color: {PRIMARY};
    color: white;
}}
QPlainTextEdit {{
    background-color: {SURFACE_INPUT};
    color: #d4d4d4;
    border: none;
    border-radius: 6px;
    font-family: "Consolas", monospace;
    font-size: 10px;
}}
QFrame[class="pill"] {{
    background-color: {SURFACE_HOVER};
    border-radius: 14px;
    padding: 2px 12px;
}}
QPushButton[class="accordion-header"] {{
    background-color: {SURFACE_2};
    color: {TEXT_PRIMARY};
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 6px;
    font-size: {FONT_MD}px;
    font-weight: bold;
    margin-bottom: 2px;
}}
QPushButton[class="accordion-header"]:hover {{
    background-color: {SURFACE_HOVER};
}}
QFrame#log_drawer {{
    background-color: {SURFACE_0};
    border-top: 1px solid {DIVIDER};
}}
"""


# ── Backward-compat aliases (consumed by pages/components) ──
BG_DEEP = SURFACE_0
BG_MAIN = SURFACE_1
BG_PANEL = SURFACE_2
BG_INPUT = SURFACE_INPUT
BG_HOVER = SURFACE_HOVER
BG_ACTIVE = SURFACE_ACTIVE
BORDER = DIVIDER
TEXT = TEXT_PRIMARY
TEXT_MUTED = TEXT_SECONDARY
TEXT_FAINT = TEXT_HINT
ACCENT = PRIMARY
ACCENT_HOVER = PRIMARY_HOVER
GREEN = POSITIVE
YELLOW = WARNING
RED = DESTRUCTIVE
BLUE = INFO
PAD_XS = GAP_XS
PAD_SM = GAP_SM
PAD_MD = GAP_MD
PAD_LG = GAP_LG
SIDEBAR_W = LIVE_PANEL_WIDTH
HEADER_H = TOOLBAR_HEIGHT
FS_H1 = FONT_XL
FS_H2 = FONT_LG
FS_BODY = FONT_MD
FS_SMALL = FONT_SM
FS_TINY = FONT_XS

# legacy function alias
build_stylesheet = buildStylesheet
