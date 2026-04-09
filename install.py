#!/usr/bin/env python3
"""
install.py -- B4YC dependency checker and installer
Detects your OS and ensures all required system tools are present.

Usage: python install.py
"""

import os
import platform
import shutil
import subprocess
import sys


# ── Formatting helpers ─────────────────────────────────────────────────────

def title(s):
    print(f"\n  {s}")
    print("  " + "-" * len(s))


def ok(msg):
    print(f"  [OK]   {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def err(msg):
    print(f"  [MISS] {msg}")


def info(msg):
    print(f"         {msg}")


# ── Helpers ────────────────────────────────────────────────────────────────

def which(cmd):
    """Returns True if a command exists on PATH."""
    return shutil.which(cmd) is not None


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def prompt_yes(question):
    try:
        return input(f"\n  {question} (y/N) ").strip().lower() == "y"
    except (KeyboardInterrupt, EOFError):
        return False


# ── Python version check ───────────────────────────────────────────────────

def check_python():
    title("Python version")
    v = sys.version_info
    if v >= (3, 8):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        err(f"Python {v.major}.{v.minor}.{v.micro}")
        info("B4YC requires Python 3.8 or later.")
        info("Download: https://python.org/downloads/")
        sys.exit(1)


# ── Linux ──────────────────────────────────────────────────────────────────

# (tool_name, package_name, required/optional, description)
LINUX_TOOLS = [
    # Core — Wi-Fi scanning
    ("iw",           "iw",              True,  "Wi-Fi scanner (preferred)"),
    ("ip",           "iproute2",        True,  "Interface + IP detection"),
    ("nmcli",        "network-manager", False, "Wi-Fi fallback scanner + SSID detection"),
    ("iwlist",       "wireless-tools",  False, "Wi-Fi fallback scanner"),
    # Bluetooth
    ("bluetoothctl", "bluez",           False, "BLE scanner (preferred)"),
    ("hcitool",      "bluez",           False, "BLE scanner (legacy fallback)"),
]

APT_PACKAGES  = ["iw", "iproute2", "network-manager", "wireless-tools", "bluez"]
DNF_PACKAGES  = ["iw", "iproute", "NetworkManager", "wireless-tools", "bluez"]
PACMAN_PACKAGES = ["iw", "iproute2", "networkmanager", "wireless_tools", "bluez"]


def install_linux():
    title("Linux — required system tools")

    missing_pkgs = []
    for tool, pkg, required, desc in LINUX_TOOLS:
        if which(tool):
            ok(f"{tool:<16s} {desc}")
        else:
            if required:
                err(f"{tool:<16s} {desc}  [package: {pkg}]")
            else:
                warn(f"{tool:<16s} {desc}  [package: {pkg}]  (optional fallback)")
            if pkg not in missing_pkgs:
                missing_pkgs.append(pkg)

    if not missing_pkgs:
        print("\n  All tools present — no installation needed.")
        return

    # Detect package manager
    if which("apt-get"):
        install_cmd = ["sudo", "apt-get", "install", "-y"] + _map_pkgs(missing_pkgs, APT_PACKAGES)
        pm_name = "apt"
    elif which("dnf"):
        install_cmd = ["sudo", "dnf", "install", "-y"] + _map_pkgs(missing_pkgs, DNF_PACKAGES)
        pm_name = "dnf"
    elif which("pacman"):
        install_cmd = ["sudo", "pacman", "-S", "--noconfirm"] + _map_pkgs(missing_pkgs, PACMAN_PACKAGES)
        pm_name = "pacman"
    else:
        warn("No supported package manager found (apt / dnf / pacman).")
        info("Install manually: " + "  ".join(missing_pkgs))
        return

    print(f"\n  Package manager: {pm_name}")
    print(f"  Command: {' '.join(install_cmd)}")

    if prompt_yes("Install missing packages now?"):
        result = run_cmd(install_cmd)
        if result.returncode == 0:
            ok("Installation complete.")
        else:
            err("Installation failed:")
            print(result.stderr[:800])
    else:
        info("Skipped. Run the command above manually when ready.")


def _map_pkgs(missing, mapping_list):
    """Return only the packages from mapping_list that cover missing items."""
    return [p for p in mapping_list if any(m in p for m in missing)]


# ── macOS ──────────────────────────────────────────────────────────────────

AIRPORT_PATH = ("/System/Library/PrivateFrameworks/Apple80211.framework"
                "/Versions/Current/Resources/airport")

MACOS_TOOLS = [
    # Wi-Fi
    (AIRPORT_PATH,     "built-in", True,  "Wi-Fi scanner (removed in macOS 14)"),
    ("system_profiler", "built-in", True,  "Wi-Fi + BLE fallback scanner"),
    ("networksetup",    "built-in", True,  "Wi-Fi connect + interface info"),
    ("ipconfig",        "built-in", True,  "IP address lookup"),
    # Optional active scan helper
    ("wdutil",          "built-in", False, "Wi-Fi diagnostic tool (macOS 12+)"),
]


def install_mac():
    title("macOS — required system tools")

    _v = tuple(int(x) for x in platform.mac_ver()[0].split(".")[:2] if x.isdigit())
    print(f"\n  macOS {platform.mac_ver()[0]}")

    for path_or_cmd, source, required, desc in MACOS_TOOLS:
        # airport is a file path, not a PATH command
        if "/" in path_or_cmd:
            present = os.path.isfile(path_or_cmd)
        else:
            present = which(path_or_cmd)

        if present:
            ok(f"{os.path.basename(path_or_cmd):<20s} {desc}")
        else:
            if path_or_cmd == AIRPORT_PATH and _v >= (14, 0):
                warn(f"{'airport':<20s} {desc}")
                info("Removed in macOS 14 — system_profiler will be used instead.")
                info("Wi-Fi scanning works but returns cached data, not a live scan.")
            elif required:
                err(f"{os.path.basename(path_or_cmd):<20s} {desc}")
                info("This is unexpected — reinstall macOS CLI tools:")
                info("  xcode-select --install")
            else:
                warn(f"{os.path.basename(path_or_cmd):<20s} {desc}  (optional)")

    print("\n  No pip packages required — B4YC uses macOS built-in tools only.")

    if _v >= (14, 0):
        print("\n  Note: macOS 14+ removed the airport utility.")
        print("  B4YC falls back to system_profiler SPAirPortDataType automatically.")
        print("  Active Wi-Fi scanning may not discover all nearby networks.")


# ── Windows ────────────────────────────────────────────────────────────────

WINDOWS_TOOLS = [
    ("netsh",       True,  "Wi-Fi scan, connect, profile management"),
    ("powershell",  True,  "Traffic stats via Get-NetAdapterStatistics"),
    ("ipconfig",    True,  "IP + interface info"),
]


def install_windows():
    title("Windows — required system tools")

    for cmd, required, desc in WINDOWS_TOOLS:
        # Try both powershell.exe and pwsh (PowerShell 7+)
        if cmd == "powershell":
            present = which("powershell") or which("pwsh")
        else:
            present = which(cmd)

        if present:
            ok(f"{cmd:<16s} {desc}")
        else:
            if required:
                err(f"{cmd:<16s} {desc}")
            else:
                warn(f"{cmd:<16s} {desc}  (optional)")

    # Check Wi-Fi adapter
    title("Windows — Wi-Fi adapter")
    result = run_cmd(["netsh", "wlan", "show", "interfaces"])
    if result.returncode == 0 and "State" in result.stdout:
        # Extract interface name and state
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Name") and ":" in line:
                iface = line.split(":", 1)[1].strip()
                ok(f"Wi-Fi adapter: {iface}")
            elif line.startswith("State") and ":" in line:
                state = line.split(":", 1)[1].strip()
                if "connected" in state.lower():
                    ok(f"State: {state}")
                else:
                    warn(f"State: {state}  (not connected — scanning will still work)")
    else:
        warn("No Wi-Fi adapter found or Wi-Fi is disabled.")
        info("Enable Wi-Fi: Settings > Network & Internet > Wi-Fi")

    print("\n  No pip packages required — B4YC uses Windows built-in tools only.")
    print("\n  Note: Bluetooth (BLE) scanning is not supported on Windows.")
    print("        Scan and anomaly detection work fully.")

    # Python launch tip
    print("\n  To start B4YC:")
    print("    python b4yc.py web    -- opens in your browser")
    print("    python b4yc.py help   -- all commands")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("\n  B4YC — dependency check")
    print("  " + "=" * 38)

    check_python()

    os_name = platform.system()

    if os_name == "Linux":
        install_linux()
    elif os_name == "Darwin":
        install_mac()
    elif os_name == "Windows":
        install_windows()
    else:
        warn(f"Unknown OS: {os_name}")
        info("B4YC supports Linux, macOS, and Windows.")
        sys.exit(1)

    print("\n  Ready. Start with:  python b4yc.py web\n")


if __name__ == "__main__":
    main()
