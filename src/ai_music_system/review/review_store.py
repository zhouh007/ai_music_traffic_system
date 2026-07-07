from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..models import ReviewRecord


def save_default_review(
    review_path: Path,
    song_id: str,
    run_id: str = "",
    prompt_version: str = "",
) -> ReviewRecord:
    review = ReviewRecord(
        song_id=song_id,
        run_id=run_id,
        prompt_version=prompt_version,
        review_source="system",
        score_evidence={"reason": "default_review_placeholder"},
    )
    save_review(review_path, review)
    return review


def load_review(review_path: Path) -> ReviewRecord:
    return ReviewRecord.model_validate_json(review_path.read_text(encoding="utf-8"))


def save_review(review_path: Path, review: ReviewRecord) -> None:
    if not review.reviewed_at:
        review.reviewed_at = datetime.now().isoformat(timespec="seconds")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
