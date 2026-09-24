#!/usr/bin/env python3
"""Generate build provenance metadata without secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def feed_commit(data: dict[str, Any], name: str) -> str | None:
    for feed in data.get("feeds", []):
        if isinstance(feed, dict) and feed.get("name") == name:
            return str(feed.get("commit"))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--final-config", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        data = load_yaml(args.config)
    except ConfigReadError as exc:
        print(f"build-info error: {exc}")
        return 1

    base = data["base"]
    target = data["target"]
    image = data["image"]
    components = data["components"]
    mihomo = components["mihomo"]

    info = {
        "project": "j4125-immortalwrt",
        "device": data["hardware"]["board"],
        "target": f"{target['target']}/{target['subtarget']}",
        "image": f"{image['filesystem']}-{image['format']}",
        "immortalwrt_ref": base["ref"],
        "immortalwrt_commit": base["commit"],
        "packages_commit": feed_commit(data, "packages"),
        "luci_commit": feed_commit(data, "luci"),
        "routing_commit": feed_commit(data, "routing"),
        "istore_commit": components["istore"]["commit"],
        "openclash_commit": components["openclash"]["commit"],
        "mihomo_version": mihomo["ref"],
        "mihomo_sha256": mihomo["sha256"],
        "config_sha256": sha256_file(args.final_config),
        "source_commit": args.source_commit,
        "image_name": args.image.name,
        "image_sha256": sha256_file(args.image),
        "manifest_name": args.manifest.name,
        "manifest_sha256": sha256_file(args.manifest),
        "build_time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())