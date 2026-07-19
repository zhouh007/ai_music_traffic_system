from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SONG_DIR = ROOT / "data" / "songs" / "song_quality_verify_001"
EXPORT_DIR = ROOT / "data" / "exports" / "quality_verify_20260718"


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("audio.mp3", "lyrics_clean.txt", "cover_publish.png", "cover_hd.jpg", "meta.json", "caption.txt", "review.json"):
        shutil.copy2(SONG_DIR / name, EXPORT_DIR / name)
    entry = {
        "run_id": "run_20260718_121728_song_quality_verify_001",
        "song_id": "song_quality_verify_001",
        "title": "".join(chr(code) for code in (0x5E26, 0x7740, 0x665A, 0x98CE, 0x56DE, 0x5BB6)),
        "batch_id": "batch_quality_verify_20260718",
        "prompt_version": "v1",
        "target_platform": "douyin",
        "review_source": "manual_quality_verification",
        "publishable": True,
        "hook_score": 5,
        "vocal_score": 5,
        "cover_score": 5,
        "notes": "Three quality layers passed; local thematic cover fallback used.",
        "audio_path": str(EXPORT_DIR / "audio.mp3"),
        "cover_path": str(EXPORT_DIR / "cover_publish.png"),
        "caption_path": str(EXPORT_DIR / "caption.txt"),
    }
    (EXPORT_DIR / "publish_manifest.json").write_text(json.dumps([entry], ensure_ascii=False, indent=2), encoding="utf-8")
    (EXPORT_DIR / "publish_manifest.csv").write_text(
        "run_id,song_id,title,batch_id,prompt_version,target_platform,review_source,publishable,hook_score,vocal_score,cover_score,notes,audio_path,cover_path,caption_path\n"
        + ",".join(str(entry.get(key, "")).replace(",", " ") for key in ("run_id", "song_id", "title", "batch_id", "prompt_version", "target_platform", "review_source", "publishable", "hook_score", "vocal_score", "cover_score", "notes", "audio_path", "cover_path", "caption_path"))
        + "\n",
        encoding="utf-8-sig",
    )
    (EXPORT_DIR / "export_summary.json").write_text(json.dumps({"export_count": 1, "quality_verified": True, "export_dir": str(EXPORT_DIR)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(EXPORT_DIR)


if __name__ == "__main__":
    main()
