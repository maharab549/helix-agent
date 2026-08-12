---
name: repo-inspector
description: Inspect a software repository, summarize structure, detect build commands, and propose next steps.
---

# Repo Inspector

Use local shell tools first:

```bash
rg --files
git status --short
```

Look for:

- Package manifests and lockfiles.
- Test commands and CI workflows.
- Entry points and public APIs.
- Documentation freshness.
- Risky generated files or vendored dependencies.
