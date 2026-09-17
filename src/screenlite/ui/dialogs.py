"""Desktop dashboard and responsive export dialogs."""

from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .theme import STYLE


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(callback)
    return widget


def pil_pixmap(image):
    rgba = image.convert('RGBA')
    data = rgba.tobytes('raw', 'RGBA')
    qimage = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


def file_size_text(size):
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    return f'{size / (1024 * 1024):.2f} MB'


class _Illustration(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(136)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y, w, h = self.width() // 2 - 126, 12, 252, 110
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#E2EEE5'))
        painter.drawRoundedRect(x - 22, y + 12, w + 44, h - 8, 24, 24)
        painter.setBrush(QColor('#FFFFFF'))
        painter.setPen(QPen(QColor('#B7CFC2'), 1.5))
        painter.drawRoundedRect(x, y, w, h, 9, 9)
        painter.setPen(QPen(QColor('#087F75'), 2, Qt.PenStyle.DashLine))
        painter.drawRect(x + 55, y + 26, 142, 63)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#B7D6C7'))
        painter.drawEllipse(x + 68, y + 38, 19, 19)
        painter.setPen(QPen(QColor('#087F75'), 3))
        painter.drawLine(x + 69, y + 76, x + 102, y + 57)
        painter.drawLine(x + 102, y + 57, x + 122, y + 70)
        painter.drawLine(x + 122, y + 70, x + 158, y + 45)
        painter.drawLine(x + 158, y + 45, x + 183, y + 76)
        painter.setBrush(QColor('#087F75'))
        painter.drawEllipse(x + 187, y + 80, 26, 26)


class MainWindow(QMainWindow):
    quit_requested = Signal()
    capture_requested = Signal()
    record_requested = Signal()
    compress_requested = Signal()
    settings_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('ScreenLite · 轻巧记录')
        self.exit_on_close = False
        self.resize(590, 530)
        self.setMinimumSize(530, 480)
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(label('SCREENLITE', 'eyebrow'))
        header.addStretch()
        header.addWidget(button('设置', self.settings_requested.emit))
        layout.addLayout(header)
        layout.addWidget(_Illustration())
        layout.addWidget(label('留住屏幕上的好内容', 'title'))
        layout.addWidget(label('截图、录屏、压缩，让分享更简单。', 'muted'))
        row = QHBoxLayout()
        self.capture_button = button('截取屏幕', self.capture_requested.emit, 'primary')
        self.record_button = button('录制屏幕', self.record_requested.emit)
        self.capture_button.setMinimumHeight(56)
        self.record_button.setMinimumHeight(56)
        row.addWidget(self.capture_button)
        row.addWidget(self.record_button)
        layout.addLayout(row)
        self.shortcut_label = label('Ctrl + Alt + A 截图    ·    Ctrl + Alt + R 录屏', 'muted')
        layout.addWidget(self.shortcut_label)
        layout.addStretch()
        bottom = QHBoxLayout()
        bottom.addWidget(button('压缩已有文件', self.compress_requested.emit))
        bottom.addStretch()
        self.status_label = label('最小化后可用快捷键 · 关闭即退出', 'muted')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom.addWidget(self.status_label, 1)
        layout.addLayout(bottom)

    def set_recording(self, recording, seconds=0):
        self.capture_button.setEnabled(not recording)
        self.record_button.setObjectName('danger' if recording else '')
        self.record_button.setText(f'停止录制  {seconds // 60:02d}:{seconds % 60:02d}' if recording else '录制屏幕')
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def closeEvent(self, event):
        if self.exit_on_close:
            event.ignore()
            self.quit_requested.emit()
        else:
            super().closeEvent(event)

    def set_status(self, text):
        self.status_label.setText(text)

    def set_shortcuts(self, capture, record):
        self.shortcut_label.setText(f'{capture} 截图    ·    {record} 录屏')


class _ImageWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, image, size, path, preset, parent):
        super().__init__(parent)
        self.image, self.size, self.path, self.preset = image, size, path, preset

    def run(self):
        try:
            if self.path is None:
                result = self.image.resize(self.size, Image.Resampling.LANCZOS)
            else:
                from screenlite.media import export_image
                result = export_image(self.image, self.path, *self.size, self.preset, exact_size=True)
            self.succeeded.emit(result)
        except (OSError, ValueError, TypeError, ImportError, RuntimeError) as error:
            self.failed.emit(str(error))
        finally:
            self.image = None


