# Project Plan

## Goal

Build a traffic-first AI music production system.

Phase 1 goal:

Create a local semi-automatic workflow that can produce real publishable song packages for manual release.

Current strategic goal:

Turn this project into a local AI music release system that is:

- centered on one primary target platform at a time
- able to generate and package songs in batches
- able to keep human review and final publish confirmation in the loop
- able to track generation, review, export, and publish state end to end
- easy to operate daily without opening raw JSON files for every decision

Boundary:

- focus on traffic publishing
- focus on real release capability
- keep the first version simple
- delay full automation until the publishable workflow is stable

## Target Refinement

The next stage of the project should optimize for five things:

1. single-primary-platform execution
2. end-to-end traceability and auditability
3. lightweight, explainable quality scoring
4. operational publish-queue usability
5. explicit scope discipline about what stays deferred

This means:

- one `target_platform` should guide the creative and release strategy at a time
- every song should be traceable from topic to publish outcome
- quality scores should stay simple, rule-based, and reviewable for now
- publish jobs should behave like an operator-friendly queue, not just loose JSON files
- heavy optimization systems should remain deferred until the publishable workflow is stable

## Phase Plan

### Phase 1: Foundation

Objective:

Set up the project so development can move fast without mixing concerns.

Scope:

- project structure
- config files
- data models
- storage layout
- CLI entry
- pipeline skeleton

Done when:

- the project can run from one CLI entry
- folders and files are consistently organized
- provider integrations can be added without changing the whole structure

### Phase 2: Core Production Flow

Objective:

Implement the minimum real generation pipeline.

Scope:

- topic input
- lyrics generation
- lyrics cleaning
- music generation
- cover generation
- cover post-processing
- package assembly

Done when:

- a topic can become a full local song package
- outputs include lyrics, audio, cover, metadata, and caption
- failed steps can be identified clearly

### Phase 3: Publish Loop

Objective:

Make the output usable for real publishing.

Scope:

- manual review files
- approve or reject flow
- export approved songs
- basic run logs
- retry selected steps

Done when:

- approved songs can be exported for manual upload
- review status is recorded
- operators can quickly see what is publishable

### Phase 4: Automation Upgrade

Objective:

Improve operator efficiency after the core workflow is stable.

Scope:

- batch scheduling
- auto topic expansion
- simple quality filtering
- provider switching rules
- optional upload automation

Done when:

- daily operation requires less manual repetition
- the system can process larger batches with low friction

### Phase 5: Multi-Platform Publish Automation

Objective:

Turn approved exports into platform-ready publish tasks.

Scope:

- publish video asset generation
- per-platform caption adaptation
- publish job queue and status tracking
- browser launch hooks for upload execution
- publish result recording
- dedicated music-platform packaging for fanqie_music and qishui_music
- safer semi-automatic submit flow with human final confirmation

Done when:

- approved exports can become platform publish jobs in one command
- operators can track upload progress per platform
- the system reduces repeated packaging work before manual or assisted upload
- short-video and music-distribution workflows stay decoupled
- music-platform uploads default to manual final confirmation rather than unattended submit

### Phase 5.1: Platform Creative Profiles

Objective:

Turn platform differences into explicit generation rules rather than ad hoc operator memory.

Scope:

- define stable creative profiles for short-video and music-platform releases
- map each publish platform to one default creative profile
- document the non-negotiable generation constraints for each profile
- use these rules to prevent regressions such as short songs, long instrumental intros, or wrong package expectations

Done when:

- `fanqie_music` and `qishui_music` are treated as longform music-platform targets by default
- `douyin` and other short-video surfaces remain optimized for hook-first distribution
- operators can see the expected duration and intro behavior for a platform before generation
- future song batches do not depend on remembering previous manual corrections

## Current Focus

Current active phase:

- Phase 5: Multi-Platform Publish Automation

Current priorities:

1. keep the publishable workflow stable and human-confirmed
2. improve metadata traceability for generation, export, and publish steps
3. keep one primary target platform configurable even when packaging for multiple platforms
4. defer heavy trend, experiment, and traffic-optimization systems until the publish loop is stable

## Next Goal Layer

The next meaningful product-level completion target is:

- operators can review songs, export approved work, prepare publish jobs, and manage publish state from CLI views that are readable, traceable, and batch-friendly
- new songs and publish jobs carry enough metadata to explain where they came from and why they were approved or blocked
- the active workflow no longer depends on garbled text assets or ambiguous state labels
- the project remains intentionally narrow and does not expand into recommendation, trend, experiment, or analytics-heavy systems yet

## Remaining Goal Gaps

