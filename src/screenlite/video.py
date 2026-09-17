"""Asynchronous FFmpeg jobs. All coordinates at this boundary are physical pixels."""

import re
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .media import find_ffmpeg, publish_file

VIDEO_CRF = {"ultra": 16, "clear": 18, "balanced": 23, "small": 28}
VIDEO_MF_QUALITY = {"ultra": 90, "clear": 82, "balanced": 72, "small": 58}
_BASE = ["-hide_banner", "-n", "-progress", "pipe:1", "-nostats"]


def _capture_size(rect, fps: int) -> tuple[int, int]:
    if not isinstance(fps, int) or not 1 <= fps <= 120:
        raise ValueError("录制帧率必须在 1 至 120 之间。")
    if any(not isinstance(getattr(rect, name), int) for name in ("x", "y", "width", "height")):
        raise ValueError("选区必须使用整数物理像素坐标。")
    width, height = rect.width // 2 * 2, rect.height // 2 * 2
    if min(width, height) < 2:
        raise ValueError("视频选区宽高不能小于 2 像素。")
    return width, height


def build_record_command(
    rect,
    path: str | Path,
    fps: int = 30,
    backend: str = "auto",
    *,
    local_rect=None,
    output_idx: int = 0,
    draw_mouse: bool = True,
    quality: str = "balanced",
) -> list[str]:
    """Build recording arguments. rect is global; local_rect is DXGI-local.

    auto intentionally uses gdigrab until a verified DXGI display mapping is
    supplied via an explicitly selected backend. A failed process is never retried against
    a partially written recording.
    """
    width, height = _capture_size(rect, fps)
    if quality not in VIDEO_CRF:
        raise ValueError("未知的视频质量档位。")
    if backend in ("ddagrab-hardware", "ddagrab-software"):
        if local_rect is None or _capture_size(local_rect, fps) != (width, height):
            raise ValueError("ddagrab 需要与全局选区大小一致的屏幕局部坐标。")
        return build_ddagrab_command(
            local_rect,
            path,
            fps,
            output_idx,
            hardware=backend == "ddagrab-hardware",
            draw_mouse=draw_mouse,
            quality=quality,
        )
    if backend not in ("auto", "gdigrab"):
        raise ValueError("此录制入口使用 gdigrab；ddagrab 需要显式的屏幕编号与屏幕局部坐标。")
    return [
        *_BASE,
        "-f",
        "gdigrab",
        "-framerate",
        str(fps),
        "-draw_mouse",
        str(int(bool(draw_mouse))),
        "-offset_x",
        str(rect.x),
        "-offset_y",
        str(rect.y),
        "-video_size",
        f"{width}x{height}",
        "-i",
        "desktop",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        str(VIDEO_CRF[quality]),
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "2",
        "-f",
        "matroska",
        str(path),
    ]


def build_ddagrab_command(
    rect,
    path: str | Path,
    fps: int = 30,
    output_idx: int = 0,
    *,
    hardware: bool = True,
    draw_mouse: bool = True,
    quality: str = "balanced",
) -> list[str]:
    """Explicit hardware strategy: rect must be local to the given DXGI output.

    Callers must verify output_idx and bounds against DXGI enumeration; a Qt
    screen index or a positive desktop-global x/y is not a valid mapping.
    """
    width, height = _capture_size(rect, fps)
    if not isinstance(output_idx, int) or output_idx < 0 or min(rect.x, rect.y) < 0:
        raise ValueError("ddagrab 需要有效屏幕编号与非负的屏幕局部坐标。")
    if quality not in VIDEO_MF_QUALITY:
        raise ValueError("未知的视频质量档位。")
    capture = (
        f"ddagrab=output_idx={output_idx}:framerate={fps}:offset_x={rect.x}:"
        f"offset_y={rect.y}:video_size={width}x{height}:draw_mouse={int(bool(draw_mouse))}"
    )
    return [
        *_BASE,
        "-f",
        "lavfi",
        "-i",
        capture,
        "-vf",
        "hwdownload,format=bgra",
        "-an",
        "-c:v",
        "h264_mf",
        "-hw_encoding",
        str(int(bool(hardware))),
        "-rate_control",
        "quality",
        "-quality",
        str(VIDEO_MF_QUALITY[quality]),
        "-f",
        "matroska",
        str(path),
    ]