class ImageDialog(QDialog):
    exported = Signal(str)

    def __init__(self, image, root, parent=None):
        super().__init__(parent)
        # Read-only shared ownership; resizing/encoding always creates its own result.
        self.image = image
        self.root = Path(root)
        self._worker = None
        self.output_path = None
        self.setWindowTitle('保存截图 · ScreenLite')
        self.setStyleSheet(STYLE)
        self.resize(740, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        layout.addWidget(label('这一刻，已为你留住', 'title'))
        preview = self.preview = QLabel()
        preview.setObjectName('preview')
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumHeight(230)
        thumbnail = self.image.copy()
        thumbnail.thumbnail((660, 300), Image.Resampling.LANCZOS)
        preview.setPixmap(pil_pixmap(thumbnail))
        thumbnail.close()
        layout.addWidget(preview, 1)
        form = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(['PNG · 无损画质', 'JPEG · 通用小体积', 'WebP · 高效压缩'])
        form.addRow('文件格式', self.format_combo)
        self.size_combo = QComboBox()
        self.size_combo.addItems(['原始尺寸', '50% · 缩小一半', '1080p · 适合大屏', '720p · 轻松分享',
                                 '自定义宽高 · 锁定比例', '75%', '25%', '长边 1920 px',
                                 '长边 1280 px', '长边 720 px'])
        form.addRow('导出尺寸', self.size_combo)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 32768)
        self.width_spin.setValue(min(32768, self.image.width))
        self.width_spin.setSuffix(' px')
        self.width_spin.setEnabled(False)
        form.addRow('自定义宽度', self.width_spin)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 32768)
        self.height_spin.setValue(min(32768, self.image.height))
        self.height_spin.setSuffix(' px')
        self.height_spin.setEnabled(False)
        form.addRow('自定义高度', self.height_spin)
        self.quality_combo = QComboBox()
        for title, value in [('清晰 · 保留细节', 'clear'), ('均衡 · 推荐', 'balanced'), ('小巧 · 优先体积', 'small')]:
            self.quality_combo.addItem(title, value)
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.addItem('无损 · PNG', 'lossless')
        form.addRow('画质偏好', self.quality_combo)
        layout.addLayout(form)
        self.status_label = label('', 'muted')
        layout.addWidget(self.status_label)
        self.size_combo.currentIndexChanged.connect(self._update_size)
        self.width_spin.valueChanged.connect(self._width_changed)
        self.height_spin.valueChanged.connect(self._height_changed)
        self.format_combo.currentIndexChanged.connect(self._update_size)
        self.quality_combo.currentIndexChanged.connect(self._quality_changed)
        actions = QHBoxLayout()
        self.copy_button = button('复制图片', self.copy_image)
        self.save_button = button('保存图片…', self.choose_export, 'primary')
        actions.addWidget(self.copy_button)
        actions.addStretch()
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self._update_size()

    def output_size(self):
        width, height = self.image.size
        index = self.size_combo.currentIndex()
        ratio = 1.0
        if index == 1:
            ratio = 0.5
        elif index in (2, 3):
            max_width, max_height = (1920, 1080) if index == 2 else (1280, 720)
            ratio = min(1, max_width / width, max_height / height)
        elif index == 4:
            return self.width_spin.value(), self.height_spin.value()
        elif index in (5, 6):
            ratio = 0.75 if index == 5 else 0.25
        elif index in (7, 8, 9):
            ratio = min(1, (1920, 1280, 720)[index - 7] / max(width, height))
        return max(1, round(width * ratio)), max(1, round(height * ratio))

    def _width_changed(self, width):
        self.height_spin.blockSignals(True)
        self.height_spin.setValue(max(1, round(width * self.image.height / self.image.width)))
        self.height_spin.blockSignals(False)
        self._update_size()

    def _height_changed(self, height):
        self.width_spin.blockSignals(True)
        self.width_spin.setValue(max(1, round(height * self.image.width / self.image.height)))
        self.width_spin.blockSignals(False)
        self._update_size()

    def _quality_changed(self):
        if self.quality_combo.currentData() == 'lossless':
            self.format_combo.setCurrentIndex(0)
        self._update_size()

    def _update_size(self):
        self.width_spin.setEnabled(self.size_combo.currentIndex() == 4)
        self.height_spin.setEnabled(self.size_combo.currentIndex() == 4)
        if self.format_combo.currentIndex() != 0 and self.quality_combo.currentData() == 'lossless':
            self.quality_combo.setCurrentIndex(1)
        width, height = self.output_size()
        self.status_label.setText(f'{self.image.width} × {self.image.height} → {width} × {height} px'
                                  + ('    PNG 保留完整画质' if self.format_combo.currentIndex() == 0 else ''))

    def copy_image(self):
        self._start_worker(None)

    @Slot(object)
    def _copied(self, image):
        QApplication.clipboard().setPixmap(pil_pixmap(image))
        self.status_label.setText('已复制到剪贴板，可以直接粘贴。')

    def choose_export(self):
        extension = ['png', 'jpg', 'webp'][self.format_combo.currentIndex()]
        timestamp = datetime.now(UTC).astimezone()
        default = self.root / f'ScreenLite_{timestamp:%Y%m%d_%H%M%S}.{extension}'
        selected, _ = QFileDialog.getSaveFileName(self, '保存图片', str(default), f'图片 (*.{extension})')
        if selected:
            path = Path(selected)
            if not path.suffix:
                path = path.with_suffix('.' + extension)
            self.start_export(path)

    def start_export(self, path):
        self._start_worker(Path(path))

    def _start_worker(self, path):
        if self._worker is not None:
            return
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.status_label.setText('正在处理图片…')
        self._worker = _ImageWorker(self.image, self.output_size(), path,
                                    'clear' if self.quality_combo.currentData() == 'lossless'
                                    else self.quality_combo.currentData(), self)
        self._worker.succeeded.connect(self._copied if path is None else self._saved,
                                       Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._image_failed, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._worker_finished, Qt.ConnectionType.QueuedConnection)
        self._worker.start()

    @Slot(str)
    def _image_failed(self, error):
        self.status_label.setText('处理失败：' + error)

    @Slot(object)
    def _saved(self, path):
        self.output_path = Path(path)
        try:
            size = ' · ' + file_size_text(self.output_path.stat().st_size)
        except OSError:
            size = ''
        self.status_label.setText('已保存' + size + '：' + str(path))
        self.exported.emit(str(path))

    @Slot()
    def _worker_finished(self):
        if self._worker is None:
            return
        self._worker.deleteLater()
        self._worker = None
        self.save_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def release_resources(self):
        if self._worker is not None:
            # Modal close is normally deferred until finished; also handle exception cleanup.
            self._worker.wait()
            self._worker.deleteLater()
            self._worker = None
        self.preview.clear()
        self.image = None

    def reject(self):
        if self._worker is not None:
            self.status_label.setText('正在保存，请稍候再关闭。')
            return
        super().reject()

    def closeEvent(self, event):
        if self._worker is not None:
            self.status_label.setText('正在保存，请稍候再关闭。')
            event.ignore()
        else:
            super().closeEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = dict(settings)
        self.setWindowTitle('设置 · ScreenLite')
        self.setMinimumWidth(480)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        layout.addWidget(label('按你的习惯来', 'title'))
        form = QFormLayout()
        self.capture_key = QKeySequenceEdit(QKeySequence(settings.get('screenshot_hotkey', 'Ctrl+Alt+A')))
        self.record_key = QKeySequenceEdit(QKeySequence(settings.get('record_hotkey', 'Ctrl+Alt+R')))
        self.capture_key.setMaximumSequenceLength(1)
        self.record_key.setMaximumSequenceLength(1)
        form.addRow('截图快捷键', self.capture_key)
        form.addRow('录屏快捷键', self.record_key)
        self.fps_combo = QComboBox()
        for fps in (15, 30, 60):
            self.fps_combo.addItem(f'{fps} 帧 / 秒', fps)
        self.fps_combo.setCurrentIndex(max(0, self.fps_combo.findData(settings.get('fps', 30))))
        form.addRow('录制帧率', self.fps_combo)
        self.preset_combo = QComboBox()
        for name, preset in [('清晰', 'clear'), ('均衡', 'balanced'), ('小巧', 'small')]:
            self.preset_combo.addItem(name, preset)
        self.preset_combo.setCurrentIndex(max(0, self.preset_combo.findData(settings.get('preset', 'balanced'))))
        form.addRow('默认画质', self.preset_combo)
        self.copy_check = QCheckBox('截图后自动复制到剪贴板')
        self.copy_check.setChecked(settings.get('copy_after_capture', True))
        form.addRow('', self.copy_check)
        self.countdown_combo = QComboBox()
        self.countdown_combo.addItem('立即开始', 0)
        self.countdown_combo.addItem('3 秒倒计时', 3)
        self.countdown_combo.setCurrentIndex(max(0, self.countdown_combo.findData(settings.get('countdown', 3))))
        form.addRow('录制倒计时', self.countdown_combo)
        self.cursor_check = QCheckBox('录制时显示鼠标指针')
        self.cursor_check.setChecked(settings.get('record_cursor', True))
        form.addRow('', self.cursor_check)
        self.output_edit = QLineEdit(str(settings.get('output_dir', '')))
        row = QHBoxLayout()
        row.addWidget(self.output_edit)
        row.addWidget(button('浏览…', self._choose_directory))
        form.addRow('保存位置', row)
        layout.addLayout(form)
        self.message_label = label('快捷键在后台也可使用；按 Esc 可取消当前选区。', 'muted')
        layout.addWidget(self.message_label)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Save).setText('保存设置')
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def _choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择保存位置', self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def values(self):
        result = dict(self._settings)
        result.update(screenshot_hotkey=self.capture_key.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                      record_hotkey=self.record_key.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                      fps=self.fps_combo.currentData(), preset=self.preset_combo.currentData(),
                      copy_after_capture=self.copy_check.isChecked(),
                      countdown=self.countdown_combo.currentData(), record_cursor=self.cursor_check.isChecked(),
                      output_dir=self.output_edit.text().strip())
        return result

    def accept(self):
        values = self.values()
        capture, record = values['screenshot_hotkey'], values['record_hotkey']
        if not capture or not record or capture == record:
            self.message_label.setText('请设置两个不同且非空的快捷键。')
            return
        super().accept()


