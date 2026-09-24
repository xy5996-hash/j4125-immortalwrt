#!/usr/bin/env python3
"""Validate the generated x86_64 combined EFI image and package manifest."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from config_lib import DEFAULT_YAML
from check_manifest import check_packages, load_patterns, parse_manifest, required_packages


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=check)


def gzip_integrity(path: Path) -> None:
    with gzip.open(path, "rb") as handle:
        while handle.read(1024 * 1024):
            pass


def decompress_image(image: Path, raw_image: Path) -> None:
    with gzip.open(image, "rb") as source, raw_image.open("wb") as destination:
        shutil.copyfileobj(source, destination, length=1024 * 1024)


def loop_partitions(raw_image: Path) -> tuple[str, dict[str, str]]:
    loop = run(["sudo", "losetup", "--find", "--show", "--partscan", str(raw_image)]).stdout.strip()
    if not loop:
        raise RuntimeError("losetup did not return a loop device")
    try:
        output = run(["lsblk", "-ln", "-o", "NAME,FSTYPE", loop]).stdout
        partitions: dict[str, str] = {}
        for line in output.splitlines():
            columns = line.split()
            if len(columns) >= 2 and columns[0].startswith(Path(loop).name):
                partitions[f"/dev/{columns[0]}"] = columns[1]
        return loop, partitions
    except Exception:
        run(["sudo", "losetup", "-d", loop], check=False)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--build-info", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    temp_dir_obj = tempfile.TemporaryDirectory(prefix="image-check-")
    temp_dir = Path(temp_dir_obj.name)
    raw_image = temp_dir / "firmware.img"
    mount_dir = temp_dir / "boot"
    loop_device: str | None = None

    try:
        if not args.image.is_file():
            raise RuntimeError(f"image not found: {args.image}")
        if args.image.stat().st_size < 10 * 1024 * 1024:
            raise RuntimeError("compressed image is unexpectedly small")

        gzip_integrity(args.image)
        decompress_image(args.image, raw_image)
        if raw_image.stat().st_size < 32 * 1024 * 1024:
            raise RuntimeError("decompressed image is unexpectedly small")

        file_output = run(["file", "-b", str(raw_image)]).stdout.strip()
        if "boot sector" not in file_output.lower() and "partition" not in file_output.lower():
            errors.append(f"unexpected image file type: {file_output}")

        sgdisk = run(["sgdisk", "--verify", str(raw_image)], check=False)
        if sgdisk.returncode != 0:
            errors.append(f"sgdisk verification failed: {sgdisk.stdout}{sgdisk.stderr}")
        partition_table = run(["sgdisk", "-p", str(raw_image)], check=False).stdout
        if "EFI System Partition" not in partition_table and "EF00" not in partition_table:
            errors.append("EFI System Partition not found in GPT")
        if "Linux filesystem" not in partition_table and "8300" not in partition_table:
            errors.append("Linux root filesystem partition not found in GPT")

        loop_device, partitions = loop_partitions(raw_image)
        squashfs_device = next((device for device, fs in partitions.items() if fs == "squashfs"), None)
        if squashfs_device is None:
            errors.append(f"squashfs rootfs partition not found: {partitions}")
        else:
            squash = run(["unsquashfs", "-s", squashfs_device], check=False)
            if squash.returncode != 0:
                errors.append(f"squashfs superblock check failed: {squash.stdout}{squash.stderr}")

        boot_device = next((device for device, fs in partitions.items() if fs in {"vfat", "fat"}), None)
        if boot_device is None:
            errors.append(f"EFI/FAT boot partition not found: {partitions}")
        else:
            mount_dir.mkdir()
            mounted = run(["sudo", "mount", "-o", "ro", boot_device, str(mount_dir)], check=False)
            if mounted.returncode != 0:
                errors.append(f"boot partition mount failed: {mounted.stderr}")
            else:
                try:
                    if not any((mount_dir / path).is_file() for path in ("boot/vmlinuz", "vmlinuz")):
                        errors.append("kernel image not found on boot partition")
                finally:
                    run(["sudo", "umount", str(mount_dir)], check=False)

        manifest_packages = parse_manifest(args.manifest.read_text(encoding="utf-8"))
        forbidden = load_patterns(args.profile)
        errors.extend(check_packages(manifest_packages, forbidden))
        missing = sorted(set(required_packages(args.profile)) - set(manifest_packages))
        errors.extend(f"required package missing from manifest: {package}" for package in missing)

        if args.build_info:
            info = json.loads(args.build_info.read_text(encoding="utf-8"))
            if info.get("image_sha256") is None or info.get("manifest_sha256") is None:
                errors.append("build-info.json does not include image/manifest hashes")

        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1

        print(
            "image sanity OK: gzip, GPT, EFI, kernel, squashfs rootfs, "
            "required packages, forbidden packages, build-info"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - command-line validation gate
        print(f"image sanity failed: {exc}")
        return 1
    finally:
        if loop_device:
            run(["sudo", "losetup", "-d", loop_device], check=False)
        temp_dir_obj.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())