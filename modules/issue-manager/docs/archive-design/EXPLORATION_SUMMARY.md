# Exploration Summary: Actor Loop Architecture

**Date:** 2025-10-22
**Purpose:** Document findings from beads and amplifier-dev exploration to inform actor loop design

---

## 1. Beads Project Key Patterns

### 1.1 Task Data Model

**Core Issue Structure:**
```python
{
    "id": "bd-1",                    # Unique identifier
    "title": str,                     # 500 char max
    "description": str,
    "design": str,                    # Optional design docs
    "acceptance_criteria": str,
    "notes": str,
    "status": "open|in_progress|blocked|closed",
    "priority": int,                  # 0-4 scale
    "issue_type": "bug|feature|task|epic|chore",
    "assignee": str,
    "estimated_minutes": int,
    "created_at": datetime,
    "updated_at": datetime,
    "closed_at": datetime,           # Set only when closed
    "external_ref": str,             # e.g., "gh-9", "jira-ABC"
    "compaction_level": int,         # For memory decay
    "labels": list[str]
}
```

### 1.2 Dependency System (Four Types)

1. **`blocks`** - Hard blocker (B can't start until A finishes)
2. **`related`** - Informational link
3. **`parent-child`** - Epic contains Task (blocking propagates down)
4. **`discovered-from`** - Found during work on another issue

**Key Invariants:**
- No self-dependencies
- No cycles (checked across ALL dependency types)
- Blocking propagates through parent-child hierarchy

### 1.3 Ready Work Detection (Critical Algorithm)

The "ready work" concept uses recursive logic to determine startable tasks:

```sql
WITH RECURSIVE
  -- Step 1: Find directly blocked issues
  blocked_directly AS (
    SELECT issue_id FROM dependencies d
    JOIN issues blocker ON d.depends_on_id = blocker.id
    WHERE d.type = 'blocks'
      AND blocker.status IN ('open', 'in_progress', 'blocked')
  ),

  -- Step 2: Propagate blockage through parent-child
  blocked_transitively AS (
    SELECT issue_id FROM blocked_directly
    UNION ALL
    SELECT d.issue_id
    FROM blocked_transitively bt
    JOIN dependencies d ON d.depends_on_id = bt.issue_id
    WHERE d.type = 'parent-child'
  )

-- Step 3: Select ready issues (open + not blocked)
SELECT * FROM issues
WHERE status = 'open'
  AND NOT EXISTS (SELECT 1 FROM blocked_transitively WHERE issue_id = i.id)
ORDER BY priority ASC, created_at ASC
```

**Adaptation for Text Files:**
- Store dependencies separately (JSONL format)
- Build in-memory graph on load
- Use Python networkx or custom traversal for cycle detection
- Cache "ready work" calculation until task state changes

### 1.4 Storage Pattern (SQLite → Text)

**Current (SQLite):**
- `issues` table
- `dependencies` table
- `labels` table (many-to-many)
- `comments` table
- `events` table (audit trail)
- `dirty_issues` table (incremental sync)

**Proposed (Text Files):**
- `tasks/tasks.jsonl` - One task per line, sorted by ID
- `tasks/dependencies.jsonl` - One dependency per line
- `tasks/events.jsonl` - Append-only audit log
- In-memory index for fast lookups
- Dirty tracking for incremental writes

### 1.5 Workflow Patterns

**Discovery-Driven Creation:**
```bash
# Working on bd-5, discover blocker
create_task("Missing API endpoint", type="task", priority=1)
add_dependency(from_id="bd-5", to_id="bd-6", type="blocks")
# bd-5 automatically marked as "blocked"
```

**Session Pattern:**
```python
1. list(status="in_progress")      # Check abandoned work
2. ready(limit=5)                   # Get unblocked tasks
3. show(task_id)                    # Review top priority
4. update(task_id, status="in_progress")
5. # ... do work ...
6. close(task_id, reason="Completed")
7. ready()                          # Check newly unblocked
```

---

## 2. Amplifier Architecture Patterns

### 2.1 Session & Coordinator

**Session (`AmplifierSession`):**
- Entry point for all Amplifier interactions
- Manages session lifecycle
- Loads and initializes modules
- Provides infrastructure context (session_id, parent_id, config)

**Coordinator (`ModuleCoordinator`):**
- Central hub for module mounting
- Provides infrastructure to modules:
  - `session_id` - for persistence/correlation
  - `parent_id` - for lineage tracking
  - `config` - mount plan access
  - `loader` - dynamic module loading
- Mount points: `orchestrator`, `context`, `providers`, `tools`, `hooks`

### 2.2 Orchestrator Pattern

**Interface:**
```python
class Orchestrator:
    async def execute(
        self,
        prompt: str,
        context: ContextManager,
        providers: dict[str, Provider],
        tools: dict[str, Tool],
        hooks: HookRegistry
    ) -> str:
        """Execute prompt and return final response"""
```

**Current Orchestrators:**
- `loop-basic` - Sequential execution, deterministic
- `loop-events` - Event-driven
- `loop-streaming` - Streaming responses

**Key Insights:**
- Orchestrator controls the entire execution flow
- Single entry point: `execute()`
- Returns final string response
- Emits events throughout execution

### 2.3 Event System

**Canonical Events** ([amplifier-core/amplifier_core/events.py:1](amplifier-core/amplifier_core/events.py#L1)):
```python
# Session lifecycle
SESSION_START = "session:start"
SESSION_END = "session:end"
SESSION_FORK = "session:fork"

# Prompt lifecycle
PROMPT_SUBMIT = "prompt:submit"
PROMPT_COMPLETE = "prompt:complete"

# Provider calls
PROVIDER_REQUEST = "provider:request"
PROVIDER_RESPONSE = "provider:response"
PROVIDER_ERROR = "provider:error"

# Tool invocations
TOOL_PRE = "tool:pre"
TOOL_POST = "tool:post"
TOOL_ERROR = "tool:error"

# Context management
CONTEXT_PRE_COMPACT = "context:pre_compact"
CONTEXT_POST_COMPACT = "context:post_compact"
```

**Hook Registry:**
- Modules register callbacks for events
- Hooks observe but don't block execution
- Default fields auto-injected (session_id, parent_id)

### 2.4 Module Mount Pattern

**Mount Function Signature:**
```python
async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any] | None = None
) -> Callable | None:
    """
    Mount module to coordinator.

    Returns:
        Optional cleanup function
    """
    module = MyModule(config)
    await coordinator.mount("mount_point", module, name="module-name")

    # Return cleanup if needed
    async def cleanup():
        await module.close()
    return cleanup
```

**Mount Points:**
- `orchestrator` - Single instance
- `context` - Single instance
- `providers` - Dict by name
- `tools` - Dict by name
- `hooks` - Registry (special)

---

## 3. Separation Patterns Analysis

### 3.1 Current Amplifier Pattern (Single Loop)

```
User Input
    ↓
AmplifierSession.execute(prompt)
    ↓
Orchestrator.execute()
    ↓
Provider.complete() ←→ Tool.execute()
    ↓
Return final response
```

**Characteristics:**
- Synchronous request-response
- No persistence between executions
- No background processing
- User waits for completion

### 3.2 Proposed Actor Loop Pattern (Dual Loop)

```
┌─────────────────────────────────────────────────────┐
│ CONVERSATIONAL LOOP (User-Facing)                   │
│ - Handles user interaction                          │
│ - Reads task state                                  │
│ - Coordinates user input requests                   │
│ - Returns immediately                               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ↓ (reads tasks, posts user inputs)
┌──────────────────┴──────────────────────────────────┐
│ TASK QUEUE (Text Files)                             │
│ - tasks.jsonl                                       │
│ - dependencies.jsonl                                │
│ - user_inputs.jsonl (pending questions)             │
└──────────────────┬──────────────────────────────────┘
                   │
                   ↓ (consumes tasks, makes progress)
┌──────────────────┴──────────────────────────────────┐
│ ACTOR LOOP (Background Worker)                      │
│ - Runs continuously                                 │
│ - Processes ready work                              │
│ - Executes tasks autonomously                       │
│ - Blocks on user input requests                     │
│ - Resumes when inputs available                     │
└─────────────────────────────────────────────────────┘
```

### 3.3 Key Differences

| Aspect | Current (Single Loop) | Proposed (Dual Loop) |
|--------|----------------------|----------------------|
| **Execution** | Synchronous | Async background |
| **Persistence** | None | Task queue on disk |
| **User Input** | Immediate prompt | Deferred via queue |
| **Progress** | Blocks user | Continuous |
| **State** | Ephemeral | Durable |
| **Resumption** | None | Automatic |

### 3.4 Coordination Mechanism

**Option A: Shared File System**
- Tasks stored in JSONL files
- Actor loop polls for changes
- Conversational loop reads/writes directly
- Simple but requires file locking

**Option B: Event System Extension**
- New events: `TASK_CREATED`, `TASK_UPDATED`, `USER_INPUT_PROVIDED`
- Actor loop subscribes to events
- Conversational loop publishes events
- More complex but better separation

**Recommendation:** Start with Option A (files), migrate to Option B later.

---

## 4. Design Implications

### 4.1 Required Modules

1. **Task Manager Module** (`amplifier-module-task-manager`)
   - Mount point: New type `task-manager`
   - Text-based storage (JSONL)
   - CRUD operations
   - Ready work calculation
   - Dependency management

2. **Actor Orchestrator** (`amplifier-module-loop-actor`)
   - Mount point: `orchestrator`
   - Background execution loop
   - Consumes task queue
   - Blocks on user input requests
   - Emits progress events

3. **Conversational Coordinator Hook** (`amplifier-module-hook-conversation-coordinator`)
   - Mount point: `hooks`
   - Observes task state
   - Surfaces user input requests
   - Formats task updates for user

### 4.2 Integration Points

**Session Forking:**
- Actor loop spawns child sessions for subtasks
- Uses existing `SESSION_FORK` event
- Tracks lineage via `parent_id`

**User Input Coordination:**
- New file: `tasks/user_inputs.jsonl`
- Actor loop creates entries when blocked
- Conversational loop checks for pending inputs
- User provides inputs via conversation
- Actor loop resumes when inputs available

**Event Extensions:**
- `TASK_CREATED` - New task added
- `TASK_UPDATED` - Task state changed
- `TASK_BLOCKED` - Task blocked on input
- `ACTOR_IDLE` - No ready work
- `ACTOR_PROGRESS` - Work completed

### 4.3 Configuration Pattern

```yaml
session:
  orchestrator: loop-actor  # Background worker
  context: context-persistent  # Must persist across runs

task_manager:
  module: task-manager
  config:
    data_dir: .amplifier/tasks/
    auto_create_dir: true

hooks:
  - module: hook-conversation-coordinator
    config:
      check_interval: 1.0  # seconds
```

---

## 5. Open Questions

1. **Actor Loop Lifecycle**
   - Should it run as separate process or async task?
   - How to start/stop gracefully?
   - Restart on crash?

2. **User Input Format**
   - Structured (JSON with schema) or freeform?
   - Context preservation in requests?
   - Multi-turn clarification?

3. **Task Creation Interface**
   - New tool: `create_task()`?
   - Automatic discovery from conversation?
   - Both?

4. **Conflict Resolution**
   - Concurrent task updates from actor + user?
   - File locking strategy?
   - Optimistic concurrency control?

5. **Observability**
   - How to surface actor progress to user?
   - Real-time updates vs polling?
   - Historical task audit trail?

---

## 6. Next Steps

1. ✅ Complete exploration (DONE)
2. → Design task manager module specification
3. → Design actor loop orchestrator specification
4. → Design conversation coordinator hook specification
5. → Create comprehensive design document
6. → Prototype minimal working implementation
