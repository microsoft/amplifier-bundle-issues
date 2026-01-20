---
bundle:
  name: issues
  version: 2.1.0
  description: Issue-aware bundle with GitHub sync, autonomous issue management, and team visibility

includes:
  - bundle: issues:behaviors/issues

agents:
  issue-tracking:
    path: issues:agents/issue-tracking.md
    description: Query and analyze team work patterns across GitHub issues
---

@issues:context/issues-instructions.md


