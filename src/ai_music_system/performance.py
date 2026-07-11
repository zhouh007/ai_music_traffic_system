from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .models import PerformanceRecord
from .storage.file_store import ensure_dir, write_json


class PerformanceStore:
    def __init__(self, data_dir: Path) -> None:
        self.records_dir = data_dir / "performance" / "records"

    def record(self, **values) -> PerformanceRecord:
        record = PerformanceRecord(
            captured_at=datetime.now().isoformat(timespec="microseconds"), **values
        )
        target = ensure_dir(self.records_dir / record.platform / record.song_id)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{uuid4().hex[:8]}"
        write_json(target / f"{stamp}.json", record.model_dump(mode="json"))
        return record

    def summarize(self, platform: str | None = None, song_id: str | None = None) -> dict:
        records = self._load(platform=platform, song_id=song_id)
        latest: dict[tuple[str, str], PerformanceRecord] = {}
        for record in records:
            key = (record.platform, record.song_id)
            if key not in latest or record.captured_at > latest[key].captured_at:
                latest[key] = record
        rows = list(latest.values())
        return {
            "record_count": len(records),
            "latest_song_count": len(rows),
            "totals": {
                "views": sum(row.views for row in rows),
                "likes": sum(row.likes for row in rows),
                "favorites": sum(row.favorites for row in rows),
                "shares": sum(row.shares for row in rows),
                "followers_gained": sum(row.followers_gained for row in rows),
                "revenue": round(sum(row.revenue for row in rows), 2),
            },
            "latest": [row.model_dump(mode="json") for row in rows],
        }

    def _load(self, platform: str | None, song_id: str | None) -> list[PerformanceRecord]:
        if not self.records_dir.exists():
            return []
        records = []
        for path in self.records_dir.rglob("*.json"):
            record = PerformanceRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if platform and record.platform != platform:
                continue
            if song_id and record.song_id != song_id:
                continue
            records.append(record)
        return records
