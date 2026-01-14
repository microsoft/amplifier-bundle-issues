# Issue Session-End Hook

Hook that automatically marks issues when an Amplifier session ends, enabling session linking and continuity tracking.

## What It Does

When an Amplifier session ends with issues still `in_progress`, this hook:

1. Finds all in-progress issues
2. Checks which issues were touched by the current session
3. Emits `session_ended` events on those issues

This enables users to:
- See which sessions were interrupted
- Resume context later with `amplifier session resume <session_id>`
- Track the full history of sessions that worked on an issue

## Configuration

```yaml
hooks:
  - module: hook-issue-session-end
    source: git+https://github.com/microsoft/amplifier-bundle-issues@main#subdirectory=modules/hook-issue-session-end
    config:
      priority: 90      # Hook priority (default: 90, runs late)
      enabled: true     # Whether hook is active (default: true)
```

## How It Works

The hook registers on the `session:end` event and:

1. Gets the current session ID from event data
2. Finds the issue_manager tool
3. Lists all in-progress issues
4. For each issue, checks if events exist with the current session ID
5. If yes, emits a `session_ended` event

## Session Linking

This hook works together with the session tracking in `IssueManager` to provide full session linking:

- Every issue operation records the session ID in events
- This hook marks when sessions end
- The `get_sessions` operation retrieves all linked sessions

## Example

```
Session abc123 starts
  → Creates issue #1 (event: created, session_id: abc123)
  → Updates issue #1 to in_progress (event: updated, session_id: abc123)
Session abc123 ends
  → session_ended event emitted (event: session_ended, session_id: abc123)

Later, user can run:
  issue_manager(operation='get_sessions', params={'issue_id': '#1'})
  → Returns: {linked_sessions: ['abc123'], ...}
  
  amplifier session resume abc123
  → Revives full context from that session
```

## Dependencies

- `amplifier-core`
- `amplifier-module-issue-manager`
