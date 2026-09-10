from __future__ import annotations

import tempfile
from pathlib import Path
from typing import BinaryIO

import ffmpeg
import static_ffmpeg


def validate_video(payload: bytes | BinaryIO) -> bool:
    """
    Returns True when the video is corrupted or unreadable.
    """
    if isinstance(payload, bytes):
        data = payload
    else:
        position = None
        try:
            position = payload.tell()
        except (AttributeError, OSError):
            pass
        try:
            payload.seek(0)
        except (AttributeError, OSError):
            pass
        data = payload.read()
        if position is not None:
            try:
                payload.seek(position)
            except OSError:
                pass

    if not data:
        return True

    input_path: Path | None = None
    try:
        static_ffmpeg.add_paths()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".video") as temp_file:
            temp_file.write(data)
            input_path = Path(temp_file.name)

        probe_info = ffmpeg.probe(str(input_path))
        return not any(stream.get("codec_type") == "video" for stream in probe_info.get("streams", ()))
    except (ffmpeg.Error, KeyError, OSError, ValueError):
        return True
    finally:
        if input_path is not None:
            try:
                input_path.unlink()
            except OSError:
                pass


def generate_thumbnail(payload: bytes | BinaryIO) -> bytes:
    """
    Extracts a JPEG thumbnail from a video.
    """
    if isinstance(payload, bytes):
        data = payload
    else:
        position = None
        try:
            position = payload.tell()
        except (AttributeError, OSError):
            pass
        try:
            payload.seek(0)
        except (AttributeError, OSError):
            pass
        data = payload.read()
        if position is not None:
            try:
                payload.seek(position)
            except OSError:
                pass

    if not data:
        raise RuntimeError("No video payload was provided.")

    input_path: Path | None = None
    try:
        static_ffmpeg.add_paths()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".video") as temp_file:
            temp_file.write(data)
            input_path = Path(temp_file.name)

        stdout, _ = (
            ffmpeg
            .input(str(input_path), ss=0)
            .output("pipe:", format="image2", vcodec="mjpeg", vframes=1)
            .run(capture_stdout=True, capture_stderr=True)
        )
        return stdout
    except ffmpeg.Error as exc:
        error_msg = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "Error interno de FFmpeg"
        raise RuntimeError(f"Error al renderizar el thumbnail: {error_msg}") from exc
    finally:
        if input_path is not None:
            try:
                input_path.unlink()
            except OSError:
                pass
