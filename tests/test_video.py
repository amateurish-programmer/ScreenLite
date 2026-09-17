import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_record_command_keeps_negative_coordinates_and_even_dimensions(tmp_path):
    from screenlite.video import build_record_command

    path = tmp_path / "录像 文件.mkv"
    args = build_record_command(SimpleNamespace(x=-1920, y=-20, width=801, height=601), path)
    assert args[args.index("-offset_x") + 1] == "-1920"
    assert args[args.index("-offset_y") + 1] == "-20"
    assert args[args.index("-video_size") + 1] == "800x600"
    assert args[args.index("-f") + 1] == "gdigrab"
    assert args[args.index("-c:v") + 1] == "libx264"
    assert args[-1] == str(path)
    assert "-n" in args


def test_ddagrab_uses_explicit_monitor_local_mapping(tmp_path):
    from screenlite.video import build_ddagrab_command

    args = build_ddagrab_command(
        SimpleNamespace(x=40, y=60, width=801, height=601), tmp_path / "record.mkv", output_idx=2
    )
    assert "ddagrab=output_idx=2:framerate=30:offset_x=40:offset_y=60:video_size=800x600" in args
    assert "hwdownload,format=bgra" in args
    assert args[args.index("-c:v") + 1] == "h264_mf"
    assert "-hw_encoding" in args
    assert args[args.index("-hw_encoding") + 1] == "1"
    with pytest.raises(ValueError):
        build_ddagrab_command(SimpleNamespace(x=-40, y=0, width=800, height=600), tmp_path / "bad.mkv")


@pytest.mark.parametrize(
    "rect,fps,backend",
    [
        ((0, 0, 1, 8), 30, "auto"),
        ((0, 0, 8, 8), 0, "auto"),
        ((0, 0, 8, 8), 30, "ddagrab"),
        ((0, 0, 8, 8), 30, "unknown"),
    ],
)
def test_invalid_capture_parameters_are_rejected(tmp_path, rect, fps, backend):
    from screenlite.video import build_record_command

    with pytest.raises(ValueError):
        build_record_command(
            SimpleNamespace(x=rect[0], y=rect[1], width=rect[2], height=rect[3]),
            tmp_path / "record.mkv",
            fps,
            backend,
        )


def test_transcode_command_preserves_optional_audio_and_no_overwrite(tmp_path):
    from screenlite.video import build_transcode_command

    source, target = tmp_path / "输入视频.mp4", tmp_path / "output.mp4"
    args = build_transcode_command(source, target, 1280, 720, "small")
    assert args[args.index("-i") + 1] == str(source)
    assert "0:a?" in args
    assert "aac" in args
    assert args[args.index("-crf") + 1] == "28"
    assert "force_divisible_by=2" in args[args.index("-vf") + 1]
    assert "+faststart" in args
    assert "-n" in args
    assert args[-1] == str(target)
    with pytest.raises(ValueError):
        build_transcode_command(source, source, 1280, 720)


@pytest.fixture
def sample_video(tmp_path):
    from screenlite.media import find_ffmpeg

    ffmpeg = find_ffmpeg(Path(__file__).resolve().parents[1])
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=15:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return ffmpeg, source


def test_real_transcode_is_async_and_produces_playable_even_sized_mp4(qtbot, sample_video, tmp_path):
    from screenlite.video import VideoJob

    ffmpeg, source = sample_video
    before = source.read_bytes()
    target = tmp_path / "压缩.mp4"
    job = VideoJob(tmp_path, ffmpeg=ffmpeg)
    failures, progress = [], []
    job.failed.connect(failures.append)
    job.progress.connect(progress.append)
    with qtbot.waitSignal(job.finished, timeout=30000) as finished:
        job.transcode(source, target, 159, 119)
        assert job.is_running
    assert finished.args == [str(target)]
    assert not failures
    assert progress[-1] == 100
    assert source.read_bytes() == before
    probe = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-i", str(target), "-f", "null", "-"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert probe.returncode == 0
    assert b"158x118" in probe.stderr
    assert b"Audio: aac" in probe.stderr
    assert not list(tmp_path.glob(".*.partial-*"))


def test_transcode_rejects_source_as_target_and_existing_output(qtbot, sample_video, tmp_path):
    from screenlite.video import VideoJob

    ffmpeg, source = sample_video
    original = source.read_bytes()
    job = VideoJob(tmp_path, ffmpeg=ffmpeg)
    with qtbot.waitSignal(job.failed):
        job.transcode(source, source, 160, 120)
    assert source.read_bytes() == original
    assert not job.is_running


