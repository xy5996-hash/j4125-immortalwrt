# Engineering Audit

- Audit date: 2026-09-24
- Repository: `xy5996-hash/j4125-immortalwrt`
- Audit baseline: `main` at `03d148c993611ed6bf6a9199eaa48a98905e7fde`
- Audit publication commit: `32fb25c1eea285d04fd4ae5236d170b65daad85e`
- Existing source pre-release: `v25.12.2-r0-phase1`
- Scope: configuration, renderer, feeds, local overlay, package placeholder, validation scripts, GitHub Actions
- Phase A rule: this file is the only repository change in this phase. No build implementation is included yet.

## 1. Executive Summary

The current architecture is suitable for the project:

```text
config/j4125-router.yaml
        -> scripts/render-config.py
        -> generated .config
        -> pinned ImmortalWrt source
        -> pinned feeds
        -> iStore / OpenClash / mihomo
        -> firmware build
        -> manifest validation
        -> artifact / release
```

The repository is currently a well-defined configuration and static-validation project, but it is **not build-ready**.

The strongest parts are:

- one high-level YAML profile
- deterministic rendered `.config`
- complete commit pins for ImmortalWrt and feeds
- valid GitHub Actions static validation
- no discovered credentials or subscription URLs
- broad common x86 driver policy already represented

The main build blockers are:

- no build workflow
- no real `make defconfig`/dependency resolution
- no `mihomo-core` package
- no final package manifest validation in an actual build
- generated `.config` explicitly disables `mihomo-core`
- one virtual NIC policy mismatch (`kmod-vmxnet3` is excluded)

## 2. Current Repository Architecture

```text
config/j4125-router.yaml
    |-- version and feed pins
    |-- target/image intent
    |-- hardware profile
    |-- feature flags
    |-- explicit package exclusions
    +-- component pins

scripts/profile_rules.py
    |-- feature -> package expansion
    |-- feature -> kernel Kconfig expansion
    +-- forbidden package/driver patterns

scripts/render-config.py
    +-- renders generated .config

feeds/feeds.conf.lock
    |-- five ImmortalWrt feeds
    |-- iStore
    |-- OpenClash
    +-- netwizard

.github/workflows/validate.yml
    +-- static validation and secret scan

package/mihomo-core/
    +-- README placeholder only; no package implementation
```

## 3. Audit Checklist

| Check | Result | Evidence / Finding |
|---|---|---|
| YAML is the human-maintained source | Pass | No `CONFIG_*` entries in `config/j4125-router.yaml` |
| Generated `.config` comes from YAML | Pass with limitation | `render-config.py --check` passes, but it is not a `defconfig` result |
| Second manual config source | Pass | No committed second `.config` seed |
| Profile rules match YAML intent | Partial | Broad compatibility is represented, but `kmod-vmxnet3` is excluded |
| `.config` processed by ImmortalWrt defconfig | Fail | No source checkout, feeds setup, or `make defconfig` step |
| Package dependency resolution | Not tested | No `scripts/feeds install` or build execution |
| Feeds pinned | Pass structurally | Eight feeds use 40-character commits |
| iStore pinned | Pass | Commit `3fca15b30aeed9ecacb3efc8b4a8b9c2584ad5c7` |
| OpenClash pinned | Pass | `v0.47.156`, commit `c3a33c1d3407956fdf8f0e0b7c1a4c52e6ad9593` |
| mihomo pinned | Partial | Version/asset/SHA are pinned in YAML, but no package exists |
| SHA256 verified during download | Fail | No download/build code currently verifies the mihomo asset |
| Forbidden packages checked in generated config | Pass | `check_forbidden_packages.py` passes |
| Forbidden packages checked in final manifest | Not integrated | Checker exists, but no build workflow invokes it on a real manifest |
| Clean GitHub Actions validation | Pass | Run `35974929967` succeeded |
| Clean firmware build reproducibility | Not tested | No firmware build workflow or cold-build check |
| Secret scan | Pass | Local scan and Gitleaks workflow pass |
| Build-time/runtime separation | Partial | OpenClash can download a missing core at runtime if packaging is incomplete |
| Missing referenced files | Pass for current phase | Only the intentionally absent `package/mihomo-core/Makefile` is missing |
| Phase 1 assumptions leaking into Phase 2 | Fail | Generated config explicitly sets `CONFIG_PACKAGE_mihomo-core` off |

