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

### 5. Run a batch

```powershell
python -m ai_music_system.cli run-batch --topics-file data/topics/topics_master.csv
```

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
```

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

### 16. Create multi-platform publish jobs from an approved export

```powershell
python -m ai_music_system.cli prepare-publish --export-dir data/exports/approved_20260705_075544 --platforms douyin,kuaishou,bilibili,xiaohongshu,fanqie_music,qishui_music
```

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

### 17. List publish jobs

```powershell
python -m ai_music_system.cli publish-list
```

### 18. Validate or launch a publish job

```powershell
python -m ai_music_system.cli publish-run --job-id pub_douyin_song_20260705_001_20260705_120000
python -m ai_music_system.cli publish-run --job-id pub_douyin_song_20260705_001_20260705_120000 --launch-browser
```

### 19. Mark publish result

```powershell
python -m ai_music_system.cli publish-complete --job-id pub_douyin_song_20260705_001_20260705_120000 --external-post-id 123456
python -m ai_music_system.cli publish-fail --job-id pub_douyin_song_20260705_001_20260705_120000 --reason "Upload rejected"
```

### 20. Run the safer semi-automatic music-platform flow

```powershell
python -m ai_music_system.cli music-upload-run --job-id pub_fanqie_music_song_20260705_001_20260705_095656 --dry-run
python -m ai_music_system.cli music-upload-run --job-id pub_fanqie_music_song_20260705_001_20260705_095656 --manual-login-ms 90000
```

Notes:

- this currently targets `fanqie_music` and `qishui_music`
- the default workflow fills the form and stops before final submit
- operators should review the page and click the final submit button manually
- selector templates live under `data/publish/selectors/`
- if the site changes, update the selector JSON instead of rewriting the script
- install Playwright locally with `npm install playwright` before real browser runs
- `--submit` is reserved for tightly controlled testing and is not the recommended default

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
```

This script starts a local mock provider server, runs a batch, and verifies that the expected publishable files are generated.

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
- publish status tracking for upload workflows
- music-platform semi-automatic browser form filling with selector templates
- local end-to-end verification support

Real external runs still require valid provider API keys.
