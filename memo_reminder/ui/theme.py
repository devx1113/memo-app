"""外観テーマ: Windows 11 風 (Sun Valley) のライト/ダーク、配色、フォント"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, ttk

try:
    import sv_ttk
except Exception:  # 無くても標準テーマで動く
    sv_ttk = None

IS_WIN = sys.platform == "win32"

LIGHT = {
    "bg": "#fafafa", "surface": "#ffffff", "surface2": "#f3f3f3", "border": "#e5e5e5",
    "text": "#1c1c1c", "muted": "#6b6b6b", "faint": "#a8a8a8",
    "accent": "#005fb8", "accent_fg": "#ffffff", "accent_soft": "#e5effa", "hover": "#f5f5f5",
    "sun": "#c42b1c", "sat": "#0f6cbd", "outside": "#c4c4c4",
    "high": "#c42b1c", "high_soft": "#fde7e9",
    "normal": "#005fb8", "normal_soft": "#e5effa",
    "low": "#107c10", "low_soft": "#e6f4e6",
    "pre": "#d16900", "pre_soft": "#fff1e0",
    "done": "#9a9a9a",
}
DARK = {
    "bg": "#1c1c1c", "surface": "#2b2b2b", "surface2": "#242424", "border": "#3b3b3b",
    "text": "#f3f3f3", "muted": "#a6a6a6", "faint": "#6e6e6e",
    "accent": "#57c8ff", "accent_fg": "#002b45", "accent_soft": "#1e3a50", "hover": "#323232",
    "sun": "#ff99a4", "sat": "#8cc8ff", "outside": "#555555",
    "high": "#ff99a4", "high_soft": "#4a2a2e",
    "normal": "#8cc8ff", "normal_soft": "#1e3a50",
    "low": "#8fd18f", "low_soft": "#24402a",
    "pre": "#ffb35c", "pre_soft": "#4a3519",
    "done": "#777777",
}

# 現在の配色 (apply_theme で更新される)
C: dict = dict(LIGHT)
CURRENT = {"mode": "light"}


def resource_path(rel: str) -> Path:
    """PyInstaller で exe 化したときも同梱ファイルを見つけられるようにする"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base / rel


def system_prefers_dark() -> bool:
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return False


def resolve_mode(setting: str) -> str:
    if setting == "system":
        return "dark" if system_prefers_dark() else "light"
    return "dark" if setting == "dark" else "light"


# ---------------------------------------------------------------- フォント
FONT_NAMES = ("AppBody", "AppSmall", "AppBold", "AppTitle", "AppHeader", "AppDisplay", "AppCalDay", "AppSmallStrike", "AppStrike")


_FONTS: dict = {}  # 参照を保持しないと名前付きフォントが削除される


def _ensure_fonts(root):
    for n in FONT_NAMES:
        if n not in _FONTS:
            _FONTS[n] = tkfont.Font(root, name=n, exists=False)


def apply_fonts(root, family: str, size: int):
    _ensure_fonts(root)
    spec = {
        "AppBody": (size, "normal"), "AppSmall": (max(7, size - 1), "normal"),
        "AppBold": (size, "bold"), "AppTitle": (size + 3, "bold"),
        "AppHeader": (size + 6, "bold"), "AppDisplay": (size + 10, "bold"),
        "AppCalDay": (size, "normal"),
        "AppSmallStrike": (max(7, size - 1), "normal"), "AppStrike": (size + 1, "bold"),
    }
    for n, (sz, wt) in spec.items():
        _FONTS[n].configure(family=family, size=sz, weight=wt, overstrike=n.endswith("Strike"))
    # 標準フォントと Sun Valley テーマのフォントも揃える
    for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkFixedFont"):
        try:
            tkfont.nametofont(n).configure(family=family, size=size)
        except tk.TclError:
            pass
    sv = {"SunValleyCaptionFont": size - 1, "SunValleyBodyFont": size, "SunValleyBodyStrongFont": size,
          "SunValleyBodyLargeFont": size + 3, "SunValleySubtitleFont": size + 5, "SunValleyTitleFont": size + 10}
    for n, sz in sv.items():
        try:
            f = tkfont.nametofont(n)
            f.configure(family=family, size=sz)
        except tk.TclError:
            pass


