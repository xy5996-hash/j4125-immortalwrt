#!/usr/bin/env python3
"""Boot the generated firmware in QEMU/OVMF and run basic in-guest checks."""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import TextIO

import pexpect

SHELL_PROMPT = r"root@[^#\r\n]*# "
MENU_PROMPT = r"Enter number[^\r\n]*:"
SMOKE_PROMPT = "__SMOKE__# "

COMMANDS = [
    "uname -m",
    "cat /etc/openwrt_release",
    "mount | grep ' / '",
    "ip -br link",
    "ls /sys/class/net",
    "dmesg | grep -Ei 'virtio|igc|squashfs|mounted root'",
    "test -c /dev/net/tun && echo TUN_OK",
    "test -x /etc/openclash/core/clash_meta && /etc/openclash/core/clash_meta -v",
    "apk list -I 2>/dev/null | grep -E 'luci-app-store|luci-app-openclash|mihomo-core'",
    "ps w | grep -E '[d]ropbear|[u]httpd|[d]nsmasq'",
    "echo SMOKE_COMMANDS_DONE",
]

REQUIRED_PATTERNS = {
    "x86_64": "x86_64",
    "ImmortalWrt release": "ImmortalWrt",
    "squashfs rootfs": "squashfs",
    "virtio network": "virtio",
    "TUN device": "TUN_OK",
    "mihomo core": "1.19.31",
    "iStore": "luci-app-store",
    "OpenClash": "luci-app-openclash",
    "mihomo package": "mihomo-core",
    "dropbear": "dropbear",
    "uhttpd": "uhttpd",
    "dnsmasq": "dnsmasq",
    "command completion": "SMOKE_COMMANDS_DONE",
}


def decompress_image(image: Path, raw_image: Path) -> None:
    with gzip.open(image, "rb") as source, raw_image.open("wb") as destination:
        shutil.copyfileobj(source, destination, length=1024 * 1024)


def expect_choice(child: pexpect.spawn, patterns: list[str], timeout: int) -> int:
    """Return a real pattern index, or fail clearly on EOF/timeout."""
    result = child.expect([*patterns, pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if result == len(patterns):
        raise RuntimeError("QEMU exited unexpectedly")
    if result == len(patterns) + 1:
        raise RuntimeError("timed out waiting for guest output")
    return result


def wait_for_shell(child: pexpect.spawn, timeout: int) -> None:
    """Wait for the root shell, dismissing the optional first-login shortcut menu."""
    while True:
        result = expect_choice(child, [SHELL_PROMPT, MENU_PROMPT], timeout)
        if result == 0:
            return
        # /etc/profile runs the shortcut menu before returning to the shell.
        # Ctrl-C aborts that sourced menu without logging the session out.
        child.sendcontrol("c")
        time.sleep(0.5)


def run_qemu(
    qemu: str,
    ovmf_code: Path,
    ovmf_vars_template: Path,
    image: Path,
    timeout: int,
    log_path: Path | None = None,
) -> tuple[int, str]:
    log_stream: TextIO | None = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_stream = log_path.open("w", encoding="utf-8", buffering=1)

    with tempfile.TemporaryDirectory(prefix="qemu-smoke-") as temp:
        temp_dir = Path(temp)
        raw_image = temp_dir / "firmware.img"
        ovmf_vars = temp_dir / "OVMF_VARS.fd"
        decompress_image(image, raw_image)
        shutil.copyfile(ovmf_vars_template, ovmf_vars)

        command = [
            qemu,
            "-machine",
            "q35,accel=tcg",
            "-cpu",
            "max",
            "-m",
            "2048",
            "-smp",
            "4",
            "-display",
            "none",
            "-monitor",
            "none",
            "-no-reboot",
            "-serial",
            "stdio",
            "-drive",
            f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
            "-drive",
            f"if=pflash,format=raw,file={ovmf_vars}",
            "-drive",
            f"file={raw_image},format=raw,if=ide,index=0,media=disk",
            "-netdev",
            "user,id=net0",
            "-device",
            "virtio-net-pci,netdev=net0,romfile=",
        ]

        child = pexpect.spawn(
            command[0],
            command[1:],
            encoding="utf-8",
            codec_errors="replace",
            timeout=timeout,
        )
        if log_stream:
            child.logfile_read = log_stream
        transcript = ""
        try:
            result = expect_choice(child, [r"login:", SHELL_PROMPT, MENU_PROMPT], timeout=600)
            if result == 0:
                child.sendline("root")
                auth = expect_choice(child, [r"Password:", SHELL_PROMPT, MENU_PROMPT], timeout=180)
                if auth == 0:
                    child.sendline("")
            wait_for_shell(child, timeout=180)

            child.sendline(f"export PS1='{SMOKE_PROMPT}'")
            child.expect_exact(SMOKE_PROMPT, timeout=30)

            for command in COMMANDS:
                transcript += f"\n$ {command}\n"
                child.sendline(command)
                child.expect_exact(SMOKE_PROMPT, timeout=120)
                transcript += child.before

            child.sendline("poweroff -f")
            poweroff = child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=120)
            transcript += "\n" + child.before
            if poweroff == 1:
                raise RuntimeError("timed out waiting for QEMU to power off")
            return child.exitstatus or 0, transcript
        finally:
            transcript += child.before if child.before else ""
            child.close(force=True)
            if log_stream:
                log_stream.flush()
                log_stream.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--ovmf-code", type=Path, default=Path("/usr/share/OVMF/OVMF_CODE_4M.fd"))
    parser.add_argument("--ovmf-vars", type=Path, default=Path("/usr/share/OVMF/OVMF_VARS_4M.fd"))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    if not args.image.is_file():
        print(f"qemu smoke error: image not found: {args.image}", file=sys.stderr)
        return 1
    if not args.ovmf_code.is_file() or not args.ovmf_vars.is_file():
        print("qemu smoke error: OVMF firmware files not found", file=sys.stderr)
        return 1

    try:
        return_code, transcript = run_qemu(
            args.qemu,
            args.ovmf_code,
            args.ovmf_vars,
            args.image,
            args.timeout,
            args.log,
        )
    except Exception as exc:  # noqa: BLE001 - command-line validation gate
        print(f"qemu smoke failed: {exc}", file=sys.stderr)
        if args.log and args.log.is_file():
            lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
            print("--- QEMU serial tail ---", file=sys.stderr)
            print("\n".join(lines[-120:]), file=sys.stderr)
        return 1

    print(transcript)
    panic_markers = ("Kernel panic", "VFS: Cannot open root device", "Attempted to kill init")
    for marker in panic_markers:
        if marker.lower() in transcript.lower():
            print(f"qemu smoke failed: detected {marker}", file=sys.stderr)
            return 1

    missing = [name for name, pattern in REQUIRED_PATTERNS.items() if pattern.lower() not in transcript.lower()]
    if missing:
        print(f"qemu smoke failed: missing expected markers: {missing}", file=sys.stderr)
        return 1

    if return_code not in (0, None):
        print(f"qemu smoke failed: QEMU exit status {return_code}", file=sys.stderr)
        return 1

    print("qemu smoke OK: UEFI, x86_64, kernel, squashfs rootfs, virtio network, TUN, LuCI/SSH, mihomo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())