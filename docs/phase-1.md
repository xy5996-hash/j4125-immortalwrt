# Phase 1 scope

Phase 1 established deterministic configuration and static validation only.

- ImmortalWrt source was not cloned by the phase-1 validation workflow.
- No firmware was built.
- Generated `.config` was committed for auditability, but it was not a `defconfig` result.
- Hardware intent came from `features` in `config/j4125-router.yaml`.
- Detailed OpenWrt mappings lived in `scripts/profile_rules.py`.
- A source/configuration pre-release exists, but no firmware release exists.

Phase 2 adds the real source/feed preparation, `make defconfig`, dependency checks, and the local `mihomo-core` package.