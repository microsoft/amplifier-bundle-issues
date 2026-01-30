---
description: Clear all issues from the current project (requires confirmation)
allowed-tools: [issue_manager, Bash]
---

The user wants to clear all issues from the current project. This is a destructive operation.

First, list all current issues so the user can see what will be deleted:
`issue_manager(operation='list')`

Then ask for confirmation before proceeding. If confirmed, close each issue one by one using:
`issue_manager(operation='close', params={'issue_id': '<id>', 'resolution': 'Cleared by user request'})`

Do NOT proceed without explicit user confirmation.
