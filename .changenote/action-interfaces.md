---
action: minor
---

Use seven Action entry points with separate CLI setup, environment preparation, PR checks, PR management, inspection, and GitHub publication.
Replace select and preview with inspect; remove the release entry point and root's single-operation modes without aliases.
Use root hooks or auto for complete workflows, and use standalone Actions for individual operations and publication retries.
Replace the select preparation scope with inspect and remove the retry input.
Keep the hooks default, exact-commit publication guards, historical batch verification, and managed-merge script policy.
