---
action: minor
---

Support file-free CLI releases by deriving release identity from consumed notes and verifying the complete release tree.
Keep historical metadata-only publication, completed note-bearing batch inspection, exact-commit guards, and retries.
Upgrade this Action before enabling the file-free CLI.
Replace `.changenote/releases.json` readers with verified `release-commit` and `releases` outputs.
Create local tags from the verified plan after complete preflight.
Release discovery does not run project package managers.
