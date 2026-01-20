# Issues Amplifier Bundle

Persistent issue tracking for Amplifier sessions with dependency management, priority-based scheduling, GitHub sync, and team visibility.

## What This Provides

- **issue_manager tool** - Create, list, update, and close issues with dependencies
- **GitHub sync** - Sync local issues to GitHub for team visibility
- **issue-tracking agent** - Query and analyze team work patterns
- **issue-aware bundle** - Pre-configured session with issue management enabled

## Usage

### Quick Start

Add and activate the issues bundle:

```bash
# Add the bundle to your registry
amplifier bundle add git+https://github.com/microsoft/amplifier-bundle-issues@main

# Set it as active
amplifier bundle use issues

# Start an interactive session
amplifier
```

Then interact with issues:

```
You: "Create an issue to implement user authentication"
Assistant: [Creates issue with the issue_manager tool]

You: "What can I work on?"
Assistant: [Lists ready issues with get_ready operation]

You: "Work on issue <id>"
Assistant: [Updates status to in_progress and begins work]
```

### Include in Another Bundle

Add to your bundle's `includes:` section:

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-issues@main
```

### Manual Configuration

Add the tools to your own bundle:

```yaml
tools:
  - module: tool-issue
    source: git+https://github.com/microsoft/amplifier-bundle-issues@main#subdirectory=modules/tool-issue
    config:
      data_dir: ~/.amplifier/projects/{project}/issues
      auto_create_dir: true
      actor: assistant

hooks:
  - module: hook-issue-auto-work
    source: git+https://github.com/microsoft/amplifier-bundle-issues@main#subdirectory=modules/hook-issue-auto-work
    config:
      priority: 100
      max_auto_iterations: 10
      inject_role: system
```

Then add instructions in your bundle context similar to what is found in the [bundle.md](./bundle.md).

## Data Storage

Issues are stored in your home directory under a project-specific path:

```
~/.amplifier/
└── projects/
    └── {project}/
        └── issues/
            ├── issues.jsonl          # Issue records
            ├── dependencies.jsonl    # Issue relationships
            └── events.jsonl          # Change history
```

The `{project}` placeholder is automatically derived from your working directory.

This can be configured in your bundle (see the Manual Configuration section).

## Issue Operations

The issue_manager tool supports:

- **create** - New issue with priority and type
- **list** - Filter by status, priority, assignee
- **get** - Show issue details
- **update** - Change status, priority, blocking notes
- **close** - Mark complete with reason
- **get_ready** - Find work with no blockers
- **get_blocked** - See blocked issues
- **add_dep** - Link issues with dependencies
- **remove_dep** - Remove dependency links
- **get_sessions** - Get all Amplifier sessions linked to an issue
- **sync_to_github** - Sync local issues to GitHub for team visibility (NEW!)

## Issue States

- **open** - Created, not yet started
- **in_progress** - Actively being worked on
- **blocked** - Waiting on dependencies
- **closed** - Completed

## Session Linking

Issues are automatically linked to Amplifier sessions. Every operation (create, update, close, etc.) records the session ID, enabling you to:

- **Track which sessions worked on an issue** - See the full history of sessions that touched an issue
- **Resume sessions for follow-up questions** - Use `amplifier session resume <session_id>` to revive context
- **Understand issue history** - See what each session did (created, updated, closed, etc.)

Query linked sessions:

```
You: "What sessions have worked on issue X?"
Assistant: [Uses get_sessions operation to show linked sessions]

You: "Resume the session that created this issue"
Assistant: [You can run: amplifier session resume <session_id>]
```

## Team Visibility (NEW!)

### GitHub Sync

Sync your local issues to GitHub for team visibility:

```
You: "Sync my issues to GitHub"
Assistant: [Syncs local issues to microsoft-amplifier/amplifier-shared]
```

Issues are synced with:
- Structured labels (status, area, priority)
- Session links preserved in issue body
- Local JSONL remains source of truth
- GitHub issue number stored in local metadata

**What gets synced:**
- All open and in-progress issues (by default)
- Closed issues only if you specify `include_closed: true`
- Only issues not already synced (idempotent)

**Example sync output:**
```json
{
  "synced": [
    {
      "issue_id": "issue_1737403800_abc123",
      "github_number": 42,
      "github_url": "https://github.com/microsoft-amplifier/amplifier-shared/issues/42"
    }
  ],
  "synced_count": 1,
  "skipped_count": 3,
  "errors": [],
  "error_count": 0
}
```

### Team Queries

Ask questions about team work using the **issue-tracking agent**:

```
You: "What did we accomplish last week?"
You: "Who's working on Core?"
You: "What's blocked?"
You: "Is anyone working on something similar to session optimization?"
```

The agent:
- Queries GitHub issues via `gh` CLI
- Interprets results with LLM
- Returns structured, readable summaries
- Groups by person, area, or priority as appropriate
- Detects duplicate work before you create issues

**Example query response:**

```
# Team Accomplishments (Last Week)

## Summary
The team closed 8 issues, focusing on Core refactoring and Foundation improvements.

## By Person

### @robotdad (4 issues)
- **Core**: Refactored session analyzer (#42) - Reduced memory usage by 60%
- **Core**: Fixed event logging race condition (#38)
- **Foundation**: Updated bundle composition docs (#45)
- **Modules**: Released tool-stats v1.2 (#47)

### @malicata (3 issues)
- **Bundles**: Created design-intelligence bundle (#50)
- **Foundation**: Added recipe validation (#49)
- **Core**: Improved error messages (#44)

## Highlights
- 🎯 High priority: Session analyzer refactoring completed
- 🚀 New capability: design-intelligence bundle shipped
```

### Configuration

**GitHub repo**: Default is `microsoft-amplifier/amplifier-shared`. Override in sync params:

```
You: "Sync issues to GitHub repo my-org/my-work-tracker"
```

**Prerequisites:**
- GitHub CLI installed (`gh --version`)
- Authenticated with GitHub (`gh auth login`)
- Write access to target repository

## Priorities

- **0** - Critical
- **1** - High
- **2** - Normal (default)
- **3** - Low
- **4** - Deferred

## Contributing

> [!NOTE]
> This project is not currently accepting external contributions, but we're actively working toward opening this up. We value community input and look forward to collaborating in the future. For now, feel free to fork and experiment!

Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
