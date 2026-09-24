#!/usr/bin/env python3
"""Render high-level YAML intent into an ImmortalWrt .config file."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from profile_rules import (
    expand_feature_kconfig,
    expand_feature_packages,
    feature_map,
    unique,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_YAML = REPO_ROOT / "config" / "j4125-router.yaml"
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ConfigError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"YAML file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"top-level YAML value must be a mapping: {path}")
    if data.get("schema_version") != 1:
        raise ConfigError("unsupported or missing schema_version; expected 1")
    return data


def require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a mapping")
    return value


def require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"{key} must be a list")
    return value


def validate_source(data: dict[str, Any]) -> None:
    base = require_mapping(data, "base")
    for field in ("repository", "ref", "commit", "package_manager"):
        if not base.get(field):
            raise ConfigError(f"base.{field} is required")
    if not COMMIT_RE.fullmatch(str(base["commit"])):
        raise ConfigError("base.commit must be a full 40-character commit hash")
    if base["package_manager"] != "apk":
        raise ConfigError("base.package_manager must be apk for ImmortalWrt 25.12")

    hardware = require_mapping(data, "hardware")
    if hardware.get("profile") != "cnction-j4125-4l":
        raise ConfigError("hardware.profile must be cnction-j4125-4l")
    ethernet = hardware.get("ethernet")
    if not isinstance(ethernet, dict):
        raise ConfigError("hardware.ethernet must be a mapping")
    if ethernet.get("driver") != "igc":
        raise ConfigError("hardware.ethernet.driver must be igc")
    if ethernet.get("pci_id") != "8086:125c":
        raise ConfigError("hardware.ethernet.pci_id must be 8086:125c")
    if ethernet.get("port_count") != 4:
        raise ConfigError("hardware.ethernet.port_count must be 4")

    components = require_mapping(data, "components")
    mihomo = require_mapping(components, "mihomo")
    for field in ("repository", "ref", "asset", "sha256", "install_path"):
        if not mihomo.get(field):
            raise ConfigError(f"components.mihomo.{field} is required")
    if not SHA256_RE.fullmatch(str(mihomo["sha256"])):
        raise ConfigError("components.mihomo.sha256 must be a lowercase SHA-256")

    for component in ("istore", "openclash", "setup_wizard"):
        value = require_mapping(components, component)
        commit = str(value.get("commit", ""))
        if not COMMIT_RE.fullmatch(commit):
            raise ConfigError(f"components.{component}.commit must be a full commit hash")


def validate_packages(packages: dict[str, Any]) -> tuple[list[str], list[str]]:
    include_raw = require_list(packages, "include")
    exclude_raw = require_list(packages, "exclude")
    include = [str(item) for item in include_raw]
    exclude = [str(item) for item in exclude_raw]

    for item in include + exclude:
        if not PACKAGE_RE.fullmatch(item):
            raise ConfigError(f"invalid package name: {item!r}")

    duplicates = sorted({item for item in include if include.count(item) > 1})
    if duplicates:
        raise ConfigError(f"duplicate package include entries: {duplicates}")

    overlap = sorted(set(include) & set(exclude))
    if overlap:
        raise ConfigError(f"packages cannot be both included and excluded: {overlap}")
    return include, exclude


def append_kconfig(lines: list[str], symbol: str, value: str) -> None:
    if value == "n":
        lines.append(f"# {symbol} is not set")
    else:
        lines.append(f"{symbol}={value}")


def render(data: dict[str, Any], source_path: Path) -> str:
    validate_source(data)
    features = feature_map(data)

    target = require_mapping(data, "target")
    image = require_mapping(data, "image")
    if (target.get("target"), target.get("subtarget"), target.get("profile")) != (
        "x86",
        "64",
        "generic",
    ):
        raise ConfigError("target must be x86/64 generic")
    if image.get("filesystem") != "squashfs":
        raise ConfigError("image.filesystem must be squashfs")
    if image.get("format") != "combined-efi":
        raise ConfigError("image.format must be combined-efi")

    include, exclude = validate_packages(require_mapping(data, "packages"))
    packages = unique(expand_feature_packages(data) + include)
    overlap = sorted(set(packages) & set(exclude))
    if overlap:
        raise ConfigError(f"expanded feature packages overlap exclusions: {overlap}")

    yaml_text = source_path.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    yaml_digest = hashlib.sha256(yaml_text.encode("utf-8")).hexdigest()
    base = require_mapping(data, "base")
    components = require_mapping(data, "components")
    mihomo = require_mapping(components, "mihomo")
    setup_wizard = require_mapping(components, "setup_wizard")
    shortcut_menu = require_mapping(components, "shortcut_menu")

    lines: list[str] = [
        "# Generated by scripts/render-config.py. Do not edit manually.",
        f"# Source profile: {source_path.relative_to(REPO_ROOT).as_posix()}",
        f"# Source SHA256: {yaml_digest}",
        f"# ImmortalWrt ref: {base['ref']} ({base['commit']})",
        f"# ImmortalWrt kernel series: {base.get('kernel_series', 'unknown')}",
        f"# Hardware profile: {require_mapping(data, 'hardware')['profile']}",
        f"# Enabled features: {', '.join(sorted(name for name, on in features.items() if on))}",
        "",
        "# Target and image",
        "CONFIG_TARGET_x86=y",
        "CONFIG_TARGET_x86_64=y",
        "CONFIG_TARGET_MULTI_PROFILE=y",
        "CONFIG_TARGET_DEVICE_x86_64_DEVICE_generic=y",
        'CONFIG_TARGET_DEVICE_PACKAGES_x86_64_DEVICE_generic=""',
        "CONFIG_TARGET_ROOTFS_SQUASHFS=y",
        "# CONFIG_TARGET_ROOTFS_EXT4FS is not set",
        f"CONFIG_TARGET_KERNEL_PARTSIZE={int(image.get('kernel_partition_mib', 32))}",
        f"CONFIG_TARGET_ROOTFS_PARTSIZE={int(image.get('rootfs_partition_mib', 512))}",
        f"CONFIG_TARGET_IMAGES_GZIP={'y' if image.get('gzip') else 'n'}",
        "CONFIG_GRUB_EFI_IMAGES=y",
        "# CONFIG_GRUB_IMAGES is not set",
        "CONFIG_GRUB_CONSOLE=y",
        "CONFIG_GRUB_TIMEOUT=5",
        'CONFIG_GRUB_TITLE="ImmortalWrt J4125-4L"',
        "# CONFIG_ISO_IMAGES is not set",
        "# CONFIG_QCOW2_IMAGES is not set",
        "# CONFIG_VDI_IMAGES is not set",
        "# CONFIG_VMDK_IMAGES is not set",
        "# CONFIG_VHDX_IMAGES is not set",
        "CONFIG_USE_APK=y",
        "CONFIG_CCACHE=y",
        "CONFIG_REPRODUCIBLE_DEBUG_INFO=y",
        "",
        "# Kernel requirements derived from enabled hardware features",
    ]

    for symbol, value in expand_feature_kconfig(data).items():
        append_kconfig(lines, symbol, value)

    lines.extend(["", "# Selected firmware packages"])
    for package in packages:
        lines.append(f"CONFIG_PACKAGE_{package}=y")

    lines.extend(["", "# Explicitly excluded packages and drivers"])
    for package in exclude:
        lines.append(f"# CONFIG_PACKAGE_{package} is not set")

    lines.extend(
        [
            "",
            "# Component provenance",
            f"# iStore commit: {components['istore']['commit']}",
            f"# OpenClash ref/commit: {components['openclash']['ref']} {components['openclash']['commit']}",
            f"# mihomo ref/asset: {mihomo['ref']} {mihomo['asset']}",
            f"# mihomo sha256: {mihomo['sha256']}",
            f"# setup wizard ref/commit: {setup_wizard['ref']} {setup_wizard['commit']}",
            f"# shortcut menu version: {shortcut_menu['version']}",
            "# CONFIG_PACKAGE_mihomo-core is not set  # phase 2 after local package exists",
            "",
        ]
    )
    return "\n".join(lines)


def write_or_check(output_path: Path, rendered: str, check: bool) -> int:
    if check:
        if not output_path.exists():
            print(f"missing generated config: {output_path}", file=sys.stderr)
            return 1
        actual = output_path.read_text(encoding="utf-8")
        if actual == rendered:
            return 0
        diff = difflib.unified_diff(
            actual.splitlines(),
            rendered.splitlines(),
            fromfile=str(output_path),
            tofile="rendered-from-yaml",
            lineterm="",
        )
        print("\n".join(diff), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    config_path = args.config.resolve()
    try:
        data = load_yaml(config_path)
        rendered = render(data, config_path)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    output = args.output
    if output is None:
        output_value = require_mapping(data, "output").get("generated_config")
        if not output_value:
            raise ConfigError("output.generated_config is missing")
        output = (REPO_ROOT / str(output_value)).resolve()
    else:
        output = output.resolve()

    result = write_or_check(output, rendered, args.check)
    if result == 0 and not args.check:
        print(f"wrote {output}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
