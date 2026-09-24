# Phase 1 scope

This phase establishes deterministic configuration and validation only.

- No ImmortalWrt source clone is performed by CI.
- No package download or firmware build is performed by CI.
- No GitHub Release is created.
- The generated `.config` is checked into source control for auditability.
- The hardware profile is driven by `features` in `config/j4125-router.yaml`.
- Detailed OpenWrt kernel and package mappings live in `scripts/profile_rules.py`.
- The final package manifest check is implemented now and will be connected to the future build workflow.