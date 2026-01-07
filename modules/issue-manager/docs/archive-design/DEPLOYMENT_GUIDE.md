# Task Management Architecture - Deployment Guide

**Version:** 0.3.0
**Date:** 2025-10-23
**Status:** Fully Implemented - Ready for User Testing

---

## Overview

This guide explains how to deploy and test the Task Management Architecture implementation for Amplifier.

---

## What Was Implemented

✅ **Task Manager Module** (`amplifier-module-task-manager`)
- JSONL-based persistent task queue
- Dependency management with cycle detection
- Leaf-based scheduling algorithm
- Event emission for observability
- 41/41 tests passing

✅ **Task Tool Module** (`amplifier-module-tool-task`)
- Assistant interface to task operations
- 8 operations (create, list, get, update, close, add_dependency, get_ready, get_blocked)
- 21/21 tests passing

✅ **Task-Aware Profile** (`task-aware`)
- Enhanced system instructions for autonomous execution
- Configuration for task manager and task tool
- Based on `base` profile with filesystem and bash tools

✅ **Documentation Updates**
- Mount Plan Specification updated with `task_manager` section
- AGENTS.md updated with task events taxonomy
- Module README files with usage examples

---

## Installation Steps

### 1. Install All Required Modules in Amplifier's Environment

**Single command to install all modules:**

```bash
uv tool install \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-context-persistent \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-loop-basic \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-task-manager \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-tool-task \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-tool-filesystem \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-tool-bash \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-hooks-logging \
  --with /data/repos/msft/amplifier/amplifier-dev/amplifier-module-provider-anthropic \
  amplifier
```

**What this does:**
- Installs all required modules for the task-aware profile into amplifier's tool environment
- Includes task-manager and tool-task (our new modules)
- Includes all dependencies (context-persistent, loop-basic, filesystem, bash, hooks-logging, provider-anthropic)

### 2. Verify Modules are Installed

```bash
python -c "import amplifier_module_task_manager; import amplifier_module_tool_task; print('✅ Modules installed successfully')"
```

### 3. Run Module Tests (Optional)

Test the modules in their local directories:

```bash
# Test Task Manager
cd /data/repos/msft/amplifier/amplifier-dev/amplifier-module-task-manager
uv run pytest  # Should show 41/41 passing

# Test Task Tool
cd /data/repos/msft/amplifier/amplifier-dev/amplifier-module-tool-task
uv run pytest  # Should show 21/21 passing
```

### 4. Profile Installation

The profile is automatically available once copied to the installed location:

```bash
cp /data/repos/msft/amplifier/amplifier-dev/amplifier-app-cli/amplifier_app_cli/data/profiles/task-aware.md \
   ~/.local/share/uv/tools/amplifier/lib/python3.13/site-packages/amplifier_app_cli/data/profiles/task-aware.md
```

**Note**: The single `uv tool install` command in step 1 installs both the profile and all modules. No separate profile copy needed.

### 5. Core Updates (Completed)

The following core changes have been made to support task management:

**amplifier-core/amplifier_core/coordinator.py**:
- Added `"task-manager"` to mount_points dictionary (line 53)
- Updated mount() to recognize task-manager as single-module mount point (line 107)
- Updated unmount() to handle task-manager (line 140)
- Updated get() to retrieve task-manager (line 165)
- Note: Uses hyphenated name "task-manager" to match module's mount call

**amplifier-core/amplifier_core/session.py** (lines 143-165):
- Added task_manager loading logic between context and providers
- Handles both dict and string format for task_manager config
- Logs loading process and handles failures gracefully

**amplifier-app-cli/pyproject.toml**:
- Updated amplifier-core source to use local path dependency
- Changed from git URL to `{ path = "../amplifier-core", editable = true }`

---

## Testing the Implementation

### Test 1: Profile Loads Successfully

```bash
cd ~/amplifier  # or any working directory
amplifier run --profile task-aware --mode chat
```

**Expected**: Session starts successfully with task tools available

**If profile not found**: The profile uses `file://` sources pointing to `/data/repos/msft/amplifier/amplifier-dev/`. Ensure:
- The amplifier-dev directory exists at that path
- All required modules exist (loop-basic, context-persistent, task-manager, tool-task, filesystem, bash, hooks-logging)

### Test 2: Task Tool Available

Once in session:
```
/tools
```

**Expected**: Should list `task` tool among available tools

### Test 3: Create a Task

```python
# In amplifier session
task({"operation": "create", "params": {"title": "Test task", "description": "Testing task management", "priority": 2}})
```

**Expected**: Returns success with task object containing `task-1` or similar ID

### Test 4: Get Ready Tasks

```python
task({"operation": "get_ready", "params": {"limit": 10}})
```

**Expected**: Returns the task created in Test 3

### Test 5: Complex Workflow

Give the assistant a complex task:
```
"Implement a simple authentication system with the following components:
1. User database schema
2. Login endpoint
3. Token generation
Please break this down and work through it autonomously."
```

**Expected**:
- Assistant creates subtasks with priorities and dependencies
- Works through ready tasks
- Marks tasks as blocked if needed
- Presents blocking questions together
- Closes tasks as completed

### Test 6: Persistence

