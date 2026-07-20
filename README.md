# AI Music Traffic System

AI music generation and publishing workflow focused on traffic growth first.

## Phase 1 target

Build a real publishable local workflow:

1. Load topics
2. Generate lyrics
3. Clean lyrics
4. Generate music
5. Generate covers
6. Package publish assets
7. Review manually
8. Export approved songs

This project is intentionally:

- local-first
- CLI-driven
- file-based
- provider-replaceable
- semi-automatic in v1

## Project structure

```text
src/ai_music_system/
  cli.py
  config.py
  models.py
  orchestrator.py
  topic_manager.py
  prompts/
  pipeline/
  providers/
  storage/
  review/

config/
data/
scripts/
```

## Quick start

### 1. Create venv

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install package

```powershell
pip install -e .
```

### 3. Configure API keys

Preferred local setup:

1. Copy `.env.example` to `.env`
2. Fill in your real keys

Or set environment variables manually:

```powershell
$env:DEEPSEEK_API_KEY="your_key"
$env:MINIMAX_API_KEY="your_key"
$env:AGNES_API_KEY="your_key"
```

Optional local override file:

`config/providers.local.json`

The lyrics provider is OpenAI-compatible at the HTTP layer, so you can point it to a relay such as `cc switch` by overriding:

- `lyrics_provider.base_url`
- `lyrics_provider.model`
- `lyrics_provider.api_key` or `lyrics_provider.api_key_env`

Important:

- `cc switch -> GPT` can replace lyrics generation
- it does not replace the music generation provider
- song audio still needs a music model such as MiniMax

MiniMax note:

- the current working endpoint in this project is `https://api.minimaxi.com/v1`
- the default text-to-music model is `music-2.6-free`
- optional reference-audio mode uses `music-cover-free`
- use `generation_mode=text_to_music` for normal lyric-driven generation
- use `generation_mode=reference_audio` only when you have a valid `reference_audio_url`
- use `distribution_target=short_video|hybrid|music_platform` to steer lyrics structure by release goal
- use `config/pipeline.local.json` to override `target_platform` and `prompt_version` for the current release strategy
- `music_platform_intro_max_seconds` can enforce a maximum allowed lead-vocal entry time for music-platform songs
- `music_platform_min_duration_seconds` defines the hard minimum acceptable music-platform song length
- `music_platform_preferred_min_duration_seconds` documents the preferred lower bound for longform release quality
- `music_platform_max_duration_seconds` defines an upper bound to catch unexpectedly long outputs
- music-platform generation uses a fixed maximum of two retries to keep the workflow simple and predictable
- `music_platform_retry_target_vocal_seconds` makes retry prompts stricter than the final hard threshold
- `music_platform_retry_target_duration_seconds` makes retry prompts ask for a longer full-song result than the hard minimum

### 4. Prepare topics

Edit:

`data/topics/topics_master.csv`

Topic CSV supports:

- `distribution_target=short_video`
- `distribution_target=hybrid`
- `distribution_target=music_platform`

Suggested usage:

- `short_video`: Douyin / Kuaishou first, stronger early hook
- `hybrid`: shared default for short video plus music distribution
- `music_platform`: Fanqie Music / Qishui Music first, more complete single-song feel

Platform profile reminder:

- `fanqie_music` and `qishui_music` should default to the `music_platform` creative profile
- `douyin`, `kuaishou`, `xiaohongshu`, and similar traffic-first video surfaces should default to `short_video`
- do not assume a song that worked for short-video distribution is automatically suitable for music-platform release

Music-platform generation expectations:

- full-song structure rather than short-video BGM structure
- target duration should usually be at least `2:45`
- preferred duration range should usually be `3:00-4:00`
- vocal entry should usually arrive within about `2-3` seconds
- avoid long instrumental intros when the target is a formal music-platform release
- generated audio is now checked after creation, and tracks with lead vocals entering after the configured intro limit are regenerated automatically
- generated audio duration is also checked after creation, and tracks that land outside the configured music-platform duration window are regenerated automatically
- chorus should contain a short repeatable hook that is memorable on first listen
- verses should lean on concrete everyday imagery instead of abstract emotional filler
- healing / late-night songs should still lift slightly emotionally rather than staying flat
- line lengths should stay singable and rhythmically even for AI vocal generation
- the first lines of the chorus should also work well as a `10-20` second shareable snippet
- title generation should balance platform clarity with release-grade subtlety: easy to remember, but still emotionally specific and not slogan-like
- cover direction should default to soft healing illustration with calm, gently uplifting energy instead of neon urban or dark cinematic moods unless the song explicitly requires otherwise

Short-video generation expectations:

