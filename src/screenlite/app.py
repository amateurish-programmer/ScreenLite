"""Application coordinator: tray, hotkeys and capture lifecycle."""
import argparse
import logging
import sys
from datetime import datetime
from uuid import uuid4
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QElapsedTimer, QLockFile, QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QMenu, QMessageBox, QSystemTrayIcon, QVBoxLayout

from screenlite.capture import capture_monitor, image_pixmap
from screenlite.config import SettingsStore
from screenlite.geometry import Rect, logical_to_physical
from screenlite.platform_win import Hotkeys, enable_dpi_awareness, monitor_bounds


def app_root() -> Path:
    return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor('transparent'))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor('#177c6b'))
    painter.setPen(QPen(QColor('#177c6b'), 1))
    painter.drawRoundedRect(2, 2, 60, 60, 16, 16)
    painter.setPen(QPen(QColor('#ffffff'), 4))
    for x, y, dx, dy in ((18, 18, 10, 10), (46, 18, -10, 10),
                         (18, 46, 10, -10), (46, 46, -10, -10)):
        painter.drawLine(x, y, x + dx, y)
        painter.drawLine(x, y, x, y + dy)
    painter.end()
    return QIcon(pixmap)


class Controller(QObject):
    def __init__(self, app, root: Path, enable_hotkeys: bool = True):
        super().__init__()
        from screenlite.ui.dialogs import MainWindow
        self.app, self.root = app, Path(root)
        self.store = SettingsStore(self.root)
        self.settings = self.store.load()
        self.state = 'idle'
        self.overlays = []
        self.frames = {}
        self._closing_overlays = False
        self.hotkeys = None
        self.record_job = None
        self.countdown = None
        self._quit_after_record = False
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._update_recording)
        self._elapsed = QElapsedTimer()
        self.window = MainWindow()
        self.window.shortcut_label.setText(f"{self.settings['screenshot_hotkey']} 截图    ·    {self.settings['record_hotkey']} 录屏")
        self.window.setWindowIcon(app_icon())
        self.window.capture_requested.connect(lambda: self.begin_selection('capture'))
        self.window.record_requested.connect(self.toggle_record)
        self.window.compress_requested.connect(self.compress)
        self.window.settings_requested.connect(self.configure)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip('ScreenLite · 随手截取与记录')
        self.menu = QMenu()
        for title, callback in [('打开 ScreenLite', self.show_window), ('截图', lambda: self.begin_selection('capture')),
                                ('开始 / 停止录屏', self.toggle_record), ('压缩文件', self.compress),
                                ('打开录制素材', self.open_recordings),
                                ('设置', self.configure), ('退出', self.request_quit)]:
            action = QAction(title, self.menu)
            action.triggered.connect(callback)
            self.menu.addAction(action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        if enable_hotkeys:
            self.hotkeys = Hotkeys(app)
            self.hotkeys.events.triggered.connect(self._hotkey)
            try:
                self.hotkeys.configure(self.settings['screenshot_hotkey'], self.settings['record_hotkey'])
            except (ValueError, OSError) as error:
                self.window.set_status(str(error))
                QTimer.singleShot(0, self.show_window)
        if self.store.warning:
            self.window.set_status(self.store.warning)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def _hotkey(self, identifier):
        if identifier == 1:
            self.begin_selection('capture')
        elif identifier == 2:
            self.toggle_record()

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def error(self, message):
        logging.error('%s', message)
        self.window.set_status(message)
        self.tray.showMessage('ScreenLite', message, QSystemTrayIcon.MessageIcon.Warning, 6000)
        self.show_window()

    def begin_selection(self, mode='capture'):
        if self.state != 'idle':
            return
        self.state = 'selecting'
        self.window.hide()
        QTimer.singleShot(220, lambda: self._capture_screens(mode))

    def _capture_screens(self, mode):
        if self.state != 'selecting':
            return
        from screenlite.ui.selection import SelectionOverlay
        try:
            native = monitor_bounds()
            for screen in self.app.screens():
                bounds = native.get(screen.name())
                if bounds is None:
                    raise RuntimeError('无法匹配显示器坐标，请重新连接显示器后重试')
                frame = capture_monitor(bounds)
                scale = bounds.width / screen.geometry().width()
                self.frames[screen.name()] = (frame, bounds, scale)
            focus = None
            for screen in self.app.screens():
                frame, bounds, scale = self.frames[screen.name()]
                overlay = SelectionOverlay(screen, image_pixmap(frame, scale), mode=mode)
                overlay.selected.connect(lambda rect, name=screen.name(): self._selected(name, rect, mode))
                overlay.cancelled.connect(self.cancel_selection)
                self.overlays.append(overlay)
                overlay.show()
                if screen.geometry().contains(QCursor.pos()):
                    focus = overlay
            if focus:
                focus.raise_()
                focus.activateWindow()
        except Exception as error:
            self.cancel_selection()
            self.error(f'无法获取屏幕：{error}')

    def _close_overlays(self):
        self._closing_overlays = True
        for overlay in self.overlays:
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
        self._closing_overlays = False

    def cancel_selection(self):
        if self._closing_overlays:
            return
        self._close_overlays()
        self.frames.clear()
        self.state = 'idle'

    def _selected(self, name, rect, mode):
        if self.state != 'selecting':
            return
        frame, bounds, scale = self.frames[name]
        local = Rect(rect.x(), rect.y(), rect.width(), rect.height())
        physical = logical_to_physical(local, bounds, scale)
        self._close_overlays()
        self.frames.clear()
        if mode == 'record':
            self.arm_recording(physical)
            return
        x, y = physical.x - bounds.x, physical.y - bounds.y
        image = frame.crop((x, y, min(frame.width, x + physical.width), min(frame.height, y + physical.height)))
        self._show_image(image)

    def _show_image(self, image):
        from screenlite.ui.dialogs import ImageDialog
        self.state = 'exporting'
        try:
            output = Path(self.settings['output_dir']) if self.settings['output_dir'] else self.root / 'exports'
            dialog = ImageDialog(image, output, self.window)
            dialog.quality_combo.setCurrentIndex(dialog.quality_combo.findData(self.settings['preset']))
            dialog.exec()
            dialog.deleteLater()
        finally:
            self.state = 'idle'

    def toggle_record(self):
        if self.state == 'recording':
            self.state = 'stopping'
            self._record_timer.stop()
            self.window.set_status('正在保存录制，请稍候…')
            self.tray.setToolTip('ScreenLite · 正在保存录制')
            self.record_job.stop_record()
        elif self.state == 'countdown':
            self._cancel_countdown()
        elif self.state == 'idle':
            from screenlite.media import find_ffmpeg
            try:
                find_ffmpeg(self.root)
                self.begin_selection('record')
            except OSError as error:
                self.error(str(error))

    def arm_recording(self, rect):
        self.state = 'countdown'
        self._record_rect = rect
        self._remaining = 3
        self.countdown = QDialog()
        self.countdown.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                                      | Qt.WindowType.Tool)
        self.countdown.setStyleSheet('QDialog{background:#173d37;border-radius:12px;} QLabel{color:white;}')
        layout = QVBoxLayout(self.countdown)
        self._countdown_label = QLabel('3')
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setStyleSheet('font-size:64px;font-weight:600;padding:10px 45px;')
        layout.addWidget(self._countdown_label)
        layout.addWidget(QLabel('准备录制 · Esc 取消'))
        self.countdown.rejected.connect(self._cancel_countdown)
        self.countdown.show()
        self.countdown.activateWindow()
        self._countdown_timer.start(1000)

    def _cancel_countdown(self):
        self._countdown_timer.stop()
        self._close_countdown()
        self.state = 'idle'
        self.window.set_status('已取消录制')

    def _close_countdown(self):
        if self.countdown:
            self.countdown.blockSignals(True)
            self.countdown.close()
            self.countdown.deleteLater()
            self.countdown = None

    def _countdown_tick(self):
        self._remaining -= 1
        if self._remaining > 0:
            self._countdown_label.setText(str(self._remaining))
        else:
            self._countdown_timer.stop()
            self._close_countdown()
            QTimer.singleShot(250, self._start_recording)

    def _start_recording(self):
        if self.state != 'countdown':
            return
        from screenlite.video import VideoJob
        self._close_countdown()
        self.state = 'starting'
        directory = self.root / 'data' / 'recordings'
        destination = directory / f'ScreenLite_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}.mkv'
        self.record_job = VideoJob(self.root, parent=self)
        self.record_job.started.connect(self._record_started)
        self.record_job.finished.connect(self._record_finished)
        self.record_job.failed.connect(self._record_failed)
        self.record_job.start_record(self._record_rect, destination, fps=self.settings['fps'])

    def _record_started(self):
        if self.state == 'stopping':
            self.record_job.stop_record()
            return
        self.state = 'recording'
        self._elapsed.start()
        self._record_timer.start(1000)
        self._update_recording()

    def _update_recording(self):
        seconds = self._elapsed.elapsed() // 1000
        self.window.set_recording(True, seconds)
        self.window.set_status('正在录制 · 使用录屏快捷键停止')
        self.tray.setToolTip(f'ScreenLite · 正在录制 {seconds // 60:02d}:{seconds % 60:02d}')

    def _release_recording(self):
        self._record_timer.stop()
        if self.record_job:
            self.record_job.deleteLater()
            self.record_job = None
        self.state = 'idle'
        self.window.set_recording(False)
        self.tray.setToolTip('ScreenLite · 随手截取与记录')

    def _record_finished(self, path):
        self._release_recording()
        if self._quit_after_record:
            self.request_quit()
        else:
            self._show_video(Path(path), recorded=True)

    def _record_failed(self, message):
        self._release_recording()
        self.error(message)
        if self._quit_after_record:
            self.request_quit()

    def _show_video(self, source, recorded=False):
        from screenlite.ui.dialogs import VideoExportDialog
        self.state = 'exporting'
        try:
            dialog = VideoExportDialog(source, self.root, self.window)
            dialog.output_directory = Path(self.settings['output_dir']) if self.settings['output_dir'] else self.root / 'exports'
            dialog.quality_combo.setCurrentIndex(dialog.quality_combo.findData(self.settings['preset']))
            dialog.exec()
            if recorded and dialog.output_path:
                # Delete only this application's known original after a successful export.
                recordings = (self.root / 'data' / 'recordings').resolve()
                if source.resolve().parent == recordings:
                    source.unlink(missing_ok=True)
            elif recorded:
                self.window.set_status('录制素材已保留，可从托盘“打开录制素材”继续导出')
            dialog.deleteLater()
        except (OSError, ValueError) as error:
            self.error(f'导出未完成，原始文件已保留：{error}')
        finally:
            self.state = 'idle'

    def open_recordings(self):
        directory = self.root / 'data' / 'recordings'
        try:
            directory.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
        except OSError as error:
            self.error(str(error))

    def compress(self):
        if self.state != 'idle':
            return
        self.state = 'choosing'
        source, _ = QFileDialog.getOpenFileName(self.window, '选择要压缩的图片或视频',
                                               self.settings['output_dir'],
                                               '图片或视频 (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mkv *.mov *.avi *.webm);;所有文件 (*)')
        self.state = 'idle'
        if not source:
            return
        if Path(source).suffix.lower() in ('.mp4', '.mkv', '.mov', '.avi', '.webm'):
            self._show_video(Path(source))
            return
        try:
            with Image.open(source) as opened:
                self._show_image(ImageOps.exif_transpose(opened).copy())
        except Exception as error:
            self.error(f'无法读取文件：{error}')

    def configure(self):
        if self.state != 'idle':
            return
        from screenlite.ui.dialogs import SettingsDialog
        self.state = 'settings'
        try:
            dialog = SettingsDialog(self.settings, self.window)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                values = dialog.values()
                previous = self.settings.copy()
                try:
                    if self.hotkeys:
                        self.hotkeys.configure(values['screenshot_hotkey'], values['record_hotkey'])
                    self.store.save(values)
                except (ValueError, OSError):
                    if self.hotkeys:
                        self.hotkeys.configure(previous['screenshot_hotkey'], previous['record_hotkey'])
                    raise
                self.settings = values
                self.window.shortcut_label.setText(f"{values['screenshot_hotkey']} 截图    ·    {values['record_hotkey']} 录屏")
                self.window.set_status('设置已保存')
        except (ValueError, OSError) as error:
            self.error(str(error))
        finally:
            self.state = 'idle'

    def request_quit(self):
        if self.state in ('starting', 'recording', 'stopping'):
            self._quit_after_record = True
            self.state = 'stopping'
            self.record_job.stop_record()
            return
        if self.state == 'countdown':
            self._cancel_countdown()
        if self.state not in ('idle', 'selecting'):
            self.error('请先完成或取消当前操作，再退出')
            return
        self.shutdown()
        self.app.quit()

    def shutdown(self):
        self._countdown_timer.stop()
        self._record_timer.stop()
        self._close_countdown()
        self.cancel_selection()
        if self.hotkeys:
            self.hotkeys.clear()
            self.app.removeNativeEventFilter(self.hotkeys)
        self.tray.hide()
        self.window.hide()


