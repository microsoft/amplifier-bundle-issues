# Issues Amplifier Bundle

Persistent issue tracking for Amplifier sessions with dependency management and priority-based scheduling.

## What This Provides

- **issue_manager tool** - Create, list, update, and close issues with dependencies
- **issue-aware bundle** - Pre-configured session with issue management enabled

## Usage

### Quick Start

Run Amplifier with the issues bundle directly:

```bash
amplifier run --bundle git+https://github.com/microsoft/amplifier-bundle-issues@main
```

Or from a local path:

```bash
amplifier run --bundle ./bundle.md
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

## Issue States

- **open** - Created, not yet started
- **in_progress** - Actively being worked on
- **blocked** - Waiting on dependencies
- **closed** - Completed

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
