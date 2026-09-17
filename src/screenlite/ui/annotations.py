"""Logical-coordinate annotation commands shared by preview and physical export."""

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF


@dataclass
class Annotation:
    tool: str
    points: list[QPointF]
    color: QColor
    width: int
    text: str = ''
    patch: QImage = field(default_factory=QImage)

    @property
    def rect(self):
        return QRectF(self.points[0], self.points[-1]).normalized()

    def paint(self, painter: QPainter):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color, self.width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        start, end = self.points[0], self.points[-1]
        if self.tool == 'rectangle':
            painter.drawRect(self.rect)
        elif self.tool == 'ellipse':
            painter.drawEllipse(self.rect)
        elif self.tool == 'arrow':
            painter.drawLine(start, end)
            angle = atan2(end.y() - start.y(), end.x() - start.x())
            length = max(10, self.width * 4)
            head = QPolygonF([end, QPointF(end.x() - length * cos(angle - pi / 6),
                                          end.y() - length * sin(angle - pi / 6)),
                             QPointF(end.x() - length * cos(angle + pi / 6),
                                     end.y() - length * sin(angle + pi / 6))])
            painter.setBrush(self.color)
            painter.drawPolygon(head)
        elif self.tool == 'pen':
            path = QPainterPath(start)
            for point in self.points[1:]:
                path.lineTo(point)
            if len(self.points) == 1 or all(point == start for point in self.points):
                painter.drawPoint(start)
            else:
                painter.drawPath(path)
        elif self.tool == 'mosaic' and not self.patch.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawImage(self.rect, self.patch)
        elif self.tool == 'text':
            font = QFont('Microsoft YaHei')
            font.setPixelSize(14 + self.width * 3)
            painter.setFont(font)
            painter.drawText(QRectF(start.x(), start.y(), 10000, 200),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.text)
        painter.restore()