# ---------------------------------------------------------------- テーマ
def apply_theme(root: tk.Tk, setting: str, family: str, size: int):
    mode = resolve_mode(setting)
    CURRENT["mode"] = mode
    C.clear()
    C.update(DARK if mode == "dark" else LIGHT)
    style = ttk.Style(root)
    if sv_ttk is not None:
        sv_ttk.set_theme(mode, root)
        # sv_ttk は <<ThemeChanged>> のたびに tk_setPalette で全ウィジェットの色を塗り替えるため、
        # 独自配色が消えないよう、ここで一度だけ同期的に適用してバインドを外す
        try:
            root.tk.call("configure_colors")
            root.bind_class("Tk", "<<ThemeChanged>>", "")
        except tk.TclError:
            pass
    else:
        for t in ("vista", "clam"):
            if t in style.theme_names():
                style.theme_use(t)
                break
    apply_fonts(root, family, size)

    lh = tkfont.nametofont("AppBody").metrics("linespace")
    style.configure("Treeview", rowheight=int(lh * 1.9))
    style.configure("Muted.TLabel", foreground=C["muted"])
    style.configure("Small.TLabel", foreground=C["muted"], font="AppSmall")
    style.configure("Title.TLabel", font="AppTitle")
    style.configure("Header.TLabel", font="AppHeader")
    style.configure("Display.TLabel", font="AppDisplay")
    style.configure("Section.TLabel", font="AppBold", foreground=C["accent"])
    style.configure("Bold.TLabel", font="AppBold")
    # 面 (カード) 用
    style.configure("Surface.TFrame", background=C["surface"])
    style.configure("Surface.TLabel", background=C["surface"])
    style.configure("SurfaceMuted.TLabel", background=C["surface"], foreground=C["muted"])
    style.configure("SurfaceTitle.TLabel", background=C["surface"], font="AppTitle")
    style.configure("SurfaceHeader.TLabel", background=C["surface"], font="AppHeader")
    style.configure("Surface.TCheckbutton", background=C["surface"])
    root.configure(bg=C["bg"])
    root.option_add("*Menu.font", "AppBody")
    style_titlebar(root)
    return mode


def style_titlebar(win):
    """Windows 10/11: タイトルバーをダークに / Windows 11: 角を丸く"""
    if not IS_WIN:
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        dark = ctypes.c_int(1 if CURRENT["mode"] == "dark" else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (新旧)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark), 4) == 0:
                break
    except Exception:
        pass


def round_corners(win):
    """Windows 11 で枠なしウィンドウの角を丸くする"""
    if not IS_WIN:
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
    except Exception:
        pass


def set_window_icon(win):
    """ウィンドウ/タスクバーのアイコン"""
    try:
        ico = resource_path("assets/app.ico")
        if IS_WIN and ico.exists():
            win.iconbitmap(default=str(ico))
            return
        png = resource_path("assets/app.png")
        if png.exists():
            img = tk.PhotoImage(file=str(png))
            win._app_icon = img  # GC 防止
            win.iconphoto(True, img)
    except Exception:
        pass


def priority_colors(priority: str) -> tuple[str, str]:
    return C.get(priority, C["normal"]), C.get(priority + "_soft", C["normal_soft"])


def bind_mousewheel(widget, canvas):
    """ホイールスクロール (マウスが乗っている間だけ有効)"""
    def on_wheel(e):
        if e.num == 4:
            delta = -1
        elif e.num == 5:
            delta = 1
        else:
            delta = -1 if e.delta > 0 else 1
        first, last = canvas.yview()
        if (first > 0 or delta > 0) and (last < 1 or delta < 0):
            canvas.yview_scroll(delta * 3, "units")

    def enter(_):
        widget.bind_all("<MouseWheel>", on_wheel)
        widget.bind_all("<Button-4>", on_wheel)
        widget.bind_all("<Button-5>", on_wheel)

    def leave(_):
        widget.unbind_all("<MouseWheel>")
        widget.unbind_all("<Button-4>")
        widget.unbind_all("<Button-5>")

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")
