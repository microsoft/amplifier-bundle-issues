# Design Feedback & Discussion

**Date Started:** 2025-10-22
**Status:** In Progress
**Reviewers:** Paul Payne

---

## Feedback Items

### FB-1: Lazy Loading Not Needed

**From:** Paul Payne
**Date:** 2025-10-22
**Section:** 5.1.5 Implementation Notes - In-Memory Index

**Feedback:**
> We probably don't need to do lazy loading... the speed of building an index on the fly from a jsonl file of this size is minimal compared to the wait times on the LLMs.

**Analysis:**
- **Current Design:** Proposed lazy loading with dirty tracking for incremental writes
- **Reality Check:** JSONL parsing is extremely fast (< 10ms for 1000s of tasks)
- **LLM Context:** Every LLM call is 100ms-10s, dwarfing file I/O
- **Complexity Cost:** Lazy loading + dirty tracking adds state management complexity

**Proposed Change:**
- **Simpler approach:** Always load full index on TaskManager init
- **Write strategy:** Write entire JSONL file on any change (still fast)
- **Remove:** Dirty tracking, incremental writes, external modification detection
- **Keep:** In-memory index for fast queries during operation

**Impact:**
- ✅ Dramatically simpler implementation
- ✅ Eliminates entire class of bugs (stale index, sync issues)
- ✅ Still fast enough (file I/O << LLM latency)
- ⚠️ Slightly slower on very large task lists (10k+ tasks)
- ⚠️ Lost: incremental sync optimization

**Decision:** Accept simplification - consistent with ruthless simplicity philosophy

**Code Impact:**
```python
# OLD (Complex)
class TaskManager:
    def __init__(self, data_dir):
        self._index = None  # Lazy loaded
        self._dirty_tasks = set()

    async def _ensure_loaded(self):
        if self._index is None:
            self._index = self._load_index()

    async def update_task(self, task_id, **updates):
        await self._ensure_loaded()
        # ... update ...
        self._dirty_tasks.add(task_id)

    async def _write_dirty(self):
        # Complex incremental write logic
        ...

# NEW (Simple)
class TaskManager:
    def __init__(self, data_dir):
        self._index = self._load_index()  # Always load on init

    async def update_task(self, task_id, **updates):
        # ... update in-memory ...
        self._write_tasks()  # Always write full file

    def _write_tasks(self):
        # Simple: write all tasks to JSONL
        with open(self.tasks_file, 'w') as f:
            for task in self._index.tasks_by_id.values():
                f.write(json.dumps(asdict(task)) + '\n')
```

**Status:** ✅ Agreed - simplify

---

### FB-2: Use Topological Sort for Task Ordering

**From:** Paul Payne
**Date:** 2025-10-22
**Section:** 5.1.5 Implementation Notes - Ready Work Algorithm

**Feedback:**
> I don't see anything in your design about topological sort, since we have a dependency tree we should probably use it along with the priorities to determine next work

**Analysis:**
- **Current Design:** Only checks if task is blocked (binary: ready or not)
- **Missing:** Optimal execution order considering entire dependency graph
- **Better approach:** Topological sort + priority for intelligent ordering

**Why Topological Sort:**
1. **Ensures valid execution order** - Never start a task before its dependencies
2. **Reveals parallelization opportunities** - Tasks at same topo level can run concurrently (future)
3. **Optimizes for completion** - Work on tasks that unblock the most other tasks
4. **Standard graph algorithm** - Well-understood, efficient (O(V+E))

**Proposed Change:**

```python
def get_ready_tasks(self, limit: int | None = None) -> list[Task]:
    """
    Get tasks ready to execute, ordered by:
    1. Topological sort (dependency order)
    2. Priority within same topo level
    3. Creation time as tiebreaker
    """
    # Step 1: Build dependency graph (only 'blocks' edges)
    graph = self._build_dependency_graph()

    # Step 2: Topological sort (using networkx or custom)
    try:
        topo_order = list(nx.topological_sort(graph))
    except nx.NetworkXError:
        # Cycle detected (shouldn't happen due to validation)
        raise ValueError("Dependency cycle detected")

    # Step 3: Filter to open tasks only
    open_tasks = {t.id: t for t in self.tasks_by_status.get('open', [])}
    ready_in_topo_order = [
        tid for tid in topo_order
        if tid in open_tasks
    ]

    # Step 4: Sort by priority within topo order
    # Group by "depth" in topo sort (tasks at same level)
    tasks_with_depth = []
    for tid in ready_in_topo_order:
        task = open_tasks[tid]
        depth = self._compute_topo_depth(tid, graph)
        tasks_with_depth.append((depth, task.priority, task.created_at, task))

    # Sort: depth first (topo order), then priority, then time
    tasks_with_depth.sort(key=lambda x: (x[0], x[1], x[2]))

    ready = [t for _, _, _, t in tasks_with_depth]

    return ready[:limit] if limit else ready

def _compute_topo_depth(self, task_id: str, graph: nx.DiGraph) -> int:
    """
    Compute topological depth (longest path from root).
    Tasks with depth=0 have no dependencies.
    Tasks with depth=N depend on tasks with depth < N.
    """
    if task_id not in graph:
        return 0

    # Longest path from any root to this node
    predecessors = list(graph.predecessors(task_id))
    if not predecessors:
        return 0

    return 1 + max(self._compute_topo_depth(p, graph) for p in predecessors)
```

