"""Verify the built EXE's own native window: launch, minimize, close and hotkey cleanup.

Only targets windows belonging to the process started by this script. Does not
send input, capture the user's desktop, or terminate other application instances.
"""

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('This check requires Windows')
    exe = args.executable.resolve(strict=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]

    def keys_free():
        result = {}
        for index, letter in enumerate('AR', 701):
            available = bool(user.RegisterHotKey(None, index, 0x4003, ord(letter)))
            result[letter] = available
            if available:
                user.UnregisterHotKey(None, index)
        return result

    def main_window(pid):
        found = []

        @callback_type
        def visit(hwnd, _):
            process = wintypes.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(process))
            if process.value == pid and user.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(256)
                user.GetWindowTextW(hwnd, title, len(title))
                if title.value == 'ScreenLite · 轻巧记录':
                    found.append(hwnd)
            return True

        user.EnumWindows(visit, 0)
        return found[0] if found else None

    before = keys_free()
    evidence = []
    for run in range(2):
        existing_settings = (exe.parent / 'data' / 'settings.json').exists()
        start = time.monotonic()
        process = subprocess.Popen([str(exe)], cwd=exe.parent)
        hwnd = None
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and process.poll() is None:
                hwnd = main_window(process.pid)
                if hwnd:
                    break
                time.sleep(0.1)
            if not hwnd or user.IsIconic(hwnd):
                raise RuntimeError('EXE did not show a normal main window')
            launch_seconds = round(time.monotonic() - start, 2)
            user.PostMessageW(hwnd, 0x0112, 0xF020, 0)  # WM_SYSCOMMAND / SC_MINIMIZE
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not user.IsIconic(hwnd):
                time.sleep(0.05)
            if not user.IsIconic(hwnd) or process.poll() is not None:
                raise RuntimeError('Minimize did not preserve the running process')
            during = keys_free()
            if any(before[key] and during[key] for key in before):
                raise RuntimeError('Expected global shortcut was not registered while minimized')
            user.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE on our exact process window.
            code = process.wait(timeout=15)
            if code:
                raise RuntimeError(f'EXE close exit code: {code}')
            after = keys_free()
            if after != before:
                raise RuntimeError('Global shortcut registration was not restored after exit')
            evidence.append({'run': run + 1, 'existing_settings': existing_settings,
                             'main_window_visible': True, 'launch_seconds': launch_seconds,
                             'minimized_process_alive': True, 'exit_code': code,
                             'shortcuts_available_before': before,
                             'shortcuts_available_minimized': during,
                             'shortcuts_restored_after_close': after})
        finally:
            if process.poll() is None:
                if hwnd:
                    user.PostMessageW(hwnd, 0x0010, 0, 0)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Only the test process this script owns, never a pre-existing instance.
                    process.terminate()
                    process.wait(timeout=5)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