def build_transcode_command(
    source: str | Path,
    target: str | Path,
    max_width: int,
    max_height: int,
    preset: str = "balanced",
    *,
    scale_fraction: float | None = None,
) -> list[str]:
    """Fit video without upscaling, keeping even dimensions for H.264 4:2:0."""
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise ValueError("输出文件不能与原文件相同。")
    if preset not in VIDEO_CRF:
        raise ValueError("未知的视频质量档位。")
    if any(not isinstance(value, int) or value < 2 for value in (max_width, max_height)):
        raise ValueError("视频最大宽高必须是至少为 2 的整数。")
    if scale_fraction is not None and (
        not isinstance(scale_fraction, (int, float)) or not 0 < scale_fraction <= 1
    ):
        raise ValueError("视频缩放比例必须大于 0 且不超过 1。")
    factor = f"*{scale_fraction:g}" if scale_fraction is not None else ""
    scale = (
        f"scale=w='max(2,min({max_width},iw{factor}))':h='max(2,min({max_height},ih{factor}))':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
    )
    return [
        *_BASE,
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        scale,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(VIDEO_CRF[preset]),
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "2",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(target),
    ]


def build_probe_command(
    local_rect,
    backend: str,
    *,
    output_idx: int = 0,
    fps: int = 30,
    draw_mouse: bool = True,
    quality: str = "balanced",
) -> list[str]:
    """Encode three desktop frames to the null sink; never create a media file."""
    if backend not in ("ddagrab-hardware", "ddagrab-software"):
        raise ValueError("只能探测明确的 ddagrab 编码后端。")
    command = build_ddagrab_command(
        local_rect,
        "-",
        fps,
        output_idx,
        hardware=backend == "ddagrab-hardware",
        draw_mouse=draw_mouse,
        quality=quality,
    )
    return [*command[:-3], "-frames:v", "3", "-f", "null", "-"]


class RecorderProbe(QObject):
    """Probe an explicitly trusted DXGI mapping before countdown/recording.

    For this release callers only map a single monitor to output_idx=0. Never
    infer a multi-monitor DXGI mapping from Qt screen order. Both MF strategies
    are tested with actual frames, then gdigrab is selected as the compatibility
    fallback (validated when recording starts). Each attempt has a finite timeout.
    cancel is silent and never emits selected. Keep this object alive until
    is_running becomes false after cancellation.
    """

    selected = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, root=None, parent=None, *, ffmpeg=None, timeout_ms: int = 4000):
        super().__init__(parent)
        if timeout_ms < 1:
            raise ValueError("探测超时必须大于 0。")
        self.root = Path(root) if root is not None else Path.cwd()
        self._ffmpeg = Path(ffmpeg) if ffmpeg is not None else None
        self._timeout_ms = timeout_ms
        self._process: QProcess | None = None
        self._active = False
        self._cancelled = False
        self._index = 0
        self._candidates = ("ddagrab-hardware", "ddagrab-software")
        self._rect = None
        self._options = {}
        self._stderr = ""
        self.diagnostics: list[str] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timeout)

    @property
    def is_running(self) -> bool:
        return self._active

    def start(self, local_rect, output_idx=0, fps=30, draw_mouse=True, quality="balanced") -> None:
        if self._active:
            raise RuntimeError("录制能力探测正在运行。")
        try:
            # Validate the actual capture mapping even if a custom probe builder
            # is supplied in tests; this also bounds invalid public parameters.
            build_ddagrab_command(local_rect, "-", fps, output_idx, quality=quality)
            self._ffmpeg = self._ffmpeg or find_ffmpeg(self.root)
        except (OSError, ValueError, RuntimeError) as error:
            self.failed.emit(str(error))
            return
        self._rect = local_rect
        self._options = {"output_idx": output_idx, "fps": fps, "draw_mouse": draw_mouse, "quality": quality}
        self._index = 0
        self._cancelled = False
        self._active = True
        self.diagnostics = []
        self._attempt()

    def _attempt(self) -> None:
        if self._cancelled:
            self._active = False
            self.cancelled.emit()
            return
        if self._index == len(self._candidates):
            self._active = False
            self.selected.emit("gdigrab")
            return
        backend = self._candidates[self._index]
        self._stderr = ""
        process = QProcess(self)
        self._process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        # Bound Qt slots avoid a child->closure->parent ownership cycle during
        # deferred process deletion. Such a cycle can destroy the parent from
        # inside its child's destructor when a short-lived probe loses its owner.
        process.readyReadStandardOutput.connect(self._read_probe_output)
        process.started.connect(self._probe_started)
        process.errorOccurred.connect(self._probe_error)
        process.finished.connect(self._probe_finished)
        try:
            arguments = build_probe_command(self._rect, backend, **self._options)
        except (ValueError, OSError) as error:
            self._release_probe()
            self._active = False
            self.failed.emit(str(error))
            return
        process.start(str(self._ffmpeg), arguments)
        self._timer.start(self._timeout_ms)

    def _probe_started(self) -> None:
        if self._cancelled and self._process:
            self._process.kill()

    def _read_probe_output(self) -> None:
        process = self._process
        if process:
            self._stderr = (self._stderr + bytes(process.readAllStandardOutput()).decode("utf-8", "replace"))[
                -4000:
            ]

    def _timeout(self) -> None:
        if self._active and self._process:
            self.diagnostics.append(f"{self._candidates[self._index]}: 探测超时")
            self._process.kill()

    def cancel(self) -> None:
        if self._active:
            self._cancelled = True
            if self._process:
                self._process.kill()

    def _release_probe(self) -> None:
        self._timer.stop()
        if self._process:
            self._process.deleteLater()
            self._process = None

    def _probe_error(self, error) -> None:
        process = self.sender()
        if process is not self._process or error != QProcess.ProcessError.FailedToStart:
            return
        message = process.errorString()
        self._release_probe()
        self._active = False
        if self._cancelled:
            self.cancelled.emit()
        else:
            self.failed.emit(f"无法启动 FFmpeg：{message}")

    def _probe_finished(self, code: int, status) -> None:
        process = self.sender()
        if process is not self._process:
            return
        self._read_probe_output()
        self._release_probe()
        if self._cancelled:
            self._active = False
            self.cancelled.emit()
        elif code == 0 and status == QProcess.ExitStatus.NormalExit:
            self._active = False
            self.selected.emit(self._candidates[self._index])
        else:
            self.diagnostics.append(f"{self._candidates[self._index]}: {self._stderr[-1200:]}")
            self._index += 1
            self._attempt()


