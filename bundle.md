---
bundle:
  name: issues
  version: 2.0.0
  description: Issue-aware bundle with autonomous issue management and persistent tracking

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: issues:behaviors/issues
---

@issues:context/issues-instructions.md

---

@foundation:context/shared/common-system-base.md
