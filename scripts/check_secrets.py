#!/usr/bin/env python3
"""Reject likely credentials, private keys, and proxy subscription URLs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "build", "openwrt", "bin"}
SKIP_FILES = {SELF_PATH}
MAX_TEXT_SIZE = 2 * 1024 * 1024

CONTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("Bearer token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*")),
    (
        "credential assignment",
        re.compile(
            r"(?ix)\b(?:password|passwd|pwd|api[_-]?key|secret|"
            r"access[_-]?token|refresh[_-]?token|auth[_-]?token|private[_-]?key)\b"
            r"\s*[:=]\s*[\"']?"
            r"(?!(?:true|false|null|none|~|0|1|change[_-]?me|replace[_-]?me|"
            r"example|redacted|\$\{|<))"
            r"(?P<value>[^\s\"'#]{6,})"
        ),
    ),
    (
        "proxy subscription URL",
        re.compile(
            r"(?i)\b(?:ss|ssr|vmess|vless|trojan|hysteria2?|tuic|clash|mihomo)://[^\s\"']+"
        ),
    ),
    (
        "subscribe URL",
        re.compile(r"(?i)https?://[^\s\"']*(?:subscribe|subscription|sub\?|token=|key=)[^\s\"']*"),
    ),
]

SECRET_FILENAME_PATTERNS = [
    re.compile(r"(?i)^\.env(?:\..*)?$"),
    re.compile(r"(?i).*\.(?:pem|key|p12|pfx|token|sub)$"),
    re.compile(r"(?i)^(?:id_rsa|id_ed25519|secrets?\.ya?ml)$"),
]


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path in SKIP_FILES:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_SIZE:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:
            continue
        yield path, data.decode("utf-8", errors="replace")


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path, text in iter_text_files(root):
        relative = path.relative_to(root).as_posix()
        for pattern in SECRET_FILENAME_PATTERNS:
            if pattern.search(path.name):
                findings.append(f"{relative}: suspicious filename")
                break
        for label, pattern in CONTENT_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{relative}:{line}: {label}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()

    findings = scan(root)
    if findings:
        for finding in findings:
            print(f"ERROR: {finding}", file=sys.stderr)
        return 1
    print("secret scan OK: no likely credentials or subscription URLs found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
