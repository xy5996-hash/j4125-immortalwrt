# mihomo-core placeholder

The mihomo version and SHA-256 are pinned in `config/j4125-router.yaml`.

The local `mihomo-core` package is intentionally not implemented in phase 1. OpenClash is selected in the generated `.config`; the core package will be added in phase 2, verified, and then selected with `CONFIG_PACKAGE_mihomo-core=y`.

Do not place a downloaded core binary or subscription data in this repository without a reviewed package definition and matching SHA-256.