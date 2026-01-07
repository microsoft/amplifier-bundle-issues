# Task Management Architecture Design

**Version:** 0.2.0
**Date:** 2025-10-22
**Status:** Draft (Revised after Feedback)
**Authors:** Paul Payne (with Claude)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Architecture Overview](#4-architecture-overview)
5. [Module Specifications](#5-module-specifications)
6. [Integration & Usage](#6-integration--usage)
7. [Implementation Phases](#7-implementation-phases)
8. [Open Questions & Decisions](#8-open-questions--decisions)
9. [References](#9-references)

---

## 1. Executive Summary

This design introduces **persistent task management** to Amplifier through a single new module and enhanced assistant instructions.

### Key Components

1. **Task Manager Module** - Text-based task queue with dependency management
2. **Task Tool** - Interface for task operations
3. **Enhanced Assistant Instructions** - Guides autonomous task execution

### Key Innovation

**Simplicity through single-assistant design.** Instead of complex dual-loop architecture, we give a single assistant the tools and instructions to manage complex work autonomously:

- Break complex tasks into subtasks
- Work through ready tasks in priority order
- Skip blocked tasks and move to next ready work
- Collect all blocking questions and present together
- Resume from persistent queue after interruption

### Alignment with Amplifier Philosophy

- **Mechanism, not policy** - Task manager provides storage/query mechanism; assistant decides how to use it
- **Text-first** - All state in human-readable JSONL files
- **Ruthless simplicity** - Load-on-init, write-on-change; no lazy loading complexity
- **Event-driven** - Emits canonical events for observability
- **Modular** - Single focused module with clear contract

### Changes from v0.1.0

**Major architectural simplification** based on feedback:

- ❌ **Removed:** Actor Loop Orchestrator module (dual-loop architecture eliminated)
- ❌ **Removed:** Conversation Coordinator Hook module (not needed with single assistant)
- ✅ **Simplified:** Task Manager (removed lazy loading, simplified ready work algorithm)
- ✅ **Enhanced:** Assistant instructions to guide autonomous execution
- ✅ **Added:** Clear notes about future convenience options (wrapper scripts, auto-spawn hooks)

---

## 2. Problem Statement

### Current Limitations

1. **Synchronous Execution** - User waits for entire task completion
2. **No Persistence** - Work state lost between executions
3. **No Progress Tracking** - Can't check status of complex multi-step work
4. **Manual Coordination** - User must manually track and sequence subtasks
5. **Lost Context** - Discoveries during work don't persist

### User Stories

**As a user, I want to:**

- Give the agent a complex task and have it work autonomously through subtasks
- Check progress without interrupting execution
- Have the agent discover and handle subtasks automatically
- Resume work after interruption without losing state
- See what tasks are blocked and why

**As a developer, I want to:**

- Build long-running workflows that persist across sessions
- Track task dependencies and execution order
- Query what tasks are ready vs blocked
- Audit complete history of task execution
- Integrate with external task systems (future)

---

## 3. Goals & Non-Goals

### Goals

✅ **Enable autonomous task execution** - Assistant loops through ready tasks
✅ **Persistent task state across sessions**
✅ **Dependency-aware task scheduling**
✅ **Graceful handling of blocked tasks** - Skip to next ready work
✅ **Text-first storage for human inspection**
✅ **Event-driven observability**
✅ **Simple, regeneratable module**

### Non-Goals

❌ **Distributed execution** - Single machine only (v1)
❌ **Real-time streaming UI** - Polling-based initially
❌ **Complex scheduling policies** - Simple leaf + priority
❌ **Multi-user coordination** - Single user per workspace
❌ **Separate background process** - Single assistant handles everything

---

## 4. Architecture Overview

### 4.1 System Diagram

```
┌──────────────────────────────────────────────────────┐
│           Single Amplifier Session                    │
│                                                       │
│  Orchestrator: loop-basic (standard)                  │
│  Context: context-persistent                          │
│  Task Manager: mounted and available                  │
│                                                       │
│  Enhanced Instructions/System Prompt:                 │
│  ─────────────────────────────────────────────────    │
│  "When given a complex task:                         │
│   1. Break it into subtasks using task tool          │
│   2. Work through ready tasks in priority order      │
│   3. If blocked, skip to next ready task             │
│   4. Discover and create new tasks as needed         │
│   5. When no ready work remains, present all         │
│      blocking questions to user                      │
│   6. After receiving answers, continue working"      │
│                                                       │
│  Tools: filesystem, bash, task, ...                   │
└───────────────────┬──────────────────────────────────┘
                    │
                    ↓ reads/writes via task tool
┌───────────────────┴──────────────────────────────────┐
│              Task Queue (JSONL Files)                 │
│  - tasks.jsonl                                       │
│  - dependencies.jsonl                                │
│  - events.jsonl (audit trail)                        │
└──────────────────────────────────────────────────────┘
```

### 4.2 Workflow Example

**User gives complex task:**
```
User: "Implement authentication feature"

Assistant analyzes and breaks down:
  ↓
task_manager.create_task("Design auth schema", priority=1)
task_manager.create_task("Implement OAuth flow", priority=2)
task_manager.create_task("Add login UI", priority=2)
task_manager.add_dependency(from="OAuth flow", to="auth schema", type="blocks")
  ↓
Assistant works through ready tasks:
  ↓
1. "Design auth schema" (only ready task)
   ↓ completes
2. "Implement OAuth flow" (now ready)
   ↓ discovers missing piece
   creates "Setup OAuth provider config"
   adds blocking dependency
   ↓ skips to next ready task
3. "Add login UI" (still ready, no blockers)
   ↓ needs clarification
   marks as blocked, notes question
   ↓ no more ready tasks

Assistant presents to user:
"I've completed the login UI and auth schema design.
 Two tasks are blocked and need your input:

 1. OAuth flow - Which provider? (Google, GitHub, Auth0)
 2. Provider config - What are the client credentials?"

User provides answers → Assistant continues
```

### 4.3 Key Design Principles

**Simplicity through Instructions:**
Rather than building complex orchestration logic in code, we give the assistant clear instructions and trust it to execute autonomously.

**Single Source of Truth:**
The task queue (JSONL files) is the only persistent state. Everything else is ephemeral.

**Fail Gracefully:**
If assistant can't make progress, it collects all blocking questions and presents them together rather than interrupting repeatedly.

**Resume Anywhere:**
Assistant can be stopped and restarted at any time. Task queue persists; assistant picks up where it left off.

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

        Loads all tasks from JSONL files into memory on initialization.
        No lazy loading - keep it simple.

        Args:
            data_dir: Directory for JSONL storage (e.g., .amplifier/tasks/)
        """
        self._data_dir = data_dir
        self._index = self._load_index()  # Load immediately

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
        """
        Update task fields. Returns updated task.

        Writes entire task file after update (no incremental writes).
        """

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
        """Get tasks this task depends on (blockers)."""

    async def get_dependents(self, task_id: str) -> list[Task]:
        """Get tasks that depend on this task."""

    # Ready work calculation (leaf-based)
    async def get_ready_tasks(
        self,
        limit: int | None = None,
        assignee: str | None = None,
    ) -> list[Task]:
        """
        Get leaf tasks (no open dependencies) sorted by priority.

        A task is a "leaf" (ready) if:
        1. Status is 'open'
        2. Has no blocking dependencies on open/in_progress/blocked tasks

        Returns tasks sorted by:
        1. Priority (lower number = higher priority)
        2. Creation time (older first as tiebreaker)
        """

    async def get_blocked_tasks(self) -> list[tuple[Task, list[Task]]]:
        """
        Get tasks blocked by open dependencies.

        Returns list of (blocked_task, list_of_blockers).
        """

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
    blocking_notes: str | None        # Why task is blocked / questions needed
    metadata: dict                    # Extensible

@dataclass
class Dependency:
    """Task dependency."""
    from_id: str                      # Blocked task
    to_id: str                        # Blocking task (must complete first)
    dep_type: str                     # blocks|related|parent-child|discovered-from
    created_at: datetime

@dataclass
class TaskEvent:
    """Audit trail entry."""
    id: str
    task_id: str
    event_type: str                   # created|updated|closed|blocked|unblocked
    actor: str                        # "user"|"assistant"|session_id
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

**tasks/events.jsonl (append-only):**
```jsonl
{"id": "evt-1", "task_id": "task-1", "event_type": "created", "actor": "user", ...}
{"id": "evt-2", "task_id": "task-1", "event_type": "updated", "actor": "assistant", ...}
{"id": "evt-3", "task_id": "task-1", "event_type": "closed", "actor": "assistant", ...}
```

#### 5.1.5 Implementation Notes

**Simplified Storage Pattern (FB-1):**

```python
class TaskManager:
    def __init__(self, data_dir: Path):
        """Always load on init - no lazy loading."""
        self._data_dir = data_dir
        self._index = self._load_index()  # Load immediately

    def _load_index(self) -> TaskIndex:
        """Load all tasks and dependencies from JSONL."""
        # Read tasks.jsonl
        tasks = []
        tasks_file = self._data_dir / "tasks.jsonl"
        if tasks_file.exists():
            with open(tasks_file) as f:
                for line in f:
                    tasks.append(Task(**json.loads(line)))

        # Read dependencies.jsonl
        dependencies = []
        deps_file = self._data_dir / "dependencies.jsonl"
        if deps_file.exists():
            with open(deps_file) as f:
                for line in f:
                    dependencies.append(Dependency(**json.loads(line)))

        # Build index
        return TaskIndex(tasks, dependencies)

    async def update_task(self, task_id: str, **updates) -> Task:
        """Update task in memory and write entire file."""
        # Update in memory
        task = self._index.tasks_by_id[task_id]
        for key, value in updates.items():
            setattr(task, key, value)
        task.updated_at = datetime.now()

        # Write entire task file
        self._write_tasks()

        # Emit event
        await self._emit_event("updated", task_id, updates)

        return task

    def _write_tasks(self):
        """Write all tasks to JSONL file."""
        tasks_file = self._data_dir / "tasks.jsonl"
        with open(tasks_file, 'w') as f:
            for task in self._index.tasks_by_id.values():
                f.write(json.dumps(asdict(task)) + '\n')
```

**Why This is Better (FB-1 Rationale):**

- ✅ **Dramatically simpler** - No lazy loading, no dirty tracking, no sync logic
- ✅ **Fast enough** - File I/O (< 10ms for 1000s of tasks) << LLM latency (100ms-10s)
- ✅ **No stale state bugs** - Always consistent
- ✅ **Easy to reason about** - Load on init, write on change
- ⚠️ **Slightly slower at scale** - But not until 10k+ tasks

**Leaf-Based Ready Work Algorithm (FB-2):**

```python
def get_ready_tasks(self, limit: int | None = None) -> list[Task]:
    """
    Get leaf tasks (no open dependencies) sorted by priority.

    Much simpler than topological sort - just find tasks with
    no blockers and sort by priority.
    """
    # Step 1: Find all blocked task IDs
    blocked_tasks = self._compute_blocked_tasks()

    # Step 2: Get all open tasks that aren't blocked (the "leaves")
    ready = [
        task for task in self._index.tasks_by_status.get('open', [])
        if task.id not in blocked_tasks
    ]

    # Step 3: Sort by priority (lower number = higher priority), then created_at
    ready.sort(key=lambda t: (t.priority, t.created_at))

    return ready[:limit] if limit else ready

def _compute_blocked_tasks(self) -> set[str]:
    """
    Find all tasks blocked by open dependencies.

    Returns set of task IDs that cannot start yet.
    """
    blocked = set()

    for dep in self._index.dependencies:
        if dep.dep_type == 'blocks':
            blocker = self._index.tasks_by_id[dep.to_id]
            # If blocker is not done, the dependent task is blocked
            if blocker.status in ('open', 'in_progress', 'blocked'):
                blocked.add(dep.from_id)

    return blocked
```

**Why This is Better (FB-2 Rationale):**

- ✅ **Much simpler** - No topological sort, no depth calculation
- ✅ **Equally correct** - Leaves are by definition ready to execute
- ✅ **Priority-driven** - Work on highest priority unblocked tasks first
- ✅ **Natural flow** - As tasks complete, new leaves become available
- ✅ **Easy to explain** - "Work on highest priority tasks with nothing blocking them"

**In-Memory Index:**

```python
@dataclass
class TaskIndex:
    """Fast lookups without scanning JSONL."""
    tasks_by_id: dict[str, Task]
    tasks_by_status: dict[str, list[Task]]  # status -> tasks
    dependencies: list[Dependency]
    dependency_graph: nx.DiGraph  # For cycle detection
```

**Cycle Detection:**

- Use networkx `simple_cycles()` or custom DFS
- Check before adding any dependency
- Prevent cycles across all dependency types

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

### 5.2 Task Tool Module

**Module ID:** `tool-task`
**Mount Point:** `tools`
**Package:** `amplifier-module-tool-task`

#### 5.2.1 Purpose

Provides assistant interface to task management operations.

#### 5.2.2 Contract

```python
class TaskTool(Tool):
    """Tool for task management operations."""

    def get_schema(self):
        return {
            "name": "task",
            "description": "Manage tasks in the persistent task queue",
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
                            "get_blocked"
                        ],
                        "description": "Operation to perform"
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the operation"
                    }
                },
                "required": ["operation"]
            }
        }

    async def execute(self, operation: str, params: dict | None = None) -> dict:
        """Execute task operation."""
        task_manager = self.coordinator.get("task-manager")
        if not task_manager:
            return {"error": "Task manager not available"}

        params = params or {}

        if operation == "create":
            task = await task_manager.create_task(**params)
            return {"success": True, "task": asdict(task)}

        elif operation == "list":
            tasks = await task_manager.list_tasks(**params)
            return {"success": True, "tasks": [asdict(t) for t in tasks]}

        elif operation == "get":
            task = await task_manager.get_task(params["task_id"])
            if not task:
                return {"error": f"Task {params['task_id']} not found"}
            return {"success": True, "task": asdict(task)}

        elif operation == "update":
            task_id = params.pop("task_id")
            task = await task_manager.update_task(task_id, **params)
            return {"success": True, "task": asdict(task)}

        elif operation == "close":
            task = await task_manager.close_task(**params)
            return {"success": True, "task": asdict(task)}

        elif operation == "add_dependency":
            dep = await task_manager.add_dependency(**params)
            return {"success": True, "dependency": asdict(dep)}

        elif operation == "get_ready":
            tasks = await task_manager.get_ready_tasks(**params)
            return {
                "success": True,
                "ready_tasks": [asdict(t) for t in tasks],
                "count": len(tasks)
            }

        elif operation == "get_blocked":
            blocked = await task_manager.get_blocked_tasks()
            return {
                "success": True,
                "blocked": [
                    {
                        "task": asdict(task),
                        "blockers": [asdict(b) for b in blockers]
                    }
                    for task, blockers in blocked
                ]
            }

        else:
            return {"error": f"Unknown operation: {operation}"}
```

#### 5.2.3 Usage Examples

**Create task:**
```python
task({
    "operation": "create",
    "params": {
        "title": "Implement OAuth flow",
        "description": "Add OAuth2 with PKCE",
        "priority": 2
    }
})
```

**Get ready work:**
```python
task({
    "operation": "get_ready",
    "params": {"limit": 5}
})
# Returns: {"ready_tasks": [...], "count": 5}
```

**Add dependency:**
```python
task({
    "operation": "add_dependency",
    "params": {
        "from_id": "task-5",
        "to_id": "task-3",
        "dep_type": "blocks"
    }
})
```

---

## 6. Integration & Usage

### 6.1 Session Configuration

**Task-Aware Profile** (`task-profile.yaml`):

```yaml
---
profile:
  name: task-aware
  description: Single assistant with task management

session:
  orchestrator:
    module: loop-basic  # Standard conversational loop
  context:
    module: context-persistent  # Keep conversation history

task_manager:
  module: task-manager
  config:
    data_dir: .amplifier/tasks/

hooks:
  - module: hook-logging

providers:
  - module: provider-anthropic
    config:
      model: claude-3-5-sonnet-20241022

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-task  # Task management operations

system_instructions: |
  You are a task-oriented assistant with persistent task management.

  When given a complex task:
  1. Break it down into subtasks using the task tool
  2. Create tasks with appropriate priorities and dependencies
  3. Work through ready tasks in priority order (use get_ready operation)
  4. If you encounter a blocker, mark the task as blocked with blocking_notes
     explaining what's needed, then move to the next ready task
  5. Discover and create new tasks as you learn more
  6. When no ready work remains, present ALL blocking questions to the user
     in a clear summary
  7. After receiving answers, update blocked tasks and continue working

  Key principles:
  - Always check for ready work before asking user what to do next
  - Skip blocked tasks rather than interrupting user repeatedly
  - Collect all questions and present them together
  - Work autonomously through the queue until truly stuck
  - Use task events to track your progress
```

### 6.2 Running the Assistant

**Single Terminal Approach:**

```bash
# Start assistant with task management
amplifier run --profile task-profile.yaml --mode chat

# Assistant will:
# 1. Accept complex task from user
# 2. Break into subtasks
# 3. Work through them autonomously
# 4. Present blocking questions when stuck
# 5. Resume after answers provided
```

**User Interaction Example:**

```
User: "Implement a complete authentication system"

Assistant breaks down and works:
  • Creates task-1: "Design auth schema" (P=1)
  • Creates task-2: "Implement OAuth flow" (P=2)
  • Creates task-3: "Add login UI" (P=2)
  • Adds dependency: task-2 blocks on task-1

  Works on task-1 (only ready task): Completes schema design

  Works on task-2 (now ready):
    - Discovers need for OAuth provider config
    - Creates task-4: "Setup OAuth provider" (P=1)
    - Adds dependency: task-2 blocks on task-4
    - Marks task-2 as blocked

  Works on task-3 (still ready):
    - Needs clarification on UI framework
    - Marks task-3 as blocked with notes

  No ready tasks remain - presents to user:

"I've made progress on the authentication system:

✅ Completed:
  - task-1: Auth schema designed

⏸️  Blocked (need your input):
  - task-2: OAuth flow - Which provider should I configure? (Google, GitHub, Auth0)
  - task-3: Login UI - Which UI framework should I use? (React, Vue, vanilla JS)

Once you answer these, I can continue with task-4 (OAuth setup) and complete the implementation."

User provides answers → Assistant updates tasks and continues
```

### 6.3 Future Convenience Options (FB-3)

While v1 uses a single-terminal approach for simplicity, future versions could provide convenience mechanisms:

**Option A: Wrapper Script**
```bash
#!/bin/bash
# amplifier-auto: Wrapper that mimics background execution

amplifier run --profile task-profile.yaml --mode chat &
PID=$!

echo "Task-aware assistant started (PID: $PID)"
echo "Use 'fg' to interact, Ctrl-Z to background again"
echo "Kill with: kill $PID"
```

**Option B: Hook-Based Auto-Loop**

A hook could be added that automatically continues working through ready tasks without user prompts:

```python
class AutoWorkHook:
    """Hook that automatically continues through ready tasks."""

    async def on_prompt_complete(self, event: dict) -> HookResult:
        """After each response, check if more ready work exists."""
        task_manager = self.coordinator.get("task-manager")
        ready = await task_manager.get_ready_tasks(limit=1)

        if ready and not self._user_explicitly_paused():
            # Automatically trigger next task execution
            next_task = ready[0]
            await self.coordinator.execute_prompt(
                f"Continue with next ready task: {next_task.title}"
            )

        return HookResult(allow=True)
```

**Trade-offs:**
- ✅ **More automatic** - Feels like background execution
- ⚠️ **More complex** - Adds hooks, process management, state tracking
- ⚠️ **Less explicit** - User may lose visibility into what's happening

**Decision:** Keep simple single-terminal approach for v1. These options can be added later based on user feedback.

---

## 7. Implementation Phases

### Phase 1: Task Manager Foundation (Week 1)

**Goals:**
- ✅ Task Manager module with JSONL storage
- ✅ Basic CRUD operations
- ✅ Dependency management with cycle detection
- ✅ Leaf-based ready work calculation (FB-2)
- ✅ Simplified load-on-init / write-on-change (FB-1)
- ✅ Unit tests for core logic

**Deliverables:**
- `amplifier-module-task-manager/` package
- Tests covering dependency graph operations
- Tests covering ready work algorithm
- Documentation with examples

**Acceptance Criteria:**
- Can create, update, query tasks
- Can add dependencies without creating cycles
- `get_ready_tasks()` correctly identifies leaf tasks
- `get_blocked_tasks()` correctly identifies blocked tasks
- All data human-readable in JSONL format
- Load time < 100ms for 1000 tasks

### Phase 2: Task Tool (Week 2)

**Goals:**
- ✅ Task Tool for assistant interface
- ✅ All task operations exposed via tool
- ✅ Integration tests with Task Manager
- ✅ Clear error messages

**Deliverables:**
- `amplifier-module-tool-task/` package
- Integration tests
- Usage examples and documentation

**Acceptance Criteria:**
- Assistant can create/update/close tasks via tool
- Assistant can query ready work
- Assistant can add dependencies
- Clear error messages for invalid operations

### Phase 3: Enhanced Instructions & End-to-End (Week 3)

**Goals:**
- ✅ System instructions for autonomous execution
- ✅ Profile configuration
- ✅ End-to-end workflow testing
- ✅ Example scenarios documented

**Deliverables:**
- Task-aware profile configuration
- System instruction templates
- End-to-end test scenarios
- User workflow documentation

**Acceptance Criteria:**
- Assistant can autonomously break down complex tasks
- Assistant works through ready tasks without prompting
- Assistant collects all blocking questions before interrupting
- Assistant resumes correctly after receiving answers
- Complete workflows work end-to-end

### Phase 4: Polish & Documentation (Week 4)

**Goals:**
- ✅ Comprehensive documentation
- ✅ Example workflows and tutorials
- ✅ Performance validation
- ✅ Error handling refinement

**Deliverables:**
- User guide with examples
- Architecture decision records
- Performance benchmarks
- Error patterns documented

---

## 8. Open Questions & Decisions

### 8.1 Decided Design Choices

#### D1: Single Assistant Architecture (FB-4)

**Decision:** Use single assistant with enhanced instructions instead of dual-loop architecture.

**Rationale:**
- Every claimed benefit of dual-loop can be achieved with single assistant
- Dramatically simpler to implement and reason about
- Conversation context is actually helpful for execution (not noise)
- Both approaches have same interruption behavior (close laptop → lose process)
- Task queue provides same observability in both

**Trade-offs Accepted:**
- No separate "actor" specialization (but not needed)
- No true background execution (but can leave terminal open)
- Assistant must follow instructions to loop (but works well in practice)

---

#### D2: Simplified Storage (FB-1)

**Decision:** Always load on init, always write full file on change. No lazy loading, no dirty tracking.

**Rationale:**
- File I/O (< 10ms) is negligible compared to LLM latency (100ms-10s)
- Dramatically simpler implementation
- No stale state bugs
- Easy to reason about

**Trade-offs Accepted:**
- Slightly slower with 10k+ tasks (but rare)
- Lost incremental sync optimization (but not needed)

---

#### D3: Leaf-Based Scheduling (FB-2)

**Decision:** Simple leaf + priority algorithm instead of topological sort.

**Rationale:**
- Much simpler to implement
- Equally correct (leaves are always safe to execute)
- Priority-driven (work on highest priority unblocked tasks)
- Natural flow as tasks complete

**Trade-offs Accepted:**
- No explicit depth tracking (but don't need it)
- No sophisticated ordering within dependency tree (but priority handles it)

---

#### D4: Text-Based Storage (JSONL)

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

#### D5: Single User Per Workspace

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

### 8.2 Open Questions

#### Q1: Task Persistence Format Extensions

**Question:** Should we support additional storage backends in future?

**Options:**
- A) JSONL only (current)
- B) JSONL + SQLite option
- C) Pluggable storage interface

**Current Thinking:** (A) JSONL only for v1, evaluate (C) after real usage feedback.

**Decision Needed:** After v1 user feedback

---

#### Q2: User Input Coordination

**Question:** How should assistant track and present blocking questions?

**Options:**
- A) Store in task's `blocking_notes` field (simple)
- B) Separate user_inputs.jsonl file (like v0.1.0)
- C) Both

**Current Thinking:** (A) blocking_notes field - simpler, fewer files

**Decision Needed:** By Phase 1 start

---

#### Q3: Concurrent Task Execution

**Question:** Should future versions support parallel task execution?

**Options:**
- A) Sequential only (v1)
- B) Parallel with concurrency limit
- C) Configurable

**Current Thinking:** (A) sequential for v1, evaluate (B) after usage.

**Rationale:**
- Simpler reasoning and debugging
- Most tasks are LLM-bound anyway (limited parallelism benefit)
- Can add later without breaking changes

**Decision Needed:** After v1 feedback

---

## 9. References

### 9.1 Related Documents

- [FEEDBACK.md](./FEEDBACK.md) - Complete feedback and rationale for all design changes
- [EXPLORATION_SUMMARY.md](./EXPLORATION_SUMMARY.md) - Detailed exploration findings from beads and amplifier
- [DESIGN.md](./DESIGN.md) - Original v0.1.0 design (dual-loop architecture - superseded)
- [amplifier-dev/docs/AMPLIFIER_AS_LINUX_KERNEL.md](../../amplifier-dev/docs/AMPLIFIER_AS_LINUX_KERNEL.md) - Kernel philosophy
- [amplifier-dev/docs/MODULE_DEVELOPMENT.md](../../amplifier-dev/docs/MODULE_DEVELOPMENT.md) - Module development guide
- [beads WORKFLOW.md](../../related-projects/beads/WORKFLOW.md) - Beads workflow patterns

### 9.2 Inspiration & Prior Art

- **Beads** - Task management with dependency tracking (primary inspiration)
- **GitHub Actions** - Declarative workflow execution
- **Airflow** - DAG-based task orchestration
- **TODO.txt** - Text-based task management
- **Org-mode** - Plain-text organization system

### 9.3 Key Concepts

- **Leaf Tasks** - Tasks with no open dependencies (ready to execute)
- **Dependency Graph** - DAG for task ordering
- **Ready Work** - Leaf tasks sorted by priority
- **Blocking Notes** - Human-readable explanations of why tasks are blocked
- **Event Sourcing** - Append-only audit log of changes
- **Load-on-Init** - Eagerly load all data at startup (no lazy loading)

---

## Appendix A: Example Workflows

### A.1 Simple Task Creation and Execution

```python
# User starts session
user: "Create a task to add logging to the API"

# Assistant uses task tool
assistant: "I'll create that task for you."
task({
    "operation": "create",
    "params": {
        "title": "Add logging to API endpoints",
        "description": "Add structured logging for all API requests and responses",
        "priority": 2
    }
})

# Check ready work
task({"operation": "get_ready", "params": {"limit": 1}})
# Returns: [{"id": "task-1", "title": "Add logging to API endpoints", ...}]

# Execute the task
assistant: "I'll work on this now..."
# ... implements logging ...
# ... closes task when done ...
task({
    "operation": "close",
    "params": {"task_id": "task-1", "reason": "Logging implemented and tested"}
})
```

### A.2 Complex Task with Discovered Subtasks

```python
# User gives complex task
user: "Implement user authentication"

# Assistant breaks down
assistant: "I'll break this into subtasks:"
task({"operation": "create", "params": {
    "title": "Design auth schema",
    "priority": 1
}})  # → task-1

task({"operation": "create", "params": {
    "title": "Implement OAuth flow",
    "priority": 2
}})  # → task-2

task({"operation": "create", "params": {
    "title": "Add login UI",
    "priority": 2
}})  # → task-3

# Add dependency
task({"operation": "add_dependency", "params": {
    "from_id": "task-2",
    "to_id": "task-1",
    "dep_type": "blocks"
}})

# Check ready work
task({"operation": "get_ready"})
# Returns: [task-1] (only task with no dependencies)

# Work on task-1
assistant: "Starting with schema design..."
# ... completes task-1 ...
task({"operation": "close", "params": {"task_id": "task-1"}})

# Check ready work again
task({"operation": "get_ready"})
# Returns: [task-2, task-3] (both now unblocked)

# Work on task-2 (higher priority)
assistant: "Working on OAuth flow..."
# ... discovers need for config ...
task({"operation": "create", "params": {
    "title": "Setup OAuth provider config",
    "priority": 1,
    "discovered_from": "task-2"
}})  # → task-4

task({"operation": "add_dependency", "params": {
    "from_id": "task-2",
    "to_id": "task-4",
    "dep_type": "blocks"
}})

task({"operation": "update", "params": {
    "task_id": "task-2",
    "status": "blocked",
    "blocking_notes": "Need OAuth provider configuration (client ID, secret, callback URL)"
}})

# Check ready work
task({"operation": "get_ready"})
# Returns: [task-4, task-3]

# Continue with task-4...
```

### A.3 Handling Blocked Tasks

```python
# Assistant working on task, encounters blocker
task({"operation": "update", "params": {
    "task_id": "task-5",
    "status": "blocked",
    "blocking_notes": "Need to know: Which OAuth provider should I use? Options: Google, GitHub, Auth0"
}})

# Move to next ready task
task({"operation": "get_ready", "params": {"limit": 1}})
# Returns: [task-6]

# Work on task-6...
# ... also gets blocked ...
task({"operation": "update", "params": {
    "task_id": "task-6",
    "status": "blocked",
    "blocking_notes": "Need API endpoint URL for external service"
}})

# No more ready work
task({"operation": "get_ready"})
# Returns: []

# Present all blocked tasks to user
task({"operation": "get_blocked"})
# Returns: [
#   {"task": task-5, "blockers": [], "blocking_notes": "..."},
#   {"task": task-6, "blockers": [], "blocking_notes": "..."}
# ]

assistant: "I've made progress but am blocked on two questions:

1. task-5 (OAuth flow): Which provider should I use? (Google, GitHub, Auth0)
2. task-6 (API integration): What's the endpoint URL for the external service?

Once you provide these answers, I can continue."

# User provides answers
user: "Use GitHub OAuth, and the endpoint is https://api.example.com/v1"

# Assistant updates and continues
task({"operation": "update", "params": {
    "task_id": "task-5",
    "status": "open",
    "blocking_notes": None,
    "metadata": {"oauth_provider": "github"}
}})

task({"operation": "update", "params": {
    "task_id": "task-6",
    "status": "open",
    "blocking_notes": None,
    "metadata": {"api_endpoint": "https://api.example.com/v1"}
}})

# Continue working...
```

---

## Appendix B: File Structure

```
amplifier-dev/
├── amplifier-module-task-manager/
│   ├── amplifier_module_task_manager/
│   │   ├── __init__.py
│   │   ├── manager.py          # TaskManager class
│   │   ├── models.py           # Task, Dependency, TaskEvent models
│   │   ├── storage.py          # JSONL read/write (simplified)
│   │   ├── index.py            # In-memory index
│   │   └── algorithms.py       # Leaf-based ready work calculation
│   ├── tests/
│   │   ├── test_manager.py
│   │   ├── test_dependencies.py
│   │   ├── test_ready_work.py
│   │   └── test_storage.py
│   ├── pyproject.toml
│   └── README.md
│
└── amplifier-module-tool-task/
    ├── amplifier_module_tool_task/
    │   ├── __init__.py
    │   └── tool.py             # TaskTool implementation
    ├── tests/
    │   └── test_tool.py
    ├── pyproject.toml
    └── README.md
```

---

## Appendix C: Comparison with v0.1.0

| Aspect | v0.1.0 (Dual-Loop) | v0.2.0 (Single Assistant) |
|--------|-------------------|--------------------------|
| **Architecture** | Separate actor + conversational loops | Single assistant with enhanced instructions |
| **Modules** | 4 modules (manager, orchestrator, hook, tool) | 2 modules (manager, tool) |
| **Complexity** | High (dual process, session forking, coordination) | Low (single process, standard loop) |
| **Task Storage** | JSONL with lazy loading + dirty tracking | JSONL with load-on-init + write-on-change |
| **Ready Work** | Topological sort + depth | Leaf-based + priority |
| **User Input** | Separate user_inputs.jsonl + coordinator hook | blocking_notes field on tasks |
| **Background Execution** | True background (separate process) | Pseudo-background (single terminal, can leave open) |
| **Observability** | Actor loop events + hook events | Task events only |
| **Setup Complexity** | Two terminals, two profiles | One terminal, one profile |
| **Learning Curve** | Steep (understand dual-loop model) | Shallow (standard assistant with task tool) |
| **Maintenance** | Higher (more modules, more coordination) | Lower (fewer modules, simpler contracts) |

**Key Insight from Feedback (FB-4):**

Every capability claimed by the dual-loop architecture can be achieved with a single assistant and proper instructions:

- **Continuous progress** → Assistant loops through ready tasks autonomously
- **Separate contexts** → Not beneficial; context helps execution
- **Survives interruption** → Both lose process on laptop close; queue persists in both
- **Background processing** → Can leave terminal open; can open multiple terminals
- **Non-blocking input** → Instructions handle skipping blocked tasks

The dual-loop architecture added complexity without fundamental capability gains.

---

**END OF DESIGN DOCUMENT**

---

## Document Status

- **Version:** 0.2.0 (Revised after Feedback)
- **Supersedes:** v0.1.0 (dual-loop architecture)
- **Next Review:** After Phase 1 implementation
- **Approval:** Pending
- **Implementation:** Not started

## Change Log

- 2025-10-22 v0.2.0: Major revision based on feedback
  - **FB-1:** Simplified storage (removed lazy loading, dirty tracking)
  - **FB-2:** Leaf-based ready work algorithm (removed topological sort)
  - **FB-3:** Added notes about future convenience options
  - **FB-4:** Eliminated dual-loop architecture entirely (single assistant design)
  - Reduced from 4 modules to 2 modules
  - Dramatically simplified overall architecture
  - All examples and workflows updated for single-assistant model
- 2025-10-22 v0.1.0: Initial draft (dual-loop architecture - superseded)