```bash
# Exit the amplifier session (Ctrl-D or exit)

# Check that task data was persisted
ls -la .amplifier/tasks/
cat .amplifier/tasks/tasks.jsonl
cat .amplifier/tasks/dependencies.jsonl
cat .amplifier/tasks/events.jsonl
```

**Expected**:
- Files exist and contain JSONL data
- tasks.jsonl contains your created tasks
- events.jsonl contains audit trail

```bash
# Restart session
amplifier run --profile task-aware --mode chat

# List tasks
task({"operation": "list"})
```

**Expected**: Previously created tasks are still present

---

## Verification Checklist

- [ ] Both modules install without errors
- [ ] All tests pass (62/62 total)
- [ ] Profile loads successfully
- [ ] Task tool is available in session
- [ ] Can create tasks
- [ ] Can query ready tasks
- [ ] Task data persists to `.amplifier/tasks/`
- [ ] Tasks survive session restart
- [ ] Events are emitted to `.amplifier/tasks/events.jsonl`
- [ ] Assistant follows autonomous execution instructions

---

## Troubleshooting

### Profile Not Found

**Error**: `Warning: Could not load profile 'task-aware': Profile 'task-aware' not found in search paths`

**Fix**: Copy the profile to the installed location:
```bash
cp /data/repos/msft/amplifier/amplifier-dev/amplifier-app-cli/amplifier_app_cli/data/profiles/task-aware.md \
   /home/payne/.local/share/uv/tools/amplifier/lib/python3.13/site-packages/amplifier_app_cli/data/profiles/task-aware.md
```

### Module Not Found

**Error**: `Failed to load module 'task-manager': Module 'task-manager' not found`

**Cause**: The profile uses `file://` sources that point to specific paths

**Fix Options**:
1. Ensure `/data/repos/msft/amplifier/amplifier-dev/` exists with all modules
2. Or update the profile to use different sources (git URLs or installed packages)
3. Or install the modules as packages:
   ```bash
   cd /data/repos/msft/amplifier/amplifier-dev/amplifier-module-task-manager
   uv pip install -e .

   cd /data/repos/msft/amplifier/amplifier-dev/amplifier-module-tool-task
   uv pip install -e .
   ```

### Task Manager Not Available

**Symptom**: Task tool returns `{"error": "Task manager not available"}`

**Cause**: task_manager didn't mount successfully

**Debug**:
1. Check amplifier logs: `amplifier logs`
2. Look for `task_manager:*` or mount errors
3. Verify task-manager module installed: `ls /data/repos/msft/amplifier/amplifier-dev/amplifier-module-task-manager/`

### Cloud Sync I/O Errors

**Symptom**: Intermittent file write errors

**Cause**: Task data in cloud-synced folder (OneDrive, Dropbox, etc.)

**Fix**:
1. Set "Always keep on this device" for `.amplifier/tasks/` folder
2. Or move task data to local directory:
   ```yaml
   task_manager:
     config:
       data_dir: /tmp/amplifier/tasks/
   ```

---

## Known Issues

### Pre-Existing Type Errors

The `make check` hook reports type errors in unrelated code:
- `related-projects/beads/` (12 errors)
- `scenarios/python-sandbox/` (1 warning)

**These are pre-existing issues** not related to the task management implementation. The task management modules themselves have clean types and passing tests.

---

## File Locations

**Modules**:
- `/data/repos/msft/amplifier/amplifier-dev/amplifier-module-task-manager/`
- `/data/repos/msft/amplifier/amplifier-dev/amplifier-module-tool-task/`

**Profile**:
- Source: `/data/repos/msft/amplifier/amplifier-dev/amplifier-app-cli/amplifier_app_cli/data/profiles/task-aware.md`
- Installed: `~/.local/share/uv/tools/amplifier/lib/python3.13/site-packages/amplifier_app_cli/data/profiles/task-aware.md`

**Documentation**:
- Design: `/data/repos/msft/amplifier/ai_working/actor/DESIGN_v2.md`
- This guide: `/data/repos/msft/amplifier/ai_working/actor/DEPLOYMENT_GUIDE.md`

**Data** (created at runtime):
- `.amplifier/tasks/tasks.jsonl`
- `.amplifier/tasks/dependencies.jsonl`
- `.amplifier/tasks/events.jsonl`

---

## Next Steps

1. **Test the implementation** using the tests above
2. **Report any issues** discovered during testing
3. **Iterate on profile** if needed (adjust system instructions, add more tools, etc.)
4. **Consider enhancements**:
   - Wrapper script for pseudo-background execution
   - Auto-work hook for continuous execution
   - SQLite storage for larger task counts
   - Multi-user support

---

## Success Criteria

Implementation is successful if:
✅ All 62 tests pass
✅ Profile loads and session starts
✅ Tasks can be created, updated, and closed
✅ Dependencies can be added without cycles
✅ Ready work calculation returns correct tasks
✅ Task data persists across sessions
✅ Events are emitted and logged
✅ Assistant follows autonomous execution workflow

---

## Support

For issues or questions:
- Review the design document: `ai_working/actor/DESIGN_v2.md`
- Check module READMEs for API details
- Review AGENTS.md for event taxonomy
- Check amplifier logs: `amplifier logs`
