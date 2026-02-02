---
bundle:
  name: issues
  version: 2.0.1
  description: Issue-aware bundle with autonomous issue management and persistent tracking

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main # For standalone use
  - bundle: issues:behaviors/issues
---

@issues:context/issues-instructions.md


