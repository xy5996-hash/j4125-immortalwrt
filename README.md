# ImmortalWrt J4125-4L Router

This repository builds a personal ImmortalWrt x86_64 firmware profile for one fixed router:

- CncTion J4125-4L
- Intel Celeron J4125
- 4 GiB RAM
- 4x Intel I226-V using the `igc` driver
- bare-metal UEFI
- squashfs combined EFI image
- broad common x86 hardware compatibility
- functional restraint: no Docker, NAS, Samba, media, or download-server services

## Configuration model

`config/j4125-router.yaml` is the only human-maintained profile. It describes high-level intent such as target, image type, feature flags, package exclusions, and pinned component versions.

`scripts/render-config.py` converts that intent into an initial `.config`. The committed file under `config/generated/` is generated output and must not be edited manually.

## Current implementation

- pinned ImmortalWrt `v25.12.2`
- pinned ImmortalWrt, iStore, OpenClash, mihomo, and setup-wizard versions
- pinned `feeds.conf.lock`
- local `mihomo-core` package
- setup wizard `luci-app-netwizard`
- reviewed console shortcut menu
- static hardware, forbidden-package, manifest, and secret checks
- manual defconfig foundation workflow
- Phase B foundation run verified in GitHub Actions (35978658528)

## Layout

```text
config/                 YAML profile and generated .config
feeds/                  pinned feeds
files/                  non-secret runtime overlay
package/mihomo-core/    pinned mihomo core package
scripts/                renderer and validation tools
.github/workflows/      validation and foundation workflows
```

## Local validation

```bash
python3 -m pip install -r requirements.txt
bash scripts/validate-config.sh
```

For the clean-source configuration foundation:

```bash
python3 scripts/verify-mihomo-asset.py
python3 scripts/prepare-build-foundation.py --work-dir /tmp/j4125-foundation
```

The foundation workflow does not compile a firmware image or create a GitHub Release.