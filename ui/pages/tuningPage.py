"""Settings tab: full user-facing tuning surface with collapsible switch→detail groups."""
import logging

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from config import profile_store as preferences, option_registry

def t(s: str) -> str: return s

from .. import style as T
from .. import components as W

log = logging.getLogger("dhe")


class SettingsTab(QWidget):
    SHOW_RESET = True
    DEVELOPER_VIEW = False
    PAGE_TITLE = "Settings"
    PAGE_SUBTITLE = "Haptic/trigger tuning. Left = subtle, Right = intense."

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.settings = app.settings
        self._switches: dict[str, W.ToggleSwitch] = {}
        self._sliders: dict[str, W.FloatSlider] = {}
        self._detail_frames: dict[str, QWidget] = {}
        self._building = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(W.PageHeader(t(self.PAGE_TITLE), t(self.PAGE_SUBTITLE)))
        self._scroll = W.ScrollArea()
        layout.addWidget(self._scroll)

        self._building = True
        self._build()
        self._building = False

        if self.SHOW_RESET:
            btn = W.DangerButton(t("Reset to defaults"))
            btn.clicked.connect(self._on_reset)
            self._scroll.add_widget(btn)

        app.register_refresh(self._refresh_widgets)

    def _build(self):
        if self.DEVELOPER_VIEW:
            return
        groups = option_registry.settings_groups_resolved()
        for grp in groups:
            self._build_group_card(grp)

    def _build_group_card(self, grp: dict):
        card = W.Card()
        card_layout = card.card_layout()
        card_layout.addWidget(W.H2(t(grp["title"])))

        if grp.get("description"):
            desc = grp["description"]
            if "\u26a0\ufe0f" in desc:
                card_layout.addWidget(W.Warning(t(desc), wrap=600))
            else:
                card_layout.addWidget(W.Hint(t(desc), wrap=600))

        # Always-visible sliders
        for spec in grp["always"]:
            if not hasattr(self.settings, spec.key):
                continue
            value = getattr(self.settings, spec.key)
            label = self._tagged_label(spec)
            hint = spec.description_ko or spec.description_en or ""
            if isinstance(value, bool):
                self._add_switch(card_layout, spec.key, label, hint)
            elif spec.ui_min is not None and spec.ui_max is not None:
                self._add_slider(card_layout, spec.key, label, value, spec.ui_min, spec.ui_max, hint)

        # Switch → detail collapsibles
        for sw_spec, detail_specs in grp["switches"].items():
            if not hasattr(self.settings, sw_spec.key):
                continue
            label = self._tagged_label(sw_spec)
            hint = sw_spec.description_ko or sw_spec.description_en or ""
            self._add_switch(card_layout, sw_spec.key, label, hint)

            if detail_specs:
                detail_frame = QWidget()
                detail_layout = QVBoxLayout(detail_frame)
                detail_layout.setContentsMargins(T.PAD_MD, 0, 0, 0)
                detail_layout.setSpacing(T.PAD_XS)
                self._detail_frames[sw_spec.key] = detail_frame

                for dspec in detail_specs:
                    if not hasattr(self.settings, dspec.key):
                        continue
                    dval = getattr(self.settings, dspec.key)
                    dlabel = self._tagged_label(dspec)
                    dhint = dspec.description_ko or dspec.description_en or ""
                    if dspec.ui_min is not None and dspec.ui_max is not None:
                        self._add_slider(detail_layout, dspec.key, dlabel, dval, dspec.ui_min, dspec.ui_max, dhint)

                card_layout.addWidget(detail_frame)
                if not getattr(self.settings, sw_spec.key):
                    detail_frame.setVisible(False)

        self._scroll.add_widget(card)

    @staticmethod
    def _tagged_label(spec) -> str:
        """Prepend [Haptic] or [Trigger] tag to label for clarity."""
        base = option_registry.bilingual(spec)
        a = spec.affects
        if a == "haptic":
            return f"[Haptic] {base}"
        elif a == "trigger":
            return f"[Trigger] {base}"
        elif a in ("haptic_trigger", "both"):
            return f"[Haptic][Trigger] {base}"
        return base

    # ------------------------------------------------------------------
    # Row builders

    def _add_switch(self, layout, attr: str, label: str, hint: str):
        row = W.FieldRow(label, hint)
        sw = W.ToggleSwitch()
        sw.setChecked(bool(getattr(self.settings, attr)))
        sw.toggled.connect(lambda checked, a=attr: self._on_switch(a, checked))
        row.controls_layout.addWidget(sw)
        layout.addWidget(row)
        self._switches[attr] = sw

    def _add_slider(self, layout, attr: str, label: str, value, lo, hi, hint: str):
        row = W.FieldRow(label, hint)
        is_pct = self._is_percent_display(attr)
        if is_pct:
            shown = self._display_value(attr, value)
            pct_range = option_registry.percent_slider_range(attr)
            if pct_range:
                pct_lo, pct_hi = pct_range
            else:
                pct_lo, pct_hi = 0, 300
            steps = max(1, int(pct_hi - pct_lo))
            slider = W.FloatSlider(pct_lo, pct_hi, steps)
        else:
            shown = float(value)
            steps = max(1, int(hi - lo)) if isinstance(value, int) else 220
            slider = W.FloatSlider(float(lo), float(hi), steps)
        slider.set_value(float(shown))
        slider.valueChanged.connect(lambda v, a=attr: self._on_slider(a, v))
        row.controls_layout.addWidget(slider)
        layout.addWidget(row)
        self._sliders[attr] = slider

    # ------------------------------------------------------------------
    # Display helpers

    def _is_percent_display(self, attr: str) -> bool:
        return (not self.DEVELOPER_VIEW) and not getattr(self, "IS_SYSTEM", False) and option_registry.is_percent_tuning_key(attr)

    def _display_value(self, attr: str, raw):
        if self._is_percent_display(attr):
            pct = option_registry.percent_from_raw(attr, raw)
            if pct is not None:
                pct_range = option_registry.percent_slider_range(attr)
                if pct_range:
                    return max(pct_range[0], min(pct_range[1], pct))
                return max(0.0, min(300.0, pct))
        return raw

    def _raw_value_from_display(self, attr: str, shown):
        if self._is_percent_display(attr):
            raw = option_registry.raw_from_percent(attr, shown)
            if raw is not None:
                return raw
        return shown

    # ------------------------------------------------------------------
    # Event handlers

    def _on_switch(self, attr: str, checked: bool):
        if self._building or self.app._refreshing:
            return
        if getattr(self.settings, attr) != checked:
            setattr(self.settings, attr, checked)
            preferences.save(self.settings)
            log.info("%s = %s", attr, checked)
            self.app.setting_feedback(attr)
        # Toggle detail frame visibility
        frame = self._detail_frames.get(attr)
        if frame is not None:
            frame.setVisible(checked)

    def _on_slider(self, attr: str, shown: float):
        if self._building or self.app._refreshing:
            return
        current = getattr(self.settings, attr)
        new = self._raw_value_from_display(attr, shown)
        if isinstance(current, int) and not isinstance(current, bool):
            new = int(round(new))
        if new != current:
            setattr(self.settings, attr, new)
            preferences.save_debounced(self.settings)
            self.app.setting_feedback(attr)

    def _on_reset(self):
        from config.settings import Settings
        defaults = Settings()
        for attr in self._sliders:
            if hasattr(defaults, attr):
                setattr(self.settings, attr, getattr(defaults, attr))
        for attr in self._switches:
            if hasattr(defaults, attr):
                setattr(self.settings, attr, getattr(defaults, attr))
        preferences.save(self.settings)
        self._refresh_widgets(force=True)

    # ------------------------------------------------------------------
    # External refresh
    def _refresh_widgets(self, force: bool = False):
        if not force and not self.isVisible():
            return
        self._building = True
        try:
            for attr, sw in self._switches.items():
                if not hasattr(self.settings, attr):
                    continue
                want = bool(getattr(self.settings, attr))
                if sw.isChecked() != want:
                    sw.setChecked(want)
                frame = self._detail_frames.get(attr)
                if frame is not None:
                    frame.setVisible(want)
            for attr, sld in self._sliders.items():
                if not hasattr(self.settings, attr):
                    continue
                want = float(self._display_value(attr, getattr(self.settings, attr)))
                if abs(sld.value() - want) > 0.5:
                    sld.set_value(want)
        finally:
            self._building = False