**Example Scenario:**

```
Dependency graph:
  task-1 (Setup, P=1)
    ├─ task-2 (Schema, P=2)
    │   ├─ task-4 (API, P=2)
    │   └─ task-5 (Tests, P=3)
    └─ task-3 (Docs, P=3)

Topological sort: [task-1, task-2, task-3, task-4, task-5]

Depths:
  task-1: depth=0 (no deps)
  task-2, task-3: depth=1 (depend on task-1)
  task-4, task-5: depth=2 (depend on task-2)

Ready work order:
1. task-1 (depth=0, priority=1) ← Start here
2. After task-1 completes:
   - task-2 (depth=1, priority=2) ← Before task-3
   - task-3 (depth=1, priority=3)
3. After task-2 completes:
   - task-4 (depth=2, priority=2) ← Before task-5
   - task-5 (depth=2, priority=3)
```

**Benefits:**
- ✅ **Optimal ordering** - Work flows naturally through dependency graph
- ✅ **Priority respected** - Within each topo level, higher priority first
- ✅ **Unblocking efficiency** - Complete tasks that unblock most work first
- ✅ **Future parallelization** - Easy to identify tasks at same depth (can run parallel)
- ✅ **Debuggable** - Topo depth is visible/explainable to users

**Implementation Notes:**
- Use `networkx.topological_sort()` - standard, efficient, well-tested
- Cache topo sort until dependency graph changes
- For cycle detection, `add_dependency()` can use `nx.is_directed_acyclic_graph()`

**Impact on Design:**
- Section 5.1.5 "Ready Work Algorithm" needs update
- Add topo sort to dependencies: `networkx` (already planned for cycle detection)
- Update `get_ready_tasks()` implementation
- Add example showing topo ordering in action

**Status:** 🟡 Under discussion

**UPDATED APPROACH** (from Paul):
> Actually, I imagine a better approach would be to get all leaves in all dependency trees and just work on the highest priority one next (not worrying about depth).

**Revised Algorithm (Simpler!):**

```python
def get_ready_tasks(self, limit: int | None = None) -> list[Task]:
    """
    Get leaf tasks (no open dependencies) sorted by priority.

    A task is a "leaf" (ready) if:
    1. Status is 'open'
    2. Has no blocking dependencies on open/in_progress tasks
    """
    # Step 1: Find all blocking dependencies
    blocked_tasks = self._compute_blocked_tasks()

    # Step 2: Get all open tasks that aren't blocked
    ready = [
        task for task in self.tasks_by_status.get('open', [])
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

    for dep in self.dependencies:
        if dep.dep_type == 'blocks':
            blocker = self.tasks_by_id[dep.to_id]
            # If blocker is not done, the dependent task is blocked
            if blocker.status in ('open', 'in_progress', 'blocked'):
                blocked.add(dep.from_id)

    return blocked
```

**Why This is Better:**

1. **Simpler** - No topo sort, no depth calculation
2. **Equally correct** - Leaves are by definition ready to execute
3. **Priority-driven** - Work on highest priority leaves first
4. **Natural flow** - As tasks complete, new leaves become available
5. **Easy to explain** - "Work on highest priority tasks that have nothing blocking them"

**Example (Same Graph):**
```
task-1 (Setup, P=1)
  ├─ task-2 (Schema, P=2)
  │   ├─ task-4 (API, P=2)
  │   └─ task-5 (Tests, P=3)
  └─ task-3 (Docs, P=3)

Initially:
  Leaves: [task-1]  (only task with no deps)
  Next: task-1 (P=1)

After task-1 completes:
  Leaves: [task-2 (P=2), task-3 (P=3)]
  Next: task-2 (P=2) ← Higher priority

After task-2 completes:
  Leaves: [task-3 (P=3), task-4 (P=2), task-5 (P=3)]
  Next: task-4 (P=2) ← Highest priority leaf

After task-4 completes:
  Leaves: [task-3 (P=3), task-5 (P=3)]
  Next: task-3 (P=3) or task-5 (P=3) ← Equal priority, use created_at
```

