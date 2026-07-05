from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import ReviewRecord, SongRecord, TopicRecord
from .orchestrator import BatchOrchestrator
from .pipeline.package_builder import (
    build_publish_manifest_entry,
    export_approved_song,
    write_export_manifest,
)
from .review.review_store import load_review, save_review
from .storage.file_store import ensure_dir, write_json
from .storage.run_log import log_step
from .topic_manager import build_topic_record, load_topics_from_csv, write_topics_to_csv


class AutomationService:
    def __init__(self, project_root: Path, config) -> None:
        self.project_root = project_root
        self.config = config
        self.orchestrator = BatchOrchestrator(project_root, config)

    def expand_topics(
        self,
        source_topics_file: Path,
        output_count: int,
        batch_id: str | None = None,
        output_file: Path | None = None,
    ) -> Path:
        source_topics = load_topics_from_csv(source_topics_file)
        if not source_topics:
            raise RuntimeError("No seed topics found in source file.")
        seed_rows = [
            {
                "topic": item.topic,
                "audience": item.audience,
                "mood": item.mood,
                "scene": item.scene,
                "style_hint": item.style_hint,
                "publish_platform": item.publish_platform,
            }
            for item in source_topics[: min(len(source_topics), 8)]
        ]
        target_batch_id = batch_id or f"batch_{datetime.now():%Y%m%d_%H%M%S}_expanded"
        prompt = (
            "Based on the seed topics below, generate new Chinese short-video song topics.\n"
            "Return JSON only. The format must be an array.\n"
            f"Generate exactly {output_count} items.\n"
            "Each item must contain: topic, audience, mood, scene, style_hint, publish_platform.\n"
            "Keep items practical for short-form traffic content and avoid repeating seed wording.\n"
            f"Seed topics: {json.dumps(seed_rows, ensure_ascii=False)}"
        )
        payload = {
            "model": self.config.lyrics_provider.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You generate structured Chinese content ideas and must return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "temperature": min(max(self.config.lyrics_provider.temperature, 0.7), 1.1),
        }
        response = self.orchestrator.http_client.post_json(
            url=self.config.lyrics_provider.base_url.rstrip("/") + "/chat/completions",
            payload=payload,
            bearer_token=self.config.lyrics_provider.api_key,
            timeout_seconds=self.config.lyrics_provider.timeout_seconds,
        )
        raw_content = response["choices"][0]["message"]["content"].strip()
        expanded_payload = _parse_json_block(raw_content)
        if not isinstance(expanded_payload, list) or not expanded_payload:
            raise RuntimeError("Topic expansion provider did not return a valid topic array.")

        topics: list[TopicRecord] = []
        for index, item in enumerate(expanded_payload[:output_count], start=1):
            topics.append(
                build_topic_record(
                    batch_id=target_batch_id,
                    index=index,
                    topic=str(item.get("topic", "")).strip(),
                    audience=str(item.get("audience", source_topics[0].audience)).strip(),
                    mood=str(item.get("mood", source_topics[0].mood)).strip(),
                    scene=str(item.get("scene", source_topics[0].scene)).strip(),
                    style_hint=str(item.get("style_hint", source_topics[0].style_hint)).strip(),
                    publish_platform=str(
                        item.get("publish_platform", source_topics[0].publish_platform)
                    ).strip(),
                )
            )
        if len(topics) < output_count:
            raise RuntimeError(f"Expanded only {len(topics)} topics, expected {output_count}.")

        output_path = output_file or (
            self.config.topics_dir / f"{target_batch_id}.csv"
        )
        write_topics_to_csv(output_path, topics)
        write_json(
            output_path.with_suffix(".response.json"),
            {
                "batch_id": target_batch_id,
                "source_topics_file": str(source_topics_file),
                "raw_content": raw_content,
                "response": response,
            },
        )
        log_step(f"Expanded {len(topics)} topics to {output_path}")
        return output_path

    def schedule_batch(self, topics_file: Path, run_after: str | None = None) -> Path:
        queue_dir = ensure_dir(self.config.queue_dir)
        run_after_value = run_after or datetime.now().isoformat(timespec="seconds")
        job_id = f"job_{datetime.now():%Y%m%d_%H%M%S}"
        job_path = queue_dir / f"{job_id}.json"
        write_json(
            job_path,
            {
                "job_id": job_id,
                "topics_file": str(topics_file),
                "run_after": run_after_value,
                "status": "pending",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "started_at": "",
                "finished_at": "",
                "export_root": "",
            },
        )
        log_step(f"Scheduled batch job {job_id} for {topics_file}")
        return job_path

    def run_scheduled(
        self,
        auto_filter: bool = False,
        min_total_score: int = 12,
        export_approved: bool = False,
    ) -> list[dict]:
        queue_dir = ensure_dir(self.config.queue_dir)
        now = datetime.now()
        results: list[dict] = []
        for job_path in sorted(queue_dir.glob("job_*.json")):
            job = json.loads(job_path.read_text(encoding="utf-8"))
            if job.get("status") != "pending":
                continue
            run_after = datetime.fromisoformat(job["run_after"])
            if run_after > now:
                continue
            topics_file = Path(job["topics_file"])
            job["status"] = "running"
            job["started_at"] = datetime.now().isoformat(timespec="seconds")
            write_json(job_path, job)
            self._run_batch(topics_file)
            batch_id = _read_first_batch_id(topics_file)
            filter_summary = None
            if auto_filter:
                filter_summary = self.auto_filter(batch_id=batch_id, min_total_score=min_total_score)
            export_dir = ""
            if export_approved:
                export_dir = str(self.export_approved())
            job["status"] = "completed"
            job["finished_at"] = datetime.now().isoformat(timespec="seconds")
            job["export_root"] = export_dir
            write_json(job_path, job)
            result = {"job_id": job["job_id"], "topics_file": str(topics_file), "filter_summary": filter_summary}
            results.append(result)
            log_step(f"Completed scheduled job {job['job_id']}")
        return results

    def auto_filter(
        self,
        batch_id: str | None,
        min_total_score: int = 12,
        songs_dir: Path | None = None,
    ) -> dict:
        source_dir = songs_dir or self.config.songs_dir
        approved: list[str] = []
        shortlisted: list[dict] = []
        skipped: list[dict] = []
        for song_dir in sorted(source_dir.iterdir()):
            if not song_dir.is_dir():
                continue
            song_path = song_dir / "song.json"
            topic_path = song_dir / "topic.json"
            review_path = song_dir / "review.json"
            if not song_path.exists() or not topic_path.exists():
                continue
            song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
            if batch_id and song.batch_id != batch_id:
                continue
            topic = TopicRecord.model_validate_json(topic_path.read_text(encoding="utf-8"))
            review = load_review(review_path) if review_path.exists() else ReviewRecord(song_id=song.song_id)
            metrics = _evaluate_song(song, topic)
            total_score = metrics["hook_score"] + metrics["vocal_score"] + metrics["cover_score"]
            if song.status == "generated" and total_score >= min_total_score:
                review.hook_score = metrics["hook_score"]
                review.vocal_score = metrics["vocal_score"]
                review.cover_score = metrics["cover_score"]
                review.publishable = True
                review.notes = metrics["notes"]
                save_review(review_path, review)
                approved.append(song.song_id)
                shortlisted.append(
                    {"song_id": song.song_id, "batch_id": song.batch_id, "total_score": total_score}
                )
            else:
                skipped.append(
                    {
                        "song_id": song.song_id,
                        "batch_id": song.batch_id,
                        "status": song.status,
                        "total_score": total_score,
                    }
                )
        summary = {
            "batch_id": batch_id or "all",
            "min_total_score": min_total_score,
            "approved_count": len(approved),
            "approved_song_ids": approved,
            "shortlisted": shortlisted,
            "skipped": skipped,
        }
        summary_path = ensure_dir(self.config.data_dir / "reports") / (
            f"auto_filter_{batch_id or 'all'}_{datetime.now():%Y%m%d_%H%M%S}.json"
        )
        write_json(summary_path, summary)
        log_step(f"Auto-filter complete: approved={len(approved)} summary={summary_path}")
        return summary

    def process_batch(
        self,
        topics_file: Path,
        auto_expand_count: int = 0,
        auto_filter_enabled: bool = False,
        min_total_score: int = 12,
        export_approved_enabled: bool = False,
    ) -> dict:
        actual_topics_file = topics_file
        expanded_from = ""
        if auto_expand_count > 0:
            actual_topics_file = self.expand_topics(
                source_topics_file=topics_file,
                output_count=auto_expand_count,
            )
            expanded_from = str(topics_file)
        self._run_batch(actual_topics_file)
        filter_summary = None
        if auto_filter_enabled:
            batch_id = _read_first_batch_id(actual_topics_file)
            filter_summary = self.auto_filter(batch_id=batch_id, min_total_score=min_total_score)
        export_dir = ""
        if export_approved_enabled:
            export_dir = str(self.export_approved())
        return {
            "topics_file": str(actual_topics_file),
            "expanded_from": expanded_from,
            "auto_filter": filter_summary,
            "export_dir": export_dir,
        }

    def export_approved(self) -> Path:
        export_root = ensure_dir(self.config.exports_dir / f"approved_{datetime.now():%Y%m%d_%H%M%S}")
        manifest_entries: list[dict] = []
        for song_dir in self.config.songs_dir.iterdir():
            if not song_dir.is_dir():
                continue
            review_path = song_dir / "review.json"
            song_path = song_dir / "song.json"
            if not review_path.exists() or not song_path.exists():
                continue
            review = load_review(review_path)
            if not review.publishable:
                continue
            song = SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
            exported_dir = export_approved_song(song, review, export_root)
            manifest_entries.append(build_publish_manifest_entry(song, review, exported_dir))
        write_export_manifest(export_root, manifest_entries)
        log_step(f"Exported {len(manifest_entries)} approved songs to {export_root}")
        return export_root

    def _run_batch(self, topics_file: Path) -> None:
        topics = load_topics_from_csv(topics_file)
        for topic in topics:
            self.orchestrator.run_topic(topic)


