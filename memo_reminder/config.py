"""Settings and data-folder handling."""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

APP_NAME = "MemoReminder"
VERSION = "1.1.0"


def data_dir() -> Path:
    """Where data is stored (Windows: %APPDATA%\\MemoReminder)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_SETTINGS: dict = {
    # ---- Notification timing ----
    "notify_enabled": True,          # master switch
    "notify_time": "07:00",          # time of day reminders start
    "days_before": 0,                # start reminding N days ahead (0 = on the day only)
    "display_minutes": 5,            # how long a reminder stays visible (0 = until closed)
    "interval_minutes": 5,           # pause before it re-appears
    "snooze_minutes": 10,
    "snooze_choices": "5,10,15,30,60",
    "pre_alert_enabled": True,       # extra "starting soon" reminder
    "pre_alert_minutes": 15,
    "notify_until": "start",         # timed events: keep reminding until start / end / day_end
    # ---- Popup ----
    "popup_position": "bottom_right",  # bottom_right / top_right / bottom_left / top_left / center
    "popup_width": 420,
    "popup_opacity": 0.97,
    "popup_flash": True,
    "native_toast": False,           # also send a Windows toast (needs winotify)
    # ---- Sound ----
    "sound_enabled": True,
    "sound_alias": "SystemNotification",
    "sound_file": "",                # a .wav file overrides the system sound
    # ---- Appearance ----
    "language": "en",                # en / ja
    "theme": "system",               # system / light / dark
    "font_family": "",               # "" = automatic for the language
    "font_size": 10,
    "week_start": "sunday",          # sunday / monday
    "upcoming_days": 14,
    # ---- Behaviour ----
    "minimize_to_tray": True,
    "start_minimized": False,
    "autostart": False,
    "check_interval_seconds": 10,
    # ---- Internal ----
    "window_geometry": "",
    "tray_hint_shown": False,
}

SOUND_ALIASES = [
    "SystemNotification",
    "SystemAsterisk",
    "SystemExclamation",
    "SystemHand",
    "SystemQuestion",
    "SystemDefault",
]


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "settings.json")
        self.values = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for k, v in loaded.items():
                    if k in DEFAULT_SETTINGS:
                        self.values[k] = v
            except (OSError, ValueError):
                pass

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def __getitem__(self, key):
        return self.values.get(key, DEFAULT_SETTINGS.get(key))

    def __setitem__(self, key, value):
        self.values[key] = value

    def get(self, key, default=None):
        return self.values.get(key, default)

    def font(self) -> str:
        """The font to use; picks a good default for the language when not set."""
        fam = (self["font_family"] or "").strip()
        if fam:
            return fam
        return "Yu Gothic UI" if self["language"] == "ja" else "Segoe UI"

    def snooze_list(self) -> list[int]:
        out = []
        for part in str(self["snooze_choices"]).replace("、", ",").split(","):
            part = part.strip()
            if part.isdigit() and int(part) > 0:
                out.append(int(part))
        return out or [5, 10, 15, 30, 60]
