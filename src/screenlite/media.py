"""Image encoding and portable FFmpeg discovery (no UI dependencies)."""

import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_QUALITY = {"clear": (95, 92), "balanced": (88, 82), "small": (75, 68)}


def find_ffmpeg(root: str | Path) -> Path:
    """Prefer the portable distribution, then PATH, then the optional dev wheel."""
    bundled = Path(root) / "bin" / "ffmpeg.exe"
    if bundled.is_file():
        return bundled
    executable = shutil.which("ffmpeg")
    if executable:
        return Path(executable)
    try:
        import imageio_ffmpeg

        executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if executable.is_file():
            return executable
    except (ImportError, RuntimeError, OSError):
        pass
    raise FileNotFoundError("未找到 FFmpeg，请将 ffmpeg.exe 放入程序目录的 bin 文件夹。")


def publish_file(temporary: Path, target: Path) -> None:
    """Publish a complete file without replacing a concurrently created target."""
    if os.name == "nt":
        # Windows rename refuses existing targets and also works on FAT/exFAT.
        temporary.rename(target)
    else:
        # POSIX rename replaces existing files; link instead for no-clobber.
        os.link(temporary, target)
        temporary.unlink()


def export_image(
    image: Image.Image,
    path: str | Path,
    width: int,
    height: int,
    preset: str = "balanced",
    *,
    exact_size: bool = False,
) -> Path:
    """Fit inside the requested box and atomically export to a *new* path.

    By default width/height are bounding limits and aspect ratio is preserved.
    A caller that already computed and displayed rounded pixel dimensions may
    set exact_size=True to use those exact dimensions without a second aspect
    fit. The caller then owns aspect-ratio calculation (including EXIF rotation).
    Call this synchronous encoder from a worker for large images. JPEG alpha is
    composited on white; PNG stays lossless for all three quality presets.
    """
    target = Path(path)
    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
    if preset not in IMAGE_QUALITY:
        raise ValueError("未知的图片质量档位。")
    if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 1:
        raise ValueError("图片尺寸必须是正整数。")
    format_name = formats.get(target.suffix.lower())
    if format_name is None:
        raise ValueError("图片格式仅支持 PNG、JPEG 和 WebP。")
    if target.exists():
        raise FileExistsError(f"文件已存在，请选择新文件名：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    oriented = ImageOps.exif_transpose(image)
    if exact_size:
        resized = oriented.resize((width, height), Image.Resampling.LANCZOS)
    else:
        resized = ImageOps.contain(oriented, (width, height), Image.Resampling.LANCZOS)
    options = {}
    if format_name == "JPEG":
        rgba = resized.convert("RGBA")
        resized = Image.new("RGB", rgba.size, "white")
        resized.paste(rgba, mask=rgba.getchannel("A"))
        options = {"quality": IMAGE_QUALITY[preset][0], "optimize": True}
    elif format_name == "WEBP":
        resized = resized.convert(
            "RGBA" if "A" in resized.getbands() or "transparency" in resized.info else "RGB"
        )
        options = {"quality": IMAGE_QUALITY[preset][1], "method": 6 if preset == "small" else 4}
    else:
        options = {"optimize": True}
    descriptor, filename = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=".tmp", dir=target.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            resized.save(stream, format=format_name, **options)
            stream.flush()
            os.fsync(stream.fileno())
        publish_file(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
