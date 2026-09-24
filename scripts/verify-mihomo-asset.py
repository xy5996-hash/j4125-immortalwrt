#!/usr/bin/env python3
"""Download and verify the pinned mihomo release asset."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        data = load_yaml(args.config)
        mihomo = data["components"]["mihomo"]
        url = str(mihomo["source_url"])
        expected = str(mihomo["sha256"])
    except (ConfigReadError, KeyError, TypeError) as exc:
        print(f"mihomo asset verification error: {exc}")
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="mihomo-verify-") as temp_dir:
            archive = Path(temp_dir) / "mihomo.gz"
            request = urllib.request.Request(url, headers={"User-Agent": "j4125-immortalwrt-validator/1"})
            with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)

            actual, size = sha256_file(archive)
            if actual != expected:
                raise RuntimeError(f"SHA256 mismatch: expected {expected}, got {actual}")

            with gzip.open(archive, "rb") as binary:
                magic = binary.read(4)
            if magic != b"\x7fELF":
                raise RuntimeError(f"decompressed asset is not an ELF binary: {magic!r}")

            result = {
                "asset": mihomo["asset"],
                "url": url,
                "sha256": actual,
                "archive_size": size,
                "elf": True,
            }
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001 - this is a command-line validation gate
        print(f"mihomo asset verification failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())