def _parse_json_block(raw_content: str) -> object:
    text = raw_content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        last_fence = text.rfind("```")
        text = text[first_newline + 1 : last_fence].strip()
    return json.loads(text)


def _evaluate_song(song: SongRecord, topic: TopicRecord) -> dict:
    lyrics_length = len(song.lyrics_clean_path.read_text(encoding="utf-8")) if song.lyrics_clean_path.exists() else 0
    audio_exists = song.audio_path.exists() and song.audio_path.stat().st_size > 10_000
    cover_exists = song.cover_publish_path.exists() and song.cover_publish_path.stat().st_size > 1_000
    hook_score = 5 if 80 <= lyrics_length <= 800 else 3 if lyrics_length > 0 else 0
    vocal_score = 5 if audio_exists else 0
    cover_score = 5 if cover_exists else 0
    notes = (
        f"Auto filtered for {topic.publish_platform}; "
        f"lyrics_length={lyrics_length}, audio_exists={audio_exists}, cover_exists={cover_exists}"
    )
    return {
        "hook_score": hook_score,
        "vocal_score": vocal_score,
        "cover_score": cover_score,
        "notes": notes,
    }


def _read_first_batch_id(topics_file: Path) -> str | None:
    topics = load_topics_from_csv(topics_file)
    if not topics:
        return None
    return topics[0].batch_id
