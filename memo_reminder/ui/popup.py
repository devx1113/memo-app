"""Reminder popups shown in a corner of the screen (card style)."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable

from ..i18n import app_title, fmt_date, fmt_minutes, tr
from ..models import Memo
from ..scheduler import Alert
from .. import winutil
from .theme import C, priority_colors, resource_path, round_corners

def alert_heading(alert: Alert, now: datetime | None = None) -> str:
    now = now or datetime.now()
    if alert.kind == "pre" and alert.event_start:
        mins = max(0, int((alert.event_start - now).total_seconds() // 60) + 1)
        return tr("Starting soon · in {mins} min", mins=mins)
    if alert.days_until == 0:
        return tr("Today's event")
    if alert.days_until == 1:
        return tr("Tomorrow's event")
    return tr("In {n} days", n=alert.days_until)


def alert_text(alert: Alert, memo: Memo) -> str:
    return f"{fmt_date(alert.occ_date)}  ·  {memo.time_label()}"


def snooze_label(m: int) -> str:
    return tr("In {t}", t=fmt_minutes(m))


class PopupManager:
    """ポップアップの生成・積み重ね配置を担当"""

    def __init__(self, root: tk.Tk, settings):
        self.root = root
        self.settings = settings
        self.popups: list[ReminderPopup] = []
        self._icon = None
        # コールバックは App 側で設定
        self.on_ack: Callable[[str], None] = lambda k: None
        self.on_snooze: Callable[[str, int], None] = lambda k, m: None
        self.on_complete: Callable[[str], None] = lambda k: None
        self.on_open: Callable[[str], None] = lambda memo_id: None

    def small_icon(self):
        if self._icon is None:
            try:
                img = tk.PhotoImage(master=self.root, file=str(resource_path("assets/app.png")))
                self._icon = img.subsample(max(1, img.width() // 18))
            except Exception:
                self._icon = False
        return self._icon or None

    def show(self, alert: Alert, memo: Memo):
        p = ReminderPopup(self, alert, memo)
        self.popups.append(p)
        self.layout()
        p.deiconify()
        p.attributes("-topmost", True)
        round_corners(p)
        if memo.eff(self.settings, "sound"):
            winutil.play_sound(self.settings["sound_alias"], self.settings["sound_file"])
        if self.settings["native_toast"]:
            winutil.show_native_toast(f"{alert_heading(alert)}: {memo.title}",
                                      alert_text(alert, memo) + ("\n" + memo.content if memo.content else ""))
        return p

    def hide(self, popup):
        if popup in self.popups:
            self.popups.remove(popup)
        popup.destroy()
        self.layout()

    def layout(self):
        if not self.popups:
            return
        left, top, right, bottom = winutil.work_area(self.root)
        pos = self.settings["popup_position"]
        margin, gap = 16, 10
        y_cursor = None
        for p in self.popups:
            p.update_idletasks()
            w, h = p.width, p.winfo_reqheight()
            if pos == "center":
                x = (left + right - w) // 2
            elif pos.endswith("left"):
                x = left + margin
            else:
                x = right - w - margin
            if pos.startswith("top") or pos == "center":
                if y_cursor is None:
                    y_cursor = top + margin if pos.startswith("top") else (top + bottom) // 2 - h // 2
                y = y_cursor
                y_cursor += h + gap
            else:
                if y_cursor is None:
                    y_cursor = bottom - margin
                y = y_cursor - h
                y_cursor = y - gap
            p.geometry(f"{w}x{h}+{x}+{y}")

    def raise_all(self):
        for p in self.popups:
            try:
                p.lift()
                p.attributes("-topmost", True)
            except tk.TclError:
                pass

    def refresh_texts(self):
        for p in self.popups:
            p.refresh_heading()


class ReminderPopup(tk.Toplevel):
    def __init__(self, mgr: PopupManager, alert: Alert, memo: Memo):
        super().__init__(mgr.root)
        self.mgr = mgr
        self.alert = alert
        self.memo = memo
        s = mgr.settings
        if alert.kind == "pre":
            color, soft = C["pre"], C["pre_soft"]
        else:
            color, soft = priority_colors(memo.priority)
        self.color = color
        self.width = int(s["popup_width"])
        bg = C["bg"]

        self.withdraw()  # 位置が決まるまで隠しておく
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", float(s["popup_opacity"]))
        except (tk.TclError, ValueError):
            pass
        self.config(bg=C["border"], padx=1, pady=1)

        outer = tk.Frame(self, bg=bg)
        outer.pack(fill="both", expand=True)
        self.stripe = tk.Frame(outer, bg=color, width=6)
        self.stripe.pack(side="left", fill="y")
        body = tk.Frame(outer, bg=bg, padx=16, pady=12)
        body.pack(side="left", fill="both", expand=True)
        wrap = self.width - 50

        # ---- 1行目: アプリ名 + 閉じる ----
        top = tk.Frame(body, bg=bg)
        top.pack(fill="x")
        icon = mgr.small_icon()
        if icon:
            tk.Label(top, image=icon, bg=bg).pack(side="left", padx=(0, 6))
        tk.Label(top, text=app_title(), bg=bg, fg=C["muted"], font="AppSmall").pack(side="left")
        close = tk.Label(top, text="×", bg=bg, fg=C["muted"], font="AppTitle", cursor="hand2", padx=4)
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: mgr.on_ack(alert.key))
        close.bind("<Enter>", lambda e: close.config(fg=C["text"], bg=C["hover"]))
        close.bind("<Leave>", lambda e: close.config(fg=C["muted"], bg=bg))

        # ---- 種類 (チップ) ----
        self.kind_lbl = tk.Label(body, text="", bg=soft, fg=color, font="AppBold", padx=8, pady=1)
        self.kind_lbl.pack(anchor="w", pady=(10, 6))

        # ---- タイトル・日時・内容 ----
        title = tk.Label(body, text=memo.title or tr("(untitled)"), bg=bg, fg=C["text"], font="AppHeader",
                         anchor="w", justify="left", wraplength=wrap, cursor="hand2")
        title.pack(fill="x")
        title.bind("<Button-1>", lambda e: mgr.on_open(memo.id))
        tk.Label(body, text=alert_text(alert, memo), bg=bg, fg=C["muted"], font="AppBody",
                 anchor="w").pack(fill="x", pady=(2, 0))
        if memo.content.strip():
            lines = memo.content.strip().splitlines()
            snippet = "\n".join(lines[:4]) + ("\n…" if len(lines) > 4 else "")
            tk.Label(body, text=snippet, bg=bg, fg=C["text"], font="AppBody", anchor="w",
                     justify="left", wraplength=wrap).pack(fill="x", pady=(8, 0))

        # ---- ボタン ----
        btns = tk.Frame(body, bg=bg)
        btns.pack(fill="x", pady=(14, 2))
        snooze_default = int(s["snooze_minutes"])
        ttk.Button(btns, text=tr("Got it"), style="Accent.TButton",
                   command=lambda: mgr.on_ack(alert.key)).pack(side="left")
        ttk.Button(btns, text=snooze_label(snooze_default),
                   command=lambda: mgr.on_snooze(alert.key, snooze_default)).pack(side="left", padx=(6, 0))
        mb = ttk.Menubutton(btns, text="")
        menu = tk.Menu(mb, tearoff=False)
        for m in s.snooze_list():
            menu.add_command(label=tr("Remind me in {t}", t=fmt_minutes(m)), command=lambda m=m: mgr.on_snooze(alert.key, m))
        mb.config(menu=menu)
        mb.pack(side="left", padx=(2, 0))
        ttk.Button(btns, text=tr("Mark done"), command=lambda: mgr.on_complete(alert.key)).pack(side="right")

        self.update_idletasks()
        self.geometry(f"{self.width}x{self.winfo_reqheight()}")
        self.refresh_heading()
        if s["popup_flash"]:
            self.after(150, self._flash, 8)

    def refresh_heading(self):
        try:
            self.kind_lbl.config(text=alert_heading(self.alert))
        except tk.TclError:
            pass

    def _flash(self, n: int):
        try:
            if not self.winfo_exists():
                return
            on = n % 2 == 1 and n > 0
            self.config(bg=self.color if on else C["border"])
            if n > 0:
                self.after(350, self._flash, n - 1)
        except tk.TclError:
            pass
