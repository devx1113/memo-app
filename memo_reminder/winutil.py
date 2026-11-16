"""Windows 固有の機能 (他OSでは何もしないか代替動作)"""
from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

from .config import APP_NAME
from .i18n import app_title

IS_WIN = sys.platform == "win32"
SINGLE_INSTANCE_PORT = 47613


# ---------------- 高DPI対応 ----------------
def enable_dpi_awareness() -> None:
    if not IS_WIN:
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_app_user_model_id() -> None:
    """タスクバーのアイコンを python.exe と分けるため"""
    if not IS_WIN:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)
    except Exception:
        pass


# ---------------- 作業領域 (タスクバーを除いた画面) ----------------
def work_area(root) -> tuple[int, int, int, int]:
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48


# ---------------- サウンド ----------------
def play_sound(alias: str, wav_file: str = "") -> None:
    if IS_WIN:
        try:
            import winsound
            if wav_file and Path(wav_file).exists():
                winsound.PlaySound(wav_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.PlaySound(alias or "SystemNotification",
                                   winsound.SND_ALIAS | winsound.SND_ASYNC)
            return
        except Exception:
            pass
    # 非Windows: ベル
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


# ---------------- Windows ネイティブ通知 (任意) ----------------
def native_toast_available() -> bool:
    if not IS_WIN:
        return False
    try:
        import winotify  # noqa: F401
        return True
    except ImportError:
        return False


def show_native_toast(title: str, message: str) -> None:
    if not native_toast_available():
        return

    def _run():
        try:
            from winotify import Notification
            n = Notification(app_id=app_title(), title=title, msg=message[:250], duration="long")
            n.show()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


# ---------------- 自動起動 ----------------
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller で exe 化した場合
        return f'"{sys.executable}" --minimized'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    if pyw.exists():
        exe = pyw
    script = Path(__file__).resolve().parent.parent / "main.pyw"
    return f'"{exe}" "{script}" --minimized'


def set_autostart(enabled: bool) -> bool:
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except Exception:
        return False


# ---------------- 多重起動防止 ----------------
class SingleInstance:
    """ローカルポートを使った多重起動防止。2つ目の起動時は既存ウィンドウを前面に出す。"""

    def __init__(self, on_activate):
        self.on_activate = on_activate
        self.sock: socket.socket | None = None

    def acquire(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if IS_WIN:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        except OSError:
            s.close()
            self._notify_existing()
            return False
        s.listen(1)
        self.sock = s
        threading.Thread(target=self._serve, daemon=True).start()
        return True

    def _serve(self):
        while self.sock:
            try:
                conn, _ = self.sock.accept()
                with conn:
                    if conn.recv(16).startswith(b"SHOW"):
                        self.on_activate()
            except OSError:
                break

    def _notify_existing(self):
        try:
            with socket.create_connection(("127.0.0.1", SINGLE_INSTANCE_PORT), timeout=2) as c:
                c.sendall(b"SHOW")
        except OSError:
            pass
