from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .audio_review import detect_first_vocal_entry
from .cover_strategy import format_cover_prompt
from .http import JsonHttpClient
from .lyrics_prompting import load_lyrics_prompt
from .models import SongRecord, TopicRecord
from .pipeline.cover_renderer import render_publish_covers
from .pipeline.lyrics_cleaner import normalize_lyrics
from .pipeline.package_builder import build_caption, build_song_metadata
from .platform_profiles import audio_constraints, infer_distribution_target, is_music_platform_target
from .providers.image.openai_compatible_provider import OpenAICompatibleImageProvider
from .local_lyrics import compose_local_lyrics, select_local_title
from .providers.music.minimax_provider import MiniMaxMusicProvider
from .review.review_store import save_default_review
from .storage.file_store import ensure_dir, write_json, write_text
from .storage.run_log import log_step


class BatchOrchestrator:
    def __init__(self, project_root: Path, config) -> None:
        self.project_root = project_root
        self.config = config
        self.http_client = JsonHttpClient()
        self.music_provider = MiniMaxMusicProvider(config.music_provider, self.http_client)
        self.image_provider = OpenAICompatibleImageProvider(config.image_provider, self.http_client)

    def run_topic(self, topic: TopicRecord) -> SongRecord:
        base_song_id = topic.topic_id.replace("tp_", "song_")
        song_id = f"{datetime.now():%Y%m%d}_{base_song_id}"
        song_dir = ensure_dir(self.config.songs_dir / song_id)
        song = self._build_song_record(song_id, topic, song_dir)

        log_step(f"Running topic {topic.topic_id} -> {song.song_id}")
        write_json(song.song_dir / "topic.json", topic.model_dump())
        try:
            lyrics_prompt, prompt_variant = load_lyrics_prompt(self.project_root, topic)
            write_text(song.song_dir / "lyrics_prompt_variant.txt", prompt_variant)
            lyrics_input_path = song.song_dir / "lyrics_input.txt"
            if lyrics_input_path.exists():
                raw_lyrics = lyrics_input_path.read_text(encoding="utf-8")
                write_text(song.song_dir / "lyrics_prompt.txt", "Local lyrics input; no external lyrics provider used.\n")
                write_json(song.song_dir / "lyrics_response.json", {"source": "local_input", "external_provider": False, "path": str(lyrics_input_path)})
            else:
                raw_lyrics = compose_local_lyrics(topic)
                write_text(song.song_dir / "lyrics_prompt.txt", "Local creative-brief composer; no external lyrics provider used.\n")
                write_json(song.song_dir / "lyrics_response.json", {"source": "local_creative_brief", "external_provider": False, "prompt_variant": prompt_variant})
            write_text(song.lyrics_raw_path, raw_lyrics)

            clean_lyrics = normalize_lyrics(raw_lyrics)
            write_text(song.lyrics_clean_path, clean_lyrics)
            title_input_path = song.song_dir / "title_input.txt"
            if title_input_path.exists():
                refined_title = title_input_path.read_text(encoding="utf-8").strip()
                title_prompt = "Local title input; no external title provider used."
                title_response = {"source": "local_input", "external_provider": False, "path": str(title_input_path)}
            else:
                refined_title = select_local_title(topic)
                title_prompt = "Local creative-brief title selector; no external title provider used."
                title_response = {"source": "local_creative_brief", "external_provider": False}
            song.title = refined_title
            write_text(song.song_dir / "title_prompt.txt", title_prompt)
            write_json(song.song_dir / "title_response.json", title_response)
            write_text(song.song_dir / "title_selected.txt", refined_title)

            self._generate_music_with_validation(song=song, topic=topic, lyrics=clean_lyrics)

            cover_status = {
                "status": "pending",
                "song_id": song.song_id,
                "provider": self.config.image_provider.name,
                "model": self.config.image_provider.model,
            }
            try:
                cover_prompt_template = (
                    self.project_root / "src" / "ai_music_system" / "prompts" / "cover_prompt.txt"
                ).read_text(encoding="utf-8")
                cover_prompt, cover_direction = format_cover_prompt(cover_prompt_template, song, topic, clean_lyrics)
                write_text(song.song_dir / "cover_prompt.txt", cover_prompt)
                write_json(song.song_dir / "cover_direction.json", cover_direction)
                cover_meta = self.image_provider.generate_cover(cover_prompt, song.cover_raw_path)
                write_json(song.song_dir / "cover_response.json", cover_meta)
                render_publish_covers(
                    source_path=song.cover_raw_path,
                    publish_path=song.cover_publish_path,
                    hd_path=song.cover_hd_path,
                    title=song.title,
                    publish_size=self.config.cover_publish_size,
                    hd_size=self.config.cover_hd_size,
                )
                cover_status = {
                    "status": "ready",
                    "song_id": song.song_id,
                    "provider": self.config.image_provider.name,
                    "model": self.config.image_provider.model,
                    "prompt": cover_prompt,
                    "source_ids": [],
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "outputs": {
                        "raw": str(song.cover_raw_path),
                        "publish": str(song.cover_publish_path),
                        "hd": str(song.cover_hd_path),
                    },
                }
            except Exception as cover_exc:
                cover_status = {
                    "status": "pending",
                    "song_id": song.song_id,
                    "error_message": str(cover_exc),
                }
                log_step(f"Cover deferred for {song.song_id}: {cover_exc}")
            write_json(song.song_dir / "cover_task.json", cover_status)

            song.status = "generated"
            song.generated_at = datetime.now().isoformat(timespec="seconds")
            write_json(song.meta_path, build_song_metadata(song, topic, self.config))
            write_text(song.caption_path, build_caption(song, topic))
            save_default_review(
                song.review_path,
                song.song_id,
                run_id=song.run_id,
                prompt_version=song.prompt_version,
            )
            log_step(f"Finished song {song.song_id}")
        except Exception as exc:
            song.status = "failed"
            song.error_message = str(exc)
            # Preserve a reviewable failure state so partial outputs can be repaired
            # and re-evaluated without manually reconstructing review.json.
            save_default_review(
                song.review_path,
                song.song_id,
                run_id=song.run_id,
                prompt_version=song.prompt_version,
            )
            write_json(
                song.song_dir / "error.json",
                {
                    "song_id": song.song_id,
                    "topic_id": song.topic_id,
                    "error_message": song.error_message,
                },
            )
            log_step(f"Failed song {song.song_id}: {song.error_message}")
        write_json(song.song_dir / "song.json", song.model_dump(mode="json"))
        return song

    def refine_song_title(self, song_id: str) -> SongRecord:
        song_dir = self.config.songs_dir / song_id
        topic = TopicRecord.model_validate_json((song_dir / "topic.json").read_text(encoding="utf-8"))
        song = SongRecord.model_validate_json((song_dir / "song.json").read_text(encoding="utf-8"))
        lyrics = song.lyrics_clean_path.read_text(encoding="utf-8")
        title_input_path = song.song_dir / "title_input.txt"
        if title_input_path.exists():
            refined_title = title_input_path.read_text(encoding="utf-8").strip()
            title_prompt = "Local title input; no external title provider used."
            title_response = {"source": "local_input", "external_provider": False, "path": str(title_input_path)}
        else:
            refined_title = select_local_title(topic)
            title_prompt = "Local creative-brief title selector; no external title provider used."
            title_response = {"source": "local_creative_brief", "external_provider": False}
        song.title = refined_title
        write_text(song.song_dir / "title_prompt.txt", title_prompt)
        write_json(song.song_dir / "title_response.json", title_response)
        write_text(song.song_dir / "title_selected.txt", refined_title)
        render_publish_covers(
            source_path=song.cover_raw_path,
            publish_path=song.cover_publish_path,
            hd_path=song.cover_hd_path,
            title=song.title,
            publish_size=self.config.cover_publish_size,
            hd_size=self.config.cover_hd_size,
        )
        write_json(song.meta_path, build_song_metadata(song, topic, self.config))
        write_text(song.caption_path, build_caption(song, topic))
        write_json(song.song_dir / "song.json", song.model_dump(mode="json"))
        log_step(f"Refined title for {song.song_id} -> {song.title}")
        return song

    def retry_song_step(self, song_id: str, step: str) -> SongRecord:
        song_dir = self.config.songs_dir / song_id
        topic_path = song_dir / "topic.json"
        if not topic_path.exists():
            raise FileNotFoundError(f"Topic file not found for song: {song_id}")
        topic = TopicRecord.model_validate_json(topic_path.read_text(encoding="utf-8"))
        song_path = song_dir / "song.json"
        song = (
            SongRecord.model_validate_json(song_path.read_text(encoding="utf-8"))
            if song_path.exists()
            else self._build_song_record(song_id, topic, song_dir)
        )
        requested_step = step.strip().lower()
        log_step(f"Retrying {requested_step} for {song_id}")
        if requested_step == "all":
            return self.run_topic(topic)
        if requested_step == "music":
            clean_lyrics = song.lyrics_clean_path.read_text(encoding="utf-8")
            self._generate_music_with_validation(song=song, topic=topic, lyrics=clean_lyrics)
        if requested_step == "cover":
            lyrics = song.lyrics_clean_path.read_text(encoding="utf-8")
            cover_prompt_template = (self.project_root / "src" / "ai_music_system" / "prompts" / "cover_prompt.txt").read_text(encoding="utf-8")
            cover_prompt, cover_direction = format_cover_prompt(cover_prompt_template, song, topic, lyrics)
            write_text(song.song_dir / "cover_prompt.txt", cover_prompt)
            write_json(song.song_dir / "cover_direction.json", cover_direction)
            cover_meta = self.image_provider.generate_cover(cover_prompt, song.cover_raw_path)
            write_json(song.song_dir / "cover_response.json", cover_meta)
            render_publish_covers(
                source_path=song.cover_raw_path,
                publish_path=song.cover_publish_path,
                hd_path=song.cover_hd_path,
                title=song.title,
                publish_size=self.config.cover_publish_size,
                hd_size=self.config.cover_hd_size,
            )
        if requested_step == "package":
            if not song.generated_at:
                song.generated_at = datetime.now().isoformat(timespec="seconds")
            write_json(song.meta_path, build_song_metadata(song, topic, self.config))
            write_text(song.caption_path, build_caption(song, topic))
        song.status = "generated"
        write_json(song.song_dir / "song.json", song.model_dump(mode="json"))
        return song

    def _build_song_record(self, song_id: str, topic: TopicRecord, song_dir: Path) -> SongRecord:
        return SongRecord(
            song_id=song_id,
            topic_id=topic.topic_id,
            batch_id=topic.batch_id,
            run_id=f"run_{datetime.now():%Y%m%d_%H%M%S}_{song_id}",
            prompt_version=self.config.prompt_version,
            title=topic.topic.strip()[:12] if len(topic.topic.strip()) > 12 else topic.topic.strip(),
            mode=topic.generation_mode or "text_to_music",
            status="running",
            song_dir=song_dir,
            lyrics_raw_path=song_dir / "lyrics_raw.txt",
            lyrics_clean_path=song_dir / "lyrics_clean.txt",
            audio_path=song_dir / "audio.mp3",
            cover_raw_path=song_dir / "cover_raw.png",
            cover_publish_path=song_dir / "cover_publish.png",
            cover_hd_path=song_dir / "cover_hd.jpg",
            meta_path=song_dir / "meta.json",
            caption_path=song_dir / "caption.txt",
            review_path=song_dir / "review.json",
        )

    def _generate_music_with_validation(self, *, song: SongRecord, topic: TopicRecord, lyrics: str) -> dict:
        # Keep provider spend predictable: one initial attempt plus at most two retries.
        retry_count = 2
        last_error = ""
        for attempt in range(retry_count + 1):
            style_hint = self._build_music_style_hint(topic, topic.style_hint, attempt)
            try:
                music_meta = self.music_provider.generate_music(
                    lyrics=lyrics,
                    title=song.title,
                    style_hint=style_hint,
                    output_path=song.audio_path,
                    generation_mode=topic.generation_mode,
                    reference_audio_url=topic.reference_audio_url,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < retry_count:
                    log_step(f"Retrying music for {song.song_id}: provider error: {last_error}")
                    continue
                break
            write_json(song.song_dir / f"music_response_attempt_{attempt + 1}.json", music_meta)
            write_json(song.song_dir / "music_response.json", music_meta)
            audio_analysis = self._analyze_audio_result(
                song=song,
                topic=topic,
                music_meta=music_meta,
                attempt=attempt + 1,
            )
            if audio_analysis["status"] in {"passed", "skipped"}:
                return music_meta
            last_error = audio_analysis.get("error_message", "audio validation failed")
            if attempt < retry_count:
                reasons = ", ".join(audio_analysis.get("failed_checks", [])) or "audio validation failed"
                log_step(f"Retrying music for {song.song_id}: {reasons}")
        raise RuntimeError(last_error or f"Music intro validation failed for {song.song_id}")

    def _analyze_audio_result(self, *, song: SongRecord, topic: TopicRecord, music_meta: dict, attempt: int) -> dict:
        intro_result = detect_first_vocal_entry(song.audio_path)
        first_vocal_second = intro_result.get("first_vocal_second")
        constraints = audio_constraints(topic.distribution_target, topic.publish_platform)
        max_intro_seconds = float(constraints["max_intro_seconds"])
        intro_passed = first_vocal_second is not None and float(first_vocal_second) <= max_intro_seconds
        duration_seconds = intro_result.get("audio_duration_seconds") or self._extract_duration_seconds(music_meta)
        min_duration_seconds = float(constraints["min_duration_seconds"])
        preferred_min_duration_seconds = float(self.config.music_platform_preferred_min_duration_seconds) if is_music_platform_target(topic.distribution_target, topic.publish_platform) else min_duration_seconds
        max_duration_seconds = float(constraints["max_duration_seconds"])
        duration_too_short = duration_seconds is None or float(duration_seconds) < min_duration_seconds
        duration_too_long = duration_seconds is not None and float(duration_seconds) > max_duration_seconds
        duration_passed = (not duration_too_short) and (not duration_too_long)
        failed_checks: list[str] = []
        if not intro_passed:
            failed_checks.append(
                f"intro too long at {first_vocal_second}s (limit {max_intro_seconds}s)"
            )
        if duration_too_short:
            failed_checks.append(
                f"duration too short at {duration_seconds}s (minimum {min_duration_seconds}s)"
            )
        if duration_too_long:
            failed_checks.append(
                f"duration too long at {duration_seconds}s (maximum {max_duration_seconds}s)"
            )
        passed = intro_passed and duration_passed
        analysis = {
            "attempt": attempt,
            "status": "passed" if passed else "failed",
            "max_intro_seconds": max_intro_seconds,
            "first_vocal_second": first_vocal_second,
            "duration_seconds": duration_seconds,
            "min_duration_seconds": min_duration_seconds,
            "preferred_min_duration_seconds": preferred_min_duration_seconds,
            "max_duration_seconds": max_duration_seconds,
            "duration_in_preferred_range": (
                duration_seconds is not None
                and preferred_min_duration_seconds <= float(duration_seconds) <= max_duration_seconds
            ),
            "failed_checks": failed_checks,
            "error_message": "" if passed else "; ".join(failed_checks),
            **intro_result,
        }
        write_json(song.song_dir / f"audio_validation_attempt_{attempt}.json", analysis)
        write_json(song.song_dir / "audio_validation.json", analysis)
        write_json(
            song.song_dir / f"audio_intro_analysis_attempt_{attempt}.json",
            {
                "attempt": attempt,
                "status": "passed" if intro_passed else "failed",
                "max_intro_seconds": max_intro_seconds,
                "first_vocal_second": first_vocal_second,
                "error_message": (
                    "" if intro_passed else f"First stable vocal enters at {first_vocal_second}s, exceeding limit {max_intro_seconds}s."
                ),
                **intro_result,
            },
        )
        write_json(
            song.song_dir / "audio_intro_analysis.json",
            {
                "attempt": attempt,
                "status": "passed" if intro_passed else "failed",
                "max_intro_seconds": max_intro_seconds,
                "first_vocal_second": first_vocal_second,
                "error_message": (
                    "" if intro_passed else f"First stable vocal enters at {first_vocal_second}s, exceeding limit {max_intro_seconds}s."
                ),
                **intro_result,
            },
        )
        return analysis

    def _build_music_style_hint(self, topic: TopicRecord, base_style_hint: str, attempt: int) -> str:
        target = infer_distribution_target(topic.distribution_target, topic.publish_platform)
        if target == "short_video":
            baseline_rules = (
                "\n\nShort-video composition requirements:\n"
                "- enter the main vocal or hook within 3 seconds\n"
                "- target 30-90 seconds of immediately usable music\n"
                "- make the opening 20 seconds work as a standalone clip\n"
                "- do not add a cinematic instrumental intro or a long outro"
            )
        elif target == "hybrid":
            baseline_rules = (
                "\n\nHybrid composition requirements:\n"
                "- enter the main vocal or hook within 5 seconds\n"
                "- target 60-150 seconds while preserving a complete emotional arc\n"
                "- make a 10-20 second excerpt independently usable\n"
                "- avoid a long instrumental intro"
            )
        else:
            baseline_rules = (
                "\n\nMusic-platform composition requirements:\n"
                "- this must feel like a complete release-ready full song, not a short clip\n"
                "- target total duration is 195-220 seconds; do not finish before 180 seconds\n"
                "- start clear lead vocal within 5-10 seconds; never use a cinematic or ambient-only opening\n"
                "- choose the section order and repetition pattern for the declared creative mode; do not force verse-pre-chorus-bridge on every song\n"
                "- prioritize a memorable melody, singable rhythm, vocal phrasing, dynamic lift, and a satisfying ending over lyric density\n"
                "- lyrics should leave breathing room for instrumental motifs, vocal ad-libs, melodic repetition, and groove\n"
                "- avoid underdeveloped structure, a single chorus loop, short-video BGM pacing, or an abrupt early ending"
            )
        mode_rules = {
            "mood": "\n\nCreative mode: mood song. Prioritize melodic atmosphere, sensory texture, gentle repetition, humming space, and vocal phrasing over plot or dense lyrics.",
            "healing_gentle": "\n\nCreative mode: healing gentle song. Use a slow, airy vocal flow, spacious phrasing, restrained dynamics, acoustic warmth, and a quiet final lift. Prefer a non-narrative nature-imagery composition built from wind, grass, flowers, trees, rain, clouds, water, light, mist, and distant landscape. Let the sound and scene carry the emotion; do not make the song about a character or a problem that needs solving. Alternate short and long lyric phrases, keep a small set of recurring images, build a simple 4-8 syllable hummable hook, add a brief wordless vocalise or open-vowel response, and leave room for held notes, breaths, humming, instrumental answers, and melodic tails. Avoid dramatic belting, plot-heavy lyrics, motivational slogans, dense metaphors, and long uniform verses.",
            "playful_hook": "\n\nCreative mode: playful hook song. Prioritize a cute rhythmic hook, call-and-response phrasing, small vocal ad-libs, and replayable repetition over narrative detail.",
            "slice_of_life": "\n\nCreative mode: life-slice song. Use separate snapshots and recurring musical motifs; do not force a continuous story.",
            "anthemic": "\n\nCreative mode: anthemic song. Prioritize communal melodic lift and a strong chorus identity over diary-like verses.",
            "narrative": "\n\nCreative mode: narrative song. Use clear scene progression and emotional change.",
        }
        enriched_hint = base_style_hint + mode_rules.get(topic.creative_mode, "") + baseline_rules
        if attempt <= 0:
            return enriched_hint
        constraints = audio_constraints(topic.distribution_target, topic.publish_platform)
        target_vocal_seconds = constraints["max_intro_seconds"]
        if target == "short_video":
            extra_rules = (
                "\n\nShort-video retry requirement:\n"
                f"- stable lead vocal or hook must enter within {target_vocal_seconds:.0f} seconds\n"
                "- keep the result between 30 and 90 seconds and do not add a long intro or outro\n"
                "- make the first 20 seconds immediately usable as a clip"
            )
        elif target == "hybrid":
            extra_rules = (
                "\n\nHybrid retry requirement:\n"
                f"- stable lead vocal or hook must enter within {target_vocal_seconds:.0f} seconds\n"
                "- keep the result between 60 and 150 seconds while preserving an emotional arc\n"
                "- do not delay the first sung line behind ambience"
            )
        else:
            target_duration_seconds = float(self.config.music_platform_retry_target_duration_seconds)
            extra_rules = (
                "\n\nRetry requirement for music-platform release:\n"
                f"- stable lead vocal must enter within {target_vocal_seconds:.0f} seconds\n"
                f"- total song duration must target 200-220 seconds and must not finish before {target_duration_seconds:.0f} seconds\n"
                "- use an instrumental interlude or final lift when it suits the creative mode; repeat the core musical hook before a short outro\n"
                "- do not generate a long instrumental-only intro or collapse the song into a short clip"
            )
        return enriched_hint + extra_rules

    def _extract_duration_seconds(self, music_meta: dict) -> float | None:
        extra_info = music_meta.get("extra_info") or {}
        duration_ms = extra_info.get("music_duration")
        if duration_ms in {None, ""}:
            return None
        try:
            return round(float(duration_ms) / 1000.0, 2)
        except (TypeError, ValueError):
            return None
