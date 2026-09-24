# Runtime overlay

This directory contains reviewed, non-secret configuration and local runtime files.

Phase 1 includes the requested console shortcut menu:

- `etc/profiles`
- `etc/profile.d/99-ezopwrt-menu.sh`

The menu contains password-clearing commands as functionality, but no passwords, tokens, subscription URLs, or private keys. File hashes are pinned in `config/j4125-router.yaml` and checked by CI.