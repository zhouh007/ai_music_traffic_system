# Project Plan

## Goal

Build a traffic-first AI music production system.

Phase 1 goal:

Create a local semi-automatic workflow that can produce real publishable song packages for manual release.

Boundary:

- focus on traffic publishing
- focus on real release capability
- keep the first version simple
- delay full automation until the publishable workflow is stable

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

## Current Focus

Current active phase:

- Phase 5: Multi-Platform Publish Automation

Current priorities:

1. generate platform-ready publish assets
2. adapt one export into multiple platform jobs
3. record publish execution status clearly
4. keep the final submit step human-confirmed by default

## Working Rules

- do not add dashboard work before the core pipeline is stable
- do not optimize analytics before publish export is working
- do not over-design provider stability for the first pass
- prefer simple local solutions that keep iteration speed high

## Change Rule

New features should answer one question first:

Does this help us ship or stabilize the publishable workflow?

If no, it should usually wait.
