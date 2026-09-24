#!/usr/bin/env python3
"""Fail a build when the final package manifest contains forbidden packages."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml, matches_any, yaml_list_of_strings
from profile_rules import (
    FORBIDDEN_MANIFEST_PATTERNS,
    expand_feature_packages,
    feature_map,
    unique,
)

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")


def parse_manifest(text: str) -> list[str]:
    packages: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if " - " in line:
            name = line.split(" - ", 1)[0].strip()
        else:
            name = line.split()[0]
        if name.startswith("+"):
            name = name[1:]
        if _NAME_RE.fullmatch(name):
            packages.append(name)
    return packages


def literal_patterns(values: list[str]) -> list[str]:
    patterns: list[str] = []
    for value in values:
        escaped = re.escape(value)
        patterns.append(rf"^{escaped}(?:$|[-_.])")
    return patterns


def check_packages(packages: list[str], forbidden_patterns: list[str]) -> list[str]:
    errors: list[str] = []
    for package in packages:
        matched = matches_any(package, forbidden_patterns)
        if matched:
            errors.append(f"forbidden package in manifest: {package} (pattern: {matched})")
    return errors


def load_patterns(profile_path: Path) -> list[str]:
    data = load_yaml(profile_path)
    literal = yaml_list_of_strings(data, "security", "forbidden_manifest_packages")
    return FORBIDDEN_MANIFEST_PATTERNS + literal_patterns(literal)


def required_packages(profile_path: Path) -> list[str]:
    data = load_yaml(profile_path)
    feature_map(data)
    return unique(expand_feature_packages(data))


def self_test(patterns: list[str]) -> int:
    clean = ["base-files", "kmod-igc", "luci-app-openclash", "luci-app-store"]
    unsafe = clean + ["dockerd", "samba4-server", "transmission-daemon"]
    clean_errors = check_packages(clean, patterns)
    unsafe_errors = check_packages(unsafe, patterns)
    if clean_errors:
        print("manifest self-test failed: clean fixture was rejected")
        for error in clean_errors:
            print(f"ERROR: {error}")
        return 1
    if not unsafe_errors:
        print("manifest self-test failed: unsafe fixture was accepted")
        return 1
    print(f"manifest self-test OK: unsafe fixture rejected with {len(unsafe_errors)} findings")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--profile", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        patterns = load_patterns(args.profile)
    except ConfigReadError as exc:
        print(f"manifest check error: {exc}")
        return 1

    if args.self_test:
        return self_test(patterns)
    if args.manifest is None:
        print("manifest check error: --manifest is required unless --self-test is used")
        return 1

    try:
        packages = parse_manifest(args.manifest.read_text(encoding="utf-8"))
        required = required_packages(args.profile)
    except (OSError, ConfigReadError) as exc:
        print(f"manifest check error: {exc}")
        return 1

    errors = check_packages(packages, patterns)
    missing = sorted(set(required) - set(packages))
    for package in missing:
        errors.append(f"required package missing from manifest: {package}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"manifest check OK: {len(packages)} packages, no forbidden entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