def test_failed_ffmpeg_start_emits_once_and_remains_reusable(qtbot, tmp_path):
    from screenlite.video import VideoJob

    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    job = VideoJob(tmp_path, ffmpeg=tmp_path / "missing.exe")
    failures = []
    job.failed.connect(failures.append)
    with qtbot.waitSignal(job.failed, timeout=5000):
        job.transcode(source, tmp_path / "out.mp4", 160, 120)
    assert len(failures) == 1
    assert not job.is_running
    assert not (tmp_path / "out.mp4").exists()


def test_cancel_does_not_publish_or_damage_source(qtbot, sample_video, tmp_path):
    from screenlite.video import VideoJob

    ffmpeg, source = sample_video
    before = source.read_bytes()
    target = tmp_path / "cancelled.mp4"
    job = VideoJob(tmp_path, ffmpeg=ffmpeg)
    completed = []
    job.finished.connect(completed.append)
    job.started.connect(job.cancel)
    with qtbot.waitSignal(job.failed, timeout=10000) as failed:
        job.transcode(source, target, 160, 120)
    assert "取消" in failed.args[0]
    assert not completed
    assert not target.exists()
    assert source.read_bytes() == before
    assert not job.is_running


def test_target_created_during_job_is_preserved_and_partial_retained(qtbot, sample_video, tmp_path):
    from screenlite.video import VideoJob

    ffmpeg, source = sample_video
    target = tmp_path / "competing.mp4"
    job = VideoJob(tmp_path, ffmpeg=ffmpeg)
    with qtbot.waitSignal(job.failed, timeout=30000) as failure:
        job.transcode(source, target, 160, 120)
        target.write_bytes(b"another application wrote this")
    assert target.read_bytes() == b"another application wrote this"
    assert job.partial_path.is_file()
    assert str(job.partial_path) in failure.args[0]


def test_cancel_transcode_removes_partial_after_encoding_starts(qtbot, sample_video, tmp_path, monkeypatch):
    from screenlite import video

    ffmpeg, source = sample_video
    original_builder = video.build_transcode_command

    def realtime_input(*args, **kwargs):
        command = original_builder(*args, **kwargs)
        command.insert(command.index("-i"), "-re")
        return command

    monkeypatch.setattr(video, "build_transcode_command", realtime_input)
    target = tmp_path / "cancelled-after-start.mp4"
    job = video.VideoJob(tmp_path, ffmpeg=ffmpeg)
    job.transcode(source, target, 160, 120)
    qtbot.waitUntil(lambda: job.partial_path.is_file(), timeout=5000)
    with qtbot.waitSignal(job.failed, timeout=10000):
        job.cancel()
    assert not target.exists()
    assert not job.partial_path.exists()


@pytest.mark.parametrize("cancel", [False, True])
def test_record_stop_finalizes_mkv_but_cancel_retains_partial(qtbot, tmp_path, monkeypatch, cancel):
    from PySide6.QtCore import QTimer

    from screenlite import video
    from screenlite.media import find_ffmpeg

    ffmpeg = find_ffmpeg(Path(__file__).resolve().parents[1])

    # Substitute only the capture device: exercise the real long-running process,
    # stdin stop, container finalization and publication without capturing a user desktop.
    def synthetic_capture(rect, path, fps, backend):
        return [
            "-hide_banner",
            "-n",
            "-re",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x48:rate=10",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "ultrafast",
            "-f",
            "matroska",
            str(path),
        ]

    monkeypatch.setattr(video, "build_record_command", synthetic_capture)
    job = video.VideoJob(tmp_path, ffmpeg=ffmpeg)
    target = tmp_path / "record.mkv"
    stop = job.cancel if cancel else job.stop_record
    job.started.connect(lambda: QTimer.singleShot(600, stop))
    with qtbot.waitSignal(job.failed if cancel else job.finished, timeout=10000) as completed:
        job.start_record(SimpleNamespace(x=0, y=0, width=64, height=48), target)
    if cancel:
        assert not target.exists()
        assert job.partial_path.is_file()
        assert str(job.partial_path) in completed.args[0]
        recording = job.partial_path
    else:
        assert completed.args == [str(target)]
        assert target.is_file()
        assert not job.partial_path.exists()
        recording = target
    probe = subprocess.run(
        [str(ffmpeg), "-v", "error", "-i", str(recording), "-f", "null", "-"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert probe.returncode == 0
