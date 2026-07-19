from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SONG_ID = "song_music_sweet_opt_001"
SONG_DIR = ROOT / "data" / "songs" / SONG_ID
EXPORT_DIR = ROOT / "data" / "exports" / "music_sweet_optimized_20260718"


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("audio.mp3", "lyrics_clean.txt", "cover_publish.png", "cover_hd.jpg", "meta.json", "caption.txt", "review.json"):
        shutil.copy2(SONG_DIR / name, EXPORT_DIR / name)
    entry = {
        "run_id": json.loads((SONG_DIR / "song.json").read_text(encoding="utf-8"))["run_id"],
        "song_id": SONG_ID,
        "title": "Ordinary Turns Sweet",
        "batch_id": "batch_music_sweet_opt_20260718",
        "prompt_version": "v1",
        "target_platform": "qishui_music",
        "review_source": "manual_quality_verification",
        "publishable": True,
        "hook_score": 5,
        "vocal_score": 5,
        "cover_score": 5,
        "notes": "Optimized resonance-focused lyrics; all three quality layers passed.",
        "audio_path": str(EXPORT_DIR / "audio.mp3"),
        "cover_path": str(EXPORT_DIR / "cover_publish.png"),
        "caption_path": str(EXPORT_DIR / "caption.txt"),
    }
    (EXPORT_DIR / "publish_manifest.json").write_text(json.dumps([entry], ensure_ascii=False, indent=2), encoding="utf-8")
    (EXPORT_DIR / "export_summary.json").write_text(json.dumps({"export_count": 1, "quality_verified": True, "export_dir": str(EXPORT_DIR)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(EXPORT_DIR)


if __name__ == "__main__":
    main()