**Trade-offs:**
- ✅ Much simpler implementation
- ✅ Still optimal (always work on highest priority unblocked task)
- ✅ No need for topo sort at all
- ⚠️ Doesn't explicitly track "depth" (but don't need to!)

**Status:** 🟢 Agreed - use simple leaf + priority approach

---

## Feedback Summary

**Total Items:** 4
**Resolved:** 3 (FB-1, FB-2, FB-3)
**Pending:** 1 (FB-4)
**Blocked:** 0

---

### FB-3: Eliminate Dual-Loop Architecture - Keep Task Management Only

**From:** Paul Payne
**Date:** 2025-10-22
**Section:** Overall Architecture (Sections 4, 5.2, 5.3, 6)

**Feedback:**
> Yeah, I guess there doesn't seem to be a compelling reason to make a separate process, as fun as it may be. Go ahead and summarize all this thinking in another feedback item. Let's ditch the dual-loop, but keep the beads-like stuff.

**Analysis:**

After thorough discussion, we've concluded that the **dual-loop architecture adds complexity without fundamental capability gains**. Every benefit claimed can be achieved with a single assistant and proper task management.

**Original Claims vs. Reality:**

| Claimed Benefit | Reality Check |
|----------------|---------------|
| **Continuous progress without prompts** | Single assistant can loop through tasks with proper instructions |
| **Separate contexts** | Conversation context is minimal and often helpful to execution; separation loses context |
| **Survives interruption** | Both approaches have same problem: close laptop → lose process. Task queue persists in both. |
| **Background processing** | Can leave single assistant terminal open overnight; can open multiple terminals if needed |
| **Non-blocking user input** | Instructions can tell assistant to skip blocked tasks and collect all questions |
| **Observability** | Task queue provides same visibility in both approaches |

**What Dual-Loop Actually Provided:**
- ✅ Architectural clarity (clean separation of concerns)
- ✅ Specialized execution models (different timeouts/configs)
- ❌ **No fundamental capabilities** that single assistant can't achieve

**The Core Insight:**
A single assistant with the right instructions can:
- Loop through tasks autonomously (no prompts needed between tasks)
- Skip blocked tasks and work on others
- Collect all blocking questions and present them together
- Resume from task queue state after interruption

**What We're Keeping:**
1. ✅ **Task Manager Module** - Beads-inspired task queue with dependencies
2. ✅ **Text-based storage** - JSONL for human-readable task state
3. ✅ **Dependency management** - Blocks, parent-child, discovered-from
4. ✅ **Ready work calculation** - Leaf-based scheduling by priority
5. ✅ **User input coordination** - Track blocked questions, collect answers
6. ✅ **Task Tool** - Interface for task operations

**What We're Removing:**
1. ❌ **Actor Loop Orchestrator** module (amplifier-module-loop-actor)
2. ❌ **Conversation Coordinator Hook** module (amplifier-module-hook-conversation-coordinator)
3. ❌ **Dual-process architecture** (no separate actor/chat processes)
4. ❌ **Session forking for tasks** (no child sessions per task)
5. ❌ **Separate terminals/profiles** (one assistant does everything)

**Revised Architecture:**

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

**Workflow Example:**

```
User: "Implement authentication feature"

When creating the next design iteration, incorporate these changes:

1. **TaskManager Simplification (FB-1):**
   - Remove lazy loading
   - Remove dirty tracking
   - Simplify to: load on init, write on every change
   - Update implementation notes to reflect simplicity

2. **Ready Work Algorithm (FB-2):**
   - Use leaf-based scheduling (tasks with no open dependencies)
   - Sort by priority, then created_at
   - Remove topo sort complexity
   - Simple: find blocked tasks, filter them out, sort remainder by priority

3. **Two-Terminal Design Note (FB-3):**
   - Keep two-terminal approach for v1
   - Add note in Section 6.2 about future convenience options
   - Document wrapper script approach
   - Mention potential hook-based auto-spawn for future

4. **Philosophy Alignment:**
   - Call out FB-1 as example of ruthless simplicity
   - Call out FB-2 as example of simple > clever
   - Call out FB-3 as example of explicit > implicit
   - Reference: "Optimize for clarity, not premature performance"

---

## Open Discussion

_Space for ongoing conversation before finalizing feedback..._

---

**Status Key:**
- 🟢 Agreed - will incorporate
- 🟡 Under discussion
- 🔴 Needs decision
- ⚪ Deferred to later

**Next Steps:**
- Continue gathering feedback
- When complete, create DESIGN_v2.md with all changes
