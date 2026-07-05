from __future__ import annotations

from datetime import datetime


def log_step(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")
