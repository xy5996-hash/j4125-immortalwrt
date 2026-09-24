# ImmortalWrt J4125-4L Phase 1

This is a **source and configuration pre-release**. It does not contain a firmware image.

## Included

- ImmortalWrt `v25.12.2` (`4fc16f2985a358bd43bb522e43f05395fcbd6ed5`)
- high-level `config/j4125-router.yaml`
- deterministic YAML to `.config` renderer
- pinned ImmortalWrt feeds, iStore, OpenClash, mihomo, and setup wizard
- `feeds.conf.lock`
- J4125/I226 hardware profile checks
- common x86 compatibility set: Intel/Realtek wired NICs, NVMe, USB storage/network/serial, common hardware sensors
- expanded forbidden-package checks
- secret scanning
- GitHub Actions validation workflow

## Requested UI components

- setup wizard: `luci-app-netwizard` `v2.1.5`
- console shortcut menu: local vetted overlay with pinned SHA-256

## Not included

- firmware `.img` or `.img.gz`
- final package manifest
- first full ImmortalWrt build
- runtime subscriptions, passwords, tokens, or private keys

## Validation

Run:

```bash
python3 -m pip install -r requirements.txt
bash scripts/validate-config.sh
```

The generated `.config` is intentionally committed for auditability. The future firmware build must run `scripts/check_manifest.py --manifest <manifest>` before publishing any image.