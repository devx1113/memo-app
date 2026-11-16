"""Dialog for creating and editing a memo."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from ..i18n import fmt_minutes, priorities, repeats, reverse, tr
from ..models import Memo, parse_date
from .theme import C, style_titlebar
from .widgets import DateEntry, TimeEntry


class OverrideRow:
    """A settings row with a "use default" checkbox."""

    def __init__(self, parent, row: int, label: str, widget_factory, default_text: str, hint: str = ""):
        self.use_default = tk.BooleanVar(value=True)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        self.widget = widget_factory(parent)
        self.widget.grid(row=row, column=1, sticky="w", padx=6)
        cb = ttk.Checkbutton(parent, text=tr("Default ({value})", value=default_text),
                             variable=self.use_default, command=self.sync)
        cb.grid(row=row, column=2, sticky="w")
        if hint:
            ttk.Label(parent, text=hint, style="Small.TLabel").grid(row=row, column=3, sticky="w", padx=6)

    def sync(self):
        state = "disabled" if self.use_default.get() else "normal"
        if hasattr(self.widget, "set_state"):
            self.widget.set_state(state)
        else:
            self.widget.config(state=state)


class MemoEditor(tk.Toplevel):
    def __init__(self, master, settings, memo: Memo | None = None, initial_date: date | None = None,
                 on_save=None, on_delete=None, is_new: bool | None = None):
        super().__init__(master)
        self.withdraw()
        self.configure(bg=C["bg"])
        self.settings = settings
        self.is_new = memo is None if is_new is None else is_new
        self.memo = memo.copy() if memo else Memo(date=(initial_date or date.today()).isoformat())
        self.on_save = on_save
        self.on_delete = on_delete
        self.title(tr("New memo") if self.is_new else tr("Edit memo"))
        self.transient(master)
        self.resizable(True, True)
        self.minsize(680, 540)
        self._build()
        self._load()
        self.bind("<Control-Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        px = master.winfo_rootx() + 60
        py = master.winfo_rooty() + 40
        self.geometry(f"+{max(0, px)}+{max(0, py)}")
        self.deiconify()
        style_titlebar(self)
        self.grab_set()
        self.title_entry.focus_set()

    # ------------------------------------------------------------------
    def _build(self):
        s = self.settings
        ttk.Label(self, text=tr("New memo") if self.is_new else tr("Edit memo"), style="Header.TLabel").pack(
            anchor="w", padx=18, pady=(14, 4))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=16, pady=(4, 0))

        # ===== Details =====
        f = ttk.Frame(nb, padding=16)
        nb.add(f, text=f"  {tr('Details')}  ")
        f.columnconfigure(1, weight=1)

        def label(text, row, sticky="w"):
            ttk.Label(f, text=text).grid(row=row, column=0, sticky=sticky, pady=4, padx=(0, 10))

        label(tr("Title"), 0)
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(f, textvariable=self.title_var)
        self.title_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)

        label(tr("Date"), 1)
        self.date_entry = DateEntry(f, week_start=s["week_start"])
        self.date_entry.grid(row=1, column=1, sticky="w")

        label(tr("Time"), 2)
        tf = ttk.Frame(f)
        tf.grid(row=2, column=1, columnspan=3, sticky="w")
        self.all_day = tk.BooleanVar()
        ttk.Checkbutton(tf, text=tr("All day / no time"), variable=self.all_day,
                        command=self._sync_time).pack(side="left")
        ttk.Label(tf, text="   " + tr("Start")).pack(side="left")
        self.start_entry = TimeEntry(tf)
        self.start_entry.pack(side="left", padx=4)
        ttk.Label(tf, text=tr("End")).pack(side="left")
        self.end_entry = TimeEntry(tf)
        self.end_entry.pack(side="left", padx=4)
        self.has_end = tk.BooleanVar(value=True)
        self.has_end_cb = ttk.Checkbutton(tf, text=tr("Has end time"), variable=self.has_end,
                                          command=self._sync_time)
        self.has_end_cb.pack(side="left")

        label(tr("Priority"), 3)
        self.priority = ttk.Combobox(f, values=list(priorities().values()), state="readonly", width=10)
        self.priority.grid(row=3, column=1, sticky="w")

        label(tr("Repeat"), 4)
        rf = ttk.Frame(f)
        rf.grid(row=4, column=1, columnspan=3, sticky="w")
        self.repeat = ttk.Combobox(rf, values=list(repeats().values()), state="readonly", width=20)
        self.repeat.pack(side="left")
        self.repeat.bind("<<ComboboxSelected>>", lambda e: self._sync_repeat())
        ttk.Label(rf, text="   " + tr("Until")).pack(side="left")
        self.repeat_until = DateEntry(rf, week_start=s["week_start"], allow_empty=True)
        self.repeat_until.pack(side="left", padx=4)

        label(tr("Notes"), 5, sticky="nw")
        tw = ttk.Frame(f)
        tw.grid(row=5, column=1, columnspan=3, sticky="nsew", pady=4)
        f.rowconfigure(5, weight=1)
        self.content = tk.Text(tw, height=8, wrap="word", font="AppBody", undo=True, relief="flat",
                               bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                               highlightthickness=1, highlightbackground=C["border"],
                               highlightcolor=C["accent"], padx=8, pady=6)
        sb = ttk.Scrollbar(tw, command=self.content.yview)
        self.content.config(yscrollcommand=sb.set)
        self.content.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # ===== Notifications =====
        n = ttk.Frame(nb, padding=16)
        nb.add(n, text=f"  {tr('Notifications')}  ")
        self.notify = tk.BooleanVar()
        ttk.Checkbutton(n, text=tr("Notify me about this memo"), variable=self.notify,
                        style="Switch.TCheckbutton", command=self._sync_notify).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(n, text=tr("Untick “Default” to use a different value for this memo only."),
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 6))

        def spin(lo, hi):
            return lambda p: ttk.Spinbox(p, from_=lo, to=hi, width=6)

        pre_default = (tr("{t} before", t=fmt_minutes(s["pre_alert_minutes"]))
                       if s["pre_alert_enabled"] else tr("Off"))
        days_default = tr("Same day") if int(s["days_before"]) == 0 else tr("{n} days before", n=s["days_before"])
        self.sound_labels = [tr("Play sound"), tr("Silent")]
        self.rows = {
            "notify_time": OverrideRow(n, 2, tr("Start reminding at"), lambda p: TimeEntry(p), s["notify_time"],
                                       tr("Reminders begin at this time")),
            "days_before": OverrideRow(n, 3, tr("Days in advance"), spin(0, 60), days_default,
                                       tr("0 = on the day only")),
            "display_minutes": OverrideRow(n, 4, tr("Show for (min)"), spin(0, 1440),
                                           fmt_minutes(s["display_minutes"]), tr("0 = until I close it")),
            "interval_minutes": OverrideRow(n, 5, tr("Repeat every (min)"), spin(1, 1440),
                                            fmt_minutes(s["interval_minutes"]), tr("Gap before it shows again")),
            "pre_alert_minutes": OverrideRow(n, 6, tr("“Starting soon” (min)"), spin(0, 1440), pre_default,
                                             tr("0 = no starting-soon alert")),
            "sound": OverrideRow(n, 7, tr("Sound"),
                                 lambda p: ttk.Combobox(p, values=self.sound_labels, state="readonly", width=10),
                                 self.sound_labels[0] if s["sound_enabled"] else self.sound_labels[1]),
        }

        # ===== Buttons =====
        bf = ttk.Frame(self, padding=(16, 12, 16, 16))
        bf.pack(fill="x")
        if not self.is_new and self.on_delete:
            ttk.Button(bf, text=tr("Delete"), command=self._delete).pack(side="left")
        ttk.Button(bf, text=tr("Cancel"), command=self.destroy).pack(side="right")
        ttk.Button(bf, text=tr("Save  (Ctrl+Enter)"), style="Accent.TButton",
                   command=self._save).pack(side="right", padx=8)

    # ------------------------------------------------------------------
    def _load(self):
        m = self.memo
        self.title_var.set(m.title)
        self.date_entry.set(m.date)
        self.all_day.set(m.all_day)
        self.start_entry.set(m.start_time or "10:00")
        self.end_entry.set(m.end_time or "11:00")
        self.has_end.set(bool(m.end_time) or m.all_day)
        self.priority.set(priorities().get(m.priority, tr("Medium")))
        self.repeat.set(repeats().get(m.repeat, tr("Does not repeat")))
        self.repeat_until.set(m.repeat_until)
        self.content.insert("1.0", m.content)
        self.notify.set(m.notify)

        s = self.settings
        for name, row in self.rows.items():
            v = getattr(m, name)
            row.use_default.set(v is None)
            w = row.widget
            if name == "notify_time":
                w.set(v or s["notify_time"])
            elif name == "sound":
                eff = s["sound_enabled"] if v is None else v
                w.set(self.sound_labels[0] if eff else self.sound_labels[1])
            else:
                w.set(str(m.eff(s, name)))
        self._sync_time()
        self._sync_repeat()
        self._sync_notify()

    def _repeat_key(self) -> str:
        return reverse(repeats(), self.repeat.get(), "none")

    def _sync_time(self):
        state = "disabled" if self.all_day.get() else "normal"
        self.start_entry.set_state(state)
        self.has_end_cb.config(state=state)
        self.end_entry.set_state(state if self.has_end.get() else "disabled")

    def _sync_repeat(self):
        self.repeat_until.set_state("disabled" if self._repeat_key() == "none" else "normal")

    def _sync_notify(self):
        on = self.notify.get()
        for row in self.rows.values():
            if on:
                row.sync()
            elif hasattr(row.widget, "set_state"):
                row.widget.set_state("disabled")
            else:
                row.widget.config(state="disabled")

    def _warn(self, msg: str):
        messagebox.showwarning(tr("Please check your input"), msg, parent=self)

    # ------------------------------------------------------------------
    def _save(self):
        m = self.memo
        title = self.title_var.get().strip()
        if not title:
            return self._warn(tr("Please enter a title."))
        try:
            parse_date(self.date_entry.get())
        except ValueError:
            return self._warn(tr("Please enter the date as YYYY-MM-DD."))
        until = self.repeat_until.get()
        if until and self._repeat_key() != "none":
            try:
                parse_date(until)
            except ValueError:
                return self._warn(tr("The repeat end date is not valid."))
        try:
            start = "" if self.all_day.get() else self.start_entry.get()
            end = "" if self.all_day.get() or not self.has_end.get() else self.end_entry.get()
        except ValueError:
            return self._warn(tr("The time is not valid."))

        overrides = {}
        for name, row in self.rows.items():
            if row.use_default.get():
                overrides[name] = None
                continue
            try:
                if name == "notify_time":
                    overrides[name] = row.widget.get()
                elif name == "sound":
                    overrides[name] = row.widget.get() == self.sound_labels[0]
                else:
                    v = int(row.widget.get())
                    if v < 0 or (name == "interval_minutes" and v < 1):
                        raise ValueError
                    overrides[name] = v
            except ValueError:
                return self._warn(tr("One of the notification values is not valid."))

        old_sched = (m.date, m.start_time, m.end_time, m.repeat, m.notify_time, m.days_before)
        m.title = title
        m.date = self.date_entry.get()
        m.all_day = self.all_day.get()
        m.start_time = start
        m.end_time = end
        m.priority = reverse(priorities(), self.priority.get(), "normal")
        m.repeat = self._repeat_key()
        m.repeat_until = until if m.repeat != "none" else ""
        m.content = self.content.get("1.0", "end-1c")
        m.notify = self.notify.get()
        for k, v in overrides.items():
            setattr(m, k, v)
        if old_sched != (m.date, m.start_time, m.end_time, m.repeat, m.notify_time, m.days_before):
            m.acknowledged = []  # schedule changed: bring back reminders that were dismissed
        if self.on_save:
            self.on_save(m)
        self.destroy()

    def _delete(self):
        if messagebox.askyesno(tr("Delete memo"), tr("Delete “{title}”?", title=self.memo.title), parent=self):
            if self.on_delete:
                self.on_delete(self.memo)
            self.destroy()
