from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageEnhance, ImageFilter

from .http import JsonHttpClient
from .models import ImageProviderConfig, SongRecord, TopicRecord
from .providers.image.openai_compatible_provider import OpenAICompatibleImageProvider
from .storage.file_store import write_json, write_text


def build_douyin_video_plan(song: SongRecord, topic: TopicRecord, clip: dict) -> dict:
    title = song.title.strip()
    scene = topic.visual_scene.strip() or topic.scene.strip() or "quiet natural scenery"
    return {
        "format": "1080x1920 vertical lyric video",
        "title": title,
        "audio_path": str(song.douyin_audio_path or song.song_dir / "audio_douyin.mp3"),
        "clip": clip,
        "visual_direction": scene,
        "scene_prompts": [
            f"rain-washed creek reflecting drifting clouds, wet grass at the water edge, soft morning light, no people",
            f"mist lifting from a quiet mountain valley, layers of green trees and pale sky, no people",
            f"close natural detail of raindrops on grass leaves, gentle breeze, warm diffuse light, no people",
            f"wide forest stream with moving cloud shadows and calm water, understated healing mood, no people",
        ],
    }


def _chorus_lines(lyrics: str, limit: int = 8) -> list[str]:
    lines = [line.strip() for line in lyrics.splitlines()]
    start = next((index for index, line in enumerate(lines) if line.lower() in {"[chorus]", "[final chorus]"}), 0)
    selected: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("[") and selected:
            break
        if line and not line.startswith("[") and line.lower() not in {"wu wu wu", "ah ah ah", "la la la"}:
            selected.append(line)
        if len(selected) >= limit:
            break
    return selected or [line for line in lines if line and not line.startswith("[")][:limit]


def write_ass_subtitles(output_path: Path, lyrics: str, duration_seconds: float) -> list[str]:
    lines = _chorus_lines(lyrics)
    weights = [max(len(line.replace(" ", "")), 1) for line in lines]
    total = sum(weights) or 1
    cursor = 0.0
    events: list[str] = []
    for line, weight in zip(lines, weights):
        end = min(duration_seconds, cursor + duration_seconds * weight / total)
        safe_line = line.replace("{", "（").replace("}", "）")
        events.append(f"Dialogue: 0,{_ass_time(cursor)},{_ass_time(end)},Default,,0,0,0,,{safe_line}")
        cursor = end
    content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Microsoft YaHei,48,&H00F7F4EB,&H00F7F4EB,&H80131313,&H80131313,0,0,0,0,100,100,0,0,1,2,1,2,72,72,250,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
""" + "\n".join(events) + "\n"
    write_text(output_path, content)
    return lines


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    return f"{hours}:{minutes:02d}:{remainder // 100:02d}.{remainder % 100:02d}"


def generate_scene_assets(plan: dict, song_dir: Path, image_config: ImageProviderConfig, fallback_image: Path) -> list[Path]:
    scene_dir = song_dir / "douyin_scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    provider = OpenAICompatibleImageProvider(image_config.model_copy(update={"size": "1024x1536"}), JsonHttpClient())
    outputs: list[Path] = []
    for index, direction in enumerate(plan["scene_prompts"], start=1):
        output = scene_dir / f"scene_{index:02d}.png"
        prompt = (
            "Use case: photorealistic-natural\n"
            "Asset type: portrait background for a Chinese healing-music lyric video\n"
            f"Primary request: {direction}\n"
            f"Scene continuity: {plan['visual_direction']}\n"
            "Composition/framing: 9:16 vertical, rich detail across the full frame, no central subject\n"
            "Lighting/mood: calm, gentle, rain-cleared atmosphere, subtle natural greens and cool blue-gray\n"
            "Constraints: no people, no buildings, no text, no letters, no watermark, no collage"
        )
        try:
            provider.generate_cover(prompt, output)
            source = "generated"
        except Exception as exc:
            shutil.copy2(fallback_image, output)
            source = f"fallback_cover: {exc}"
        outputs.append(output)
        write_json(scene_dir / f"scene_{index:02d}.json", {"prompt": prompt, "output_path": str(output), "source": source})
    return outputs


def create_cover_scene_fallbacks(song_dir: Path, fallback_image: Path, count: int = 4) -> list[Path]:
    """Keep a publishable render path available while the external image service is unavailable."""
    scene_dir = song_dir / "douyin_scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(fallback_image).convert("RGB")
    outputs: list[Path] = []
    for index in range(count):
        output = scene_dir / f"scene_{index + 1:02d}.png"
        background = source.resize((1080, 1920), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(18))
        background = ImageEnhance.Brightness(background).enhance(0.52 + index * 0.04)
        foreground_size = 1000 + index * 22
        foreground = source.resize((foreground_size, foreground_size), Image.Resampling.LANCZOS)
        canvas = background.copy()
        x = (1080 - foreground.width) // 2 + (index - 1) * 16
        y = 235 + (index % 2) * 58
        canvas.paste(foreground, (x, y))
        canvas.save(output, quality=95)
        write_json(
            scene_dir / f"scene_{index + 1:02d}.json",
            {"output_path": str(output), "source": "cover_fallback", "source_path": str(fallback_image)},
        )
        outputs.append(output)
    return outputs


def render_douyin_video(*, scene_paths: list[Path], audio_path: Path, subtitle_path: Path, output_path: Path, duration_seconds: float) -> Path:
    if not scene_paths:
        raise ValueError("At least one scene image is required.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_rate = 30
    subtitle = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
    if len(scene_paths) == 1:
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loop", "1", "-framerate", "12", "-i", str(scene_paths[0]), "-i", str(audio_path),
            "-t", f"{duration_seconds:.2f}",
            "-vf", (
                "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"subtitles=filename='{subtitle}'"
            ),
            "-r", "12", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError((exc.stderr or exc.stdout or str(exc)).strip()) from exc
        return output_path
    scene_duration = duration_seconds / len(scene_paths)
    frames = max(1, round(scene_duration * frame_rate))
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"]
    for image in scene_paths:
        command.extend(["-loop", "1", "-t", f"{scene_duration:.3f}", "-i", str(image)])
    command.extend(["-i", str(audio_path)])
    filters = []
    for index in range(len(scene_paths)):
        filters.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='min(zoom+0.00035,1.05)':d={frames}:s=1080x1920:fps={frame_rate},setsar=1[v{index}]"
        )
    filters.append("".join(f"[v{index}]" for index in range(len(scene_paths))) + f"concat=n={len(scene_paths)}:v=1:a=0[base]")
    filters.append(f"[base]subtitles=filename='{subtitle}'[video]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[video]", "-map", f"{len(scene_paths)}:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output_path)])
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError((exc.stderr or exc.stdout or str(exc)).strip()) from exc
    return output_path
