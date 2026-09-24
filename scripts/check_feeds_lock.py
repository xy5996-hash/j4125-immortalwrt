#!/usr/bin/env python3
"""Verify that feeds.conf.lock is fully pinned and matches the YAML profile."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_YAML = REPO_ROOT / "config" / "j4125-router.yaml"
DEFAULT_LOCK = REPO_ROOT / "feeds" / "feeds.conf.lock"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
LINE_RE = re.compile(r"^src-git\s+([A-Za-z0-9_.-]+)\s+(\S+?)\^([0-9a-f]{40})$")


class LockError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LockError(f"not a YAML mapping: {path}")
    return value


def expected_feeds(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for item in data.get("feeds", []):
        if not isinstance(item, dict):
            raise LockError("each feeds entry must be a mapping")
        name = str(item.get("name", ""))
        repository = str(item.get("repository", ""))
        commit = str(item.get("commit", ""))
        if not name or not repository or not COMMIT_RE.fullmatch(commit):
            raise LockError(f"invalid feed lock source in YAML: {item}")
        result.append((name, repository, commit))
    return result


def parse_lock(path: Path) -> list[tuple[str, str, str, str]]:
    result: list[tuple[str, str, str, str]] = []
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.fullmatch(line)
        if not match:
            raise LockError(
                f"{path}:{number}: feed must be exactly "
                "src-git <name> <repository>^<40-char-commit>"
            )
        name, repository, commit = match.groups()
        result.append((name, repository, commit, line))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()

    try:
        data = load_yaml(args.config)
        expected = expected_feeds(data)
        actual = parse_lock(args.lock)
    except (OSError, LockError, yaml.YAMLError) as exc:
        print(f"feeds lock error: {exc}")
        return 1

    actual_map = {name: (repository, commit) for name, repository, commit, _ in actual}
    expected_map = {name: (repository, commit) for name, repository, commit in expected}

    errors: list[str] = []
    missing = sorted(set(expected_map) - set(actual_map))
    extra = sorted(set(actual_map) - set(expected_map))
    if missing:
        errors.append(f"missing feeds: {missing}")
    if extra:
        errors.append(f"unexpected feeds: {extra}")
    for name in sorted(set(expected_map) & set(actual_map)):
        if expected_map[name] != actual_map[name]:
            errors.append(
                f"{name}: expected {expected_map[name][0]}^{expected_map[name][1]}, "
                f"got {actual_map[name][0]}^{actual_map[name][1]}"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"feeds lock OK: {len(actual)} feeds pinned to full commits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
