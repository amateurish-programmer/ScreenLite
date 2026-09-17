"""Desktop capture happens before any selection overlay appears."""
import mss
from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from screenlite.geometry import Rect


def capture_monitor(bounds: Rect) -> Image.Image:
    with mss.mss() as grabber:
        frame = grabber.grab({'left': bounds.x, 'top': bounds.y,
                             'width': bounds.width, 'height': bounds.height})
        return Image.frombytes('RGB', frame.size, frame.rgb)


def image_pixmap(image: Image.Image, scale: float = 1.0) -> QPixmap:
    rgba = image.convert('RGBA')
    qimage = QImage(rgba.tobytes(), rgba.width, rgba.height,
                    rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
    pixmap = QPixmap.fromImage(qimage)
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def qimage_pil(image: QImage) -> Image.Image:
    """Detach only the selected physical pixels from Qt for read-only export."""
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes('RGBA', (rgba.width(), rgba.height()), rgba.constBits(),
                           'raw', 'RGBA', rgba.bytesPerLine())
