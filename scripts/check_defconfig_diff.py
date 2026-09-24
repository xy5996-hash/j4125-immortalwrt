#!/usr/bin/env python3
"""Report and validate the before/after make defconfig diff."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml, read_config
from profile_rules import expand_feature_config, expand_feature_packages, feature_map, unique


def selected_lines(path: Path) -> set[str]:
    return {
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("CONFIG_") or line.startswith("# CONFIG_")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--large-diff-threshold", type=int, default=250)
    args = parser.parse_args()

    try:
        data = load_yaml(args.yaml)
        feature_map(data)
        before_lines = selected_lines(args.before)
        after_lines = selected_lines(args.after)
        selected_after, _ = read_config(args.after)
    except (OSError, ConfigReadError) as exc:
        print(f"defconfig diff error: {exc}")
        return 1

    diff_lines = list(
        difflib.unified_diff(
            sorted(before_lines),
            sorted(after_lines),
            fromfile=str(args.before),
            tofile=str(args.after),
            lineterm="",
        )
    )

    added = sorted(after_lines - before_lines)
    removed = sorted(before_lines - after_lines)
    print(
        f"defconfig diff: added={len(added)} removed={len(removed)} "
        f"unified_lines={len(diff_lines)}"
    )

    for line in added[:40]:
        print(f"+ {line}")
    if len(added) > 40:
        print(f"+ ... {len(added) - 40} more")
    for line in removed[:40]:
        print(f"- {line}")
    if len(removed) > 40:
        print(f"- ... {len(removed) - 40} more")

    errors: list[str] = []
    for symbol, value in expand_feature_config(data).items():
        expected = f"# {symbol} is not set" if value == "n" else f"{symbol}={value}"
        if expected not in after_lines:
            errors.append(f"required feature config missing after defconfig: {expected}")

    required_packages = unique(expand_feature_packages(data))
    missing = sorted(set(required_packages) - selected_after)
    for package in missing:
        errors.append(f"required package missing after defconfig: CONFIG_PACKAGE_{package}=y")

    changed_count = len(added) + len(removed)
    if changed_count > args.large_diff_threshold:
        print(
            f"NOTICE: defconfig changed {changed_count} lines, above reporting "
            f"threshold {args.large_diff_threshold}; review config.diff before build."
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("defconfig diff validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())