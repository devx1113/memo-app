"""Main window and overall application control."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import tkinter as tk
import uuid
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, ttk

from ..config import VERSION, Settings, data_dir
from ..i18n import (JA, app_title, date_label, fmt_minutes, is_ja, priorities, repeats, set_language, tr)
from ..models import Memo, MemoStore
from ..scheduler import Alert, AlertManager
from .. import winutil
from .editor import MemoEditor
from .popup import PopupManager
from .settings_dialog import SettingsDialog
from .theme import C, apply_theme, priority_colors, resource_path, set_window_icon, style_titlebar
from .tray import TrayIcon
from .widgets import CalendarWidget, ScrollFrame

TEST_PREFIX = "__test__"
SEP = "  ·  "


class App:
    def __init__(self, root: tk.Tk, settings: Settings, store: MemoStore, start_minimized: bool = False):
        self.root = root
        self.settings = settings
        self.store = store
        self.calls: queue.Queue = queue.Queue()
        self.last_day = date.today()
        self.test_popups: dict[str, object] = {}
        self.sel_key: str | None = None
        self.cards: dict[str, tk.Frame] = {}
        self.order: list[str] = []
        set_language(settings["language"])

        root.minsize(980, 620)
        root.geometry(settings.get("window_geometry") or "1200x740")
        set_window_icon(root)

        # ---- state ----
        self.view_mode = tk.StringVar(value="day")
        self.show_done = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        self.selected_date = date.today()

        # ---- reminders ----
        self.popups = PopupManager(root, settings)
        self.popups.on_ack = self._on_ack
        self.popups.on_snooze = self._on_snooze
        self.popups.on_complete = self._on_complete
        self.popups.on_open = self.open_memo
        self.alerts = AlertManager(store, settings, self.popups.show, self.popups.hide, store.save)

        # ---- UI ----
        self._build_ui()

        # ---- tray ----
        self.tray: TrayIcon | None = None
        self.has_tray = self._start_tray()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if start_minimized and not self.has_tray:
            root.iconify()

        self._bind_keys()
        self._poll_calls()
        self.root.after(800, self._tick)

    def _start_tray(self) -> bool:
        self.tray = TrayIcon(self.post, {
            "show": self.show_window,
            "new": lambda: (self.show_window(), self.new_memo()),
            "pause30": lambda: self.pause(30),
            "pause60": lambda: self.pause(60),
            "pause180": lambda: self.pause(180),
            "pause_inf": lambda: self.pause(None),
            "resume": self.resume,
            "settings": lambda: (self.show_window(), self.open_settings()),
            "quit": self.quit,
        }, self.alerts.is_paused)
        return self.tray.start()

    # ==================================================================
    # Cross-thread calls
    # ==================================================================
    def post(self, fn):
        """Run fn on the Tk thread (used by the tray and the single-instance listener)."""
        self.calls.put(fn)

    def _poll_calls(self):
        try:
            while True:
                fn = self.calls.get_nowait()
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    print("callback error:", e)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_calls)

    # ==================================================================
    # Building the UI
    # ==================================================================
    def _build_ui(self):
        s = self.settings
        self.root.title(app_title())
        apply_theme(self.root, s["theme"], s.font(), int(s["font_size"]))
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self.cards = {}
        self._build_menu()
        self._build_header()
        self._build_status()
        self._build_body()
        self.refresh_all()

    def _build_menu(self):
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label=tr("New memo"), accelerator="Ctrl+N", command=self.new_memo)
        fm.add_separator()
        fm.add_command(label=tr("Export…"), command=self.export_data)
        fm.add_command(label=tr("Import…"), command=self.import_data)
        fm.add_command(label=tr("Open data folder"), command=self.open_data_dir)
        fm.add_separator()
        fm.add_command(label=tr("Quit"), command=self.quit)
        m.add_cascade(label=tr("File"), menu=fm)

        vm = tk.Menu(m, tearoff=False)
        vm.add_radiobutton(label=tr("Selected day"), variable=self.view_mode, value="day", command=self.refresh_list)
        vm.add_radiobutton(label=tr("Upcoming"), variable=self.view_mode, value="upcoming", command=self.refresh_list)
        vm.add_radiobutton(label=tr("All memos"), variable=self.view_mode, value="all", command=self.refresh_list)
        vm.add_separator()
        vm.add_checkbutton(label=tr("Show completed memos"), variable=self.show_done, command=self.refresh_list)
        vm.add_command(label=tr("Go to today"), accelerator="Ctrl+T", command=lambda: self.calendar.go_today())
        m.add_cascade(label=tr("View"), menu=vm)

        nm = tk.Menu(m, tearoff=False)
        self._fill_notify_menu(nm)
        m.add_cascade(label=tr("Notifications"), menu=nm)

        tm = tk.Menu(m, tearoff=False)
        tm.add_command(label=tr("Settings…"), accelerator="Ctrl+,", command=self.open_settings)
        m.add_cascade(label=tr("Tools"), menu=tm)

        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label=tr("How to use"), command=self.show_help)
        hm.add_command(label=tr("About"), command=lambda: messagebox.showinfo(
            app_title(), f"{app_title()}  v{VERSION}\n\n{tr('Your data is stored in:')}\n{data_dir()}",
            parent=self.root))
        m.add_cascade(label=tr("Help"), menu=hm)
        self.root.config(menu=m)

    def _fill_notify_menu(self, nm: tk.Menu):
        pm = tk.Menu(nm, tearoff=False)
        for mins, label in ((30, tr("30 minutes")), (60, tr("1 hour")), (180, tr("3 hours")),
                            (None, tr("Until I resume"))):
            pm.add_command(label=label, command=lambda mm=mins: self.pause(mm))
        nm.add_cascade(label=tr("Pause notifications"), menu=pm)
        nm.add_command(label=tr("Resume notifications"), command=self.resume)
        nm.add_separator()
        nm.add_command(label=tr("Show a test notification"), command=lambda: self.test_popup(None))

    def _build_header(self):
        bar = ttk.Frame(self.root, padding=(18, 14, 18, 10))
        bar.pack(fill="x")
        try:
            img = tk.PhotoImage(master=self.root, file=str(resource_path("assets/app.png")))
            self._header_icon = img.subsample(max(1, img.width() // 34))
            ttk.Label(bar, image=self._header_icon).pack(side="left", padx=(0, 10))
        except Exception:
            pass
        ttk.Label(bar, text=app_title(), style="Title.TLabel").pack(side="left")

        ttk.Button(bar, text="+  " + tr("New memo"), style="Accent.TButton",
                   command=self.new_memo).pack(side="right")
        ttk.Button(bar, text=tr("Settings"), command=self.open_settings).pack(side="right", padx=(0, 8))
        nb = ttk.Menubutton(bar, text=tr("Notifications"))
        nm = tk.Menu(nb, tearoff=False)
        self._fill_notify_menu(nm)
        nb.config(menu=nm)
        nb.pack(side="right", padx=(0, 8))
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, width=26)
        self.search_entry.pack(side="right", padx=(0, 16))
        ttk.Label(bar, text=tr("Search"), style="Muted.TLabel").pack(side="right", padx=(0, 6))

    def _build_status(self):
        st = tk.Frame(self.root, bg=C["surface2"], highlightthickness=0)
        st.pack(fill="x", side="bottom")
        tk.Frame(st, bg=C["border"], height=1).pack(fill="x", side="top")
        inner = tk.Frame(st, bg=C["surface2"], padx=16, pady=5)
        inner.pack(fill="x")
        self.status_dot = tk.Label(inner, text="●", bg=C["surface2"], fg=C["low"], font="AppSmall")
        self.status_dot.pack(side="left")
        self.status = tk.Label(inner, text="", bg=C["surface2"], fg=C["muted"], font="AppSmall", anchor="w")
        self.status.pack(side="left", padx=(6, 0))
        self.status_right = tk.Label(inner, text="", bg=C["surface2"], fg=C["muted"], font="AppSmall")
        self.status_right.pack(side="right")

    def _build_body(self):
        pw = ttk.PanedWindow(self.root, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        left = ttk.Frame(pw, padding=(0, 0, 14, 0))
        pw.add(left, weight=5)
        self.calendar = CalendarWidget(left, on_select=self._on_date_selected,
                                       on_double=lambda d: self.new_memo(d), marks=self._marks,
                                       week_start=self.settings["week_start"])
        self.calendar.select(self.selected_date, notify=False)
        self.calendar.pack(fill="both", expand=True)
        ttk.Label(left, text=tr("Double-click a day to add a memo") + SEP + tr("Scroll to change month"),
                  style="Small.TLabel").pack(anchor="w", pady=(6, 0))

        right = ttk.Frame(pw, padding=(14, 0, 0, 0))
        pw.add(right, weight=4)

        # ---- list header ----
        head = ttk.Frame(right)
        head.pack(fill="x")
        self.list_title = ttk.Label(head, style="Header.TLabel")
        self.list_title.pack(side="left")
        self.list_count = ttk.Label(head, style="Muted.TLabel")
        self.list_count.pack(side="left", padx=(10, 0), pady=(6, 0))

        seg = ttk.Frame(right)
        seg.pack(fill="x", pady=(8, 8))
        for val, text in (("day", tr("Selected day")), ("upcoming", tr("Upcoming")), ("all", tr("All"))):
            ttk.Radiobutton(seg, text=text, value=val, variable=self.view_mode, style="Toggle.TButton",
                            command=self.refresh_list).pack(side="left", padx=(0, 4))
        ttk.Checkbutton(seg, text=tr("Show completed"), variable=self.show_done,
                        command=self.refresh_list).pack(side="right")

        # ---- list (cards) ----
        self.list_frame = ScrollFrame(right)
        self.list_frame.pack(fill="both", expand=True)

        # ---- details ----
        self.detail = tk.Frame(right, bg=C["surface"], highlightthickness=1,
                               highlightbackground=C["border"], padx=16, pady=12)
        self.detail.pack(fill="x", pady=(10, 0))
        self._build_detail()

    def _build_detail(self):
        d = self.detail
        bg = C["surface"]
        self.d_title = tk.Label(d, bg=bg, fg=C["text"], font="AppTitle", anchor="w", justify="left")
        self.d_title.pack(fill="x")
        self.d_info = tk.Label(d, bg=bg, fg=C["muted"], font="AppSmall", anchor="w", justify="left")
        self.d_info.pack(fill="x", pady=(2, 0))
        d.bind("<Configure>", lambda e: (self.d_title.config(wraplength=e.width - 40),
                                         self.d_info.config(wraplength=e.width - 40)))
        self.d_text = tk.Text(d, height=5, wrap="word", relief="flat", bd=0, bg=bg, fg=C["text"],
                              font="AppBody", highlightthickness=0, padx=0, pady=6,
                              insertbackground=C["text"], cursor="arrow")
        self.d_text.pack(fill="x")
        bf = tk.Frame(d, bg=bg)
        bf.pack(fill="x", pady=(6, 0))
        self.d_buttons = [
            ttk.Button(bf, text=tr("Edit"), style="Accent.TButton", command=self.edit_selected),
            ttk.Button(bf, text=tr("Done / Not done"), command=self.toggle_done),
            ttk.Button(bf, text=tr("Duplicate"), command=self.duplicate_selected),
        ]
        for i, b in enumerate(self.d_buttons):
            b.pack(side="left", padx=(0 if i == 0 else 6, 0))
        self.d_delete = ttk.Button(bf, text=tr("Delete"), command=self.delete_selected)
        self.d_delete.pack(side="right")
        self.d_buttons.append(self.d_delete)

    def _bind_keys(self):
        r = self.root
        r.bind_all("<Control-n>", lambda e: self.new_memo())
        r.bind_all("<Control-f>", lambda e: self.search_entry.focus_set())
        r.bind_all("<Control-t>", lambda e: self.calendar.go_today())
        r.bind_all("<Control-comma>", lambda e: self.open_settings())

        def typing(e):
            return isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Spinbox, ttk.Combobox))

        r.bind("<Delete>", lambda e: None if typing(e) else self.delete_selected())
        r.bind("<Return>", lambda e: None if typing(e) else self.edit_selected())
        r.bind("<Up>", lambda e: None if typing(e) else self._move_sel(-1))
        r.bind("<Down>", lambda e: None if typing(e) else self._move_sel(1))
        r.bind("<space>", lambda e: None if typing(e) else self.toggle_done())

    def _marks(self, d: date) -> list:
        out = []
        for m in self.store.on_date(d):
            done = m.is_done(d)
            if done and not self.show_done.get():
                continue
            label = m.title if m.all_day or not m.start_time else f"{m.start_time} {m.title}"
            out.append((label, m.priority, done))
        return out

    # ==================================================================
    # Refreshing
    # ==================================================================
    def refresh_all(self):
        self.calendar.refresh()
        self.refresh_list()
        self._update_status()

    def _on_date_selected(self, d: date):
        self.selected_date = d
        if self.view_mode.get() != "day":
            self.view_mode.set("day")
        self.refresh_list()

    def _rows(self) -> list[tuple[Memo, date]]:
        mode = self.view_mode.get()
        if mode == "day":
            d = self.selected_date
            rows = [(m, d) for m in self.store.on_date(d)]
        elif mode == "upcoming":
            today = date.today()
            end = today + timedelta(days=int(self.settings["upcoming_days"]))
            rows = []
            for m in self.store.all():
                for d in m.occurrences_between(today, end):
                    rows.append((m, d))
        else:
            rows = [(m, m.base_date) for m in self.store.all()]
        q = self.search_var.get().strip().lower()
        if q:
            rows = [(m, d) for m, d in rows if q in m.title.lower() or q in m.content.lower()]
        if not self.show_done.get():
            rows = [(m, d) for m, d in rows if not m.is_done(d)]
        rows.sort(key=lambda r: (r[1], not r[0].all_day, r[0].start_time or "", r[0].title))
        return rows

    def refresh_list(self):
        if not hasattr(self, "list_frame"):
            return
        mode = self.view_mode.get()
        if mode == "day":
            title = date_label(self.selected_date)
        elif mode == "upcoming":
            title = tr("Next {n} days", n=self.settings["upcoming_days"])
        else:
            title = tr("All memos")
        if self.search_var.get().strip():
            title += "  " + tr("(filtered)")
        rows = self._rows()
        self.list_title.config(text=title)
        self.list_count.config(text=tr("1 memo") if len(rows) == 1 else tr("{n} memos", n=len(rows)))

        inner = self.list_frame.inner
        for w in inner.winfo_children():
            w.destroy()
        self.cards = {}
        self.order = []
        if not rows:
            msg = tr("Nothing planned") if mode == "day" else tr("No memos to show")
            box = tk.Frame(inner, bg=C["bg"], pady=60)
            box.pack(fill="x")
            tk.Label(box, text=msg, bg=C["bg"], fg=C["muted"], font="AppTitle").pack()
            tk.Label(box, text=tr("Click “+ New memo” or double-click a day in the calendar"),
                     bg=C["bg"], fg=C["faint"], font="AppSmall").pack(pady=(6, 0))
        last_date = None
        for m, d in rows:
            if mode != "day" and d != last_date:
                tk.Label(inner, text=date_label(d), bg=C["bg"], fg=C["accent"] if d == date.today() else C["muted"],
                         font="AppBold", anchor="w").pack(fill="x", pady=(10 if last_date else 0, 4))
                last_date = d
            self._make_card(inner, m, d)
        if self.sel_key not in self.cards:
            self.sel_key = None
        self._paint_selection()
        self._update_detail()
        self.calendar.refresh()

    def _make_card(self, parent, m: Memo, d: date):
        key = f"{m.id}|{d.isoformat()}"
        done = m.is_done(d)
        pfg, _ = priority_colors(m.priority)
        bg = C["surface"]
        card = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=C["border"], cursor="hand2")
        card.pack(fill="x", pady=(0, 6))
        stripe = tk.Frame(card, bg=C["done"] if done else pfg, width=4)
        stripe.pack(side="left", fill="y")

        tcol = tk.Frame(card, bg=bg, width=78)
        tcol.pack(side="left", fill="y", padx=(12, 0), pady=10)
        tcol.pack_propagate(False)
        if m.all_day or not m.start_time:
            tk.Label(tcol, text=tr("All day"), bg=bg, fg=C["muted"], font="AppBold", anchor="w").pack(fill="x")
        else:
            tk.Label(tcol, text=m.start_time, bg=bg, fg=C["done"] if done else C["text"],
                     font="AppBold", anchor="w").pack(fill="x")
            if m.end_time:
                tk.Label(tcol, text=f"– {m.end_time}", bg=bg, fg=C["muted"], font="AppSmall",
                         anchor="w").pack(fill="x")

        main = tk.Frame(card, bg=bg)
        main.pack(side="left", fill="both", expand=True, pady=10)
        tk.Label(main, text=m.title or tr("(untitled)"), bg=bg, fg=C["done"] if done else C["text"],
                 font="AppStrike" if done else "AppTitle", anchor="w", width=1).pack(fill="x")
        meta = []
        if m.priority == "high":
            meta.append(tr("High priority"))
        if m.repeat != "none":
            meta.append(repeats()[m.repeat])
        meta.append(self._notify_summary(m, short=True))
        tk.Label(main, text=SEP.join(meta), bg=bg, fg=C["muted"], font="AppSmall",
                 anchor="w", width=1).pack(fill="x", pady=(2, 0))

        pill = tk.Label(card, text=tr("Done") if done else tr("Mark done"), font="AppSmall", padx=10, pady=3,
                        bg=C["low_soft"] if done else C["surface2"], fg=C["low"] if done else C["muted"],
                        cursor="hand2")
        pill.pack(side="right", padx=12)
        pill.bind("<Button-1>", lambda e: (self._select(key), self.toggle_done()))

        def bind_all(w):
            if w is pill:
                return
            w.bind("<Button-1>", lambda e: self._select(key))
            w.bind("<Double-Button-1>", lambda e: (self._select(key), self.edit_selected()))
            w.bind("<Button-3>", lambda e: self._context_menu(e, key))
            for c in w.winfo_children():
                bind_all(c)
        bind_all(card)
        card._bg_widgets = [card, tcol, main] + list(tcol.winfo_children()) + list(main.winfo_children())  # type: ignore
        self.cards[key] = card
        self.order.append(key)

    def _notify_summary(self, m: Memo, short: bool = False) -> str:
        s = self.settings
        if not m.notify or not s["notify_enabled"]:
            return tr("No reminders")
        db = int(m.eff(s, "days_before"))
        pre = int(m.eff(s, "pre_alert_minutes"))
        at = m.eff(s, "notify_time")
        txt = tr("Reminds at {t}", t=at) if db == 0 else tr("Reminds from {n} days before at {t}", n=db, t=at)
        if pre and m.start:
            txt += SEP + (tr("{t} before", t=fmt_minutes(pre)) if short
                          else tr("“Starting soon” {t} before", t=fmt_minutes(pre)))
        if not short:
            disp = int(m.eff(s, "display_minutes"))
            shown = tr("stays until closed") if disp == 0 else tr("shows for {t}", t=fmt_minutes(disp))
            txt += SEP + tr("{shown}, again after {t}", shown=shown, t=fmt_minutes(m.eff(s, "interval_minutes")))
        return txt

    def _select(self, key: str | None):
        self.sel_key = key
        self._paint_selection()
        self._update_detail()

    def _paint_selection(self):
        for key, card in self.cards.items():
            sel = key == self.sel_key
            bg = C["accent_soft"] if sel else C["surface"]
            card.config(highlightbackground=C["accent"] if sel else C["border"])
            for w in card._bg_widgets:  # type: ignore[attr-defined]
                try:
                    w.config(bg=bg)
                except tk.TclError:
                    pass

    def _move_sel(self, step: int):
        if not self.order:
            return
        if self.sel_key in self.order:
            i = max(0, min(len(self.order) - 1, self.order.index(self.sel_key) + step))
        else:
            i = 0
        self._select(self.order[i])
        self.list_frame.see(self.cards[self.order[i]])

    def _update_detail(self):
        cur = self._selected()
        self.d_text.config(state="normal")
        self.d_text.delete("1.0", "end")
        if not cur:
            self.d_title.config(text=tr("Select a memo to see its details here"), fg=C["muted"], font="AppBody")
            self.d_info.config(text="")
            for b in self.d_buttons:
                b.state(["disabled"])
        else:
            m, d = cur
            self.d_title.config(text=m.title, fg=C["text"], font="AppTitle")
            parts = [date_label(d), m.time_label(), tr("Priority: {p}", p=priorities()[m.priority])]
            if m.repeat != "none":
                rep = repeats()[m.repeat]
                if m.repeat_until:
                    rep += " " + tr("(until {d})", d=m.repeat_until)
                parts.append(rep)
            info = SEP.join(parts) + "\n" + self._notify_summary(m)
            self.d_info.config(text=info)
            self.d_text.insert("1.0", m.content or tr("(no notes)"))
            for b in self.d_buttons:
                b.state(["!disabled"])
        self.d_text.config(state="disabled")

    def _update_status(self):
        if not hasattr(self, "status"):
            return
        parts = []
        if not self.settings["notify_enabled"]:
            dot, head = C["faint"], tr("Notifications: off")
        elif self.alerts.is_paused():
            pu = self.alerts.paused_until
            dot = C["pre"]
            head = tr("Notifications: paused") if pu == datetime.max \
                else tr("Notifications: paused until {t}", t=f"{pu:%H:%M}")
        else:
            dot, head = C["low"], tr("Notifications: on")
        parts.append(head)
        vc = self.alerts.visible_count()
        if vc:
            parts.append(tr("{n} on screen", n=vc))
        nxt = self.alerts.next_events()
        if nxt:
            parts.append(tr("Next reminder {t}", t=f"{nxt:%H:%M}"))
        today = date.today()
        today_n = len([m for m in self.store.on_date(today) if not m.is_done(today)])
        parts.append(tr("Today: {n}", n=today_n))
        text = "    ·    ".join(parts)
        self.status_dot.config(fg=dot)
        self.status.config(text=text)
        self.status_right.config(text=f"v{VERSION}")
        if self.__dict__.get("tray"):
            self.tray.set_title(f"{app_title()}\n{text}")

    # ==================================================================
    # Periodic work
    # ==================================================================
    def _tick(self):
        try:
            if date.today() != self.last_day:
                self.last_day = date.today()
                self.refresh_all()
            self.alerts.tick()
            self.popups.refresh_texts()
            self.popups.raise_all()
            self._update_status()
        except Exception as e:  # noqa: BLE001  never stop the timer
            print("tick error:", e)
        self.root.after(max(2, int(self.settings["check_interval_seconds"])) * 1000, self._tick)

    # ==================================================================
    # Popup actions
    # ==================================================================
    def _on_ack(self, key):
        if key.startswith(TEST_PREFIX):
            return self._close_test(key)
        self.alerts.acknowledge(key)
        self._update_status()

    def _on_snooze(self, key, minutes):
        if key.startswith(TEST_PREFIX):
            return self._close_test(key)
        self.alerts.snooze(key, minutes)
        self._update_status()

    def _on_complete(self, key):
        if key.startswith(TEST_PREFIX):
            return self._close_test(key)
        self.alerts.complete(key)
        self.refresh_list()
        self._update_status()

    def _close_test(self, key):
        p = self.test_popups.pop(key, None)
        if p:
            self.popups.hide(p)

    def test_popup(self, override_values: dict | None):
        backup = dict(self.settings.values)
        if override_values:
            self.settings.values.update(override_values)
        try:
            now = datetime.now()
            demo = Memo(title=tr("Test: weekly team meeting"),
                        content=tr("This is a test notification.\nRoom 3F-B · bring the printed handouts"),
                        date=date.today().isoformat(), all_day=False,
                        start_time=(now + timedelta(hours=1)).strftime("%H:%M"),
                        end_time=(now + timedelta(hours=2)).strftime("%H:%M"), priority="high")
            key = f"{TEST_PREFIX}{now.timestamp()}"
            alert = Alert(key, demo.id, date.today(), "day", now, now, None, 0)
            self.test_popups[key] = self.popups.show(alert, demo)
        finally:
            self.settings.values.clear()
            self.settings.values.update(backup)

    # ==================================================================
    # Memo actions
    # ==================================================================
    def _selected(self) -> tuple[Memo, date] | None:
        if not self.sel_key:
            return None
        memo_id, d = self.sel_key.split("|")
        m = self.store.get(memo_id)
        return (m, date.fromisoformat(d)) if m else None

    def _editor(self, memo, d=None):
        MemoEditor(self.root, self.settings, memo, d, on_save=self._saved, on_delete=self._deleted)

    def new_memo(self, d: date | None = None):
        d = d or (self.selected_date if self.view_mode.get() == "day" else date.today())
        self._editor(None, d)

    def open_memo(self, memo_id: str):
        m = self.store.get(memo_id)
        if m:
            self.show_window()
            self._editor(m)

    def edit_selected(self):
        cur = self._selected()
        if cur:
            self._editor(cur[0])

    def duplicate_selected(self):
        cur = self._selected()
        if not cur:
            return
        m = cur[0].copy()
        m.id = uuid.uuid4().hex
        m.title += " " + tr("(copy)")
        m.done_dates, m.acknowledged = [], []
        MemoEditor(self.root, self.settings, m, on_save=self._saved, is_new=True)

    def delete_selected(self):
        cur = self._selected()
        if not cur:
            return
        msg = tr("Delete “{title}”?", title=cur[0].title)
        if cur[0].repeat != "none":
            msg += "\n" + tr("(All repeats of this memo will be deleted.)")
        if messagebox.askyesno(tr("Delete memo"), msg, parent=self.root):
            self._deleted(cur[0])

    def toggle_done(self):
        cur = self._selected()
        if not cur:
            return
        m, d = cur
        m.set_done(d, not m.is_done(d))
        self.store.save()
        self.alerts.reset_memo(m.id)
        self.refresh_list()
        self._update_status()

    def reset_notifications(self):
        cur = self._selected()
        if not cur:
            return
        cur[0].acknowledged = []
        self.store.save()
        self.alerts.reset_memo(cur[0].id)
        messagebox.showinfo(app_title(), tr("Dismissed reminders for this memo will show again."), parent=self.root)

    def _saved(self, m: Memo):
        self.store.add(m)
        self.alerts.reset_memo(m.id)
        try:
            self.selected_date = m.base_date
            self.calendar.select(m.base_date, notify=False)
        except ValueError:
            pass
        self.sel_key = f"{m.id}|{m.date}"
        self.refresh_list()
        if self.sel_key in self.cards:
            self.list_frame.see(self.cards[self.sel_key])
        self.alerts.tick()
        self._update_status()

    def _deleted(self, m: Memo):
        self.store.delete(m.id)
        self.alerts.reset_memo(m.id)
        self.refresh_list()
        self._update_status()

    def _context_menu(self, e, key):
        self._select(key)
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label=tr("Edit"), command=self.edit_selected)
        menu.add_command(label=tr("Done / Not done"), command=self.toggle_done)
        menu.add_command(label=tr("Duplicate"), command=self.duplicate_selected)
        menu.add_command(label=tr("Bring back dismissed reminders"), command=self.reset_notifications)
        menu.add_separator()
        menu.add_command(label=tr("Delete"), command=self.delete_selected)
        menu.tk_popup(e.x_root, e.y_root)

    # ==================================================================
    # Pausing
    # ==================================================================
    def pause(self, minutes):
        self.alerts.pause(minutes)
        self._update_status()

    def resume(self):
        self.alerts.resume()
        self.alerts.tick()
        self._update_status()

    # ==================================================================
    # Settings
    # ==================================================================
    def open_settings(self):
        SettingsDialog(self.root, self.settings, self._apply_settings, self.test_popup)

    def _apply_settings(self, vals: dict):
        old_autostart = self.settings["autostart"]
        old_lang = self.settings["language"]
        self.settings.values.update(vals)
        self.settings.save()
        set_language(self.settings["language"])
        if winutil.IS_WIN and (vals["autostart"] != old_autostart or vals["autostart"]):
            if not winutil.set_autostart(vals["autostart"]):
                messagebox.showwarning(app_title(), tr("Could not change the auto-start setting."), parent=self.root)
        self.alerts._hide_all()  # re-show reminders with the new look
        self._build_ui()
        style_titlebar(self.root)
        if vals["language"] != old_lang and self.tray:  # rebuild the tray menu in the new language
            self.tray.stop()
            self.has_tray = self._start_tray()

    # ==================================================================
    # Files
    # ==================================================================
    def export_data(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                            initialfile=f"memos_{date.today():%Y%m%d}.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            self.store.export_to(path)
            messagebox.showinfo(app_title(), tr("Export complete."), parent=self.root)

    def import_data(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            n = self.store.import_from(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(app_title(), tr("Could not import the file.") + f"\n{e}", parent=self.root)
            return
        self.alerts._hide_all()
        self.refresh_all()
        messagebox.showinfo(app_title(), tr("Imported {n} memos.", n=n), parent=self.root)

    def open_data_dir(self):
        d = str(data_dir())
        if sys.platform == "win32":
            os.startfile(d)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", d])

    def show_help(self):
        messagebox.showinfo(tr("How to use"), JA["__help__"] if is_ja() else HELP_TEXT, parent=self.root)

    # ==================================================================
    # Window
    # ==================================================================
    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_close(self):
        self._save_geometry()
        if self.settings["minimize_to_tray"]:
            if self.has_tray:
                self.root.withdraw()
                if not self.settings.get("tray_hint_shown"):
                    self.settings["tray_hint_shown"] = True
                    self.settings.save()
                    self.tray.notify(tr("Still running in the tray. Right-click the tray icon to quit."))
            else:
                self.root.iconify()
        else:
            self.quit()

    def _save_geometry(self):
        try:
            if self.root.state() == "normal":
                self.settings["window_geometry"] = self.root.geometry()
                self.settings.save()
        except tk.TclError:
            pass

    def quit(self):
        if self.root.state() == "withdrawn":
            self.show_window()
        if not messagebox.askyesno(app_title(), tr("Reminders will stop while the app is closed. Quit anyway?"),
                                   parent=self.root):
            return
        self._save_geometry()
        self.store.save()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


HELP_TEXT = """■ Adding memos
  Double-click a day in the calendar, or click “+ New memo” (Ctrl+N).

■ How reminders work (default settings)
  From 7:00 on the day, a reminder appears at the bottom right.
  It stays for 5 minutes, hides, and comes back 5 minutes later — until you dismiss it.
  Memos with a start time also get a “Starting soon” alert 15 minutes before.

■ Reminder buttons
  Got it / ×  … stop reminding me today
  In 10 min / ▾  … snooze
  Mark done  … complete the memo and stop reminders
  Click the title  … open the memo

■ Keyboard
  Ctrl+N new · Ctrl+F search · Ctrl+T today · ↑↓ select
  Enter edit · Space done · Delete remove

■ Settings
  “Settings” changes the defaults, language and theme (light/dark).
  Each memo's “Notifications” tab can override them for that memo.

■ Running in the background
  Closing the window keeps the app in the tray so reminders still appear.
  To quit completely use File → Quit (or the tray menu)."""
