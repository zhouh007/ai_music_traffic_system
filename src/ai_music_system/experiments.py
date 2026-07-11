from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import ExperimentRecord
from .storage.file_store import ensure_dir, write_json


class ExperimentStore:
    VALID_STATUSES = {"draft", "running", "completed", "cancelled"}

    def __init__(self, data_dir: Path) -> None:
        self.experiments_dir = data_dir / "experiments"

    def create(self, **values) -> ExperimentRecord:
        record = ExperimentRecord(
            experiment_id=f"exp_{datetime.now():%Y%m%d_%H%M%S}",
            created_at=datetime.now().isoformat(timespec="seconds"),
            **values,
        )
        path = ensure_dir(self.experiments_dir) / f"{record.experiment_id}.json"
        write_json(path, record.model_dump(mode="json"))
        return record

    def update(self, experiment_id: str, status: str | None, song_ids: list[str]) -> ExperimentRecord:
        if status and status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid experiment status: {status}")
        path = self.experiments_dir / f"{experiment_id}.json"
        record = ExperimentRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if status:
            record.status = status
        record.song_ids = list(dict.fromkeys([*record.song_ids, *song_ids]))
        write_json(path, record.model_dump(mode="json"))
        return record

    def list(self) -> list[dict]:
        if not self.experiments_dir.exists():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.experiments_dir.glob("exp_*.json"), reverse=True)
        ]
