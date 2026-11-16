"""System tray icon (only when pystray + Pillow are available)."""
from __future__ import annotations

import threading
from typing import Callable

from ..i18n import app_title, tr

try:
    import pystray
    from PIL import Image, ImageDraw
    AVAILABLE = True
except Exception:  # ImportError など
    AVAILABLE = False


def make_icon_image(size: int = 64):
    try:
        from .theme import resource_path
        return Image.open(resource_path("assets/app.png")).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        pass
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    # メモ用紙
    d.rounded_rectangle([s * 0.12, s * 0.08, s * 0.88, s * 0.92], radius=s * 0.1, fill="#2b78e4")
    d.rectangle([s * 0.24, s * 0.30, s * 0.76, s * 0.36], fill="white")
    d.rectangle([s * 0.24, s * 0.46, s * 0.76, s * 0.52], fill="white")
    d.rectangle([s * 0.24, s * 0.62, s * 0.58, s * 0.68], fill="white")
    # ベル
    d.ellipse([s * 0.58, s * 0.58, s * 0.96, s * 0.96], fill="#f5b400")
    return img


class TrayIcon:
    """メニュー操作は post(fn) でメインスレッドへ渡す"""

    def __init__(self, post: Callable[[Callable], None], actions: dict[str, Callable],
                 is_paused: Callable[[], bool]):
        self.post = post
        self.actions = actions
        self.is_paused = is_paused
        self.icon = None

    def start(self) -> bool:
        if not AVAILABLE:
            return False
        a = self.actions

        def act(name):
            return lambda icon, item: self.post(a[name])

        menu = pystray.Menu(
            pystray.MenuItem(tr("Open"), act("show"), default=True),
            pystray.MenuItem(tr("New memo"), act("new")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(tr("Pause notifications"), pystray.Menu(
                pystray.MenuItem(tr("30 minutes"), act("pause30")),
                pystray.MenuItem(tr("1 hour"), act("pause60")),
                pystray.MenuItem(tr("3 hours"), act("pause180")),
                pystray.MenuItem(tr("Until I resume"), act("pause_inf")),
            )),
            pystray.MenuItem(tr("Resume notifications"), act("resume"), enabled=lambda item: self.is_paused()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(tr("Settings"), act("settings")),
            pystray.MenuItem(tr("Quit"), act("quit")),
        )
        try:
            self.icon = pystray.Icon("MemoReminder", make_icon_image(), app_title(), menu)
            threading.Thread(target=self.icon.run, daemon=True).start()
        except Exception:  # トレイが使えない環境では最小化で代用
            self.icon = None
            return False
        return True

    def set_title(self, text: str):
        if self.icon:
            try:
                self.icon.title = text[:120]
            except Exception:
                pass

    def notify(self, message: str):
        if self.icon:
            try:
                self.icon.notify(message, app_title())
            except Exception:
                pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
