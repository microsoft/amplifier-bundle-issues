# amplifier-module-tool-issue

Issue management tool module for Amplifier.

## Overview

Provides a thin wrapper over IssueManager operations, exposing issue queue management capabilities to the assistant via the tool interface.

## Installation

```bash
amplifier collection add git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection
```

## Configuration

Add to your profile:

```yaml
tools:
  - module: tool-issue
    source: git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection/modules/tool-issue
    config:
      data_dir: .amplifier/issues
      auto_create_dir: true
      actor: assistant
```

## Operations

- `create`: Create a new issue
- `list`: List issues with optional filters
- `get`: Get a specific issue by ID
- `update`: Update an issue
- `close`: Close an issue
- `add_dependency`: Add a dependency between issues
- `get_ready`: Get issues ready to work on (no blockers)
- `get_blocked`: Get blocked issues and their blockers
