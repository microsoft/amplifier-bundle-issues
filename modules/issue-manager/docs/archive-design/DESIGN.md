# Actor Loop Architecture Design

**Version:** 0.1.0
**Date:** 2025-10-22
**Status:** Draft
**Authors:** Brian Krabach (with Claude)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Architecture Overview](#4-architecture-overview)
5. [Module Specifications](#5-module-specifications)
6. [Integration & Coordination](#6-integration--coordination)
7. [Implementation Phases](#7-implementation-phases)
8. [Open Questions & Decisions](#8-open-questions--decisions)
9. [References](#9-references)

---

## 1. Executive Summary

This design introduces **autonomous background task execution** to Amplifier through three new modules:

1. **Task Manager** - Text-based task queue with dependency management
2. **Actor Loop Orchestrator** - Background worker that makes continuous progress
3. **Conversation Coordinator Hook** - Bridges actor loop and user conversation

### Key Innovation

Separates **conversational interaction** (human-paced) from **work execution** (continuous). The actor loop runs autonomously in the background, only blocking when it needs human input. When blocked, it surfaces questions to the conversational loop, which coordinates getting answers from the user.

### Alignment with Amplifier Philosophy

- **Mechanism, not policy** - Provides task execution mechanism; orchestration policies remain at edges
- **Text-first** - All state in human-readable JSONL files
- **Event-driven** - Emits canonical events for observability
- **Modular** - Three independent, swappable modules
- **Studs & sockets** - Stable contracts enable independent regeneration

---

## 2. Problem Statement

### Current Limitations

1. **Synchronous Execution** - User waits for entire task completion
2. **No Persistence** - Work state lost between executions
3. **No Background Progress** - Agent can't work autonomously
4. **Manual Coordination** - User must manually track and sequence subtasks
5. **Lost Context** - Discoveries during work don't inform future work

### User Stories

**As a user, I want to:**

- Give the agent a complex task and have it work autonomously
- Check progress without blocking execution
- Provide input when needed without losing progress
- Have the agent discover and handle subtasks automatically
- Resume work after interruption without losing state

**As a developer, I want to:**

- Build long-running workflows that survive interruption
- Track task dependencies and execution order
- Query what tasks are ready vs blocked
- Audit complete history of task execution
- Integrate with external task systems

---

## 3. Goals & Non-Goals

### Goals

✅ **Enable autonomous background execution**
✅ **Persistent task state across sessions**
✅ **Dependency-aware task scheduling**
✅ **Graceful blocking on user input**
✅ **Text-first storage for human inspection**
✅ **Event-driven observability**
✅ **Modular, swappable components**

### Non-Goals

❌ **Distributed execution** - Single machine only (v1)
❌ **Real-time streaming UI** - Polling-based initially
❌ **Complex scheduling policies** - Simple FIFO + priority
❌ **Multi-user coordination** - Single user per workspace
❌ **Persistent LLM context** - Actor loop uses ephemeral sessions

---

## 4. Architecture Overview

### 4.1 System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    USER INTERACTION                           │
│              (Conversational Loop / Shell)                    │
└────────────┬─────────────────────────────────────────────────┘
             │
             │ 1. User submits prompt
             │ 2. Check for blocked tasks needing input
             │ 3. Show progress updates
             │
             ↓
┌────────────┴─────────────────────────────────────────────────┐
│        Conversation Coordinator Hook (Observer)               │
│  - Monitors task queue for user input requests               │
│  - Formats task updates for user                             │
│  - Submits user inputs back to queue                         │
└────────────┬─────────────────────────────────────────────────┘
             │
             │ reads/writes via Task Manager API
             │
             ↓
┌────────────┴─────────────────────────────────────────────────┐
│              Task Manager Module (Storage Layer)              │
│  - CRUD operations on tasks                                  │
│  - Dependency graph management                               │
│  - Ready work calculation                                    │
│  - User input queue management                               │
│                                                               │
│  Storage: JSONL files (human-readable, git-friendly)        │
│    - tasks/tasks.jsonl                                       │
│    - tasks/dependencies.jsonl                                │
│    - tasks/user_inputs.jsonl                                 │
│    - tasks/events.jsonl (audit trail)                        │
└────────────┬─────────────────────────────────────────────────┘
             │
             │ consumed by Actor Loop
             │
             ↓
┌────────────┴─────────────────────────────────────────────────┐
│         Actor Loop Orchestrator (Background Worker)           │
│  - Continuously processes ready tasks                        │
│  - Spawns child sessions for task execution                  │
│  - Creates user input requests when blocked                  │
│  - Discovers and creates subtasks                            │
│  - Emits progress events                                     │
│                                                               │
│  Loop Logic:                                                 │
│    while True:                                               │
│      ready_tasks = task_manager.get_ready()                  │
│      if not ready_tasks:                                     │
│        wait_for_changes()                                    │
│      else:                                                   │
│        task = ready_tasks[0]  # Highest priority            │
│        execute_task(task)                                    │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Component Interaction Flow

**Task Creation Flow:**
```
User: "Implement feature X"
  ↓
Conversational Loop
  ↓
task_manager.create_task(
  title="Implement feature X",
  description="...",
  status="open"
)
  ↓
Actor Loop detects new task
  ↓
Actor Loop begins execution
```

**User Input Request Flow:**
```
Actor Loop executing task
  ↓
Needs clarification (e.g., "Which API to use?")
  ↓
task_manager.create_user_input_request(
  task_id="task-5",
  question="Which API should I use for authentication?",
  context={...}
)
  ↓
task_manager.update_task("task-5", status="blocked")
  ↓
Actor Loop moves to next ready task
  ↓
Conversational Loop detects pending input
  ↓
User: "Use OAuth2 with PKCE"
  ↓
task_manager.provide_user_input(
  request_id="input-1",
  response="Use OAuth2 with PKCE"
)
  ↓
task_manager.update_task("task-5", status="open")
  ↓
Actor Loop resumes task-5
```

**Dependency Discovery Flow:**
```
Actor Loop executing task-10
  ↓
Discovers missing prerequisite
  ↓
task_manager.create_task(
  title="Missing prerequisite",
  discovered_from="task-10"
)
  ↓
task_manager.add_dependency(
  from_id="task-10",
  to_id="task-11",
  type="blocks"
)
  ↓
task_manager.update_task("task-10", status="blocked")
  ↓
Actor Loop switches to task-11
```

### 4.3 Data Flow

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       │
       ↓
┌──────┴──────────────────────────────────────────┐
│  Conversational Session                         │
│  (Ephemeral - no persistent context)            │
└──────┬──────────────────────────────────────────┘
       │
       ↓ writes tasks
┌──────┴──────────────────────────────────────────┐
│  Task Queue (JSONL Files)                       │
│  - Persistent                                   │
│  - Human-readable                               │
│  - Version controllable                         │
└──────┬──────────────────────────────────────────┘
       │
       ↓ consumes tasks
┌──────┴──────────────────────────────────────────┐
│  Actor Session (per task)                       │
│  (Ephemeral - fresh context per task)           │
│                                                  │
│  Spawns child sessions for subtasks             │
└──────┬──────────────────────────────────────────┘
       │
       ↓ produces results
┌──────┴──────────────────────────────────────────┐
│  Task Updates (written back to queue)           │
└─────────────────────────────────────────────────┘
```

**Key Insight:** Only the task queue is persistent. Sessions are ephemeral and disposable.

---

## 5. Module Specifications

### 5.1 Task Manager Module

**Module ID:** `task-manager`
**Mount Point:** NEW - `task-manager` (single instance)
**Package:** `amplifier-module-task-manager`

#### 5.1.1 Purpose

Provides persistent, text-based task queue with dependency management and ready work calculation.

#### 5.1.2 Contract (Public API)

```python
class TaskManager:
    """Task queue manager with dependency-aware scheduling."""

    def __init__(self, data_dir: Path):
        """
        Initialize task manager.

        Args:
            data_dir: Directory for JSONL storage (e.g., .amplifier/tasks/)
        """

    # Task CRUD
    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: int = 2,
        task_type: str = "task",
        assignee: str | None = None,
        parent_id: str | None = None,
    ) -> Task:
        """Create a new task. Returns Task with generated ID."""

    async def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""

    async def update_task(
        self,
        task_id: str,
        **updates
    ) -> Task:
        """Update task fields. Returns updated task."""

    async def close_task(
        self,
        task_id: str,
        reason: str = "Completed"
    ) -> Task:
        """Mark task as closed."""

    async def list_tasks(
        self,
        status: str | None = None,
        assignee: str | None = None,
        task_type: str | None = None,
        limit: int | None = None,
    ) -> list[Task]:
        """List tasks with optional filters."""

    # Dependency management
    async def add_dependency(
        self,
        from_id: str,
        to_id: str,
        dep_type: str = "blocks",
    ) -> Dependency:
        """
        Add dependency between tasks.

        Args:
            from_id: Task that is blocked
            to_id: Task that blocks (must complete first)
            dep_type: blocks|related|parent-child|discovered-from

        Raises:
            ValueError: If would create cycle
        """

    async def remove_dependency(
        self,
        from_id: str,
        to_id: str,
    ) -> None:
        """Remove dependency."""

    async def get_dependencies(self, task_id: str) -> list[Task]:
        """Get tasks this task depends on."""

    async def get_dependents(self, task_id: str) -> list[Task]:
        """Get tasks that depend on this task."""

    # Ready work calculation
    async def get_ready_tasks(
        self,
        limit: int | None = None,
        assignee: str | None = None,
    ) -> list[Task]:
        """
        Get tasks that can be started now (no open blockers).

        Returns tasks sorted by:
        1. Recent (< 48hrs) by priority
        2. Older by creation time
        """

    async def get_blocked_tasks(self) -> list[tuple[Task, list[Task]]]:
        """Get tasks blocked by open dependencies."""

    # User input coordination
    async def create_user_input_request(
        self,
        task_id: str,
        question: str,
        context: dict | None = None,
    ) -> UserInputRequest:
        """Create user input request and mark task as blocked."""

    async def provide_user_input(
        self,
        request_id: str,
        response: str,
    ) -> None:
        """Provide response to user input request and unblock task."""

    async def get_pending_user_inputs(self) -> list[UserInputRequest]:
        """Get all pending user input requests."""

    # Events
    async def get_task_events(
        self,
        task_id: str,
        limit: int | None = None,
    ) -> list[TaskEvent]:
        """Get audit trail for task."""
```

#### 5.1.3 Data Models

```python
@dataclass
class Task:
    """Task representation."""
    id: str                           # e.g., "task-1"
    title: str                        # Max 500 chars
    description: str
    status: str                       # open|in_progress|blocked|closed
    priority: int                     # 0-4 (0=highest)
    task_type: str                    # bug|feature|task|epic|chore
    assignee: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    parent_id: str | None             # For task hierarchies
    discovered_from: str | None       # Task ID that created this
    metadata: dict                    # Extensible

@dataclass
class Dependency:
    """Task dependency."""
    from_id: str                      # Blocked task
    to_id: str                        # Blocking task
    dep_type: str                     # blocks|related|parent-child|discovered-from
    created_at: datetime

@dataclass
class UserInputRequest:
    """Request for user input."""
    id: str                           # e.g., "input-1"
    task_id: str                      # Associated task
    question: str                     # What to ask user
    context: dict                     # Relevant context
    response: str | None              # User's answer
    status: str                       # pending|answered
    created_at: datetime
    answered_at: datetime | None

@dataclass
class TaskEvent:
    """Audit trail entry."""
    id: str
    task_id: str
    event_type: str                   # created|updated|closed|blocked|unblocked
    actor: str                        # "user"|"actor-loop"|session_id
    changes: dict                     # What changed
    timestamp: datetime
```

#### 5.1.4 Storage Format

**tasks/tasks.jsonl:**
```jsonl
{"id": "task-1", "title": "Setup project", "status": "closed", "priority": 1, ...}
{"id": "task-2", "title": "Implement auth", "status": "in_progress", "priority": 2, ...}
{"id": "task-3", "title": "Write tests", "status": "open", "priority": 2, ...}
```

**tasks/dependencies.jsonl:**
```jsonl
{"from_id": "task-3", "to_id": "task-2", "dep_type": "blocks", "created_at": "..."}
{"from_id": "task-4", "to_id": "task-2", "dep_type": "blocks", "created_at": "..."}
```

**tasks/user_inputs.jsonl:**
```jsonl
{"id": "input-1", "task_id": "task-2", "question": "Which OAuth provider?", "status": "pending", ...}
{"id": "input-2", "task_id": "task-5", "question": "API endpoint?", "status": "answered", "response": "...", ...}
```

**tasks/events.jsonl (append-only):**
```jsonl
{"id": "evt-1", "task_id": "task-1", "event_type": "created", "actor": "user", ...}
{"id": "evt-2", "task_id": "task-1", "event_type": "updated", "actor": "actor-loop", ...}
{"id": "evt-3", "task_id": "task-1", "event_type": "closed", "actor": "actor-loop", ...}
```

#### 5.1.5 Implementation Notes

**In-Memory Index:**
```python
class TaskIndex:
    """Fast lookups without scanning JSONL."""
    tasks_by_id: dict[str, Task]
    tasks_by_status: dict[str, list[str]]  # status -> task_ids
    dependencies_graph: nx.DiGraph
    dirty_tasks: set[str]  # Need to be written
```

**Lazy Loading:**
- Load index on first access
- Rebuild index if JSONL files modified externally
- Write only dirty tasks (incremental)

**Cycle Detection:**
- Use networkx `simple_cycles()` or custom DFS
- Check before adding any dependency
- Prevent across all dependency types

**Ready Work Algorithm:**
```python
def get_ready_tasks(self) -> list[Task]:
    """
    Tasks are ready if:
    1. status == 'open'
    2. No blocking dependencies with status in ('open', 'in_progress', 'blocked')
    3. Parent (if exists) is not blocked
    """
    blocked = self._compute_blocked_tasks()
    ready = [
        t for t in self.tasks_by_status.get('open', [])
        if t.id not in blocked
    ]
    return sorted(ready, key=self._priority_sort_key)

def _compute_blocked_tasks(self) -> set[str]:
    """Compute all transitively blocked task IDs."""
    blocked = set()

    # Direct blocks
    for dep in self.dependencies:
        if dep.dep_type == 'blocks':
            blocker = self.tasks_by_id[dep.to_id]
            if blocker.status in ('open', 'in_progress', 'blocked'):
                blocked.add(dep.from_id)

    # Propagate through parent-child
    changed = True
    while changed:
        changed = False
        for dep in self.dependencies:
            if dep.dep_type == 'parent-child':
                if dep.to_id in blocked and dep.from_id not in blocked:
                    blocked.add(dep.from_id)
                    changed = True

    return blocked
```

#### 5.1.6 Mount Function

```python
async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any] | None = None
) -> Callable | None:
    """
    Mount task manager.

    Config:
        data_dir: str - Directory for JSONL files (default: .amplifier/tasks/)
        auto_create_dir: bool - Create dir if missing (default: True)
    """
    config = config or {}
    data_dir = Path(config.get("data_dir", ".amplifier/tasks"))

    if config.get("auto_create_dir", True):
        data_dir.mkdir(parents=True, exist_ok=True)

    task_manager = TaskManager(data_dir)
    await coordinator.mount("task-manager", task_manager)

    return None  # No cleanup needed
```

---

### 5.2 Actor Loop Orchestrator

**Module ID:** `loop-actor`
**Mount Point:** `orchestrator`
**Package:** `amplifier-module-loop-actor`

#### 5.2.1 Purpose

Background execution loop that autonomously processes tasks from the queue.

#### 5.2.2 Contract

```python
class ActorLoopOrchestrator:
    """
    Background task executor that runs continuously.

    Implements the standard Orchestrator interface but with
    different semantics - execute() starts background loop
    rather than processing a single prompt.
    """

    async def execute(
        self,
        prompt: str,
        context: ContextManager,
        providers: dict[str, Provider],
        tools: dict[str, Tool],
        hooks: HookRegistry,
    ) -> str:
        """
        Start/resume actor loop.

        The prompt parameter is used as the initial goal/directive
        for the actor loop if starting fresh. If resuming, the
        prompt is ignored (tasks from queue are used).

        This method runs continuously until:
        - No more ready tasks AND no pending user inputs
        - Explicit stop signal
        - Max runtime exceeded

        Returns:
            Status summary string
        """
```

#### 5.2.3 Loop Logic

```python
async def execute(self, prompt, context, providers, tools, hooks):
    # Get task manager from coordinator
    task_manager = self.coordinator.get("task-manager")
    if not task_manager:
        raise RuntimeError("Actor loop requires task-manager module")

    # Initialize: create initial task from prompt if needed
    if await self._is_first_run():
        await task_manager.create_task(
            title=self._extract_title(prompt),
            description=prompt,
            priority=1,
        )

    # Main loop
    iteration = 0
    while iteration < self.max_iterations:
        await hooks.emit("actor:iteration_start", {
            "data": {"iteration": iteration}
        })

        # Check for ready work
        ready_tasks = await task_manager.get_ready_tasks(limit=1)

        if not ready_tasks:
            # No ready work - check if we're completely idle
            pending_inputs = await task_manager.get_pending_user_inputs()
            if not pending_inputs:
                # Nothing to do and nothing blocking - we're done
                await hooks.emit("actor:idle", {
                    "data": {"reason": "no_work"}
                })
                break
            else:
                # Blocked on user input - wait and poll
                await hooks.emit("actor:waiting_for_input", {
                    "data": {
                        "pending_count": len(pending_inputs),
                        "requests": [r.question for r in pending_inputs[:3]]
                    }
                })
                await asyncio.sleep(self.poll_interval)
                continue

        # Execute highest priority ready task
        task = ready_tasks[0]
        await self._execute_task(
            task, context, providers, tools, hooks, task_manager
        )

        iteration += 1

    return self._format_final_status(task_manager)

async def _execute_task(self, task, context, providers, tools, hooks, task_manager):
    """Execute a single task."""

    await hooks.emit("actor:task_start", {
        "data": {"task_id": task.id, "title": task.title}
    })

    # Update task status
    await task_manager.update_task(task.id, status="in_progress")

    # Create child session for task execution
    child_session = await self._spawn_child_session(
        parent=self.coordinator.session,
        task=task,
    )

    try:
        # Execute task in child session
        result = await child_session.execute(
            self._format_task_prompt(task)
        )

        # Process result
        if self._needs_user_input(result):
            # Task blocked on user input
            question = self._extract_question(result)
            await task_manager.create_user_input_request(
                task_id=task.id,
                question=question,
                context={"result": result},
            )
            # Task automatically marked as blocked by create_user_input_request
        else:
            # Task completed
            await task_manager.close_task(
                task.id,
                reason="Completed by actor loop"
            )

            # Check for discovered subtasks in result
            subtasks = self._extract_discovered_tasks(result)
            for subtask in subtasks:
                new_task = await task_manager.create_task(
                    title=subtask["title"],
                    description=subtask["description"],
                    discovered_from=task.id,
                )
                # Add blocking dependency
                await task_manager.add_dependency(
                    from_id=task.id,
                    to_id=new_task.id,
                    dep_type="discovered-from",
                )

        await hooks.emit("actor:task_complete", {
            "data": {
                "task_id": task.id,
                "status": task.status,
                "result_preview": result[:200],
            }
        })

    except Exception as e:
        await hooks.emit("actor:task_error", {
            "data": {
                "task_id": task.id,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
        })
        # Update task with error info
        await task_manager.update_task(
            task.id,
            status="blocked",
            metadata={"error": str(e)}
        )

    finally:
        await child_session.cleanup()
```

#### 5.2.4 Configuration

```python
{
    "max_iterations": 100,           # Max tasks to process per run
    "poll_interval": 2.0,            # Seconds between checks when idle
    "child_session_config": {        # Config for child sessions
        "orchestrator": "loop-basic",
        "context": "context-simple", # Ephemeral context per task
        "max_turns": 20,
    },
    "auto_discover_tasks": true,     # Extract subtasks from results
}
```

#### 5.2.5 Events Emitted

```python
ACTOR_ITERATION_START = "actor:iteration_start"
ACTOR_IDLE = "actor:idle"
ACTOR_WAITING_FOR_INPUT = "actor:waiting_for_input"
ACTOR_TASK_START = "actor:task_start"
ACTOR_TASK_COMPLETE = "actor:task_complete"
ACTOR_TASK_ERROR = "actor:task_error"
```

#### 5.2.6 Child Session Spawning

```python
async def _spawn_child_session(self, parent, task):
    """Create child session for task execution."""

    # Merge parent config with child overrides
    child_config = self._merge_configs(
        parent.config,
        self.config.get("child_session_config", {})
    )

    # Create child session with lineage
    child_session = AmplifierSession(
        config=child_config,
        parent_id=parent.session_id,  # Lineage tracking
    )

    await child_session.initialize()
    return child_session
```

---

### 5.3 Conversation Coordinator Hook

**Module ID:** `hook-conversation-coordinator`
**Mount Point:** `hooks`
**Package:** `amplifier-module-hook-conversation-coordinator`

#### 5.3.1 Purpose

Bridges conversational loop and actor loop by:
1. Surfacing pending user input requests
2. Formatting task progress for user
3. Submitting user responses back to queue

#### 5.3.2 Contract

```python
class ConversationCoordinatorHook:
    """
    Hook that coordinates between conversational and actor loops.

    Observes task queue state and surfaces relevant information
    to the conversational loop.
    """

    async def on_prompt_submit(self, event: dict) -> HookResult:
        """
        Called when user submits prompt.

        Checks for:
        - Pending user input requests (highest priority)
        - Recent task completions
        - Current task progress
        """

    async def on_prompt_complete(self, event: dict) -> HookResult:
        """
        Called after conversational loop responds.

        Extracts any user input responses and submits to queue.
        """
```

#### 5.3.3 Hook Logic

```python
async def on_prompt_submit(self, event: dict) -> HookResult:
    """Check for pending inputs before processing prompt."""

    task_manager = self.coordinator.get("task-manager")
    if not task_manager:
        return HookResult(allow=True)

    # Check for pending user inputs
    pending_inputs = await task_manager.get_pending_user_inputs()

    if pending_inputs:
        # Surface pending questions to context
        context = self.coordinator.get("context")
        if context and hasattr(context, "add_system_message"):
            message = self._format_pending_inputs_message(pending_inputs)
            await context.add_system_message(message)

    # Add task progress summary to context
    if hasattr(context, "add_system_message"):
        progress = await self._get_progress_summary(task_manager)
        await context.add_system_message(progress)

    return HookResult(allow=True)

async def on_prompt_complete(self, event: dict) -> HookResult:
    """Extract user inputs from response."""

    task_manager = self.coordinator.get("task-manager")
    if not task_manager:
        return HookResult(allow=True)

    # Parse response for user input answers
    response = event.get("data", {}).get("response", "")
    inputs = self._extract_user_inputs(response)

    for input_data in inputs:
        await task_manager.provide_user_input(
            request_id=input_data["request_id"],
            response=input_data["response"],
        )

    return HookResult(allow=True)

def _format_pending_inputs_message(self, pending_inputs):
    """Format pending user inputs for display."""
    lines = ["=== Pending Questions from Actor Loop ===\n"]
    for inp in pending_inputs[:5]:  # Show top 5
        lines.append(f"[{inp.id}] Task: {inp.task_id}")
        lines.append(f"Question: {inp.question}\n")

    lines.append("\nTo answer, include in your response:")
    lines.append("[input-1] Your answer here")
    return "\n".join(lines)
```

#### 5.3.4 Configuration

```python
{
    "check_on_prompt": true,         # Check for inputs on every prompt
    "show_progress": true,           # Include progress summary
    "max_pending_shown": 5,          # Max pending inputs to show
    "auto_parse_responses": true,    # Auto-extract user input answers
}
```

---

## 6. Integration & Coordination

### 6.1 Session Configuration

**Actor Loop Profile** (`actor-profile.yaml`):
```yaml
---
profile:
  name: actor
  description: Background task execution profile

session:
  orchestrator:
    module: loop-actor
    config:
      max_iterations: 100
      poll_interval: 2.0
  context:
    module: context-simple  # Ephemeral for actor loop

task_manager:
  module: task-manager
  config:
    data_dir: .amplifier/tasks/

hooks:
  - module: hook-conversation-coordinator
    config:
      check_on_prompt: true

providers:
  - module: provider-anthropic
    config:
      model: claude-3-5-sonnet-20241022

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-task  # New tool for task operations
```

**Conversational Profile** (`chat-profile.yaml`):
```yaml
---
profile:
  name: chat
  description: Standard conversational profile with task awareness

session:
  orchestrator:
    module: loop-basic  # Standard conversational loop
  context:
    module: context-persistent  # Preserve conversation history

task_manager:
  module: task-manager  # Same queue as actor loop
  config:
    data_dir: .amplifier/tasks/

hooks:
  - module: hook-conversation-coordinator
    config:
      check_on_prompt: true
  - module: hook-logging

providers:
  - module: provider-anthropic

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-task  # Can create/query tasks
```

### 6.2 Running Both Loops

**Terminal 1 (Actor Loop - Background):**
```bash
# Start actor loop in background
amplifier run --profile actor-profile.yaml --mode background

# Or in foreground for debugging
amplifier run --profile actor-profile.yaml
```

**Terminal 2 (Conversational - Interactive):**
```bash
# Normal interactive chat with task awareness
amplifier run --profile chat-profile.yaml --mode chat
```

**Shared State:**
- Both sessions share `.amplifier/tasks/` directory
- Conversational loop can create/query tasks
- Actor loop processes tasks autonomously
- User input requests bridge the two

### 6.3 Task Tool Module

New tool to expose task operations:

```python
class TaskTool(Tool):
    """Tool for task management operations."""

    def get_schema(self):
        return {
            "name": "task",
            "description": "Manage tasks in the task queue",
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "create",
                            "list",
                            "get",
                            "update",
                            "close",
                            "add_dependency",
                            "get_ready",
                            "provide_input"
                        ]
                    },
                    "params": {"type": "object"}
                },
                "required": ["operation"]
            }
        }

    async def execute(self, operation: str, params: dict) -> dict:
        task_manager = self.coordinator.get("task-manager")
        if not task_manager:
            return {"error": "Task manager not available"}

        if operation == "create":
            task = await task_manager.create_task(**params)
            return {"task": asdict(task)}

        elif operation == "list":
            tasks = await task_manager.list_tasks(**params)
            return {"tasks": [asdict(t) for t in tasks]}

        # ... other operations ...
