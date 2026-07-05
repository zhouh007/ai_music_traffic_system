from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


SUSPECT_MARKERS = (
    "锛",
    "銆",
    "闊",
    "鎯",
    "诲",
    "璁",
    "鐭",
    "氬",
)

TEXT_EXTENSIONS = {".txt", ".json", ".csv", ".md"}
DEFAULT_TARGETS = (
    "data/songs",
    "data/exports",
    "data/publish/packages",
    "data/publish/jobs",
)


@dataclass
class RepairResult:
    path: Path
    changed: bool
    reason: str
    preview_before: str = ""
    preview_after: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and repair mojibake-like historical text artifacts.")
    parser.add_argument(
        "--root",
        default="F:\\code\\ai_music_traffic_system",
        help="Project root path.",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Relative directories to scan.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write repaired content back to disk. Default is dry-run.",
    )
    parser.add_argument(
        "--report-json",
        help="Optional report file path for machine-readable output.",
    )
    args = parser.parse_args()

    project_root = Path(args.root)
    results: list[RepairResult] = []

    for target in args.targets:
        target_path = project_root / target
        if not target_path.exists():
            continue
        file_iter = [target_path] if target_path.is_file() else target_path.rglob("*")
        for file_path in file_iter:
            if not file_path.is_file() or file_path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            result = inspect_and_repair_file(file_path, write_changes=args.apply)
            if result is not None:
                results.append(result)

    changed = [item for item in results if item.changed]
    suspicious = [item for item in results if not item.changed]
    summary = {
        "mode": "apply" if args.apply else "dry_run",
        "scanned_targets": args.targets,
        "changed_count": len(changed),
        "suspicious_count": len(suspicious),
        "changed_files": [str(item.path) for item in changed],
        "suspicious_files": [str(item.path) for item in suspicious],
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if results:
        print("\nDetailed results:")
        for item in results:
            print(f"- {item.path}")
            print(f"  reason: {item.reason}")
            if item.preview_before:
                print(f"  before: {item.preview_before}")
            if item.preview_after:
                print(f"  after:  {item.preview_after}")

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "results": [
                        {
                            "path": str(item.path),
                            "changed": item.changed,
                            "reason": item.reason,
                            "preview_before": item.preview_before,
                            "preview_after": item.preview_after,
                        }
                        for item in results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def inspect_and_repair_file(file_path: Path, write_changes: bool) -> RepairResult | None:
    raw_bytes = file_path.read_bytes()

    try:
        original = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        decoded = try_decode_legacy_text(raw_bytes)
        if decoded is None:
            return RepairResult(file_path, changed=False, reason="unrecognized_non_utf8_text")
        if write_changes:
            file_path.write_text(decoded, encoding="utf-8")
        return RepairResult(
            path=file_path,
            changed=True,
            reason="converted_legacy_text_to_utf8",
            preview_before="<non-utf8 text>",
            preview_after=preview_text(decoded),
        )

    if not contains_suspect_markers(original):
        return None

    repaired = try_repair_text(original)
    if repaired == original:
        return RepairResult(
            path=file_path,
            changed=False,
            reason="marker_found_but_no_better_candidate",
            preview_before=preview_text(original),
        )

    if write_changes:
        file_path.write_text(repaired, encoding="utf-8")

    return RepairResult(
        path=file_path,
        changed=True,
        reason="repaired_utf8_gbk_mojibake",
        preview_before=preview_text(original),
        preview_after=preview_text(repaired),
    )


def contains_suspect_markers(text: str) -> bool:
    return any(marker in text for marker in SUSPECT_MARKERS)


def try_repair_text(text: str) -> str:
    candidates = [text]
    for encoding_name in ("gbk", "gb18030"):
        try:
            repaired = text.encode(encoding_name).decode("utf-8")
        except UnicodeError:
            continue
        candidates.append(repaired)

    best = max(candidates, key=score_text_quality)
    return best


def try_decode_legacy_text(raw_bytes: bytes) -> str | None:
    candidates: list[str] = []
    for encoding_name in ("gb18030", "gbk"):
        try:
            candidates.append(raw_bytes.decode(encoding_name))
        except UnicodeError:
            continue
    if not candidates:
        return None
    best = max(candidates, key=score_text_quality)
    return best


def score_text_quality(text: str) -> tuple[int, int, int]:
    chinese_count = sum("\u4e00" <= char <= "\u9fff" for char in text)
    suspect_hits = sum(text.count(marker) for marker in SUSPECT_MARKERS)
    replacement_hits = text.count("�") + text.count("?")
    return (chinese_count, -suspect_hits, -replacement_hits)


def preview_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


if __name__ == "__main__":
    main()
