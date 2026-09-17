"""Frozen-screen, logical-coordinate selection surface."""

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


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
        self._origin = self._clamp(event.position().toPoint())
        self._action = self._hit(self._origin)
        self._before = QRect(self.selection)
        if self._action == 'new':
            self.selection = QRect(self._origin, self._origin)
        self.update()

    def mouseMoveEvent(self, event):
        point = self._clamp(event.position().toPoint())
        if self._action:
            self._update_drag(point)
        else:
            hit = self._hit(point)
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
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._action:
            self._update_drag(self._clamp(event.position().toPoint()))
            self._action = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.selection.contains(event.position().toPoint()):
            self._confirm()

    def _confirm(self):
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
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), QColor(9, 25, 28, 130))
        r = self.selection
        if not r.isEmpty():
            painter.save()
            painter.setClipRect(r)
            painter.drawPixmap(self.rect(), self.pixmap)
            painter.restore()
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
        hint = '拖动选择录制区域' if self.mode == 'record' else '拖动选择截图区域'
        hint += '   ·   方向键微调   ·   Shift 加速   ·   Enter 确认   ·   Esc 取消'
        bar = QRect(max(8, (self.width() - 700) // 2), self.height() - 68, min(700, self.width() - 16), 40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#203334'))
        painter.drawRoundedRect(bar, 10, 10)
        painter.setPen(QColor('white'))
        painter.drawText(bar, Qt.AlignmentFlag.AlignCenter, hint)
