"""Shared widgets: calendar, time/date inputs, scrollable frame."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk
from typing import Callable

from ..i18n import fmt_month_title, tr, weekday_short
from .theme import C, bind_mousewheel, priority_colors

# date -> [(タイトル, 優先度, 完了済みか), ...]
MarksFn = Callable[[date], list]


class CalendarWidget(ttk.Frame):
    """月表示カレンダー。各日にメモのタイトルをチップで表示する。"""

    MAX_CHIPS = 3

    def __init__(self, master, on_select: Callable[[date], None] | None = None,
                 on_double: Callable[[date], None] | None = None,
                 marks: MarksFn | None = None, week_start: str = "sunday", compact: bool = False):
        super().__init__(master)
        self.on_select = on_select
        self.on_double = on_double
        self.marks = marks
        self.first_wd = 6 if week_start == "sunday" else 0
        self.selected = date.today()
        self.year, self.month = self.selected.year, self.selected.month
        self.compact = compact
        self.hover: int | None = None
        self._build()
        self.refresh()

    # ------------------------------------------------------------ 構築
    def _build(self):
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 8))
        self.title_lbl = ttk.Label(head, style="Title.TLabel" if self.compact else "Header.TLabel")
        self.title_lbl.pack(side="left", padx=(2, 0))
        ttk.Button(head, text=tr("Today"), command=self.go_today).pack(side="right")
        ttk.Button(head, text="›", width=3, command=lambda: self.shift(1)).pack(side="right", padx=(0, 6))
        ttk.Button(head, text="‹", width=3, command=lambda: self.shift(-1)).pack(side="right", padx=(0, 2))

        self.grid_frame = tk.Frame(self, bg=C["border"], bd=0)
        self.grid_frame.pack(fill="both", expand=True)
        order = [(self.first_wd + i) % 7 for i in range(7)]
        self.week_labels = []
        for col, wd in enumerate(order):
            lbl = tk.Label(self.grid_frame, text=weekday_short(wd), font="AppSmall", pady=4)
            lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1 if col < 6 else 0), pady=(0, 1))
            self.week_labels.append((lbl, wd))
            self.grid_frame.columnconfigure(col, weight=1, uniform="c")
        self.cells: list[dict] = []
        for r in range(6):
            self.grid_frame.rowconfigure(r + 1, weight=1, uniform="r")
            for c in range(7):
                i = len(self.cells)
                if self.compact:
                    f = tk.Label(self.grid_frame, font="AppBody", width=4, pady=6, cursor="hand2")
                    num = f
                    bgw = [f]
                else:
                    f = tk.Frame(self.grid_frame, height=86, width=90, cursor="hand2")
                    f.pack_propagate(False)
                    head_row = tk.Frame(f)
                    head_row.pack(fill="x", padx=4, pady=(4, 2))
                    num = tk.Label(head_row, font="AppCalDay", padx=5)
                    num.pack(side="left")
                    bgw = [f, head_row]
                    self._bind_cell(head_row, i)
                    self._bind_cell(num, i)
                f.grid(row=r + 1, column=c, sticky="nsew", padx=(0, 1 if c < 6 else 0), pady=(0, 1 if r < 5 else 0))
                self._bind_cell(f, i)
                self.cells.append({"frame": f, "num": num, "chips": [], "base_bg": bgw, "bg_widgets": list(bgw)})
        self.cell_dates: list[date] = []
        bind_mousewheel(self, _MonthScroller(self))

    def _bind_cell(self, w, i):
        w.bind("<Button-1>", lambda e: self._click(i))
        w.bind("<Double-Button-1>", lambda e: self._dbl(i))
        w.bind("<Enter>", lambda e: self._set_hover(i), add="+")
        w.bind("<Leave>", lambda e: self._set_hover(None), add="+")

    # ------------------------------------------------------------ 描画
    def _days(self) -> list[date]:
        first = date(self.year, self.month, 1)
        offset = (first.weekday() - self.first_wd) % 7
        start = first - timedelta(days=offset)
        return [start + timedelta(days=i) for i in range(42)]

    def _cell_bg(self, i: int) -> str:
        d = self.cell_dates[i]
        if d == self.selected:
            return C["accent_soft"]
        if self.hover == i:
            return C["hover"]
        return C["surface"] if d.month == self.month else C["surface2"]

    def refresh(self):
        self.title_lbl.config(text=fmt_month_title(self.year, self.month))
        self.grid_frame.config(bg=C["border"])
        for lbl, wd in self.week_labels:
            lbl.config(bg=C["surface2"], fg=C["sun"] if wd == 6 else C["sat"] if wd == 5 else C["muted"])
        self.cell_dates = self._days()
        today = date.today()
        for i, (cell, d) in enumerate(zip(self.cells, self.cell_dates)):
            in_month = d.month == self.month
            wd = d.weekday()
            fg = C["sun"] if wd == 6 else C["sat"] if wd == 5 else C["text"]
            if not in_month:
                fg = C["outside"]
            bg = self._cell_bg(i)
            num = cell["num"]
            if self.compact:
                if d == today:
                    num.config(text=str(d.day), bg=C["accent"], fg=C["accent_fg"], font="AppBold")
                else:
                    num.config(text=str(d.day), bg=bg, fg=fg, font="AppBold" if d == self.selected else "AppBody")
                cell["bg_widgets"] = [] if d == today else [num]
                continue
            for w in cell["base_bg"]:
                w.config(bg=bg)
            if d == today:
                num.config(text=str(d.day), bg=C["accent"], fg=C["accent_fg"], font="AppBold")
            else:
                num.config(text=str(d.day), bg=bg, fg=fg, font="AppBold" if d == self.selected else "AppCalDay")
            for chip in cell["chips"]:
                chip.destroy()
            cell["chips"] = []
            bgw = list(cell["base_bg"]) + ([] if d == today else [num])
            items = self.marks(d) if self.marks else []
            for title, prio, done in items[:self.MAX_CHIPS]:
                pfg, pbg = priority_colors(prio)
                chip = tk.Label(cell["frame"], text=title, anchor="w", padx=5, width=1,
                                font="AppSmallStrike" if done else "AppSmall",
                                bg=C["surface2"] if done else pbg, fg=C["done"] if done else pfg)
                chip.pack(fill="x", padx=4, pady=(0, 2))
                self._bind_cell(chip, i)
                cell["chips"].append(chip)
            if len(items) > self.MAX_CHIPS:
                more = tk.Label(cell["frame"], text=tr("+{n} more", n=len(items) - self.MAX_CHIPS), anchor="w",
                                padx=5, width=1, font="AppSmall", bg=bg, fg=C["muted"])
                more.pack(fill="x", padx=4)
                self._bind_cell(more, i)
                cell["chips"].append(more)
                bgw.append(more)
            cell["bg_widgets"] = bgw

    def _set_hover(self, i):
        old, self.hover = self.hover, i
        for j in {old, i} - {None}:
            if j < len(self.cell_dates):
                bg = self._cell_bg(j)
                for w in self.cells[j]["bg_widgets"]:
                    w.config(bg=bg)

    # ------------------------------------------------------------ 操作
    def shift(self, months: int):
        m = self.month - 1 + months
        self.year += m // 12
        self.month = m % 12 + 1
        self.refresh()

    def go_today(self):
        self.select(date.today())

    def select(self, d: date, notify: bool = True):
        self.selected = d
        self.year, self.month = d.year, d.month
        self.refresh()
        if notify and self.on_select:
            self.on_select(d)

    def _click(self, i):
        self.select(self.cell_dates[i])

    def _dbl(self, i):
        if self.on_double:
            self.on_double(self.cell_dates[i])


class _MonthScroller:
    """bind_mousewheel 用: ホイールで月を切り替える"""

    def __init__(self, cal: CalendarWidget):
        self.cal = cal

    def yview(self):
        return (0.5, 0.5)

    def yview_scroll(self, n, what):
        self.cal.shift(1 if n > 0 else -1)


class ScrollFrame(ttk.Frame):
    """縦スクロールできるフレーム。中身は self.inner に配置する。"""

    def __init__(self, master, bg_key: str = "bg"):
        super().__init__(master)
        self.bg_key = bg_key
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=C[bg_key])
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=C[bg_key])
        self.win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        bind_mousewheel(self, self.canvas)

    def recolor(self):
        self.canvas.config(bg=C[self.bg_key])
        self.inner.config(bg=C[self.bg_key])

    def to_top(self):
        self.canvas.yview_moveto(0)

    def see(self, widget):
        self.update_idletasks()
        total = max(1, self.inner.winfo_height())
        y = widget.winfo_y()
        h = self.canvas.winfo_height()
        top, bottom = self.canvas.yview()
        if y / total < top or (y + widget.winfo_height()) / total > bottom:
            self.canvas.yview_moveto(max(0, (y - h / 3) / total))


class TimeEntry(ttk.Frame):
    """HH:MM 入力"""

    def __init__(self, master, value: str = "", minute_step: int = 5):
        super().__init__(master)
        self.h = tk.StringVar()
        self.m = tk.StringVar()
        self.hs = ttk.Spinbox(self, from_=0, to=23, width=3, wrap=True, textvariable=self.h, format="%02.0f")
        self.hs.pack(side="left")
        ttk.Label(self, text=" : ").pack(side="left")
        self.ms = ttk.Spinbox(self, from_=0, to=59, width=3, wrap=True, textvariable=self.m,
                              format="%02.0f", increment=minute_step)
        self.ms.pack(side="left")
        self.set(value)

    def set(self, value: str):
        if value and ":" in value:
            h, m = value.split(":")
            self.h.set(f"{int(h):02d}")
            self.m.set(f"{int(m):02d}")
        else:
            self.h.set("09")
            self.m.set("00")

    def get(self) -> str:
        h = int(self.h.get())
        m = int(self.m.get())
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return f"{h:02d}:{m:02d}"

    def set_state(self, state: str):
        self.hs.config(state=state)
        self.ms.config(state=state)


class DateEntry(ttk.Frame):
    """YYYY-MM-DD 入力 + カレンダーから選択"""

    def __init__(self, master, value: str = "", week_start: str = "sunday", allow_empty: bool = False):
        super().__init__(master)
        self.var = tk.StringVar(value=value)
        self.week_start = week_start
        self.entry = ttk.Entry(self, textvariable=self.var, width=12)
        self.entry.pack(side="left")
        self.btn = ttk.Button(self, text=tr("Pick…"), command=self._pick)
        self.btn.pack(side="left", padx=(4, 0))
        if allow_empty:
            self.clear_btn = ttk.Button(self, text=tr("Clear"), command=lambda: self.var.set(""))
            self.clear_btn.pack(side="left", padx=(4, 0))

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, v: str):
        self.var.set(v)

    def set_state(self, state: str):
        self.entry.config(state=state)
        self.btn.config(state=state)
        if hasattr(self, "clear_btn"):
            self.clear_btn.config(state=state)

    def _pick(self):
        from .theme import style_titlebar
        top = tk.Toplevel(self)
        top.title(tr("Choose a date"))
        top.transient(self.winfo_toplevel())
        top.resizable(False, False)
        top.configure(bg=C["bg"])

        def choose(d: date):
            self.var.set(d.isoformat())
            top.destroy()

        cal = CalendarWidget(top, week_start=self.week_start, compact=True)
        try:
            cal.select(date.fromisoformat(self.get()), notify=False)
        except ValueError:
            pass
        cal.on_select = choose
        cal.pack(padx=12, pady=12)
        top.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        top.geometry(f"+{x}+{y}")
        style_titlebar(top)
        top.grab_set()
