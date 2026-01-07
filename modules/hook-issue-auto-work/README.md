# Issue Auto-Work Hook

Hook module that automatically keeps the assistant working through the issue queue.

## What It Does

After each turn completes (`prompt:complete` event), this hook:

1. **Checks for ready issues** - Uses the `issue_manager` tool to find issues with no blockers
2. **Injects context** - If ready issues exist, tells the assistant to keep working autonomously
3. **Prevents infinite loops** - Has a configurable max iteration limit (default: 10) before requiring user check-in
4. **Resets on completion** - Resets counter when no ready work remains

## How It Works

```
User: "Implement these 5 features"
Assistant: [Creates 5 issues, starts working on issue 1]
  → prompt:complete event fires
  → Hook checks: 4 ready issues remain
  → Hook injects: "Continue with next ready issue"
  → Assistant autonomously starts issue 2
  → ... continues until all 5 are done
Assistant: "All 5 features complete!"
```

## Configuration

```yaml
hooks:
  - module: hook-issue-auto-work
    source: git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection/modules/hook-issue-auto-work
    config:
      priority: 100              # Run late to see full turn (default: 100)
      max_auto_iterations: 10    # Max iterations before user check-in (default: 10)
      inject_role: system        # Role for injection: system|user (default: system)
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `priority` | int | 100 | Hook priority (lower runs earlier) |
| `max_auto_iterations` | int | 10 | Max autonomous iterations before requiring user input |
| `inject_role` | str | "system" | Role for context injection: "system" or "user" |

## Safety Features

1. **Iteration limit** - Prevents infinite loops by limiting autonomous iterations
2. **Graceful degradation** - If issue_manager tool not available, hook does nothing
3. **Error handling** - Errors don't block execution, just log and continue
4. **Ephemeral injection** - Context injection doesn't pollute conversation history

## Integration with issue-aware Profile

This hook is automatically included in the `issue-aware` profile:

```bash
amplifier run --profile max-payne-collection:issue-aware
```

## Example Flow

```
User: "Build authentication, add caching, write tests"