- hook-first creative structure
- shorter duration is acceptable
- snippet and repost friendliness matter more than full-song pacing

### 5. Run a batch

```powershell
python -m ai_music_system.cli run-batch --topics-file data/topics/topics_master.csv
```

To use human-written lyrics without an external lyrics model, create these files before running:

- `data/songs/<song_id>/lyrics_input.txt` (required)
- `data/songs/<song_id>/title_input.txt` (optional; avoids external title generation too)

The remaining music, cover, packaging, and quality-validation steps stay automatic.

### 6. Export approved songs

```powershell
python -m ai_music_system.cli export-approved
```

### 7. Approve a song for export

```powershell
python -m ai_music_system.cli approve-song --song-id song_20260704_001
```

### 8. List review status for all songs

```powershell
python -m ai_music_system.cli review-list
python -m ai_music_system.cli workflow-status
python -m ai_music_system.cli workflow-next
```

Review rows now include:

- `run_id`
- `prompt_version`
- `review_source`
- score breakdown and evidence summary
- target-platform alignment and traceability state
- `workflow-next` can preview the recommended next primary-platform step, and `--execute` can run that step

## Content quality requirements

Lyrics and title creation are local-first. The active production path does not call an external lyrics or title model: local lyrics input is used when present, otherwise the built-in creative-brief composer and title selector are used. The legacy lyrics provider configuration remains for backward compatibility only.

Generation topics may include a creative brief in addition to the legacy topic fields:

- `user_need`: the concrete situation in which a listener or creator will use the song
- `core_conflict`: the human or relationship tension that drives the lyric
- `unique_observation`: a non-generic detail that must become a memorable lyric line
- `emotional_payoff`: the emotional change the listener should receive
- `visual_scene`: the concrete scene that can guide both lyrics and cover direction
- `series_name`: the recurring content series, when the song belongs to one

Legacy topic CSV files remain readable, but new production topics should fill at least four of the five creative-brief fields before generation.

Quality evaluation now has three layers:

1. Technical: required assets, readable text, duration, vocal entry, and cover dimensions.
2. Content: song structure, concrete imagery, controlled abstraction, repeatable hook, and creative-brief completeness.
3. Context: valid distribution target, usable scene, and defined audience.

A song is not publishable when any layer fails. Short-video songs optimize for an early usable excerpt; music-platform songs optimize for a complete single and second-listen value.

### 9. Approve a whole batch

```powershell
python -m ai_music_system.cli approve-batch --batch-id batch_20260705_live
```

### 10. Retry selected steps for one song

```powershell
python -m ai_music_system.cli retry-song --song-id song_20260705_001 --step cover
```

### 11. Expand seed topics into a new batch

```powershell
python -m ai_music_system.cli expand-topics --topics-file data/topics/topics_master.csv --count 5
```

### 12. Queue a batch for later processing

```powershell
python -m ai_music_system.cli schedule-batch --topics-file data/topics/live_batch.csv --run-after 2026-07-05T21:00:00
```

### 13. Run due queued jobs

```powershell
python -m ai_music_system.cli run-scheduled --auto-filter --export-approved
```

### 14. Auto filter generated songs with simple rules

```powershell
python -m ai_music_system.cli auto-filter --batch-id batch_20260705_live --min-total-score 12
```

### 15. Run a one-shot automated batch

```powershell
python -m ai_music_system.cli process-batch --topics-file data/topics/live_batch.csv --auto-filter --export-approved
```

### 15.1 Record platform performance manually

```powershell
python -m ai_music_system.cli performance-record --song-id song_001 --platform fanqie_music --window 7d --views 120 --favorites 8 --shares 2
python -m ai_music_system.cli performance-summary --platform fanqie_music
```

Snapshots are append-only under `data/performance/records`. Summaries use the latest snapshot for each platform/song pair.

### 15.2 Manage controlled experiments

```powershell
python -m ai_music_system.cli experiment-create --name "Earlier hook" --hypothesis "An earlier chorus increases favorites" --variable "chorus timing" --control-prompt-version v2 --variant-prompt-version v3 --primary-metric favorites
python -m ai_music_system.cli experiment-update --experiment-id exp_20260711_120000 --status running --song-ids song_001,song_002
python -m ai_music_system.cli experiment-list
```

Change one declared variable per experiment. Experiment definitions are stored under `data/experiments`.

### 16. Create multi-platform publish jobs from an approved export

```powershell
python -m ai_music_system.cli prepare-publish --export-dir data/exports/approved_20260705_075544 --platforms douyin,kuaishou,bilibili,xiaohongshu,fanqie_music,qishui_music
python -m ai_music_system.cli prepare-publish --export-dir data/exports/approved_20260705_075544
```

If `--platforms` is omitted, the command uses the configured primary `target_platform`.

