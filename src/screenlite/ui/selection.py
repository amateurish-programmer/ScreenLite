"""Frozen-screen, logical-coordinate selection surface."""

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QToolButton, QVBoxLayout, QWidget)

from .annotations import Annotation


class SelectionOverlay(QWidget):
    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, screen, pixmap, mode='capture'):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setGeometry(screen.geometry())
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pixmap = pixmap
        self.mode = mode
        self.selection = QRect()
        self._action = None
        self._origin = QPoint()
        self._before = QRect()
        self._completed = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.tool = 'select'
        self.color = QColor('#ff4d58')
        self.line_width = 3
        self.annotations = []
        self._redo = []
        self._pending = None
        self.text_editor = None
        self._text_origin = QPointF()
        self._build_toolbar()

    def _button(self, symbol, tooltip, callback):
        button = QToolButton(self.toolbar)
        button.setText(symbol)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(34, 32)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        return button

    def _build_toolbar(self):
        self.toolbar = QFrame(self)
        self.toolbar.setObjectName('selectionToolbar')
        self.toolbar.setStyleSheet(
            'QFrame#selectionToolbar { background: #203334; border: 1px solid #486260; '
            'border-radius: 9px; } QToolButton { color: #edf8f5; background: transparent; '
            'border: none; border-radius: 5px; font-size: 22px; } '
            'QToolButton:hover { background: #3b5753; } '
            'QToolButton:checked { background: #427969; color: white; } '
            'QToolButton:disabled { color: #667b75; } '
            'QLabel { color: #c5d8d3; background: transparent; font-size: 12px; } '
            'QComboBox { color: #edf8f5; background: #304943; border: none; padding: 3px; }')
        self._toolbar_layout = QVBoxLayout(self.toolbar)
        self._toolbar_layout.setContentsMargins(8, 7, 8, 7)
        self._toolbar_layout.setSpacing(5)
        self._toolbar_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._tool_grid = QGridLayout()
        self._tool_grid.setSpacing(3)
        self._toolbar_layout.addLayout(self._tool_grid)
        self.tool_buttons = {}
        buttons = []
        if self.mode != 'record':
            for name, symbol, label in [('select', '↔', '调整选区'), ('rectangle', '□', '矩形'),
                                        ('ellipse', '○', '椭圆'), ('arrow', '↗', '箭头'),
                                        ('pen', '✎', '画笔'), ('mosaic', '▦', '马赛克'),
                                        ('text', 'T', '文字')]:
                button = self._button(symbol, label, lambda checked=False, tool=name: self.set_tool(tool))
                button.setCheckable(True)
                button.setChecked(name == 'select')
                self.tool_buttons[name] = button
                buttons.append(button)
            self.undo_button = self._button('↶', '撤销 Ctrl+Z', self.undo)
            self.redo_button = self._button('↷', '重做 Ctrl+Y', self.redo)
            buttons.extend([self.undo_button, self.redo_button])
        self.cancel_button = self._button('×', '取消 Esc', self._cancel)
        self.confirm_button = self._button('✓', '确认 Enter', self._confirm)
        self.confirm_button.setStyleSheet('QToolButton {color: #59e0af;}')
        buttons.extend([self.cancel_button, self.confirm_button])
        self._toolbar_buttons = buttons
        if self.mode != 'record':
            options = QHBoxLayout()
            options.setSpacing(5)
            self.color_buttons = {}
            for value, label in [('#ff4d58', '红色'), ('#ffd45c', '黄色'), ('#50dc9b', '绿色'),
                                 ('#50a5ff', '蓝色'), ('#ffffff', '白色'), ('#202020', '黑色')]:
                button = self._button('●', label, lambda checked=False, color=value: self._set_color(color))
                button.setFixedSize(24, 24)
                button.setCheckable(True)
                button.setChecked(value == self.color.name())
                button.setStyleSheet(f'QToolButton {{ color: {value}; font-size: 21px; }}'
                                     'QToolButton:checked { border: 1px solid #b0d7c9; }')
                self.color_buttons[value] = button
                options.addWidget(button)
            self.width_combo = QComboBox(self.toolbar)
            self.width_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            for label, width in [('细 2', 2), ('中 3', 3), ('粗 6', 6), ('特粗 10', 10)]:
                self.width_combo.addItem(label, width)
            self.width_combo.setCurrentIndex(1)
            self.width_combo.currentIndexChanged.connect(self._set_width)
            options.addWidget(self.width_combo)
            options.addStretch()
            self._toolbar_layout.addLayout(options)
        self.hint_label = QLabel(self.toolbar)
        self.hint_label.setWordWrap(True)
        self.hint_label.setText('拖动调整选区 · 方向键微调 · Shift 加速\nEnter 确认 · Esc 取消')
        self._toolbar_layout.addWidget(self.hint_label)
        self.toolbar.hide()
        self._sync_history_buttons()

    def _set_color(self, color):
        self.color = QColor(color)
        for value, button in self.color_buttons.items():
            button.setChecked(value == self.color.name())
        self._refresh_text_style()

    def _set_width(self, index):
        self.line_width = self.width_combo.itemData(index)
        self._refresh_text_style()

    def set_tool(self, tool):
        if self.mode == 'record' or tool not in self.tool_buttons:
            return
        self._finish_text()
        self.tool = tool
        for name, button in self.tool_buttons.items():
            button.setChecked(name == tool)
        self.setCursor(Qt.CursorShape.CrossCursor)
        if tool == 'select':
            hint = '拖动调整选区 · 方向键微调 · Shift 加速\nEnter 确认 · Esc 取消'
        elif tool == 'text':
            hint = '点击选区输入文字 · Enter 完成文字\nCtrl+Z 撤销 · 点击 ✓ 完成截图 · Esc 取消'
        else:
            hint = '拖动绘制 · 点击 ↔ 调整选区 · Ctrl+Z 撤销\nCtrl+Y 重做 · Enter 确认 · Esc 取消'
        self.hint_label.setText(hint)
        self._position_toolbar()
        self.setFocus()

    def _position_toolbar(self):
        if self.selection.isEmpty():
            self.toolbar.hide()
            return
        available = max(1, self.width() - 16)
        width = min(426 if self.mode != 'record' else 310, available)
        columns = max(1, (width - 16) // 37)
        for i, button in enumerate(self._toolbar_buttons):
            self._tool_grid.addWidget(button, i // columns, i % columns)
        self.toolbar.setFixedWidth(width)
        self._toolbar_layout.activate()
        height = self._toolbar_layout.totalHeightForWidth(width)
        if height < 0:
            height = self._toolbar_layout.sizeHint().height()
        height = min(max(height, 70), max(1, self.height() - 16))
        self.toolbar.setFixedHeight(height)
        r = self.selection
        x = min(max(8, r.x() + r.width() - width), max(8, self.width() - width - 8))
        y = r.y() + r.height() + 10
        if y + height > self.height() - 8:
            y = r.y() - height - 10
        y = max(8, min(y, self.height() - height - 8))
        self.toolbar.move(x, y)
        self.toolbar.show()
        self.toolbar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'toolbar'):
            self._position_toolbar()

    def _sync_history_buttons(self):
        if self.mode != 'record':
            self.undo_button.setEnabled(bool(self.annotations))
            self.redo_button.setEnabled(bool(self._redo))

    def undo(self):
        self._finish_text()
        if self.annotations:
            self._redo.append(self.annotations.pop())
        self._sync_history_buttons()
        self.update()

    def redo(self):
        if self._redo:
            self.annotations.append(self._redo.pop())
        self._sync_history_buttons()
        self.update()

    def _append_annotation(self, annotation):
        self.annotations.append(annotation)
        self._redo.clear()
        self._sync_history_buttons()
        self.update()

    def _start_text(self, point):
        self._finish_text()
        self._text_origin = QPointF(point)
        editor = QLineEdit(self)
        editor.setPlaceholderText('输入文字')
        width = max(30, min(250, self.selection.x() + self.selection.width() - point.x()))
        editor.setGeometry(point.x(), point.y(), width, 1)
        editor.installEventFilter(self)
        self.text_editor = editor
        self._refresh_text_style()
        editor.show()
        editor.setFocus()

    def _refresh_text_style(self):
        editor = self.text_editor
        if editor is None:
            return
        font = QFont('Microsoft YaHei')
        font.setPixelSize(14 + self.line_width * 3)
        editor.setFont(font)
        editor.setFixedHeight(font.pixelSize() + 12)
        background = '#152523' if self.color.lightnessF() > 0.45 else '#ffffff'
        editor.setStyleSheet(f'color: {self.color.name()}; background: {background}; '
                            'border: 1px solid #46e0be;')

    def eventFilter(self, watched, event):
        if watched is self.text_editor and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                self._finish_text(event.key() != Qt.Key.Key_Escape)
                return True
        return super().eventFilter(watched, event)

    def _finish_text(self, commit=True):
        editor = self.text_editor
        if editor is None:
            return
        self.text_editor = None
        text = editor.text()
        if commit and text.strip():
            self._append_annotation(Annotation('text', [QPointF(self._text_origin)],
                                               QColor(self.color), self.line_width, text=text))
        editor.removeEventFilter(self)
        editor.hide()
        editor.deleteLater()
        self.setFocus()

    def _annotation_point(self, point):
        r = self.selection
        return QPointF(max(r.x(), min(r.x() + r.width(), point.x())),
                       max(r.y(), min(r.y() + r.height(), point.y())))

    def _update_annotation(self, point):
        item = self._pending
        if item is None:
            return
        point = self._annotation_point(point)
        if item.tool == 'pen':
            if point != item.points[-1]:
                item.points.append(point)
        else:
            item.points[-1] = point
        if item.tool == 'mosaic' and not item.rect.isEmpty():
            r, ratio = item.rect, self.pixmap.devicePixelRatio()
            physical = QRect(round(r.x() * ratio), round(r.y() * ratio),
                             max(1, round(r.width() * ratio)), max(1, round(r.height() * ratio)))
            patch = self.pixmap.copy(physical).toImage()
            patch.setDevicePixelRatio(1)
            block = max(6, round((self.line_width * 2 + 4) * ratio))
            item.patch = patch.scaled(max(1, patch.width() // block), max(1, patch.height() // block),
                                      Qt.AspectRatioMode.IgnoreAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self.update()

    def _paint_annotations(self, painter):
        painter.save()
        painter.setClipRect(QRectF(self.selection))
        for annotation in self.annotations:
            annotation.paint(painter)
        if self._pending:
            self._pending.paint(painter)
        painter.restore()

    def render_selection(self):
        """Return just the selected physical pixels; no overlay controls or extra screen copy."""
        if self.pixmap.isNull() or self.selection.isEmpty():
            return QImage()
        self._finish_text()
        r, ratio = self.selection, self.pixmap.devicePixelRatio()
        crop = QRect(round(r.x() * ratio), round(r.y() * ratio),
                     round(r.width() * ratio), round(r.height() * ratio))
        image = self.pixmap.copy(crop).toImage()
        image.setDevicePixelRatio(1)
        painter = QPainter(image)
        painter.translate(-crop.x(), -crop.y())
        painter.scale(ratio, ratio)
        self._paint_annotations(painter)
        painter.end()
        return image

    def release_resources(self):
        """Drop large capture and annotation buffers before deferred QWidget deletion."""
        self._finish_text(False)
        self.pixmap = QPixmap()
        self.annotations.clear()
        self._redo.clear()
        self._pending = None
        self._action = None

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.setFocus()

    def _handles(self):
        r = self.selection
        left, top, right, bottom = r.x(), r.y(), r.x() + r.width(), r.y() + r.height()
        middle_x, middle_y = (left + right) // 2, (top + bottom) // 2
        return {'nw': QPoint(left, top), 'n': QPoint(middle_x, top), 'ne': QPoint(right, top),
                'w': QPoint(left, middle_y), 'e': QPoint(right, middle_y),
                'sw': QPoint(left, bottom), 's': QPoint(middle_x, bottom), 'se': QPoint(right, bottom)}

    def _hit(self, point):
        if self.selection.isEmpty():
            return 'new'
        for key, center in self._handles().items():
            if abs(point.x() - center.x()) <= 7 and abs(point.y() - center.y()) <= 7:
                return key
        r = self.selection
        if r.x() <= point.x() <= r.x() + r.width():
            if abs(point.y() - r.y()) <= 5:
                return 'n'
            if abs(point.y() - r.y() - r.height()) <= 5:
                return 's'
        if r.y() <= point.y() <= r.y() + r.height():
            if abs(point.x() - r.x()) <= 5:
                return 'w'
            if abs(point.x() - r.x() - r.width()) <= 5:
                return 'e'
        return 'move' if r.contains(point) else 'new'

    def _clamp(self, point):
        return QPoint(min(self.width(), max(0, point.x())), min(self.height(), max(0, point.y())))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._finish_text()
        self._origin = self._clamp(event.position().toPoint())
        if self.tool != 'select' and self.selection.contains(self._origin):
            if self.tool == 'text':
                self._start_text(self._origin)
            else:
                point = QPointF(self._origin)
                self._pending = Annotation(self.tool, [point, QPointF(point)],
                                           QColor(self.color), self.line_width)
            return
        self._action = self._hit(self._origin)
        self._before = QRect(self.selection)
        if self._action == 'new':
            self.annotations.clear()
            self._redo.clear()
            self._sync_history_buttons()
            self.selection = QRect(self._origin, self._origin)
        self.update()

    def mouseMoveEvent(self, event):
        point = self._clamp(event.position().toPoint())
        if self._pending:
            self._update_annotation(point)
        elif self._action:
            self._update_drag(point)
        else:
            hit = self._hit(point) if self.tool == 'select' else 'new'
            cursors = {'move': Qt.CursorShape.SizeAllCursor, 'n': Qt.CursorShape.SizeVerCursor,
                       's': Qt.CursorShape.SizeVerCursor, 'e': Qt.CursorShape.SizeHorCursor,
                       'w': Qt.CursorShape.SizeHorCursor, 'nw': Qt.CursorShape.SizeFDiagCursor,
                       'se': Qt.CursorShape.SizeFDiagCursor, 'ne': Qt.CursorShape.SizeBDiagCursor,
                       'sw': Qt.CursorShape.SizeBDiagCursor}
            self.setCursor(cursors.get(hit, Qt.CursorShape.CrossCursor))

    def _update_drag(self, point):
        action = self._action
        if action == 'move':
            delta = point - self._origin
            r = self._before
            x = max(0, min(self.width() - r.width(), r.x() + delta.x()))
            y = max(0, min(self.height() - r.height(), r.y() + delta.y()))
            self.selection = QRect(x, y, r.width(), r.height())
        else:
            if action == 'new':
                x1, y1, x2, y2 = self._origin.x(), self._origin.y(), point.x(), point.y()
            else:
                r = self._before
                x1, y1, x2, y2 = r.x(), r.y(), r.x() + r.width(), r.y() + r.height()
                if 'w' in action:
                    x1 = point.x()
                if 'e' in action:
                    x2 = point.x()
                if 'n' in action:
                    y1 = point.y()
                if 's' in action:
                    y2 = point.y()
            self.selection = QRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        self._position_toolbar()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pending:
            self._update_annotation(event.position().toPoint())
            item, self._pending = self._pending, None
            if (item.tool == 'pen' or not item.rect.isEmpty()
                    or (item.tool == 'arrow' and item.points[0] != item.points[-1])):
                self._append_annotation(item)
            return
        if event.button() == Qt.MouseButton.LeftButton and self._action:
            self._update_drag(self._clamp(event.position().toPoint()))
            self._action = None

    def mouseDoubleClickEvent(self, event):
        if (self.tool == 'select' and event.button() == Qt.MouseButton.LeftButton
                and self.selection.contains(event.position().toPoint())):
            self._confirm()

    def _confirm(self):
        self._finish_text()
        if not self._completed and self.selection.width() >= 2 and self.selection.height() >= 2:
            self._completed = True
            self.selected.emit(QRect(self.selection))

    def _cancel(self):
        if not self._completed:
            self._completed = True
            self.cancelled.emit()

    def closeEvent(self, event):
        self._cancel()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm()
        elif not self.selection.isEmpty():
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            delta = {Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_Right: (step, 0),
                     Qt.Key.Key_Up: (0, -step), Qt.Key.Key_Down: (0, step)}.get(event.key())
            if delta:
                r = self.selection
                r.moveTo(max(0, min(self.width() - r.width(), r.x() + delta[0])),
                         max(0, min(self.height() - r.height(), r.y() + delta[1])))
                self._position_toolbar()
                self.update()

    def paintEvent(self, event):
        if self.pixmap.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), QColor(9, 25, 28, 130))
        r = self.selection
        if not r.isEmpty():
            painter.save()
            painter.setClipRect(r)
            painter.drawPixmap(self.rect(), self.pixmap)
            painter.restore()
            self._paint_annotations(painter)
            painter.setPen(QPen(QColor('#46E0BE'), 1.5))
            painter.drawRect(QRectF(r))
            painter.setBrush(QColor('white'))
            for point in self._handles().values():
                painter.drawRect(QRectF(point.x() - 3, point.y() - 3, 6, 6))
            ratio = self.pixmap.devicePixelRatio()
            text = (f'X: {round(r.x() * ratio)}  Y: {round(r.y() * ratio)}   ·   '
                    f'{round(r.width() * ratio)} × {round(r.height() * ratio)} px')
            label = QRect(max(4, min(self.width() - 300, r.x())), max(4, r.y() - 32), 294, 26)
            painter.fillRect(label, QColor('#203334'))
            painter.setPen(QColor('white'))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, text)
        elif not self._completed:
            hint = '拖动选择录制区域' if self.mode == 'record' else '拖动选择截图区域'
            painter.setPen(QColor('white'))
            painter.drawText(self.rect().adjusted(20, 20, -20, -20),
                             Qt.AlignmentFlag.AlignCenter, hint + ' · Esc 取消')
