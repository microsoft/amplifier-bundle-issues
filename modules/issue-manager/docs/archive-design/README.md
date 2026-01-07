# Actor Loop Architecture - Design Materials

This directory contains the design documents and supporting materials for the Actor Loop architecture addition to Amplifier.

## Overview

The Actor Loop introduces **autonomous background task execution** to Amplifier, separating user conversation (human-paced) from work execution (continuous).

## Documents

### [DESIGN.md](./DESIGN.md) - **START HERE**
Comprehensive design document covering:
- Architecture overview and system diagrams
- Module specifications (Task Manager, Actor Loop, Conversation Coordinator)
- Integration patterns and coordination mechanisms
- Implementation phases and timeline
- Open questions and design decisions

### [EXPLORATION_SUMMARY.md](./EXPLORATION_SUMMARY.md)
Detailed findings from exploring:
- Beads project patterns (task management, dependencies, ready work)
- Amplifier architecture (sessions, orchestrators, events)
- Integration opportunities and extension points

## Quick Start

If you're implementing this design:

1. **Read** [DESIGN.md](./DESIGN.md) sections 1-4 for overview
2. **Review** Module Specifications (section 5) for contracts
3. **Check** Implementation Phases (section 7) for roadmap
4. **Reference** [EXPLORATION_SUMMARY.md](./EXPLORATION_SUMMARY.md) for implementation details

## Key Components

### 1. Task Manager Module
- **Purpose:** Text-based task queue with dependency management
- **Storage:** JSONL files (human-readable, git-friendly)
- **Key Features:** CRUD operations, dependency graph, ready work calculation, user input coordination

### 2. Actor Loop Orchestrator
- **Purpose:** Background worker that processes tasks autonomously
- **Key Features:** Continuous execution, child session spawning, subtask discovery, blocks on user input

### 3. Conversation Coordinator Hook
- **Purpose:** Bridges conversational and actor loops
- **Key Features:** Surfaces pending questions, formats progress updates, submits user responses

## Architecture at a Glance

```
USER (Conversational Loop)
    ↕ (reads/writes)
TASK QUEUE (JSONL files)
    ↕ (consumes)
ACTOR LOOP (Background Worker)
```

**Key Innovation:** Actor loop runs continuously, only blocking when it needs user input. Questions are queued and surfaced during normal conversation.

## Status

- **Design:** ✅ Complete (v0.1.0)
- **Implementation:** Not started
- **Target:** 4-week implementation (see Phase plan in DESIGN.md)

## Next Steps

1. Review and approve design
2. Create module skeletons
3. Implement Phase 1 (Task Manager)
4. Iterate through phases 2-4

## Questions?

See [DESIGN.md Section 8: Open Questions & Decisions](./DESIGN.md#8-open-questions--decisions)

---

**Last Updated:** 2025-10-22
