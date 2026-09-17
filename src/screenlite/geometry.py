"""Coordinate helpers: screen-local logical pixels to native desktop pixels."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("区域宽高必须大于零")


def fit_size(width: int, height: int, max_width: int, max_height: int, even: bool = False):
    if min(width, height, max_width, max_height) <= 0:
        raise ValueError("尺寸必须大于零")
    ratio = min(1.0, max_width / width, max_height / height)
    w, h = max(1, round(width * ratio)), max(1, round(height * ratio))
    if even:
        w, h = max(2, w // 2 * 2), max(2, h // 2 * 2)
    return w, h


def logical_to_physical(local: Rect, monitor: Rect, scale: float) -> Rect:
    if scale <= 0:
        raise ValueError("缩放倍率必须大于零")
    return Rect(monitor.x + round(local.x * scale), monitor.y + round(local.y * scale),
                round(local.width * scale), round(local.height * scale))
