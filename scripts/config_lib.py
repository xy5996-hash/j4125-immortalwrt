#!/usr/bin/env python3
"""Shared helpers for reading YAML profiles and generated .config files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_YAML = REPO_ROOT / "config" / "j4125-router.yaml"
DEFAULT_CONFIG = REPO_ROOT / "config" / "generated" / "immortalwrt-25.12.2-x86_64.config"
PACKAGE_SELECTED_RE = re.compile(r"^CONFIG_PACKAGE_([A-Za-z0-9][A-Za-z0-9+_.-]*)=y$")
CONFIG_VALUE_RE = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")


class ConfigReadError(RuntimeError):
    pass


def load_yaml(path: Path = DEFAULT_YAML) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigReadError(f"cannot read YAML profile {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigReadError(f"YAML profile is not a mapping: {path}")
    return value


def read_config(path: Path) -> tuple[set[str], dict[str, str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigReadError(f"cannot read generated config {path}: {exc}") from exc

    selected: set[str] = set()
    values: dict[str, str] = {}
    for line in lines:
        selected_match = PACKAGE_SELECTED_RE.fullmatch(line)
        if selected_match:
            selected.add(selected_match.group(1))
        value_match = CONFIG_VALUE_RE.fullmatch(line)
        if value_match:
            values[value_match.group(1)] = value_match.group(2)
    return selected, values


def yaml_list_of_strings(data: dict[str, Any], *keys: str) -> list[str]:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ConfigReadError(f"missing YAML field: {'.'.join(keys)}")
        value = value[key]
    if not isinstance(value, list):
        raise ConfigReadError(f"YAML field must be a list: {'.'.join(keys)}")
    return [str(item) for item in value]


def matches_any(name: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, name):
            return pattern
    return None