```

### 6.4 Event Flow

**Task Creation:**
```
User (chat): "Create task: Implement feature X"
  ↓
Conversational Loop calls task tool
  ↓
Task Manager emits TASK_CREATED event
  ↓
Actor Loop detects event (or polls queue)
  ↓
Actor Loop begins execution
```

**User Input Request:**
```
Actor Loop creates user input request
  ↓
Task Manager emits TASK_BLOCKED event
  ↓
Conversation Coordinator Hook observes
  ↓
On next user prompt, surfaces pending question
  ↓
User provides answer
  ↓
Hook extracts answer, calls provide_user_input()
  ↓
Task Manager emits TASK_UNBLOCKED event
  ↓
Actor Loop resumes task
```

---

## 7. Implementation Phases

### Phase 1: Task Manager Foundation (Week 1)

**Goals:**
- ✅ Task Manager module with JSONL storage
- ✅ Basic CRUD operations
- ✅ Dependency management with cycle detection
- ✅ Ready work calculation
- ✅ Unit tests for core logic

**Deliverables:**
- `amplifier-module-task-manager/` package
- Tests covering dependency graph operations
- Documentation with examples

**Acceptance Criteria:**
- Can create, update, query tasks
- Can add dependencies without creating cycles
- `get_ready_tasks()` correctly identifies unblocked work
- All data human-readable in JSONL format

### Phase 2: Actor Loop Orchestrator (Week 2)

**Goals:**
- ✅ Actor Loop orchestrator module
- ✅ Background execution loop
- ✅ Child session spawning
- ✅ Basic error handling

**Deliverables:**
- `amplifier-module-loop-actor/` package
- Integration tests with task manager
- Event emission for observability

**Acceptance Criteria:**
- Can process tasks from queue autonomously
- Spawns child sessions correctly
- Handles task completion and errors
- Emits all specified events

### Phase 3: User Input Coordination (Week 3)

**Goals:**
- ✅ User input request/response system
- ✅ Conversation Coordinator Hook
- ✅ Task Tool for conversational access
- ✅ End-to-end workflow

**Deliverables:**
- User input support in Task Manager
- `amplifier-module-hook-conversation-coordinator/` package
- `amplifier-module-tool-task/` package
- Integration tests for full workflow

**Acceptance Criteria:**
- Actor loop can request user input
- Conversational loop surfaces requests
- User can provide input via natural conversation
- Actor loop resumes correctly after input

### Phase 4: Polish & Documentation (Week 4)

**Goals:**
- ✅ Comprehensive documentation
- ✅ Example workflows and tutorials
- ✅ Performance optimization
- ✅ Error handling refinement

**Deliverables:**
- User guide with examples
- Architecture decision records
- Performance benchmarks
- Error recovery patterns

---

## 8. Open Questions & Decisions

### 8.1 Open Questions

#### Q1: Actor Loop Process Model

**Question:** Should actor loop run as:
- A) Separate OS process
- B) Async task in same process
- C) Optional either way

**Current Thinking:** Start with (B) async task for simplicity, add (A) later if needed.

**Trade-offs:**
- Separate process: Better isolation, survives crashes, harder coordination
- Async task: Simpler, shared memory, single point of failure

**Decision Needed:** By Phase 2 start

---

#### Q2: User Input Matching

**Question:** How to match user responses to pending input requests?

**Options:**
- A) Explicit reference: `[input-1] Answer here`
- B) Semantic matching: Parse natural language
- C) Interactive selection: CLI prompts user to choose

**Current Thinking:** Start with (A) explicit reference, add (B) later.

**Decision Needed:** By Phase 3 start

---

#### Q3: Task Persistence Format

**Question:** Should we support multiple storage backends?

**Options:**
- A) JSONL only (v1)
- B) JSONL + SQLite option
- C) Pluggable storage interface

**Current Thinking:** (A) JSONL only for v1, evaluate (C) after real usage.

**Rationale:**
- JSONL is human-readable, git-friendly, simple
- SQLite adds complexity without clear benefit initially
- If performance becomes issue, can add later

**Decision Needed:** Before Phase 1 start (DECIDED: JSONL only)

---

#### Q4: Concurrent Task Execution

**Question:** Should actor loop support parallel task execution?

**Options:**
- A) Sequential only (v1)
- B) Parallel with concurrency limit
- C) Configurable

**Current Thinking:** (A) sequential for v1, add (B) in v2 if needed.

**Rationale:**
- Simpler reasoning and debugging
- Most tasks are LLM-bound anyway (limited parallelism benefit)
- Can add later without breaking changes

**Decision Needed:** By Phase 2 start (DECIDED: Sequential only v1)

---

#### Q5: Task Discovery Strategy

**Question:** How should actor loop discover subtasks?

**Options:**
- A) Parse structured output from LLM
- B) Tool call (`create_task()`) during execution
- C) Both

**Current Thinking:** (C) Both - allow flexible discovery.

**Example A (Structured Output):**
```json
{
  "status": "blocked",
  "reason": "Missing prerequisite",
  "discovered_tasks": [
    {"title": "Create API endpoint", "priority": 1}
  ]
}
```

**Example B (Tool Call):**
```python
# During task execution
await create_task(
  title="Create API endpoint",
  description="Need /auth endpoint before continuing",
  priority=1
)
```

**Decision Needed:** By Phase 2 start

---

### 8.2 Decided Design Choices

#### D1: Text-Based Storage (JSONL)

**Decision:** Use JSONL for all task storage.

**Rationale:**
- Human-readable for debugging
- Git-friendly for version control
- Simple to implement
- No external dependencies
- Easy to export/import

**Trade-offs Accepted:**
- Slower than database for large task counts (> 1000s)
- No built-in indexing (we build in-memory)
- Concurrent access requires locking

---

#### D2: Ephemeral Actor Sessions

**Decision:** Each task execution gets a fresh session with no persistent context.

**Rationale:**
- Simpler reasoning (no context accumulation)
- Tasks are independent by default
- Prevents context contamination
- Allows parallel execution in future

**Trade-offs Accepted:**
- No learning across tasks
- Can't reference previous task results directly
- Must explicitly pass context via task description

---

#### D3: Dependency-Based Scheduling Only

**Decision:** Use dependency graph + priority for scheduling, no ML/heuristics in v1.

**Rationale:**
- Simple and predictable
- Human-understandable
- Easy to debug
- Sufficient for most workflows

**Trade-offs Accepted:**
- No learning of task duration
- No optimization for resource usage
- No adaptive scheduling

---

#### D4: Single Assignee Per Workspace

**Decision:** No multi-user coordination in v1.

**Rationale:**
- Dramatically simpler
- Most use cases are single developer
- File-based locking is simple for single user
- Can add multi-user later if needed

**Trade-offs Accepted:**
- Can't distribute work across team
- No ownership/permission model
- File conflicts if multiple users access

---

## 9. References

### 9.1 Related Documents

- [EXPLORATION_SUMMARY.md](./EXPLORATION_SUMMARY.md) - Detailed exploration findings
- [amplifier-dev/docs/AMPLIFIER_AS_LINUX_KERNEL.md](../../amplifier-dev/docs/AMPLIFIER_AS_LINUX_KERNEL.md) - Kernel philosophy
- [amplifier-dev/docs/MODULE_DEVELOPMENT.md](../../amplifier-dev/docs/MODULE_DEVELOPMENT.md) - Module development guide
- [beads WORKFLOW.md](../../related-projects/beads/WORKFLOW.md) - Beads workflow patterns

### 9.2 Inspiration & Prior Art

- **Beads** - Task management with dependency tracking
- **Temporal** - Durable execution workflows
- **Celery** - Background task queue
- **GitHub Actions** - Declarative workflow execution
- **Airflow** - DAG-based task orchestration

### 9.3 Key Concepts

- **Actor Model** - Independent agents communicating via messages
- **Event Sourcing** - Append-only audit log of changes
- **Dependency Graph** - DAG for task ordering
- **Ready Work** - Tasks with no open blockers
- **Blocking Propagation** - Parent blocks children

---

## Appendix A: Example Workflows

### A.1 Simple Task Creation

```python
# In conversational loop
user: "Create a task to implement user authentication"

