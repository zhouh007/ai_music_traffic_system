# Local Image Playground Runbook

This is the verified cover-generation path for the local GPT Image Playground.

## Standard Startup

Start the bundled workbench with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "$HOME/.codex/skills/gpt-image-playground/scripts/start-playground.ps1" -Port 4173
```

The service being reachable at `http://127.0.0.1:4173/` only proves that Vite
is running. The API proxy must also be enabled in the Playground's
`dev-proxy.config.json`:

```json
{
  "enabled": true,
  "prefix": "/api-proxy",
  "target": "https://www.codex2api.com",
  "changeOrigin": true,
  "secure": true
}
```

Restart the workbench after changing this file. A running port with proxy
disabled serves the web page but the project's POST request can return `404`.

For automated runs, set the image provider in `config/providers.local.json` to
use the Playground proxy while the local service is running:

```json
{
  "image_provider": {
    "api_proxy_url": "http://127.0.0.1:4173/api-proxy",
    "use_api_proxy": true
  }
}
```

The project then posts to `/api-proxy/images/generations`; the Playground
rewrites that path to the configured upstream `/v1/images/generations`.
Keep the API key in the environment or existing local secret configuration.
If the Playground is unavailable, cover generation is recorded as `pending`
and the song/audio flow remains usable.

## Verified Lessons

The successful path has four independent prerequisites:

1. The local Playground service must be running on port `4173`.
2. Its API proxy must be enabled and configured for the OpenAI-compatible
   Images API.
3. The Python process must receive the same image-provider key through
   `CODEX2API_API_KEY`; the browser's local-storage key is not shared with it.
4. The project must call the proxy path directly. The correct project URL is
   `http://127.0.0.1:4173/api-proxy/images/generations`, not the public URL and
   not `.../api-proxy/v1/images/generations`.

The browser succeeding while the project returns `502` does not prove that the
prompt is wrong. In this case it indicates that the two requests used
different credentials or different routing. Check the endpoint and credential
source first.

Distinguish the two common local failures:

- `404` from `127.0.0.1:4173`: the workbench is reachable, but its API proxy is
  disabled or the service was not restarted after enabling it.
- `502` from `127.0.0.1:4173`: the request reached the proxy, but the upstream
  gateway rejected or failed the forwarded request; check the project-side
  image Key and upstream model access.

The Playground browser's local-storage key is not visible to the Python
pipeline. For automated generation, provide the same provider key to the
project without committing it, for example in the ignored `.env` file:

```text
CODEX2API_API_KEY=<your image provider key>
```

Without this variable, the project may fall back to the general Codex token;
the upstream image proxy can then return `502` even though the browser UI
still succeeds.

## Fixed Configuration

- URL: `http://127.0.0.1:4173/`
- Provider mode: OpenAI compatible
- API proxy: enabled
- API interface: Images API
- Model: `gpt-image-2`
- Count: `1`
- Size: `1024x1024`
- Output format: `png`
- Quality: `auto`
- Moderation: `auto`
- API key: browser local configuration for manual use, `.env` environment for automated use

The API key is intentionally not documented here. It must never be printed in
logs, committed, or added to tracked configuration. A local ignored secret
source may be used for automated runs.

## Verification Procedure

1. Open the local Playground and confirm the fixed configuration above.
2. Submit one minimal prompt with count `1`.
3. Wait for the result card and inspect the image itself. Do not treat an old
   failed card or a transient status toast as the authoritative result.
4. Save the generated image as `cover_raw.png` in the song directory.
5. Run the existing cover renderer to create `cover_publish.png` and
   `cover_hd.jpg`.
6. Record provider, model, prompt, timestamp, source IDs, and output paths in
   `cover_task.json`.

For a direct project smoke test, use a minimal prompt and inspect only the
boolean result and output size, never the key or full request headers. A
successful run returns one `data` item and writes a non-empty image file.

## Standard Prompt Shape

Use a square, platform-ready brief with the song's concrete visual subject,
calm healing mood, and explicit exclusions:

> A square music cover image: [specific natural scene], soft natural light,
> calm healing mood, no people, no text, no logo, no watermark.

For production runs, the project cover prompt at
`src/ai_music_system/prompts/cover_prompt.txt` remains the source of truth.

## Failure Handling

Cover generation starts independently after the lyrics and title are ready. It
does not wait for audio validation and a failed image request must leave the
song and audio outputs usable. The task state is recorded in `cover_task.json`
as `running`, `ready`, or `pending` with an error message. A failed image request
can be retried later with:

```powershell
python -m ai_music_system.cli retry-song --song-id <song_id> --step cover
```

If the Playground shows an image while an older task card says `失败`, inspect
the actual image element and save that successful result. The latest visible
image is authoritative for the manual browser flow.
