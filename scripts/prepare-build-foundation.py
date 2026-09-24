#!/usr/bin/env python3
"""Prepare a pinned ImmortalWrt tree and verify the rendered configuration."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from config_lib import DEFAULT_YAML, ConfigReadError, load_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_logged(command: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        log.write(("\n$ " + " ".join(command) + "\n").encode("utf-8"))
        log.flush()
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if completed.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n" + "\n".join(tail)
        )


def prepare_source(base: dict, source_dir: Path, logs_dir: Path) -> None:
    repository = str(base["repository"])
    commit = str(base["commit"])
    if not (source_dir / ".git").is_dir():
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        run_logged(["git", "init", str(source_dir)], REPO_ROOT, logs_dir / "source.log")

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=source_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if remote.returncode == 0:
        run_logged(["git", "remote", "set-url", "origin", repository], source_dir, logs_dir / "source.log")
    else:
        run_logged(["git", "remote", "add", "origin", repository], source_dir, logs_dir / "source.log")

    run_logged(["git", "fetch", "--depth", "1", "origin", commit], source_dir, logs_dir / "source.log")
    run_logged(["git", "checkout", "--detach", commit], source_dir, logs_dir / "source.log")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_dir, text=True).strip()
    if actual != commit:
        raise RuntimeError(f"source commit mismatch: expected {commit}, got {actual}")


def copy_project_inputs(source_dir: Path) -> None:
    overlay_source = REPO_ROOT / "files"
    overlay_target = source_dir / "files"
    if overlay_target.exists():
        shutil.rmtree(overlay_target)
    shutil.copytree(overlay_source, overlay_target)

    package_source = REPO_ROOT / "package" / "mihomo-core"
    package_target = source_dir / "package" / "mihomo-core"
    if package_target.exists():
        shutil.rmtree(package_target)
    shutil.copytree(package_source, package_target)

    shutil.copyfile(REPO_ROOT / "feeds" / "feeds.conf.lock", source_dir / "feeds.conf")


def run_validation(config_path: Path, output_dir: Path) -> list[dict]:
    checks = [
        ("hardware", ["check_hardware_profile.py"]),
        ("forbidden-config", ["check_forbidden_packages.py"]),
        ("components", ["check_components.py"]),
    ]
    results: list[dict] = []
    for name, script_args in checks:
        command = [sys.executable, str(REPO_ROOT / "scripts" / script_args[0]), "--config", str(config_path)] if script_args[0] in {"check_hardware_profile.py", "check_forbidden_packages.py"} else [sys.executable, str(REPO_ROOT / "scripts" / script_args[0])]
        run_logged(command, REPO_ROOT, output_dir / f"check-{name}.log")
        results.append({"name": name, "command": command, "status": "ok"})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()

    try:
        data = load_yaml(args.config)
        base = data["base"]
    except (ConfigReadError, KeyError, TypeError) as exc:
        print(f"foundation error: {exc}")
        return 1

    default_root = Path(os.environ.get("RUNNER_TEMP", tempfile_root()))
    root = (args.work_dir or (default_root / "j4125-foundation")).resolve()
    source_dir = (args.source_dir or (root / "immortalwrt")).resolve()
    output_dir = root / "artifacts"
    logs_dir = output_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    try:
        prepare_source(base, source_dir, logs_dir)
        copy_project_inputs(source_dir)

        run_logged(["./scripts/feeds", "update", "-a"], source_dir, logs_dir / "feeds-update.log")
        run_logged(["./scripts/feeds", "install", "-a"], source_dir, logs_dir / "feeds-install.log")

        before = output_dir / "config.before-defconfig"
        run_logged(
            [sys.executable, str(REPO_ROOT / "scripts" / "render-config.py"), "--config", str(args.config.resolve()), "--output", str(before)],
            REPO_ROOT,
            logs_dir / "render-config.log",
        )
        shutil.copyfile(before, source_dir / ".config")

        run_logged(["make", "defconfig"], source_dir, logs_dir / "defconfig.log")

        after = output_dir / "config.after-defconfig"
        shutil.copyfile(source_dir / ".config", after)

        diff_lines = list(
            difflib.unified_diff(
                before.read_text(encoding="utf-8").splitlines(),
                after.read_text(encoding="utf-8").splitlines(),
                fromfile=str(before),
                tofile=str(after),
                lineterm="",
            )
        )
        (output_dir / "config.diff").write_text("\n".join(diff_lines) + ("\n" if diff_lines else ""), encoding="utf-8")

        results = run_validation(after, output_dir)
        run_logged(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_defconfig_diff.py"),
                "--before",
                str(before),
                "--after",
                str(after),
                "--yaml",
                str(args.config.resolve()),
            ],
            REPO_ROOT,
            logs_dir / "defconfig-diff.log",
        )
        results.append(
            {
                "name": "defconfig-diff",
                "returncode": 0,
                "changed_lines": len(diff_lines),
                "status": "reported",
            }
        )

        summary = {
            "immortalwrt_ref": base["ref"],
            "immortalwrt_commit": base["commit"],
            "source_dir": str(source_dir),
            "config_before_sha256": sha256_file(before),
            "config_after_sha256": sha256_file(after),
            "defconfig_diff_lines": len(diff_lines),
            "validation": results,
        }
        (output_dir / "foundation-summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - command-line build gate
        print(f"foundation failed: {exc}", file=sys.stderr)
        return 1


def tempfile_root() -> str:
    import tempfile

    return tempfile.gettempdir()


if __name__ == "__main__":
    raise SystemExit(main())