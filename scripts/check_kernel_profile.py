#!/usr/bin/env python3
"""Verify the pinned x86 target kernel fragments contain the required hardware support."""

from __future__ import annotations

import argparse
from pathlib import Path

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml
from profile_rules import expand_kernel_expectations


def parse_kconfig(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("# CONFIG_") and line.endswith(" is not set"):
            symbol = line[len("# ") : -len(" is not set")]
            values[symbol] = "n"
        elif line.startswith("CONFIG_") and "=" in line:
            symbol, value = line.split("=", 1)
            values[symbol] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    args = parser.parse_args()

    try:
        data = load_yaml(args.config)
        kernel_series = str(data["base"]["kernel_series"])
        expected = expand_kernel_expectations(data)
    except (ConfigReadError, KeyError, TypeError) as exc:
        print(f"kernel profile error: {exc}")
        return 1

    fragments = [
        args.source_dir / "target" / "linux" / "generic" / f"config-{kernel_series}",
        args.source_dir / "target" / "linux" / "x86" / f"config-{kernel_series}",
        args.source_dir / "target" / "linux" / "x86" / "64" / f"config-{kernel_series}",
    ]
    merged: dict[str, str] = {}
    found: list[str] = []
    for fragment in fragments:
        if fragment.is_file():
            found.append(str(fragment))
            merged.update(parse_kconfig(fragment))

    errors: list[str] = []
    for symbol, expected_value in expected.items():
        actual = merged.get(symbol)
        if actual != expected_value:
            errors.append(
                f"kernel profile mismatch: {symbol} expected {expected_value}, got {actual!r}"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"kernel profile OK: {len(expected)} symbols across {len(found)} target fragments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())