This step creates platform-ready publish packages, including:

- adapted caption text
- `publish_video.mp4` generated from cover plus audio for short-video platforms
- audio-first package output for `fanqie_music` and `qishui_music`
- per-job JSON status files

Music-platform package contents:

- `audio.mp3`
- `cover_publish.png`
- `lyrics_clean.txt`
- `meta.json`
- `publish_text.txt`
- `release_brief.json` for `fanqie_music`

Important:

- packaging for a music platform does not by itself guarantee the creative output is longform enough
- before approving songs for `fanqie_music` or `qishui_music`, verify duration, vocal-entry timing, and full-song feel
- if a song lands too short or too intro-heavy, regenerate it under stricter `music_platform` assumptions instead of forcing it through release packaging

### 17. List publish jobs

```powershell
python -m ai_music_system.cli publish-target
python -m ai_music_system.cli publish-list
python -m ai_music_system.cli publish-list --active-only
python -m ai_music_system.cli publish-list --traceability-state legacy_partial --all-platforms
python -m ai_music_system.cli publish-list --all-platforms
python -m ai_music_system.cli publish-list --platform douyin --status ready
python -m ai_music_system.cli publish-list --batch-id batch_20260705_live
python -m ai_music_system.cli publish-list --run-id run_20260706_002444_song_verify_001
```

### 17.1 Summarize publish queue status

```powershell
python -m ai_music_system.cli publish-summary
python -m ai_music_system.cli publish-summary --active-only --all-platforms --pretty
python -m ai_music_system.cli publish-summary --traceability-state legacy_partial --all-platforms --pretty
python -m ai_music_system.cli publish-summary --all-platforms
python -m ai_music_system.cli publish-summary --platform douyin
python -m ai_music_system.cli publish-summary --pretty
```

### 17.1.1 Archive or restore legacy publish carry-over

```powershell
python -m ai_music_system.cli publish-archive-legacy
python -m ai_music_system.cli publish-archive-legacy --from-status pending,ready
python -m ai_music_system.cli publish-archive-list
python -m ai_music_system.cli publish-archive-restore --label legacy_20260706_220000
```

Notes:

- `publish-archive-legacy` only archives `legacy_partial` jobs
- archive buckets are stored under `data/publish/archive/`
- restore moves the archived JSON job files back into `data/publish/jobs`
- this is intended to reduce daily queue noise without deleting historical evidence

### 17.2 Inspect one publish job in detail

```powershell
python -m ai_music_system.cli publish-show --job-id pub_douyin_song_20260705_001_20260705_120000
```

### 18. Validate or launch a publish job

```powershell
python -m ai_music_system.cli publish-run --job-id pub_douyin_song_20260705_001_20260705_120000
python -m ai_music_system.cli publish-run --job-id pub_douyin_song_20260705_001_20260705_120000 --launch-browser
```

### 18.1 Run due scheduled publish jobs in batch

```powershell
python -m ai_music_system.cli publish-run-due
python -m ai_music_system.cli publish-run-due --all-platforms
python -m ai_music_system.cli publish-run-due --platform bilibili --limit 3
python -m ai_music_system.cli publish-run-due --launch-browser --platform douyin
```

### 19. Mark publish result

```powershell
python -m ai_music_system.cli publish-complete --job-id pub_douyin_song_20260705_001_20260705_120000 --external-post-id 123456
python -m ai_music_system.cli publish-fail --job-id pub_douyin_song_20260705_001_20260705_120000 --reason "Upload rejected"
```

### 19.1 Mark a batch of publish jobs under review

```powershell
python -m ai_music_system.cli publish-batch-under-review --platform fanqie_music --from-status pending --notes "Submitted in dashboard"
python -m ai_music_system.cli publish-batch-under-review --batch-id batch_20260705_live --from-status ready
```

### 19.2 Mark a batch of publish jobs completed or failed

```powershell
python -m ai_music_system.cli publish-batch-complete --platform douyin --from-status under_review
python -m ai_music_system.cli publish-batch-fail --batch-id batch_20260705_live --from-status ready,under_review --reason "Platform rejected upload"
```

### 20. Run the safer semi-automatic music-platform flow

```powershell
python -m ai_music_system.cli music-upload-run --job-id pub_fanqie_music_song_20260705_001_20260705_095656 --dry-run
python -m ai_music_system.cli music-upload-run --job-id pub_fanqie_music_song_20260705_001_20260705_095656 --manual-login-ms 90000
python -m ai_music_system.cli music-upload-run --job-id pub_fanqie_music_song_20260705_001_20260705_095656 --simulate-session
```

Notes:

