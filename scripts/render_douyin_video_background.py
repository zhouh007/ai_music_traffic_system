from __future__ import annotations

import argparse
import json
import re
import traceback
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageStat
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description="Render one Douyin video in a background process.")
    parser.add_argument("--song-dir", required=True)
    parser.add_argument("--scene", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    song_dir = Path(args.song_dir).resolve()
    status_path = song_dir / "douyin_video_playground_job.json"
    output_path = Path(args.output).resolve()
    try:
        clip = json.loads((song_dir / "douyin_audio_clip.json").read_text(encoding="utf-8"))
        status_path.write_text(
            json.dumps(
                {
                    "status": "running",
                    "output_path": str(output_path),
                    "scene_paths": [str(Path(scene).resolve()) for scene in args.scene],
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _render_precomposed_video(
            song_dir=song_dir,
            scene_paths=[Path(scene).resolve() for scene in args.scene],
            output_path=output_path,
            duration_seconds=float(clip["duration_seconds"]),
        )
        quality_check = _validate_publish_video(output_path, float(clip["duration_seconds"]))
        status_path.write_text(
            json.dumps(
                {
                    "status": "ready",
                    "output_path": str(output_path),
                    "scene_paths": [str(Path(scene).resolve()) for scene in args.scene],
                    "duration_seconds": clip["duration_seconds"],
                    "quality_check": quality_check,
                    "completed_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        status_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "output_path": str(output_path),
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                    "failed_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise


def _render_precomposed_video(*, song_dir: Path, scene_paths: list[Path], output_path: Path, duration_seconds: float) -> None:
    frames_dir = song_dir / "douyin_render_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    if not scene_paths:
        raise ValueError("At least one scene is required.")
    backgrounds = [_prepare_background(scene_path) for scene_path in scene_paths]
    quiet_frames: list[Path] = []
    for index, background in enumerate(backgrounds, start=1):
        quiet = frames_dir / f"quiet_{index:02d}.jpg"
        background.save(quiet, quality=92)
        quiet_frames.append(quiet)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 54)
    subtitles = _read_ass_dialogues(song_dir / "douyin_subtitles.ass")
    rendered: list[tuple[Path, float]] = []
    for index, (start, end, text) in enumerate(subtitles, start=1):
        # Repeat each scene for a small lyric group, then dissolve at the group boundary.
        background = backgrounds[min((index - 1) * len(backgrounds) // max(len(subtitles), 1), len(backgrounds) - 1)]
        frame = background.copy()
        draw = ImageDraw.Draw(frame)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        width = bbox[2] - bbox[0]
        x = (1080 - width) // 2
        y = 1600
        draw.rounded_rectangle((x - 32, y - 18, x + width + 32, y + 88), radius=16, fill=(0, 0, 0, 105))
        draw.text((x, y), text, font=font, fill=(247, 244, 235), stroke_width=2, stroke_fill=(20, 24, 24))
        frame_path = frames_dir / f"frame_{index:02d}.jpg"
        frame.save(frame_path, quality=92)
        rendered.append((frame_path, max(0.3, end - start)))
    if not rendered:
        frame_path = frames_dir / "frame_01.jpg"
        background.save(frame_path, quality=92)
        rendered.append((frame_path, duration_seconds))

    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"]
    transition_seconds = 0.45
    sequence: list[tuple[Path, float]] = []
    cursor = 0.0
    for index, (frame_path, segment_duration) in enumerate(rendered):
        start, end, _ = subtitles[index]
        scene_index = min(index * len(quiet_frames) // max(len(rendered), 1), len(quiet_frames) - 1)
        if start > cursor:
            sequence.append((quiet_frames[scene_index], start - cursor))
        next_starts_immediately = index < len(rendered) - 1 and subtitles[index + 1][0] <= end + 0.01
        transition = transition_seconds if next_starts_immediately else 0.0
        sequence.append((frame_path, max(0.3, segment_duration - transition)))
        if transition:
            sequence.extend(_make_slide_frames(frame_path, rendered[index + 1][0], frames_dir, index + 1, transition))
        cursor = end
    if cursor < duration_seconds:
        sequence.append((quiet_frames[-1], duration_seconds - cursor))
    for frame_path, segment_duration in sequence:
        command.extend(["-loop", "1", "-framerate", "12", "-t", f"{segment_duration:.2f}", "-i", str(frame_path)])
    command.extend(["-i", str(song_dir / "audio_douyin.mp3")])
    video_inputs = "".join(f"[{index}:v]" for index in range(len(sequence)))
    command.extend([
        "-filter_complex", f"{video_inputs}concat=n={len(sequence)}:v=1:a=0[video]",
        "-map", "[video]", "-map", f"{len(sequence)}:a", "-t", f"{duration_seconds:.2f}",
        "-r", "12", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path),
    ])
    subprocess.run(command, check=True, capture_output=True, text=True)


def _prepare_background(scene_path: Path) -> Image.Image:
    _validate_complete_image(scene_path)
    source = Image.open(scene_path).convert("RGB")
    scale = max(1080 / source.width, 1920 / source.height)
    resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - 1080) // 2
    top = (resized.height - 1920) // 2
    return resized.crop((left, top, left + 1080, top + 1920))


def _make_slide_frames(current: Path, following: Path, frames_dir: Path, boundary: int, duration: float) -> list[tuple[Path, float]]:
    """Precompose a short leftward wipe so the final encode has a stable timeline."""
    steps = 6
    with Image.open(current).convert("RGB") as source, Image.open(following).convert("RGB") as incoming:
        outputs: list[tuple[Path, float]] = []
        for step in range(1, steps + 1):
            offset = round(source.width * step / steps)
            canvas = Image.new("RGB", source.size)
            canvas.paste(source.crop((offset, 0, source.width, source.height)), (0, 0))
            canvas.paste(incoming.crop((0, 0, offset, incoming.height)), (source.width - offset, 0))
            output = frames_dir / f"slide_{boundary:02d}_{step:02d}.jpg"
            canvas.save(output, quality=92)
            outputs.append((output, duration / steps))
    return outputs


def _validate_complete_image(path: Path) -> None:
    """Reject partial browser previews before they can become a video background."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()


def _validate_publish_video(path: Path, expected_duration: float) -> dict[str, object]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    inspection = probe.stderr
    duration_match = re.search(r"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)", inspection)
    if duration_match is None:
        raise RuntimeError("ffmpeg could not read the publish video duration")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if "Video:" not in inspection or "Audio:" not in inspection or not re.search(r"\b1080x1920\b", inspection):
        raise RuntimeError("publish video is missing audio or is not 1080x1920")
    if abs(duration - expected_duration) > 0.75:
        raise RuntimeError(f"publish video duration {duration:.2f}s does not match expected {expected_duration:.2f}s")
    brightness: list[float] = []
    for index, timestamp in enumerate((0.5, duration / 2, max(0.5, duration - 0.5)), start=1):
        frame_path = path.with_name(f"{path.stem}_qc_{index}.jpg")
        subprocess.run([ffmpeg, "-y", "-ss", f"{timestamp:.2f}", "-i", str(path), "-frames:v", "1", str(frame_path)], check=True, capture_output=True, text=True)
        with Image.open(frame_path) as frame:
            brightness.append(sum(ImageStat.Stat(frame.convert("L")).mean))
        frame_path.unlink(missing_ok=True)
    if min(brightness) < 4.0:
        raise RuntimeError(f"publish video contains a black frame: brightness={brightness}")
    return {"resolution": "1080x1920", "duration_seconds": round(duration, 2), "audio_present": True, "sample_brightness": [round(value, 2) for value in brightness]}


def _read_ass_dialogues(path: Path) -> list[tuple[float, float, str]]:
    entries: list[tuple[float, float, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) != 10:
            continue
        entries.append((_ass_seconds(parts[1]), _ass_seconds(parts[2]), parts[9].strip()))
    return entries


def _ass_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


if __name__ == "__main__":
    main()
