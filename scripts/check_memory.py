"""Windows-only, isolated synthetic 4K capture lifecycle memory measurement.

Does not grab the desktop, change the clipboard, trim the working set or record
user data. Run from the project venv; --source-root can compare a prior checkout.
"""

import argparse
import ctypes
from ctypes import wintypes
import gc
import json
from pathlib import Path
import sys
import tempfile


class MemoryCounters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
            'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage',
        )
    ]


def memory_mib():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'private_mib': round(counters.PrivateUsage / 1024**2, 2),
            'working_set_mib': round(counters.WorkingSetSize / 1024**2, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cycles', type=int, default=30)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.cycles < 1:
        parser.error('--cycles must be positive')
    if sys.platform != 'win32':
        parser.error('Memory counters require Windows')
    sys.path.insert(0, str(args.source_root / 'src'))
    from PIL import Image
    from PySide6.QtCore import QCoreApplication, QEvent, QRect
    from PySide6.QtWidgets import QApplication
    from screenlite import app as application
    from screenlite.geometry import Rect
    from screenlite.ui.dialogs import ImageDialog, SettingsDialog
    from screenlite.ui.selection import SelectionOverlay
    from screenlite.ui.toolbars import ScreenshotToolbar

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    application.Controller.show_window = lambda self: None
    SelectionOverlay.show = lambda self: None
    application.monitor_bounds = lambda: {s.name(): Rect(0, 0, 3840, 2160) for s in app.screens()}
    application.capture_monitor = lambda bounds: Image.new('RGB', (bounds.width, bounds.height), '#146A5A')
    modal_samples = []

    def toolbar_exec(toolbar):
        modal_samples.append(memory_mib())
        return 0

    ScreenshotToolbar.exec = toolbar_exec
    ImageDialog.exec = lambda self: 0
    SettingsDialog.exec = lambda self: 0

    def settle():
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        gc.collect()

    with tempfile.TemporaryDirectory(prefix='screenlite-memory-') as folder:
        controller = application.Controller(app, Path(folder), enable_hotkeys=False)
        controller.tray.hide()
        controller.settings['copy_after_capture'] = False
        capture_samples, settled_samples = [], []
        for cycle in range(args.cycles + 5):
            controller.state = 'selecting'
            controller._capture_screens('capture')
            capture_samples.append(memory_mib())
            screen = app.screens()[0]
            # Half-width/half-height selection: 1920 x 1080 out of a 4K desktop.
            selection = QRect(0, 0, screen.geometry().width() // 2,
                              round(1080 / (3840 / screen.geometry().width())))
            controller.overlays[0].selection = selection
            controller._selected(screen.name(), selection, 'capture')
            controller.state = 'selecting'
            controller._capture_screens('capture')
            controller.cancel_selection()
            controller.configure()
            settle()
            settled_samples.append(memory_mib())
        retained_settings = len(controller.window.findChildren(SettingsDialog))
        controller.shutdown()
        settle()
        result = {
            'source_root': str(args.source_root.resolve()), 'synthetic_desktop': '3840x2160 per monitor',
            'warmup_cycles': 5, 'measured_cycles': args.cycles,
            'after_warmup': settled_samples[4], 'after_final_cycle': settled_samples[-1],
            'private_growth_mib': round(settled_samples[-1]['private_mib'] - settled_samples[4]['private_mib'], 2),
            'capture_private_median_mib': sorted(s['private_mib'] for s in capture_samples[5:])[args.cycles // 2],
            'export_private_median_mib': sorted(s['private_mib'] for s in modal_samples[5:])[args.cycles // 2],
            'retained_settings_dialogs': retained_settings,
            'after_shutdown': memory_mib(), 'settled_samples': settled_samples,
        }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