# Behind the scenes
task = await task_manager.create_task(
    title="Implement user authentication",
    description="Add OAuth2 login with PKCE flow",
    priority=2,
)

# Actor loop picks it up
actor: Processes task...
```

### A.2 Discovered Subtasks

```python
# Actor loop executing "Implement authentication"
# Discovers missing pieces

await task_manager.create_task(
    title="Create user database schema",
    priority=1,
    discovered_from="task-5"
)
await task_manager.add_dependency(
    from_id="task-5",  # Auth task
    to_id="task-6",     # Schema task
    dep_type="blocks"
)

# task-5 now blocked, actor loop switches to task-6
```

### A.3 User Input Request

```python
# Actor loop needs clarification
await task_manager.create_user_input_request(
    task_id="task-5",
    question="Which OAuth provider should I use? (Google, GitHub, Auth0)",
    context={"options": ["google", "github", "auth0"]}
)

# User sees in next conversation
system: "Pending question from task-5: Which OAuth provider? ..."
user: "[input-1] Use GitHub OAuth"

# Hook extracts and submits
await task_manager.provide_user_input("input-1", "Use GitHub OAuth")

# Actor loop resumes task-5 with answer
```

---

## Appendix B: File Structure

```
amplifier-dev/
├── amplifier-module-task-manager/
│   ├── amplifier_module_task_manager/
│   │   ├── __init__.py
│   │   ├── manager.py          # TaskManager class
│   │   ├── models.py           # Task, Dependency models
│   │   ├── storage.py          # JSONL read/write
│   │   ├── index.py            # In-memory index
│   │   └── algorithms.py       # Ready work calculation
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
├── amplifier-module-loop-actor/
│   ├── amplifier_module_loop_actor/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # ActorLoopOrchestrator
│   │   ├── executor.py         # Task execution logic
│   │   └── discovery.py        # Subtask discovery
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
├── amplifier-module-hook-conversation-coordinator/
│   ├── amplifier_module_hook_conversation_coordinator/
│   │   ├── __init__.py
│   │   ├── hook.py             # ConversationCoordinatorHook
│   │   └── formatters.py       # Message formatting
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
└── amplifier-module-tool-task/
    ├── amplifier_module_tool_task/
    │   ├── __init__.py
    │   └── tool.py             # TaskTool
    ├── tests/
    ├── pyproject.toml
    └── README.md
```

---

**END OF DESIGN DOCUMENT**

---

## Document Status

- **Version:** 0.1.0 (Initial Draft)
- **Next Review:** After Phase 1 completion
- **Approval:** Pending
- **Implementation:** Not started

## Change Log

- 2025-10-22: Initial draft (Claude + Brian)
