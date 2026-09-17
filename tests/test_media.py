from pathlib import Path

import pytest
from PIL import Image


def test_export_preserves_aspect_and_source_pixels(tmp_path):
    from screenlite.media import export_image

    image = Image.new("RGBA", (800, 400), (255, 0, 0, 128))
    target = tmp_path / "导出.png"
    assert export_image(image, target, 300, 300) == target
    with Image.open(target) as result:
        assert result.size == (300, 150)
        assert result.mode == "RGBA"
    assert image.size == (800, 400)


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".webp"])
def test_export_exact_size_preserves_callers_rounded_pixel_dimensions(tmp_path, suffix):
    from screenlite.media import export_image

    image = Image.new("RGB", (2560, 1600), "navy")
    target = tmp_path / ("custom" + suffix)
    export_image(image, target, 500, 312, exact_size=True)
    with Image.open(target) as result:
        assert result.size == (500, 312)
    assert image.size == (2560, 1600)


@pytest.mark.parametrize("suffix,format_name", [(".jpg", "JPEG"), (".webp", "WEBP"), (".png", "PNG")])
@pytest.mark.parametrize("preset", ["clear", "balanced", "small"])
def test_export_formats_accept_transparent_images(tmp_path, suffix, format_name, preset):
    from screenlite.media import export_image

    target = tmp_path / ("output" + suffix)
    export_image(Image.new("RGBA", (32, 20), (0, 0, 0, 0)), target, 32, 20, preset)
    with Image.open(target) as result:
        assert result.format == format_name
        assert result.size == (32, 20)
        if format_name == "JPEG":
            assert result.getpixel((0, 0)) == (255, 255, 255)


def test_export_never_overwrites_existing_file(tmp_path):
    from screenlite.media import export_image

    target = tmp_path / "original.png"
    target.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        export_image(Image.new("RGB", (4, 4)), target, 4, 4)
    assert target.read_bytes() == b"original"


@pytest.mark.parametrize(
    "width,height,preset,suffix",
    [
        (0, 8, "balanced", ".png"),
        (8, -1, "balanced", ".png"),
        (8, 8, "invalid", ".png"),
        (8, 8, "balanced", ".txt"),
    ],
)
def test_invalid_export_does_not_leave_output(tmp_path, width, height, preset, suffix):
    from screenlite.media import export_image

    with pytest.raises(ValueError):
        export_image(Image.new("RGB", (8, 8)), tmp_path / ("out" + suffix), width, height, preset)
    assert list(tmp_path.iterdir()) == []


def test_find_ffmpeg_prefers_portable_binary(tmp_path):
    from screenlite.media import find_ffmpeg

    binary = tmp_path / "bin" / "ffmpeg.exe"
    binary.parent.mkdir()
    binary.write_bytes(b"portable")
    assert find_ffmpeg(tmp_path) == binary


def test_find_ffmpeg_has_development_fallback(tmp_path):
    from screenlite.media import find_ffmpeg

    assert Path(find_ffmpeg(tmp_path)).is_file()
