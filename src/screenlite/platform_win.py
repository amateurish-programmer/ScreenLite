"""Small Win32 bridge. Importing this module does not claim global hotkeys."""
import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

from screenlite.geometry import Rect


def enable_dpi_awareness():
    if sys.platform == 'win32':
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass


def exclude_from_capture(window) -> bool:
    """Exclude our own HUD; hide it if Windows cannot honor the request."""
    if sys.platform != 'win32':
        return False
    user32 = ctypes.windll.user32
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    return bool(user32.SetWindowDisplayAffinity(int(window.winId()), 0x11))


def parse_hotkey(text: str) -> tuple[int, int]:
    parts = text.upper().replace(' ', '').split('+')
    modifiers = {'CTRL': 2, 'ALT': 1, 'SHIFT': 4, 'META': 8, 'WIN': 8}
    if len(parts) < 2 or any(p not in modifiers for p in parts[:-1]):
        raise ValueError('请使用 Ctrl / Alt / Shift 加字母、数字或 F1–F24')
    mods = 0x4000
    for part in parts[:-1]:
        mods |= modifiers[part]
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key)
    elif key.startswith('F') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 111 + int(key[1:])
    else:
        raise ValueError('快捷键末尾需要字母、数字或 F1–F24')
    return mods, vk


class _Events(QObject):
    triggered = Signal(int)


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.events = _Events()
        self.registered = {}
        app.installNativeEventFilter(self)

    def configure(self, screenshot: str, record: str):
        requested = {1: parse_hotkey(screenshot), 2: parse_hotkey(record)}
        if requested[1] == requested[2]:
            raise ValueError('截图和录屏不能使用相同快捷键')
        if sys.platform != 'win32':
            raise OSError('全局快捷键仅支持 Windows')
        previous = self.registered.copy()
        self.clear()
        try:
            for identifier, (mods, vk) in requested.items():
                if not ctypes.windll.user32.RegisterHotKey(None, identifier, mods, vk):
                    raise OSError('快捷键被其他程序占用，请在设置中更换')
                self.registered[identifier] = (mods, vk)
        except OSError:
            self.clear()
            for identifier, (mods, vk) in previous.items():
                if ctypes.windll.user32.RegisterHotKey(None, identifier, mods, vk):
                    self.registered[identifier] = (mods, vk)
            raise

    def clear(self):
        if sys.platform == 'win32':
            for identifier in self.registered:
                ctypes.windll.user32.UnregisterHotKey(None, identifier)
        self.registered.clear()

    def nativeEventFilter(self, event_type, message):
        if sys.platform == 'win32':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312:
                self.events.triggered.emit(int(msg.wParam))
                return True, 0
        return False, 0


def monitor_bounds() -> dict[str, Rect]:
    """Map DISPLAY device names to actual native desktop coordinates."""
    if sys.platform != 'win32':
        return {}

    class Info(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD),
                    ('szDevice', wintypes.WCHAR * 32)]

    found = {}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32 = ctypes.windll.user32
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(Info)]

    @callback_type
    def callback(handle, dc, rect, data):
        info = Info()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcMonitor
            found[info.szDevice] = Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)
        return True

    user32.EnumDisplayMonitors(None, None, callback, 0)
    return found
