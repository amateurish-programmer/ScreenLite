"""Compact tools placed next to captured content and active recordings."""

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QVBoxLayout

from .dialogs import _ImageWorker, button, file_size_text, pil_pixmap
from .theme import STYLE


class ScreenshotToolbar(QDialog):
    details_requested = Signal()
    edit_requested = Signal()
    copied = Signal()
    closed = Signal()

    def __init__(self, image, root, parent=None):
        super().__init__(parent)
        self.image = image  # Shared read-only selection, never mutate the source.
        self.root = Path(root)
        self._worker = None
        self._pending_action = None
        self._closed = False
        self.setWindowTitle('截图完成 · ScreenLite')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(490)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        row = QHBoxLayout()
        self.copy_button = button('复制', self.copy_image)
        self.save_button = button('保存…', self.save_image, 'primary')
        self.details_button = button('更多选项', self.request_details)
        self.close_button = button('关闭', self.reject)
        for widget in (self.copy_button, self.save_button, self.details_button, self.close_button):
            row.addWidget(widget)
        layout.addLayout(row)
        self.status_label = QLabel(f'{image.width} × {image.height} px · 已截取')
        self.status_label.setObjectName('muted')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def auto_copy(self):
        self.copy_image()

    def copy_image(self):
        QApplication.clipboard().setPixmap(pil_pixmap(self.image))
        self.status_label.setText(f'{self.image.width} × {self.image.height} px · 已复制，可直接粘贴')
        self.copied.emit()

    def save_image(self):
        if self._worker is not None:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.status_label.setText('无法创建保存位置：' + str(error))
            return
        timestamp = datetime.now(UTC).astimezone()
        default = self.root / f'ScreenLite_{timestamp:%Y%m%d_%H%M%S}.png'
        chosen, _ = QFileDialog.getSaveFileName(self, '保存截图', str(default), 'PNG 图片 (*.png)')
        if chosen:
            path = Path(chosen)
            if not path.suffix:
                path = path.with_suffix('.png')
            self.start_export(path)

    def start_export(self, path):
        if self._worker is not None:
            return
        self.save_button.setEnabled(False)
        self.status_label.setText('正在保存…')
        self._worker = _ImageWorker(self.image, self.image.size, Path(path), 'clear', self)
        self._worker.succeeded.connect(self._saved, Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._failed, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    @Slot(object)
    def _saved(self, path):
        try:
            size = ' · ' + file_size_text(Path(path).stat().st_size)
        except OSError:
            size = ''
        self.status_label.setText('已保存' + size)

    @Slot(str)
    def _failed(self, error):
        self._pending_action = None
        self.status_label.setText('保存失败：' + error)

    @Slot()
    def _finished(self):
        if self._worker is None:
            return
        self._worker.deleteLater()
        self._worker = None
        self.save_button.setEnabled(True)
        action, self._pending_action = self._pending_action, None
        if action == 'details':
            self.request_details()
        elif action == 'close':
            self.reject()

    def release_resources(self):
        if self._worker is not None:
            self._worker.wait()
            self._worker.deleteLater()
            self._worker = None
        self.image = None

    def request_details(self):
        if self._worker is not None:
            self._pending_action = 'details'
            self.status_label.setText('保存完成后打开更多选项…')
            return
        self.edit_requested.emit()
        self.details_requested.emit()
        self.accept()

    def _notify_closed(self):
        if not self._closed:
            self._closed = True
            self.closed.emit()

    def reject(self):
        if self._worker is not None:
            self._pending_action = 'close'
            self.status_label.setText('保存完成后关闭…')
            return
        self._notify_closed()
        super().reject()

    def closeEvent(self, event):
        if self._worker is not None:
            self._pending_action = 'close'
            event.ignore()
            return
        self._notify_closed()
        super().closeEvent(event)


class RecordingToolbar(QDialog):
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('正在录制 · ScreenLite')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(280)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self.timer_label = QLabel('●  00:00')
        self.timer_label.setStyleSheet('font-size: 18px; color: #AF3F35; font-weight: 600;')
        layout.addWidget(self.timer_label)
        layout.addStretch()
        self.stop_button = button('停止录制', self.stop_requested.emit, 'danger')
        layout.addWidget(self.stop_button)

    def set_seconds(self, seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        clock = f'{hours:02d}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'
        self.timer_label.setText('●  ' + clock)

    def reject(self):
        self.stop_requested.emit()

    def closeEvent(self, event):
        if self.signalsBlocked():
            event.accept()
        else:
            self.stop_requested.emit()
            event.ignore()
