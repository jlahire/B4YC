# known.py — reads OS connection history to tag known vs new devices
# read-only, no active scanning
#
# Linux:   NetworkManager connection files, /var/lib/bluetooth
# macOS:   com.apple.airport.preferences.plist, com.apple.Bluetooth.plist
# Windows: netsh wlan show profiles

import os
import re
import subprocess
import platform

import config


def getKnownWifi():
    """Returns a set of SSIDs the OS has previously connected to."""
    osName = platform.system()
    if osName == "Linux":
        return _knownWifiLinux()
    elif osName == "Darwin":
        return _knownWifiMac()
    elif osName == "Windows":
        return _knownWifiWindows()
    return set()


def getKnownBle():
    """Returns a set of BLE device addresses (uppercase AA:BB:CC format) the OS has paired."""
    osName = platform.system()
    if osName == "Linux":
        return _knownBleLinux()
    elif osName == "Darwin":
        return _knownBleMac()
    return set()


def isHotspot(ssid):
    if not ssid:
        return False
    lower = ssid.lower()
    return any(p in lower for p in config.hotspotPatterns)


def wifiTag(ssid, knownSsids):
    """Returns 'known', 'hotspot', or 'new' for a given SSID."""
    if ssid and any(s.lower() == ssid.lower() for s in knownSsids):
        return "known"
    if isHotspot(ssid):
        return "hotspot"
    return "new"


def bleTag(address, knownAddresses):
    """Returns 'known' or 'new' for a BLE device address."""
    return "known" if address.upper() in knownAddresses else "new"


def tagNetworks(networks, knownSsids):
    """Adds a 'tag' field to each network dict in-place. Returns the list."""
    for n in networks:
        n["tag"] = wifiTag(n.get("ssid", ""), knownSsids)
    return networks


def tagDevices(devices, knownAddresses):
    """Adds a 'tag' field to each BLE device dict in-place. Returns the list."""
    for d in devices:
        d["tag"] = bleTag(d.get("address", ""), knownAddresses)
    return devices


# ── Linux ──────────────────────────────────────────────────────────────────

def _knownWifiLinux():
    known = set()

    # NetworkManager .nmconnection files
    dirs = [
        "/etc/NetworkManager/system-connections/",
        os.path.expanduser("~/.local/share/NetworkManager/system-connections/"),
    ]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        try:
            for fname in os.listdir(d):
                _parseNmConnFile(os.path.join(d, fname), known)
        except PermissionError:
            pass

    # nmcli fallback — connection names usually match SSIDs for Wi-Fi profiles
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and "wireless" in parts[1].lower():
                known.add(parts[0].strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return known


def _parseNmConnFile(path, known):
    """Extract SSID from a NetworkManager .nmconnection file."""
    try:
        in_wifi = False
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line == "[wifi]":
                    in_wifi = True
                elif line.startswith("[") and line.endswith("]"):
                    in_wifi = False
                elif in_wifi and line.startswith("ssid="):
                    known.add(line.split("=", 1)[1].strip())
    except (PermissionError, IOError):
        pass


def _knownBleLinux():
    known = set()
    bt_dir = "/var/lib/bluetooth/"
    if not os.path.isdir(bt_dir):
        return known
    try:
        for adapter in os.listdir(bt_dir):
            adapter_path = os.path.join(bt_dir, adapter)
            if not os.path.isdir(adapter_path):
                continue
            for device in os.listdir(adapter_path):
                if re.match(r'^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$', device):
                    known.add(device.upper())
    except PermissionError:
        pass
    return known


# ── macOS ──────────────────────────────────────────────────────────────────

def _knownWifiMac():
    known = set()
    try:
        import plistlib
        plist = "/Library/Preferences/SystemConfiguration/com.apple.airport.preferences.plist"
        with open(plist, "rb") as f:
            data = plistlib.load(f)
        for net in data.get("KnownNetworks", {}).values():
            ssid = net.get("SSIDString") or net.get("SSID_STR", "")
            if ssid:
                known.add(ssid)
    except Exception:
        pass
    return known


def _knownBleMac():
    known = set()
    try:
        import plistlib
        plist = "/Library/Preferences/com.apple.Bluetooth.plist"
        with open(plist, "rb") as f:
            data = plistlib.load(f)
        for addr in data.get("DeviceCache", {}).keys():
            # macOS uses hyphen-separated MACs: 00-11-22-33-44-55
            known.add(addr.upper().replace("-", ":"))
    except Exception:
        pass
    return known


# ── Windows ────────────────────────────────────────────────────────────────

def _knownWifiWindows():
    known = set()
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "profiles"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            stripped = line.strip()
            # "All User Profile     : ProfileName"
            if ":" in stripped and "profile" in stripped.lower():
                name = stripped.split(":", 1)[1].strip()
                if name:
                    known.add(name)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return known