- this currently targets `fanqie_music` and `qishui_music`
- the default workflow fills the form and stops before final submit
- operators should review the page and click the final submit button manually
- after the semi-auto run, the job now keeps `automation_summary` and a human-review note
- `--simulate-session` can verify the Fanqie-style operator workflow locally without launching Playwright
- selector templates live under `data/publish/selectors/`
- if the site changes, update the selector JSON instead of rewriting the script
- install Playwright locally with `npm install playwright` before real browser runs
- `--submit` is reserved for tightly controlled testing and is not the recommended default

Recommended queue habit:

- use `publish-summary` first to see backlog and per-platform state
- prefer `publish-summary --pretty` for daily operator checks
- treat unscoped publish queue commands as primary-platform commands by default
- use `publish-target` when you want to confirm which platform is currently primary
- add `--all-platforms` only when you intentionally want a cross-platform view or action
- use `--active-only` when you want to isolate current, primary-platform-aligned, fully traceable jobs
- use `--traceability-state legacy_partial` when you want to audit old carry-over jobs separately
- use batch status commands repeatedly only after checking filters such as `--platform`, `--batch-id`, or `--run-id`
- add `--from-status` when doing batch state changes so queue transitions stay deliberate
- treat music-platform jobs as draft-preparation flows until the human final submit is done

## Safer publishing mode

Recommended operating mode:

- auto prepare publish packages
- auto open the platform backend
- auto fill upload forms
- auto save draft or stop before final submit
- manual final check and submit

Reason:

- this reduces repetitive work
- it lowers the risk of triggering platform anti-automation rules compared with unattended full auto submission

## Verification

To validate the end-to-end packaging flow locally without real provider keys:

```powershell
python .\scripts\verify_local_e2e.py
python .\scripts\verify_local_e2e.py --prepare-publish
python .\scripts\verify_local_e2e.py --include-fanqie
python .\scripts\verify_local_e2e.py --prepare-publish --include-fanqie
python .\scripts\verify_local_e2e.py --include-fanqie --simulate-fanqie-session
python .\scripts\verify_local_e2e.py --prepare-publish --archive-legacy
```

This script starts a local mock provider server, runs a small multi-song batch, approves it, exports it, and can optionally prepare primary-platform publish jobs and archive legacy carry-over jobs.

## Fanqie Music Planning

The dedicated professionalization plan for the Fanqie Music path lives in:

- `FANQIE_MUSIC_STRATEGY.md`

This path is intentionally treated as different from short-video release:

- audio-first package
- music-platform-specific publish copy
- Fanqie package brief for release context
- Fanqie operator checklist for upload-time manual review
- semi-automatic upload with manual final confirmation
- stronger release-readiness checks over time

The same longform creative principle should also apply to `qishui_music`:

- both 汽水音乐 and 番茄音乐 should be treated as complete-song distribution targets
- both should avoid short-video-style duration and intro assumptions
- both should be reviewed for longform listening quality before publish prep

## Historical text repair

If you want to audit or repair old text artifacts that may contain mojibake-like Chinese garbling:

```powershell
python .\scripts\repair_mojibake.py
python .\scripts\repair_mojibake.py --apply
```

Default scan scope:

- `data/songs`
- `data/exports`
- `data/publish/packages`
- `data/publish/jobs`

## Current status

Current version provides:

- project scaffold
- data models
- config loading
- file-based topic loading
- real provider integration for DeepSeek, MiniMax, and Agnes
- distribution-target-aware lyrics prompt selection
- pipeline orchestration and failure logging
- packaging and review file handling
- batch review status listing
- batch approval support
- export manifest generation
- selected-step retry support
- auto topic expansion
- file-based batch scheduling
- simple quality auto-filtering
- one-shot batch automation
- multi-platform publish job generation
- platform-ready MP4 publish asset generation
- dedicated music-platform packaging for 番茄音乐 and 汽水音乐
- operator-friendly publish queue commands for list, summary, detail view, due-run, and batch status updates
- publish status tracking for upload workflows
- music-platform semi-automatic browser form filling with selector templates
- local end-to-end verification support
- lightweight metadata traceability with `run_id`, `prompt_version`, provider provenance, and generated timestamps
- review records now keep `review_source` and `score_evidence` for manual and auto-filter decisions
- publish job records now keep `status_history` for state transitions

Real external runs still require valid provider API keys.

### Local cover generation

For the verified local GPT Image Playground workflow, use the fixed browser
configuration and verification steps in
[`docs/LOCAL_IMAGE_PLAYGROUND_RUNBOOK.md`](docs/LOCAL_IMAGE_PLAYGROUND_RUNBOOK.md).
Cover failures remain non-blocking, and successful cover lineage is recorded in
each song directory's `cover_task.json`.