## 4. P0 Issues

### P0-1. `mihomo-core` is not implemented

Current state:

- `package/mihomo-core/README.md` exists.
- No `Makefile` exists.
- Generated `.config` contains:

```text
# CONFIG_PACKAGE_mihomo-core is not set  # phase 2 after local package exists
```

Impact:

- OpenClash is selected but the required core is not part of the firmware package set.
- A first boot may trigger OpenClash's runtime core-download path.
- The final firmware cannot currently satisfy the requirement that the pinned mihomo core is actually included.

Required Phase B work:

- add `package/mihomo-core/Makefile`
- pin exact release URL, asset name, and SHA256
- install to `/etc/openclash/core/clash_meta`
- select `CONFIG_PACKAGE_mihomo-core=y`
- update `check_components.py` and build checks to verify the real asset

### P0-2. No formal build workflow

Current state:

- Only `.github/workflows/validate.yml` exists.
- There is no `.github/workflows/build.yml`.
- No CI job checks out ImmortalWrt, applies the pinned feed lock, renders config, runs `make defconfig`, or compiles.

Impact:

- Current CI proves only static file consistency.
- It does not prove feeds can be cloned, packages can be resolved, or firmware can be built.

Required Phase B/C work:

- add `workflow_dispatch` build workflow
- fetch pinned ImmortalWrt commit
- apply `feeds/feeds.conf.lock`
- run `scripts/feeds update` and required feed installs
- copy `files/`
- render config
- run `make defconfig`
- then run `make download` and compile

### P0-3. Generated config is not a defconfig result

Current state:

- `config/generated/immortalwrt-25.12.2-x86_64.config` is deterministic renderer output.
- No `generated-config-before-defconfig` or `generated-config-after-defconfig` exists.
- No `config-diff` exists.

Impact:

- A Kconfig symbol can be invalid, hidden, renamed, or re-selected after `make defconfig`.
- Package dependencies are not resolved.
- Static string checks can pass while the final build has different selections.

Required Phase B work:

```text
render-config.py
  -> generated-config-before-defconfig
  -> make defconfig
  -> generated-config-after-defconfig
  -> config-diff
  -> final validation
```

### P0-4. Final manifest validation is not wired into a build

Current state:

- `scripts/check_manifest.py` exists and its self-test passes.
- No firmware build generates a real manifest.
- No workflow calls `check_manifest.py --manifest ...`.

Impact:

- A future dependency can still introduce Docker, Samba, Transmission, etc. without the real build failing.

Required Phase B/C work:

- extract the generated manifest from the build output
- run forbidden-package validation against the manifest
- run required-package validation against the manifest
- fail the build before artifact upload if any violation appears

### P0-5. VM NIC compatibility contradicts the final policy

Current state:

- `kmod-e1000` and `kmod-e1000e` are selected.
- QEMU/KVM virtio network support is present in the official x86 kernel configuration (`CONFIG_VIRTIO_NET=y`).
- `kmod-vmxnet3` is explicitly excluded in YAML and generated config.

Impact:

- VMware compatibility is not guaranteed.
- This conflicts with the stated requirement to retain common virtual-machine NIC drivers for testing and migration.

Required Phase B work:

- remove `kmod-vmxnet3` from the exclusion list
- add it to `broad_compat`
- verify final Kconfig and manifest
- keep `virtio-net` support verified in the final config

### P0-6. No artifact or image-validation pipeline

Current state:

- No `build.yml`.
- No image sanity script.
- No `build-info.json` generator.
- No SHA256 artifact file generation.

Impact:

- The repository cannot yet produce the requested deliverables:

```text
*.img.gz
*.sha256
manifest.txt
build-info.json
final .config
build log
```

Required Phase B/C work:

- generate all build metadata
- verify gzip/image/EFI/kernel/rootfs structure
- verify required and forbidden packages in the manifest
- hash the artifact
- upload artifact
- keep Release creation disabled until the first successful manual build

## 5. P1 Issues

- `check_components.py` validates that the mihomo SHA is syntactically 64 hex characters, but does not download or independently verify the upstream asset.
- `check_feeds_lock.py` compares YAML and lock file but does not verify remote commits, duplicate feed names, or feed reachability.
- OpenClash -> mihomo compatibility is not yet proven by a build and runtime smoke test.
- `luci-app-openclash` is known to support a runtime core download fallback; the project must ensure the pinned package prevents a missing-core fallback in the official image.
- `check_manifest.py` requires every expanded package to appear in the manifest. Some kernel packages can be built-in or named differently in a manifest; this needs validation on the first real build.
- `config/generated/...` is manually committed for auditability; any accidental hand edit will be caught by renderer check, but this is still a two-artifact maintenance surface.
- `rootfs_partition_mib: 512` may be tight for iStore, OpenClash, Ruby, translations, and future packages on the 128 GB SSD.
- OpenClash requires `luci-compat`, `ruby`, `ruby-yaml`, `dnsmasq-full`, and nftables modules; these are selected, but dependency closure has not been proven by a real defconfig.
- iStore uses an external runtime package repository. The iStore UI commit is pinned, but the catalog itself is not reproducible.
- No cold-build workflow exists to prove that clearing caches still succeeds.
- No QEMU/UEFI smoke-test script exists yet.
- `README.md` currently says "deliberately small", which conflicts with the final project positioning.
- `docs/phase-1.md` says no GitHub Release is created, while a source pre-release now exists.
- The repository contains no explicit LICENSE file.

## 6. P2 Issues

- `README.md` contains literal `\n` sequences in the feature list instead of separate Markdown lines.
- `scripts/profile_rules.py` has a formatting defect: `],    "diagnostic_tools": [...]` appears on one line. It parses correctly but is poor for reviewability.
- The current source pre-release has no custom asset; GitHub automatically exposes source archives only.
- There is no `shellcheck`/`ruff`/`pytest` gate for the scripts.
- No documented cache-eviction or clean-build retention policy exists.
- The current pinned Actions emit a Node.js 20 deprecation warning because GitHub forces them onto Node.js 24. They still pass, but should be upgraded intentionally later.

## 7. Dependency Relationships

```text
ImmortalWrt v25.12.2
  -> packages feed
  -> luci feed
  -> routing feed
  -> telephony feed
  -> video feed

ImmortalWrt + luci
  -> luci-app-store
       -> curl
       -> tar
       -> libuci-lua
       -> mount-utils
       -> luci-lib-taskd
       -> taskd
       -> luci-lib-xterm

ImmortalWrt + firewall4/nftables
  -> luci-app-openclash
       -> dnsmasq-full
       -> bash
       -> curl
       -> ca-bundle
       -> ip-full
       -> ruby
       -> ruby-yaml
       -> kmod-tun
       -> kmod-inet-diag
       -> kmod-nft-tproxy
       -> unzip
       -> mihomo-core [MISSING]
            -> /etc/openclash/core/clash_meta

ImmortalWrt + luci
  -> luci-app-netwizard
       -> luci-compat
       -> netwizard runtime files and zh_Hans translation

files/
  -> /etc/profiles
  -> /etc/profile.d/99-ezopwrt-menu.sh
       -> bash
       -> uci / ubus / jsonfilter / curl
       -> optional sensors command
```

## 8. Current Build Blockers

Ordered by first expected failure:

1. No build workflow exists to clone and prepare the pinned source/feeds.
2. No `mihomo-core` package exists.
3. Generated `.config` turns `mihomo-core` off.
4. No `make defconfig` has processed the generated config.
5. No dependency resolution or package-install step has run.
6. No real manifest has been produced or checked.
7. `kmod-vmxnet3` is excluded despite the final VM compatibility requirement.
8. No image sanity, SHA256, or `build-info.json` generation exists.

