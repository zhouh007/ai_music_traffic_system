# AI Music Traffic System Design

## Goal

Build a production-usable AI music publishing workflow for traffic growth first.

The first version should:

- generate publishable songs
- generate cover assets
- package files for manual upload
- keep human approval in the loop
- stay simple and cheap

## Phase 1 scope

The real release loop is:

1. load topics
2. generate lyrics
3. clean lyrics
4. generate music
5. generate cover
6. render final publish cover
7. package assets
8. review manually
9. export approved songs

## Design principles

- simple first
- cheap first
- publishable first
- replaceable providers
- manual approval gate

## Technical shape

- Python local application
- CLI first
- file-based storage first
- modular provider abstraction
- semi-automatic workflow first

## Core folders

```text
config/
data/
src/ai_music_system/
```

## Provider strategy

Phase 1 can use cheap or free providers first.
We do not over-optimize for provider stability yet.
But provider-specific code should stay isolated for future switching.

## Next implementation milestone

Make the CLI workflow runnable end to end with real provider integrations.