class VideoJob(QObject):
    """Own one asynchronous recording or transcode; keep alive until completion.

    start_record targets MKV; finished yields the MKV after stop_record. The UI
    can then call transcode to export MP4. failed includes a recovery path when
    a partial file exists. cancel retains recordings but removes partial
    transcodes, and emits failed, never finished. Existing files
    and the input are never replaced. No heavy work runs on the GUI thread.
    """

    progress = Signal(int)
    finished = Signal(str)
    failed = Signal(str)
    started = Signal()

    def __init__(self, root: str | Path | None = None, parent=None, *, ffmpeg: str | Path | None = None):
        super().__init__(parent)
        self.root = Path(root) if root is not None else Path.cwd()
        self._ffmpeg = Path(ffmpeg) if ffmpeg is not None else None
        self._process: QProcess | None = None
        self._active = False
        self._mode = ""
        self._target: Path | None = None
        self.partial_path: Path | None = None
        self._cancelled = False
        self._stop_requested = False
        self._stderr = ""
        self._stdout = ""
        self._duration = 0.0
        self._last_progress = -1
        self._stop_timer = QTimer(self)
        self._stop_timer.setSingleShot(True)
        self._stop_timer.timeout.connect(self._kill)

    @property
    def is_running(self) -> bool:
        return self._active

    def _prepare(self, path: str | Path, suffix: str) -> None:
        if self._active:
            raise RuntimeError("已有视频任务正在运行。")
        target = Path(path).absolute()
        if target.suffix.lower() != suffix:
            raise ValueError(f"请选择 {suffix} 文件。")
        if target.exists():
            raise FileExistsError(f"文件已存在，请选择新文件名：{target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._target = target
        self.partial_path = target.with_name(f".{target.stem}.partial-{uuid.uuid4().hex}{suffix}")

    def start_record(
        self,
        rect,
        path: str | Path,
        fps: int = 30,
        backend: str = "auto",
        *,
        local_rect=None,
        output_idx: int = 0,
        draw_mouse: bool = True,
        quality: str = "balanced",
    ) -> None:
        if self._active:
            raise RuntimeError("已有视频任务正在运行。")
        try:
            self._prepare(path, ".mkv")
            args = build_record_command(
                rect,
                self.partial_path,
                fps,
                backend,
                local_rect=local_rect,
                output_idx=output_idx,
                draw_mouse=draw_mouse,
                quality=quality,
            )
            self._launch(args, "record")
        except (OSError, ValueError, RuntimeError) as error:
            self.failed.emit(str(error))

    def transcode(
        self, source, target, max_width, max_height, preset="balanced", *, scale_fraction=None
    ) -> None:
        if self._active:
            raise RuntimeError("已有视频任务正在运行。")
        try:
            source = Path(source).absolute()
            if not source.is_file():
                raise FileNotFoundError(f"找不到原文件：{source}")
            # Validate the public source/target pair before substituting staging.
            build_transcode_command(
                source, target, max_width, max_height, preset, scale_fraction=scale_fraction
            )
            self._prepare(target, ".mp4")
            args = build_transcode_command(
                source, self.partial_path, max_width, max_height, preset, scale_fraction=scale_fraction
            )
            self._launch(args, "transcode")
        except (OSError, ValueError, RuntimeError) as error:
            self.failed.emit(str(error))

    def _launch(self, args: list[str], mode: str) -> None:
        executable = self._ffmpeg or find_ffmpeg(self.root)
        self._mode = mode
        self._cancelled = False
        self._stop_requested = False
        self._stderr = ""
        self._stdout = ""
        self._duration = 0.0
        self._last_progress = -1
        process = QProcess(self)
        self._process = process
        process.setProgram(str(executable))
        process.setArguments(args)
        process.readyReadStandardError.connect(self._read_stderr)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.started.connect(self._started)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._finished)
        self._active = True
        self.progress.emit(0)
        process.start()

    def _started(self) -> None:
        self.started.emit()
        if self._stop_requested or self._cancelled:
            self._request_stop()

    def stop_record(self) -> None:
        if self._active and self._mode == "record":
            self._stop_requested = True
            self._request_stop()

    def cancel(self) -> None:
        if self._active:
            self._cancelled = True
            self._request_stop()

    def _request_stop(self) -> None:
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.write(b"q\n")
        if not self._stop_timer.isActive():
            self._stop_timer.start(5000 if self._cancelled else 15000)

    def _kill(self) -> None:
        if self._active and self._process:
            self._process.kill()

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        self._stderr = (
            self._stderr + bytes(self._process.readAllStandardError()).decode("utf-8", "replace")
        )[-16000:]
        if not self._duration:
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", self._stderr)
            if match:
                hours, minutes, seconds = map(float, match.groups())
                self._duration = hours * 3600 + minutes * 60 + seconds

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        self._stdout += bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace")
        while "\n" in self._stdout:
            line, self._stdout = self._stdout.split("\n", 1)
            if line.startswith("out_time_us=") and self._duration:
                try:
                    value = min(99, max(0, int(int(line.split("=", 1)[1]) / (self._duration * 10000))))
                except ValueError:
                    continue
                if value > self._last_progress:
                    self._last_progress = value
                    self.progress.emit(value)

    def _process_error(self, error) -> None:
        if self._active and error == QProcess.ProcessError.FailedToStart:
            self._fail(f"无法启动 FFmpeg：{self._process.errorString()}")

    def _release(self) -> None:
        self._active = False
        self._stop_timer.stop()
        if self._process:
            self._process.deleteLater()
            self._process = None

    def _fail(self, message: str) -> None:
        if self.partial_path and self.partial_path.is_file():
            message += f"\n临时文件已保留，可尝试恢复：{self.partial_path}"
        self._release()
        self.failed.emit(message)

    def _finished(self, exit_code: int, exit_status) -> None:
        if not self._active:
            return
        self._read_stderr()
        self._read_stdout()
        if self._cancelled:
            if self._mode == "transcode" and self.partial_path:
                try:
                    self.partial_path.unlink(missing_ok=True)
                except OSError as error:
                    self._fail(f"任务已取消，但无法删除临时文件：{error}")
                    return
            self._fail("任务已取消。")
        elif exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            self._fail(f"FFmpeg 处理失败（退出码 {exit_code}）。\n{self._stderr[-2500:]}")
        elif self._mode == "record" and not self._stop_requested:
            self._fail("录制意外结束。")
        elif (
            not self.partial_path or not self.partial_path.is_file() or self.partial_path.stat().st_size == 0
        ):
            self._fail("FFmpeg 没有生成有效输出。")
        else:
            try:
                publish_file(self.partial_path, self._target)
            except OSError as error:
                self._fail(f"无法保存输出：{error}")
                return
            target = str(self._target)
            self._release()
            self.progress.emit(100)
            self.finished.emit(target)
