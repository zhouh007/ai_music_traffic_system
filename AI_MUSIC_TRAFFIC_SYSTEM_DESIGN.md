# AI Music Traffic System Design

## Goal

Build a production-usable AI music publishing workflow for traffic growth first.

The first version should:

- generate publishable songs
- generate cover assets
- package files for manual upload
- keep human approval in the loop
- stay simple and cheap

The next design target should be clearer than "more automation":

- pick one primary release platform at a time
- make the workflow explainable and traceable end to end
- make daily operation easy from CLI queue and review views
- improve quality signals without introducing black-box scoring systems
- keep the system intentionally narrow until the publish loop is operationally stable

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
- traceable metadata before heavy optimization

## Roadmap refinement

After reviewing the external optimization proposal, this project should absorb only the parts that directly strengthen the current workflow:

- keep one configurable primary `target_platform` even if we later export to multiple platforms
- add lightweight provenance such as `run_id`, `prompt_version`, provider/model info, and generated timestamps
- improve review and filtering gradually with clearer scoring inputs

The project should also explicitly optimize for:

- reviewable operator views
- stable publish-state transitions
- batch-friendly publish management
- text integrity in prompts, captions, and operator-facing output

This project should explicitly defer:

- trend engines
- experiment layers
- large asset libraries
- traffic-feedback optimization loops

Those are valuable later, but only after the publishable local workflow is stable and easy to audit.

## Current product posture

At this stage, the product is best understood as:

- a local production and release tool
- a human-in-the-loop publish system
- a traceable file-first operating workflow

It is not yet:

- a trend-discovery system
- an experiment platform
- a traffic-optimization engine
- a dashboard-first product

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

## Current completion gaps

For the current strategy, "good enough to move on" should mean:

- batch publish state changes can be repeated safely without polluting history
- operator-facing queue views stay readable enough for daily use
- publish packages, prompts, and captions stay text-clean in the active workflow
- the music-platform path remains semi-automatic with explicit human final submit
- legacy carry-over jobs can be separated from the active queue without deleting evidence
- local rehearsal can cover multiple current songs instead of only one happy-path sample

This stage does not yet require:

- traffic attribution analytics
- dashboard management UI
- trend mining or experiment infrastructure