## 9. What Should Stay Unchanged

The following should be retained in Phase B:

- high-level YAML as the human-maintained source
- `render-config.py` as the deterministic YAML -> initial `.config` stage
- pinned ImmortalWrt and feed commits
- `broad_compat` feature
- iStore UI-only integration
- OpenClash/iStore/mihomo version pinning strategy
- local shortcut menu and its SHA256 checks
- `CONFIG_TARGET_MULTI_PROFILE=y` unless a real build proves an actual problem
- i915/DRM/HDA retention unless a concrete build or dependency problem appears
- forbidden-service policy for Docker/NAS/Samba/media/download services
- no runtime subscription URLs or credentials in Git

## 10. Phase B Proposed Fix Order

1. Implement `package/mihomo-core/Makefile` and select it in the generated config.
2. Add `build.yml` with manual `workflow_dispatch` only.
3. Add a build-preparation script that:
   - checks out the pinned ImmortalWrt commit
   - installs `feeds.conf.lock`
   - runs feeds update/install
   - copies `files/`
   - renders the initial config
4. Run `make defconfig` and save before/after/diff configurations.
5. Validate final config against hardware, forbidden packages, and package dependencies.
6. Run `make download` and the first real build.
7. Generate manifest, `build-info.json`, image sanity checks, and SHA256.
8. Add QEMU/UEFI smoke testing only after the build succeeds.
9. Update README and docs to match the final "functional restraint, broad hardware compatibility" policy.
10. Keep Release creation disabled until the manual build and hardware verification pass.

## 11. Verification Plan

### Static

- `render-config.py --check`
- feeds lock validation
- component and SHA checks
- hardware profile check
- forbidden package check
- secret scan

### Build foundation

- pinned ImmortalWrt checkout
- feed update/install from the lock file
- `make defconfig`
- compare before/after configs
- verify required symbols still exist after defconfig

### Firmware

- build `squashfs-combined-efi.img.gz`
- verify manifest
- verify forbidden packages absent
- verify required packages present
- verify gzip and EFI/image structure
- verify SHA256
- generate `build-info.json`

### Runtime

- QEMU + UEFI smoke test
- physical J4125-4L test
- verify four I226-V ports and `igc`
- verify VLAN, PPPoE, IPv4/IPv6, firewall4
- verify iStore
- verify OpenClash starts and recognizes the packaged mihomo core
- verify LuCI pages

## 12. Final Audit Answers

### P0 Must Fix

- Implement `mihomo-core`.
- Add the real build workflow and pinned source/feed preparation.
- Run and validate `make defconfig`.
- Validate the real package manifest.
- Restore VMware/common VM NIC compatibility, starting with `kmod-vmxnet3`.
- Generate image sanity metadata and SHA256.

### P1 Recommended Fixes

- Strengthen remote feed/commit verification.
- Add real mihomo asset download/hash verification.
- Prove OpenClash/mihomo runtime compatibility.
- Add cold-build mode.
- Validate manifest package naming assumptions.
- Address the 512 MiB rootfs sizing risk.
- Update documentation.

### Keep Unchanged

- YAML -> renderer architecture.
- Pinned versions and feeds.
- broad x86 compatibility policy.
- i915/DRM/HDA retention.
- No iStoreOS firmware components.
- No Docker/NAS/Samba/media/download services.
- No secrets or subscriptions in Git.

### Most Likely First Build Failures

1. Missing `mihomo-core` package.
2. Feeds or nested third-party package discovery.
3. `make defconfig` rejecting or dropping expected config symbols.
4. OpenClash build dependencies and package paths.
5. iStore APK packaging compatibility.
6. Manifest required-package mismatch.
7. Missing VM NIC support during QEMU/VMware smoke tests.

### Validation After Fixes

Use a clean build environment, not the existing developer workspace:

```text
clean checkout
-> pinned ImmortalWrt
-> feeds lock
-> render YAML
-> defconfig
-> dependency resolution
-> build
-> manifest checks
-> image checks
-> SHA256/build-info
-> QEMU smoke
-> physical J4125-4L
```