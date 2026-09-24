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
from check_manifest import check_packages, load_patterns, missing_required_packages, parse_manifest, required_packages

EFI_TYPE_GUIDS = {
    "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
    "ef",
    "0xef",
}


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=check)


def gzip_integrity(path: Path) -> None:
    with gzip.open(path, "rb") as handle:
        while handle.read(1024 * 1024):
            pass


def decompress_image(image: Path, raw_image: Path) -> None:
    with gzip.open(image, "rb") as source, raw_image.open("wb") as destination:
        shutil.copyfileobj(source, destination, length=1024 * 1024)


def mount_partition(device: str, mount_dir: Path) -> None:
    mount_dir.mkdir(exist_ok=True)
    run(["sudo", "mount", "-o", "ro", device, str(mount_dir)])


def inspect_partitions(raw_image: Path, boot_mount: Path) -> tuple[bool, bool, bool]:
    sfdisk = json.loads(run(["sfdisk", "--json", str(raw_image)]).stdout)
    table = sfdisk.get("partitiontable", {})
    sector_size = int(table.get("sector-size", 512))
    partitions = table.get("partitions") or []
    if not partitions:
        raise RuntimeError("sfdisk reported no partitions")

    efi_found = False
    kernel_found = False
    squashfs_found = False
    loops: list[str] = []

    try:
        for partition in partitions:
            partition_type = str(partition.get("type", "")).lower()
            if partition_type in EFI_TYPE_GUIDS:
                efi_found = True

            start = int(partition["start"]) * sector_size
            size = int(partition["size"]) * sector_size
            loop = run(
                [
                    "sudo",
                    "losetup",
                    "--find",
                    "--show",
                    "--offset",
                    str(start),
                    "--sizelimit",
                    str(size),
                    str(raw_image),
                ]
            ).stdout.strip()
            if not loop:
                continue
            loops.append(loop)

            fstype = run(["blkid", "-o", "value", "-s", "TYPE", loop], check=False).stdout.strip()
            squash_check = run(["unsquashfs", "-s", loop], check=False)
            file_type = run(["file", "-b", "-s", loop], check=False).stdout.strip()
            print(
                f"partition start={start} size={size} type={partition_type} " 
                f"loop={loop} fstype={fstype!r} unsquashfs={squash_check.returncode} file={file_type!r}",
                flush=True,
            )
            if fstype == "squashfs" or squash_check.returncode == 0:
                squashfs_found = True

            if fstype in {"vfat", "fat", "msdos"}:
                try:
                    mount_partition(loop, boot_mount)
                    kernel_found = kernel_found or any(
                        path.is_file() for path in boot_mount.rglob("vmlinuz")
                    )
                    efi_found = efi_found or any(
                        path.name.lower() == "bootx64.efi" for path in boot_mount.rglob("*")
                    )
                finally:
                    run(["sudo", "umount", str(boot_mount)], check=False)
    finally:
        for loop in reversed(loops):
            run(["sudo", "losetup", "-d", loop], check=False)

    return efi_found, kernel_found, squashfs_found


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
    boot_mount = temp_dir / "boot"

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

        efi_found, kernel_found, squashfs_found = inspect_partitions(raw_image, boot_mount)
        if not efi_found:
            errors.append("EFI System Partition not found in image partition table")
        if not kernel_found:
            errors.append("kernel image not found on EFI/FAT boot partition")
        if not squashfs_found:
            errors.append("squashfs rootfs partition not found")

        manifest_packages = parse_manifest(args.manifest.read_text(encoding="utf-8"))
        forbidden = load_patterns(args.profile)
        errors.extend(check_packages(manifest_packages, forbidden))
        missing = missing_required_packages(manifest_packages, required_packages(args.profile))
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
            "image sanity OK: gzip, EFI, kernel, squashfs rootfs, "
            "required packages, forbidden packages, build-info"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - command-line validation gate
        print(f"image sanity failed: {exc}")
        return 1
    finally:
        temp_dir_obj.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())