def main():
    parser = argparse.ArgumentParser(description='ScreenLite Windows capture tool')
    parser.add_argument('--show', action='store_true', help='show the main window')
    parser.add_argument('--no-hotkeys', action='store_true', help='disable global hotkeys for troubleshooting')
    parser.add_argument('--smoke-test', action='store_true', help='initialize then exit after one second')
    args = parser.parse_args()
    enable_dpi_awareness()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('ScreenLite')
    app.setQuitOnLastWindowClosed(False)
    root = app_root()
    try:
        (root / 'data').mkdir(exist_ok=True)
        lock = QLockFile(str(root / 'data' / 'screenlite.lock'))
        if not lock.tryLock(100):
            QMessageBox.information(None, 'ScreenLite', 'ScreenLite 已在运行，请使用托盘图标或快捷键。')
            return 0
        logging.basicConfig(filename=root / 'data' / 'screenlite.log', level=logging.INFO, encoding='utf-8',
                            format='%(asctime)s %(levelname)s %(message)s')
        controller = Controller(app, root, enable_hotkeys=not args.no_hotkeys)
        first_run = not controller.store.path.exists()
        if first_run:
            controller.store.save(controller.settings)
        if args.show or first_run or not QSystemTrayIcon.isSystemTrayAvailable():
            controller.show_window()
        if args.smoke_test:
            QTimer.singleShot(1000, controller.request_quit)
        app.aboutToQuit.connect(controller.shutdown)
        result = app.exec()
        lock.unlock()
        return result
    except Exception as error:
        logging.exception('Startup failed')
        QMessageBox.critical(None, 'ScreenLite', f'启动失败，请将程序解压到可写目录。\n{error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
