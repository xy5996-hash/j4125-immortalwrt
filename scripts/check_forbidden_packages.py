#!/usr/bin/env python3
"""Reject selected .config packages that violate the clean-router profile."""

from __future__ import annotations

import argparse
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
from profile_rules import FORBIDDEN_DRIVER_PATTERNS, FORBIDDEN_MANIFEST_PATTERNS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML)
    args = parser.parse_args()

    try:
        data = load_yaml(args.yaml)
        selected, _ = read_config(args.config)
        excluded = yaml_list_of_strings(data, "packages", "exclude")
        yaml_patterns = yaml_list_of_strings(
            data, "security", "forbidden_manifest_packages"
        )
    except ConfigReadError as exc:
        print(f"forbidden package error: {exc}")
        return 1

    patterns = FORBIDDEN_MANIFEST_PATTERNS + FORBIDDEN_DRIVER_PATTERNS + yaml_patterns
    errors: list[str] = []
    for package in sorted(selected & set(excluded)):
        errors.append(f"package is explicitly excluded: {package}")

    for package in sorted(selected):
        matched = matches_any(package, patterns)
        if matched:
            errors.append(f"forbidden package selected: {package} (pattern: {matched})")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"forbidden package check OK: {len(selected)} selected packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