class VideoExportDialog(QDialog):
    """Asynchronous MP4 export. Source files are always retained by this dialog."""

    exported = Signal(str)

    def __init__(self, source, root, parent=None):
        super().__init__(parent)
        self.source, self.root = Path(source), Path(root)
        self.output_directory = self.source.parent
        self.output_path = None
        self._job = None
        self._close_when_done = False
        self.setWindowTitle('导出视频 · ScreenLite')
        self.setMinimumWidth(530)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        layout.addWidget(label('轻一点，分享更方便', 'title'))
        filename = label(self.source.name, 'muted')
        filename.setToolTip(str(self.source))
        layout.addWidget(filename)
        form = QFormLayout()
        self.size_combo = QComboBox()
        for title, size in [('原始尺寸', (32768, 32768)), ('1080p · 推荐', (1920, 1080)),
                            ('720p · 轻松分享', (1280, 720)), ('480p · 更小体积', (854, 480)),
                            ('75%', (32768, 32768)), ('50%', (32768, 32768)), ('自定义宽高', (1920, 1080))]:
            self.size_combo.addItem(title, size)
        self.size_combo.setCurrentIndex(1)
        form.addRow('导出尺寸', self.size_combo)
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for spin, initial in ((self.width_spin, 1920), (self.height_spin, 1080)):
            spin.setRange(2, 32768)
            spin.setValue(initial)
            spin.setSuffix(' px')
            spin.setEnabled(False)
        custom_row = QHBoxLayout()
        custom_row.addWidget(self.width_spin)
        custom_row.addWidget(label('×'))
        custom_row.addWidget(self.height_spin)
        form.addRow('自定义边界', custom_row)
        self.size_combo.currentIndexChanged.connect(self._size_changed)
        self.quality_combo = QComboBox()
        for title, preset in [('清晰 · 保留细节', 'clear'), ('均衡 · 推荐', 'balanced'), ('小巧 · 优先体积', 'small')]:
            self.quality_combo.addItem(title, preset)
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.addItem('极清 · 更高画质', 'ultra')
        form.addRow('画质偏好', self.quality_combo)
        layout.addLayout(form)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status_label = label('导出为 MP4，保留原文件。实际大小取决于画面内容。', 'muted')
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        row = QHBoxLayout()
        self.cancel_button = button('关闭', self.reject)
        self.save_button = button('导出 MP4…', self.choose_export, 'primary')
        row.addWidget(self.cancel_button)
        row.addStretch()
        row.addWidget(self.save_button)
        layout.addLayout(row)

    def _size_changed(self, index):
        self.width_spin.setEnabled(index == 6 and not self.is_busy)
        self.height_spin.setEnabled(index == 6 and not self.is_busy)

    @property
    def is_busy(self):
        return self._job is not None

    def choose_export(self):
        directory = Path(self.output_directory)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.status_label.setText('无法创建保存位置：' + str(error))
            return
        default = directory / (self.source.stem + '_分享.mp4')
        path, _ = QFileDialog.getSaveFileName(self, '保存视频', str(default), 'MP4 视频 (*.mp4)')
        if path:
            target = Path(path)
            self.start_export(target if target.suffix else target.with_suffix('.mp4'))

    def start_export(self, target):
        if self.is_busy:
            return
        target = Path(target)
        if target.resolve() == self.source.resolve():
            self.status_label.setText('导出失败：请使用新文件名，不能覆盖原文件。')
            return
        from screenlite.video import VideoJob
        self._job = VideoJob(self.root, parent=self)
        self._job.progress.connect(self._progress_changed)
        self._job.finished.connect(self._done)
        self._job.failed.connect(self._failed)
        self.save_button.setEnabled(False)
        self.size_combo.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.cancel_button.setText('取消导出')
        self.progress.setRange(0, 0)
        self.status_label.setText('正在导出视频…')
        index = self.size_combo.currentIndex()
        size = ((self.width_spin.value(), self.height_spin.value()) if index == 6
                else self.size_combo.currentData())
        fraction = {4: 0.75, 5: 0.5}.get(index)
        self.width_spin.setEnabled(False)
        self.height_spin.setEnabled(False)
        options = {'scale_fraction': fraction} if fraction is not None else {}
        self._job.transcode(self.source, target, *size, self.quality_combo.currentData(), **options)

    def _progress_changed(self, value):
        if value >= 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(value)

    def _release_job(self):
        if self._job is not None:
            self._job.deleteLater()
            self._job = None
        self.save_button.setEnabled(True)
        self.size_combo.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self._size_changed(self.size_combo.currentIndex())
        self.cancel_button.setText('关闭')
        self.progress.setRange(0, 100)
        if self._close_when_done:
            super().reject()

    def _done(self, path):
        self.output_path = Path(path)
        self._release_job()
        self.progress.setValue(100)
        detail = ''
        try:
            after = self.output_path.stat().st_size
            detail = file_size_text(after)
            before = self.source.stat().st_size
            change = '大小不变'
            if before and before != after:
                direction = '减小' if after < before else '增大'
                change = f'{direction} {abs(after - before) / before:.1%}'
            detail = f'{file_size_text(before)} → {file_size_text(after)}（{change}）'
        except OSError:
            pass
        self.status_label.setText(f'已导出 · {detail}\n{path}' if detail else '已导出：' + str(path))
        self.exported.emit(str(path))

    def _failed(self, error):
        self._release_job()
        self.progress.setValue(0)
        self.status_label.setText('导出失败：' + error)

    def reject(self):
        if self.is_busy:
            self._close_when_done = True
            self.status_label.setText('正在取消导出，原文件会保留…')
            self._job.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.is_busy:
            event.ignore()
            self.reject()
        else:
            super().closeEvent(event)
