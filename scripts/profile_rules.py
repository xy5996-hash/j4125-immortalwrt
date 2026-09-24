#!/usr/bin/env python3
"""High-level feature rules for the fixed J4125 router profile."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from config_lib import ConfigReadError

REQUIRED_TRUE_FEATURES = {
    "ipv4",
    "ipv6",
    "vlan",
    "firewall4",
    "dnsmasq_full",
    "uefi",
    "i226",
    "intel_ahci",
    "j4125_gemini_lake",
    "intel_graphics",
    "intel_microcode",
    "usb_xhci",
    "broad_compat",
    "istore",
    "openclash",
    "setup_wizard",
    "shortcut_menu",
}

BASE_PACKAGES = [
    "base-files",
    "procd-ujail",
    "uci",
    "ubus",
    "netifd",
    "fstools",
    "block-mount",
    "dropbear",
    "logd",
    "ca-bundle",
    "libustream-openssl",
    "curl",
]

FEATURE_PACKAGES: dict[str, list[str]] = {
    "ipv4": [
        "dnsmasq-full",
        "firewall4",
        "nftables-json",
        "kmod-nft-offload",
        "ppp",
        "ppp-mod-pppoe",
        "luci-app-firewall",
        "luci-app-package-manager",
        "luci-proto-ppp",
    ],
    "ipv6": ["odhcp6c", "odhcpd-ipv6only", "luci-proto-ipv6"],
    "vlan": [],
    "firewall4": ["firewall4", "nftables-json", "kmod-nft-offload"],
    "dnsmasq_full": ["dnsmasq-full"],
    "i226": ["kmod-igc"],
    "intel_ahci": [
        "kmod-fs-vfat",
        "kmod-fs-f2fs",
        "mkf2fs",
        "kmod-nls-cp437",
        "kmod-nls-iso8859-1",
        "kmod-nls-utf8",
    ],
    "j4125_gemini_lake": [
        "kmod-i2c-i801",
        "kmod-hwmon-coretemp",
        "kmod-intel-lpss",
        "kmod-intel-lpss-acpi",
        "kmod-intel-lpss-pci",
        "kmod-itco-wdt",
        "kmod-button-hotplug",
    ],
    "intel_graphics": ["kmod-drm-i915", "i915-firmware-dmc"],
    # The official x86 target does not expose AUDIO_SUPPORT HDA kmods.
    "intel_hda": [],
    "intel_microcode": ["intel-microcode"],
    "usb_xhci": ["kmod-usb-hid"],
    "broad_compat": [
        "kmod-e1000",
        "kmod-e1000e",
        "kmod-igb",
        "kmod-igbvf",
        "kmod-r8125",
        "kmod-r8126",
        "kmod-r8168",
        "kmod-r8169",
        "kmod-vmxnet3",
        "kmod-nvme",
        "kmod-usb-storage",
        "kmod-usb-storage-uas",
        "kmod-usb-net",
        "kmod-usb-net-asix",
        "kmod-usb-net-asix-ax88179",
        "kmod-usb-net-rtl8150",
        "kmod-usb-net-rtl8152-vendor",
        "kmod-usb-net-cdc-ether",
        "kmod-usb-net-rndis",
        "kmod-usb-serial",
        "kmod-usb-serial-ch341",
        "kmod-usb-serial-cp210x",
        "kmod-usb-serial-ftdi",
        "kmod-usb-serial-pl2303",
        "kmod-hwmon-it87",
        "kmod-hwmon-nct6775",
    ],
    "diagnostic_tools": ["ethtool", "pciutils"],
    "istore": [
        "luci-app-store",
        "luci-lib-taskd",
        "taskd",
        "luci-lib-xterm",
        "tar",
        "bzip2",
        "libacl",
        "libattr",
        "libzstd",
        "libuci-lua",
        "mount-utils",
    ],
    "openclash": [
        "luci-app-openclash",
        "mihomo-core",
        "luci-compat",
        "bash",
        "ip-full",
        "ruby",
        "ruby-yaml",
        "kmod-tun",
        "kmod-inet-diag",
        "kmod-nft-tproxy",
        "unzip",
    ],
    "setup_wizard": ["luci-app-netwizard", "luci-i18n-netwizard-zh-cn", "luci-compat"],
    "shortcut_menu": ["bash"],
}

FEATURE_CONFIG: dict[str, dict[str, str]] = {
    "istore": {
        "CONFIG_PACKAGE_TAR_XZ": "n",
    },
}

# These symbols live in target kernel config fragments, not in .config.
BASE_KERNEL_EXPECTATIONS: dict[str, str] = {
    "CONFIG_PCI": "y",
    "CONFIG_PCI_MSI": "y",
    "CONFIG_BLK_DEV_SD": "y",
    "CONFIG_BLK_DEV_LOOP": "y",
    "CONFIG_ATA": "y",
    "CONFIG_ATA_GENERIC": "y",
    "CONFIG_ATA_PIIX": "y",
    "CONFIG_EXT4_FS": "y",
    "CONFIG_F2FS_FS": "y",
    "CONFIG_GPIO_CDEV": "y",
    "CONFIG_I2C": "y",
    "CONFIG_MICROCODE": "y",
    "CONFIG_SQUASHFS": "y",
    "CONFIG_OVERLAY_FS": "y",
    "CONFIG_EFI_PARTITION": "y",
    "CONFIG_BRIDGE": "y",
    "CONFIG_VLAN_8021Q": "y",
    "CONFIG_USB_XHCI_HCD": "y",
    "CONFIG_USB_XHCI_PCI": "y",
}

FEATURE_KERNEL_EXPECTATIONS: dict[str, dict[str, str]] = {
    "uefi": {
        "CONFIG_64BIT": "y",
        "CONFIG_EFI": "y",
        "CONFIG_EFI_STUB": "y",
        "CONFIG_PCIEPORTBUS": "y",
        "CONFIG_PCIEASPM": "y",
        "CONFIG_PCI_MMCONFIG": "y",
    },
    "intel_ahci": {"CONFIG_SATA_AHCI": "y"},
    "j4125_gemini_lake": {
        "CONFIG_PINCTRL": "y",
        "CONFIG_PINCTRL_GEMINILAKE": "y",
        "CONFIG_SENSORS_CORETEMP": "y",
        "CONFIG_THERMAL": "y",
        "CONFIG_X86_PKG_TEMP_THERMAL": "y",
        "CONFIG_X86_ACPI_CPUFREQ": "y",
        "CONFIG_X86_INTEL_PSTATE": "y",
    },
    "intel_microcode": {"CONFIG_MICROCODE_LATE_LOADING": "y"},
    "intel_graphics": {
        "CONFIG_DRM": "y",
        "CONFIG_FB": "y",
        "CONFIG_FB_EFI": "y",
    },
}

FORBIDDEN_MANIFEST_PATTERNS = [
    r"^docker",
    r"^dockerd$",
    r"^containerd",
    r"^runc$",
    r"^samba",
    r"^ksmbd",
    r"^smbd$",
    r"^nfs-kernel-server$",
    r"^jellyfin",
    r"^plex",
    r"^transmission",
    r"^aria2",
    r"^qbittorrent",
    r"^minidlna",
]

FORBIDDEN_DRIVER_PATTERNS = [
    r"^wpad",
    r"^hostapd",
    r"^kmod-ath",
    r"^kmod-cfg80211$",
    r"^kmod-mac80211$",
    r"^kmod-iwl",
    r"^kmod-mt76",
    r"^kmod-rtw",
    r"^kmod-brcm",
    r"^kmod-bluetooth$",
    r"^bluez",
    r"^kmod-8139",
    r"^kmod-3c59x$",
    r"^kmod-alx$",
    r"^kmod-ne2k-pci$",
    r"^kmod-pcnet32$",
    r"^kmod-tulip$",
    r"^kmod-solos-pci$",
    r"^kmod-hfcpci$",
    r"^kmod-ata-artop$",
    r"^kmod-ata-nvidia-sata$",
    r"^kmod-ata-pdc202xx-old$",
    r"^kmod-ata-sil",
    r"^kmod-ata-via-sata$",
    r"^kmod-mvsas$",
    r"^kmod-megaraid",
    r"^kmod-aacraid$",
    r"^kmod-hpsa$",
    r"^kmod-cciss$",
    r"^kmod-appletalk$",
    r"^kmod-ax25",
    r"^kmod-can",
    r"^kmod-6lowpan",
    r"^kmod-batman-adv$",
    r"^kmod-nfc",
    r"^kmod-w1-",
    r"^kmod-pps-",
    r"^kmod-dvb",
    r"^kmod-video-",
    r"^kmod-joydev",
    r"^kmod-input-joydev",
    r"^kmod-thunderbolt",
    r"^kmod-ib-",
    r"^kmod-wpan",
    r"^kmod-kvm",
    r"^kmod-vfio",
    r"^kmod-vhost",
    r"^kmod-drm-amdgpu$",
    r"^kmod-drm-radeon$",
]


def feature_map(data: Mapping[str, Any]) -> dict[str, bool]:
    raw = data.get("features")
    if not isinstance(raw, Mapping):
        raise ConfigReadError("features must be a mapping")

    known = set(FEATURE_PACKAGES) | set(FEATURE_KERNEL_EXPECTATIONS)
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigReadError(f"unknown feature flags: {unknown}")

    result: dict[str, bool] = {}
    for name, value in raw.items():
        if not isinstance(value, bool):
            raise ConfigReadError(f"feature {name!r} must be true or false")
        result[str(name)] = value

    missing_required = sorted(name for name in REQUIRED_TRUE_FEATURES if not result.get(name))
    if missing_required:
        raise ConfigReadError(f"profile-critical features must be enabled: {missing_required}")
    return result


def expand_feature_packages(data: Mapping[str, Any]) -> list[str]:
    enabled = feature_map(data)
    packages = list(BASE_PACKAGES)
    for feature, values in FEATURE_PACKAGES.items():
        if enabled.get(feature):
            packages.extend(values)
    return unique(packages)


def expand_feature_config(data: Mapping[str, Any]) -> dict[str, str]:
    enabled = feature_map(data)
    symbols: dict[str, str] = {}
    for feature, values in FEATURE_CONFIG.items():
        if enabled.get(feature):
            symbols.update(values)
    return symbols


def expand_kernel_expectations(data: Mapping[str, Any]) -> dict[str, str]:
    enabled = feature_map(data)
    symbols = dict(BASE_KERNEL_EXPECTATIONS)
    for feature, values in FEATURE_KERNEL_EXPECTATIONS.items():
        if enabled.get(feature):
            symbols.update(values)
    return symbols


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result