Before this goal layer can be treated as complete, the project should still tighten these areas:

1. publish queue actions should be idempotent and safe for repeated operator use
2. queue summaries should make daily backlog and per-platform state obvious at a glance
3. active operator docs should reflect the real recommended publish flow, especially for music-platform manual final confirmation
4. release-state transitions should stay clean enough that operators can trust CLI output without opening raw JSON files

Nice to add after that, but not required for this goal:

- optional queue reset or requeue helpers for failed drafts
- stronger precondition filters for batch publish commands
- narrower platform-specific release presets once one primary platform is chosen for a full cycle

## Current Execution Goals

The next execution layer should now finish three concrete operator outcomes together:

1. expand from a single verified publish sample into a stable multi-item primary-platform workflow
2. reduce daily noise from legacy publish carry-over without destructive cleanup
3. run a more realistic small-batch primary-platform rehearsal end to end

Done when:

- active primary-platform views show multiple clean, current, fully traceable jobs
- legacy carry-over jobs can be moved out of the active queue into a reversible archive bucket
- the local verification script can generate, approve, export, and optionally prepare publish jobs for multiple mock songs in one run

## Fanqie Music Upgrade

The next specialized sub-goal under the broader publish system is:

- turn `fanqie_music` from a technically usable music-platform path into a more professional release workflow

This should specifically improve:

- music-platform copywriting
- package semantics
- operator upload guidance
- release-oriented metadata
- validation standards beyond raw file existence

Reference plan:

- `FANQIE_MUSIC_STRATEGY.md`

## Platform Profile Split

The project now needs one explicit creative split above all platform-specific workflow tweaks:

1. short-video profile
2. music-platform profile

This is not optional polish.
It is a core product rule needed to stop creative regressions across batches.

### Short-Video Profile

Primary targets:

- `douyin`
- `kuaishou`
- `xiaohongshu`
- `bilibili` short-form publish packages when used as traffic-first distribution

Creative defaults:

- hook-first writing
- earlier payoff than a full-song release
- shorter total duration is acceptable
- stronger snippet and repost friendliness
- more tolerance for short-video BGM structure

### Music-Platform Profile

Primary targets:

- `fanqie_music`
- `qishui_music`

Creative defaults:

- full-song listening experience
- complete verse / chorus / bridge structure
- short intro but not short-video BGM structure
- clear vocal entry within roughly the first `2-3` seconds
- target duration should usually be at least `2:45`
- preferred duration range should usually be `3:00-4:00`
- stronger tolerance checks against long instrumental intros
- stronger rejection of under-length outputs when the song is meant for formal music release

### Why This Split Must Be Explicit

Recent generation rounds showed the risk of leaving this rule implicit:

- music-platform songs can regress into `1:45-2:10` outputs
- intros can drift longer than intended
- operators may assume a platform is already using the right longform constraints when it is not
- the system can accidentally reuse short-video assumptions for 汽水音乐 or 番茄音乐

This split should therefore be treated as a standing goal, not a temporary reminder.

## Immediate Documentation Goal

The current planning layer should now include one explicit stabilization goal:

- document and preserve the distinction between longform music platforms and short-video traffic platforms so future generation batches inherit the correct duration, intro, and structure expectations by default

## Accepted Direction Updates

Absorb from the external optimization proposal:

- add lightweight `run_id`, `prompt_version`, and provider provenance tracking
- keep a configurable primary `target_platform` for creative alignment
- evolve review and auto-filtering toward clearer quality signals over time
- preserve local evidence files for compliance, debugging, and reuse

Do not absorb yet:

- large asset-library systems
- trend crawling engines
- full experiment layers
- traffic-feedback optimization loops
- big provider abstraction rewrites that do not help the current publishable workflow
- full dashboard products
- model-heavy scoring systems that reduce explainability before the base workflow is trustworthy

## Working Rules

- do not add dashboard work before the core pipeline is stable
- do not optimize analytics before publish export is working
- do not over-design provider stability for the first pass
- do not build heavy optimization subsystems before metadata and publish-state traceability are trustworthy
- prefer simple local solutions that keep iteration speed high

## Change Rule

## Current Product Loop Upgrade

The current implementation priority is:

1. manually record platform performance snapshots before platform traffic is large enough for automated collection
2. require objective hard quality gates before automatic approval
3. represent prompt experiments explicitly with one declared variable and a primary metric
4. cap music-platform regeneration at two retries

Large CLI or storage refactors remain deferred until these product loops produce useful operating evidence.

New features should answer one question first:

Does this help us ship or stabilize the publishable workflow?

If no, it should usually wait.
