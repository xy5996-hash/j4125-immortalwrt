#!/usr/bin/env python3
"""Validate that generated .config still matches the fixed J4125 hardware profile."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from config_lib import (
    DEFAULT_CONFIG,
    DEFAULT_YAML,
    ConfigReadError,
    load_yaml,
    matches_any,
    read_config,
    yaml_list_of_strings,
)
from profile_rules import (
    FORBIDDEN_DRIVER_PATTERNS,
    FORBIDDEN_MANIFEST_PATTERNS,
    expand_feature_kconfig,
    expand_feature_packages,
    feature_map,
    unique,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML)
    args = parser.parse_args()

    try:
        data = load_yaml(args.yaml)
        features = feature_map(data)
        selected, _ = read_config(args.config)
        raw_lines = set(args.config.read_text(encoding="utf-8").splitlines())
        include = yaml_list_of_strings(data, "packages", "include")
        exclude = yaml_list_of_strings(data, "packages", "exclude")
        security_forbidden = yaml_list_of_strings(data, "security", "forbidden_manifest_packages")
    except (OSError, ConfigReadError) as exc:
        print(f"hardware profile error: {exc}")
        return 1

    hardware = data.get("hardware")
    if not isinstance(hardware, dict):
        print("hardware profile error: hardware mapping is missing")
        return 1
    ethernet = hardware.get("ethernet")
    if not isinstance(ethernet, dict):
        print("hardware profile error: hardware.ethernet is missing")
        return 1

    errors: list[str] = []
    if ethernet.get("driver") != "igc":
        errors.append("hardware ethernet driver is not igc")
    if ethernet.get("pci_id") != "8086:125c":
        errors.append("hardware ethernet PCI ID is not 8086:125c")
    if ethernet.get("port_count") != 4:
        errors.append("hardware I226-V port count is not 4")

    expected_packages = unique(expand_feature_packages(data) + include)
    for package in expected_packages:
        if package not in selected:
            errors.append(f"missing required package selection: CONFIG_PACKAGE_{package}=y")

    expected_kconfig = expand_feature_kconfig(data)
    for symbol, value in expected_kconfig.items():
        expected_line = f"# {symbol} is not set" if value == "n" else f"{symbol}={value}"
        if expected_line not in raw_lines:
            errors.append(f"missing required kernel config: {expected_line}")

    required_image_lines = {
        "CONFIG_TARGET_x86=y",
        "CONFIG_TARGET_x86_64=y",
        "CONFIG_TARGET_DEVICE_x86_64_DEVICE_generic=y",
        'CONFIG_TARGET_DEVICE_PACKAGES_x86_64_DEVICE_generic=""',
        "CONFIG_TARGET_ROOTFS_SQUASHFS=y",
        "# CONFIG_TARGET_ROOTFS_EXT4FS is not set",
        "CONFIG_GRUB_EFI_IMAGES=y",
        "CONFIG_USE_APK=y",
    }
    for line in sorted(required_image_lines):
        if line not in raw_lines:
            errors.append(f"missing required target/image config: {line}")

    patterns = FORBIDDEN_MANIFEST_PATTERNS + FORBIDDEN_DRIVER_PATTERNS + security_forbidden
    for package in sorted(selected):
        matched = matches_any(package, patterns)
        if matched:
            errors.append(f"forbidden package selected: {package} (pattern: {matched})")

    for package in exclude:
        if package in selected:
            errors.append(f"package is explicitly excluded: {package}")

    for line in ("CONFIG_ALL=y", "CONFIG_ALL_KMODS=y", "CONFIG_ALL_NONSHARED=y"):
        if line in raw_lines:
            errors.append(f"global build-all option must not be enabled: {line}")

    for pattern in security_forbidden:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"invalid forbidden pattern {pattern!r}: {exc}")

    for feature in ("i226", "j4125_gemini_lake", "setup_wizard", "shortcut_menu"):
        if not features.get(feature):
            errors.append(f"feature {feature} must remain enabled")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(
        "hardware profile OK: 4x I226-V, J4125 platform, storage/EFI/USB, "
        "iStore, OpenClash, setup wizard, shortcut menu"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
