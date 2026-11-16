"""Settings dialog."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from ..config import DEFAULT_SETTINGS, SOUND_ALIASES
from ..i18n import (LANGUAGES, notify_until_labels, popup_positions, reverse, themes, tr,
                    week_starts)
from .. import winutil
from .theme import C, style_titlebar
from .widgets import TimeEntry


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, settings, on_apply, on_test_popup):
        super().__init__(master)
        self.withdraw()
        self.configure(bg=C["bg"])
        self.settings = settings
        self.on_apply = on_apply
        self.on_test_popup = on_test_popup
        self.title(tr("Settings"))
        self.transient(master)
        self.resizable(False, False)
        self.vars: dict[str, tk.Variable] = {}
        self._build()
        self._load(settings.values)
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx() + 80}+{master.winfo_rooty() + 40}")
        self.deiconify()
        style_titlebar(self)
        self.grab_set()

    # ---------- helpers ----------
    def _var(self, key, kind):
        v = {"bool": tk.BooleanVar, "int": tk.StringVar, "str": tk.StringVar, "float": tk.StringVar}[kind]()
        self.vars[key] = v
        v._kind = kind  # type: ignore[attr-defined]
        return v

    def _row(self, parent, r, label, widget, hint=""):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 12))
        widget.grid(row=r, column=1, sticky="w")
        if hint:
            ttk.Label(parent, text=hint, style="Small.TLabel").grid(row=r, column=2, sticky="w", padx=8)

    def _spin(self, parent, key, lo, hi, inc=1, kind="int"):
        return ttk.Spinbox(parent, from_=lo, to=hi, increment=inc, width=7, textvariable=self._var(key, kind))

    def _check(self, parent, key, text):
        return ttk.Checkbutton(parent, text=text, variable=self._var(key, "bool"), style="Switch.TCheckbutton")

    def _combo(self, parent, labels: dict, width: int):
        return ttk.Combobox(parent, values=list(labels.values()), state="readonly", width=width)

    # ---------- layout ----------
    def _build(self):
        ttk.Label(self, text=tr("Settings"), style="Header.TLabel").pack(anchor="w", padx=18, pady=(14, 4))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        span = dict(row=0, column=0, columnspan=3, sticky="w")

        # ===== Reminders =====
        f = ttk.Frame(nb, padding=18)
        nb.add(f, text=f"  {tr('Reminders')}  ")
        r = 0
        self._check(f, "notify_enabled", tr("Enable notifications")).grid(**{**span, "row": r}); r += 1
        self.notify_time = TimeEntry(f)
        self._row(f, r, tr("Start reminding at"), self.notify_time, tr("Reminders begin at this time on the day")); r += 1
        self._row(f, r, tr("Days in advance"), self._spin(f, "days_before", 0, 60),
                  tr("0 = on the day only; 1 = also the day before")); r += 1
        self._row(f, r, tr("Show for (min)"), self._spin(f, "display_minutes", 0, 1440),
                  tr("0 = stay on screen until I close it")); r += 1
        self._row(f, r, tr("Repeat every (min)"), self._spin(f, "interval_minutes", 1, 1440),
                  tr("Gap after it hides before it shows again")); r += 1
        self._row(f, r, tr("Default snooze (min)"), self._spin(f, "snooze_minutes", 1, 1440)); r += 1
        e = ttk.Entry(f, width=20, textvariable=self._var("snooze_choices", "str"))
        self._row(f, r, tr("Snooze options (min)"), e, tr("Comma-separated, e.g. 5,10,30,60")); r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=8); r += 1
        self._check(f, "pre_alert_enabled", tr("Also alert me shortly before the start time")).grid(
            **{**span, "row": r}); r += 1
        self._row(f, r, tr("“Starting soon” (min)"), self._spin(f, "pre_alert_minutes", 1, 1440),
                  tr("Only for memos with a start time")); r += 1
        self.until = self._combo(f, notify_until_labels(), 24)
        self._row(f, r, tr("Keep reminding"), self.until, tr("For timed memos (all-day memos: until midnight)")); r += 1
        self._row(f, r, tr("Check every (sec)"), self._spin(f, "check_interval_seconds", 2, 120)); r += 1

        # ===== Popup & sound =====
        p = ttk.Frame(nb, padding=18)
        nb.add(p, text=f"  {tr('Popup & sound')}  ")
        r = 0
        self.pos = self._combo(p, popup_positions(), 16)
        self._row(p, r, tr("Position"), self.pos); r += 1
        self._row(p, r, tr("Width (px)"), self._spin(p, "popup_width", 250, 900, 10)); r += 1
        self._row(p, r, tr("Opacity"), self._spin(p, "popup_opacity", 0.3, 1.0, 0.05, kind="float"), "0.3 – 1.0"); r += 1
        self._check(p, "popup_flash", tr("Flash the border when it appears")).grid(**{**span, "row": r}); r += 1
        self._check(p, "native_toast", tr("Also send a Windows notification (Action Center)")).grid(
            **{**span, "row": r}); r += 1
        if not winutil.native_toast_available():
            ttk.Label(p, text="  " + tr("Requires winotify (included in the .exe)"),
                      style="Small.TLabel").grid(**{**span, "row": r}); r += 1
        ttk.Separator(p).grid(row=r, column=0, columnspan=3, sticky="ew", pady=8); r += 1
        self._check(p, "sound_enabled", tr("Play a sound")).grid(**{**span, "row": r}); r += 1
        self.alias = ttk.Combobox(p, values=SOUND_ALIASES, width=20, textvariable=self._var("sound_alias", "str"))
        self._row(p, r, tr("System sound"), self.alias); r += 1
        wf = ttk.Frame(p)
        ttk.Entry(wf, width=28, textvariable=self._var("sound_file", "str")).pack(side="left")
        ttk.Button(wf, text=tr("Browse…"), command=self._pick_wav).pack(side="left", padx=4)
        self._row(p, r, tr("WAV file"), wf, tr("Used instead of the system sound")); r += 1
        tb = ttk.Frame(p)
        tb.grid(row=r, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(tb, text=tr("Test sound"), command=self._test_sound).pack(side="left")
        ttk.Button(tb, text=tr("Show a test notification"), command=self._test_popup).pack(side="left", padx=6)

        # ===== Appearance & behaviour =====
        g = ttk.Frame(nb, padding=18)
        nb.add(g, text=f"  {tr('Appearance & behavior')}  ")
        r = 0
        self.lang_cb = self._combo(g, LANGUAGES, 24)
        self._row(g, r, tr("Language"), self.lang_cb); r += 1
        self.theme_cb = self._combo(g, themes(), 24)
        self._row(g, r, tr("Theme"), self.theme_cb); r += 1
        self.auto_font = tr("(Automatic)")
        fams = sorted(x for x in set(tkfont.families(self)) if not x.startswith("@"))
        self.font_cb = ttk.Combobox(g, values=[self.auto_font] + fams, width=24)
        self._row(g, r, tr("Font"), self.font_cb); r += 1
        self._row(g, r, tr("Text size"), self._spin(g, "font_size", 8, 24)); r += 1
        self.week = self._combo(g, week_starts(), 12)
        self._row(g, r, tr("Week starts on"), self.week); r += 1
        self._row(g, r, tr("“Upcoming” shows (days)"), self._spin(g, "upcoming_days", 1, 365)); r += 1
        ttk.Separator(g).grid(row=r, column=0, columnspan=3, sticky="ew", pady=8); r += 1
        self._check(g, "minimize_to_tray", tr("Closing the window keeps the app running in the tray")).grid(
            **{**span, "row": r}); r += 1
        self._check(g, "start_minimized", tr("Start hidden (tray only)")).grid(**{**span, "row": r}); r += 1
        ac = self._check(g, "autostart", tr("Start automatically with Windows"))
        ac.grid(**{**span, "row": r}); r += 1
        if not winutil.IS_WIN:
            ac.config(state="disabled")

        # ===== Buttons =====
        bf = ttk.Frame(self, padding=(16, 12, 16, 16))
        bf.pack(fill="x")
        ttk.Button(bf, text=tr("Restore defaults"), command=self._reset).pack(side="left")
        ttk.Button(bf, text=tr("Cancel"), command=self.destroy).pack(side="right")
        ttk.Button(bf, text="OK", style="Accent.TButton", width=8, command=self._ok).pack(side="right", padx=8)

    # ---------- values ----------
    def _load(self, values: dict):
        for k, v in self.vars.items():
            v.set(values.get(k, DEFAULT_SETTINGS[k]))
        self.notify_time.set(values.get("notify_time", "07:00"))
        self.pos.set(popup_positions().get(values.get("popup_position"), tr("Bottom right")))
        self.until.set(notify_until_labels().get(values.get("notify_until"), tr("Until the event starts")))
        self.theme_cb.set(themes().get(values.get("theme"), tr("Match Windows")))
        self.lang_cb.set(LANGUAGES.get(values.get("language"), "English"))
        self.week.set(week_starts().get(values.get("week_start"), tr("Sunday")))
        self.font_cb.set(values.get("font_family") or self.auto_font)

    def _collect(self) -> dict | None:
        out = {}
        try:
            for k, v in self.vars.items():
                kind = v._kind  # type: ignore[attr-defined]
                raw = v.get()
                if kind == "int":
                    out[k] = int(str(raw).strip())
                    if out[k] < 0:
                        raise ValueError(k)
                elif kind == "float":
                    out[k] = float(raw)
                else:
                    out[k] = raw
            out["popup_opacity"] = min(1.0, max(0.3, float(self.vars["popup_opacity"].get())))
            out["interval_minutes"] = max(1, out["interval_minutes"])
            out["check_interval_seconds"] = max(2, out["check_interval_seconds"])
            out["notify_time"] = self.notify_time.get()
        except ValueError:
            messagebox.showwarning(tr("Please check your input"), tr("One of the numbers is not valid."), parent=self)
            return None
        out["popup_position"] = reverse(popup_positions(), self.pos.get(), "bottom_right")
        out["theme"] = reverse(themes(), self.theme_cb.get(), "system")
        out["language"] = reverse(LANGUAGES, self.lang_cb.get(), "en")
        out["notify_until"] = reverse(notify_until_labels(), self.until.get(), "start")
        out["week_start"] = reverse(week_starts(), self.week.get(), "sunday")
        font = self.font_cb.get().strip()
        out["font_family"] = "" if font == self.auto_font else font
        return out

    def _ok(self):
        vals = self._collect()
        if vals is None:
            return
        self.destroy()
        self.on_apply(vals)

    def _reset(self):
        if messagebox.askyesno(tr("Restore defaults"),
                               tr("Reset every setting to its default? (Nothing is saved until you press OK.)"),
                               parent=self):
            self._load(DEFAULT_SETTINGS)

    # ---------- tests ----------
    def _pick_wav(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("WAV", "*.wav"), (tr("All files"), "*.*")])
        if path:
            self.vars["sound_file"].set(path)

    def _test_sound(self):
        winutil.play_sound(self.vars["sound_alias"].get(), self.vars["sound_file"].get())

    def _test_popup(self):
        vals = self._collect()
        if vals is not None:
            self.on_test_popup(vals)
