# Local Image Playground Runbook

This is the verified cover-generation path for the local GPT Image Playground.

## Fixed Configuration

- URL: `http://127.0.0.1:4173/`
- Provider mode: OpenAI compatible
- API proxy: enabled
- API interface: Images API
- Model: `gpt-image-2`
- Count: `1`
- Size: `1024x1024`
- API key: browser local configuration only; never put it in this repository

The API key is intentionally not documented here. A local browser configuration
is a prerequisite, and a key must never be copied into project files, logs, or
commits.

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

## Standard Prompt Shape

Use a square, platform-ready brief with the song's concrete visual subject,
calm healing mood, and explicit exclusions:

> A square music cover image: [specific natural scene], soft natural light,
> calm healing mood, no people, no text, no logo, no watermark.

For production runs, the project cover prompt at
`src/ai_music_system/prompts/cover_prompt.txt` remains the source of truth.

## Failure Handling

Cover generation is optional for the main song workflow. A failed image request
must leave the song and audio outputs usable, record the error in
`cover_task.json`, and be retried later with:

```powershell
python -m ai_music_system.cli retry-song --song-id <song_id> --step cover
```

If the Playground shows an image while an older task card says `失败`, inspect
the actual image element and save that successful result. The latest visible
image is authoritative for the manual browser flow.
