"""Memo Reminder - launcher.
Run with pythonw (double-click) so no console window appears.
  --minimized : start hidden in the tray (used by auto-start)
"""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo_reminder import winutil  # noqa: E402
from memo_reminder.config import Settings  # noqa: E402
from memo_reminder.i18n import set_language  # noqa: E402
from memo_reminder.models import MemoStore  # noqa: E402


def main():
    app_ref = {}

    def activate():  # a second launch brings the running window to the front
        app = app_ref.get("app")
        if app:
            app.post(app.show_window)

    single = winutil.SingleInstance(activate)
    if not single.acquire():
        return  # already running

    winutil.enable_dpi_awareness()
    winutil.set_app_user_model_id()

    settings = Settings()
    set_language(settings["language"])
    store = MemoStore()
    root = tk.Tk()
    root.withdraw()  # hidden until the theme is applied (no flicker)

    from memo_reminder.ui.main_window import App
    minimized = "--minimized" in sys.argv or settings["start_minimized"]
    app_ref["app"] = App(root, settings, store, start_minimized=minimized)
    if not minimized:
        root.deiconify()
        from memo_reminder.ui.theme import style_titlebar
        style_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
