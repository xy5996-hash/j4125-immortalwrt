#!/usr/bin/env python3
"""Verify pinned component versions and local overlay file hashes."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    args = parser.parse_args()

    try:
        data = load_yaml(args.config)
    except ConfigReadError as exc:
        print(f"component check error: {exc}")
        return 1

    errors: list[str] = []
    base = data.get("base")
    components = data.get("components")
    feeds = data.get("feeds")
    if not isinstance(base, dict) or not isinstance(components, dict) or not isinstance(feeds, list):
        print("component check error: base, components, and feeds are required")
        return 1

    if not COMMIT_RE.fullmatch(str(base.get("commit", ""))):
        errors.append("base.commit is not a full commit hash")

    feed_commits: dict[str, str] = {}
    for feed in feeds:
        if not isinstance(feed, dict):
            errors.append(f"invalid feed entry: {feed!r}")
            continue
        name = str(feed.get("name", ""))
        commit = str(feed.get("commit", ""))
        if not name or not COMMIT_RE.fullmatch(commit):
            errors.append(f"feed is not pinned correctly: {feed!r}")
            continue
        feed_commits[name] = commit

    for component, feed_name in (
        ("istore", "istore"),
        ("openclash", "openclash"),
        ("setup_wizard", "netwizard"),
    ):
        value = components.get(component)
        if not isinstance(value, dict):
            errors.append(f"components.{component} is missing")
            continue
        commit = str(value.get("commit", ""))
        if not COMMIT_RE.fullmatch(commit):
            errors.append(f"components.{component}.commit is invalid")
        if feed_commits.get(feed_name) != commit:
            errors.append(
                f"components.{component}.commit does not match feed {feed_name}"
            )

    mihomo = components.get("mihomo")
    if not isinstance(mihomo, dict):
        errors.append("components.mihomo is missing")
    else:
        if not str(mihomo.get("ref", "")).startswith("v"):
            errors.append("components.mihomo.ref should be an explicit version tag")
        if not SHA256_RE.fullmatch(str(mihomo.get("sha256", ""))):
            errors.append("components.mihomo.sha256 is invalid")

    shortcut = components.get("shortcut_menu")
    if not isinstance(shortcut, dict):
        errors.append("components.shortcut_menu is missing")
    else:
        files = shortcut.get("files")
        if not isinstance(files, list) or not files:
            errors.append("components.shortcut_menu.files must not be empty")
        else:
            for item in files:
                if not isinstance(item, dict):
                    errors.append(f"invalid shortcut menu file entry: {item!r}")
                    continue
                relative = str(item.get("path", ""))
                expected = str(item.get("sha256", ""))
                if not relative or not SHA256_RE.fullmatch(expected):
                    errors.append(f"invalid shortcut menu file metadata: {item!r}")
                    continue
                path = (REPO_ROOT / relative).resolve()
                try:
                    path.relative_to(REPO_ROOT)
                except ValueError:
                    errors.append(f"shortcut menu path escapes repository: {relative}")
                    continue
                if not path.is_file():
                    errors.append(f"shortcut menu file is missing: {relative}")
                    continue
                actual = file_sha256(path)
                if actual != expected:
                    errors.append(
                        f"shortcut menu hash mismatch for {relative}: expected {expected}, got {actual}"
                    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("component check OK: ImmortalWrt, feeds, iStore, OpenClash, mihomo, netwizard, shortcut menu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
