from __future__ import annotations

import argparse
import json
from pathlib import Path


KEEP_FILES = {
    "audio.mp3",
    "audio_douyin.mp3",
    "audio_douyin_lyrics.json",
    "audio_douyin_lyrics.txt",
    "audio_intro_analysis.json",
    "audio_validation.json",
    "caption.txt",
    "cover_direction.json",
    "cover_hd.jpg",
    "cover_prompt.txt",
    "cover_publish.png",
    "cover_raw.png",
    "cover_task.json",
    "douyin_audio_clip.json",
    "lyrics_clean.txt",
    "lyrics_prompt.txt",
    "lyrics_prompt_variant.txt",
    "lyrics_raw.txt",
    "meta.json",
    "review.json",
    "song.json",
    "title_prompt.txt",
    "title_selected.txt",
    "topic.json",
}

OBVIOUS_TEMP_PATTERNS = [
    "audio_intro_analysis_attempt_*.json",
    "audio_validation_attempt_*.json",
    "audio_transcript_segments.json",
    "font_test*.png",
    "*_wrong_title.*",
    "*_estimate_extra.mp3",
    "cover_job.log",
]

AGGRESSIVE_PATTERNS = [
    "music_response*.json",
    "cover_response.json",
    "lyrics_response.json",
    "title_response.json",
]


def collect_cleanup_targets(song_dir: Path, aggressive: bool) -> list[Path]:
    patterns = list(OBVIOUS_TEMP_PATTERNS)
    if aggressive:
        patterns.extend(AGGRESSIVE_PATTERNS)

    targets: dict[Path, None] = {}
    for pattern in patterns:
        for path in song_dir.glob(pattern):
            if path.is_file() and path.name not in KEEP_FILES:
                targets[path] = None

    error_path = song_dir / "error.json"
    song_path = song_dir / "song.json"
    if error_path.exists() and _song_is_generated(song_path):
        targets[error_path] = None

    return sorted(targets)


def _song_is_generated(song_path: Path) -> bool:
    if not song_path.exists():
        return False
    try:
        return json.loads(song_path.read_text(encoding="utf-8-sig")).get("status") == "generated"
    except json.JSONDecodeError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean temporary or obsolete artifacts from a generated song folder.")
    parser.add_argument("--song-dir", required=True)
    parser.add_argument("--aggressive", action="store_true", help="Also remove large raw provider response JSON files.")
    parser.add_argument("--execute", action="store_true", help="Delete files. Omit for a dry run.")
    args = parser.parse_args()

    song_dir = Path(args.song_dir).resolve()
    if not song_dir.exists() or not song_dir.is_dir():
        raise FileNotFoundError(f"Song directory not found: {song_dir}")

    targets = collect_cleanup_targets(song_dir, aggressive=args.aggressive)
    total_bytes = sum(path.stat().st_size for path in targets)

    for path in targets:
        print(f"{path.stat().st_size:>12} {path}")

    print(json.dumps({"count": len(targets), "total_bytes": total_bytes, "execute": args.execute}, ensure_ascii=False))

    if args.execute:
        for path in targets:
            path.unlink()


if __name__ == "__main__":
    main()
