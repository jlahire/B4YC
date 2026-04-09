# Linux:   hcitool, bluetoothctl (bluez)
# macOS:   system_profiler SPBluetoothDataType
#
# everything is passive

import json
import platform
import re
import subprocess
import time


def scanBle(seconds=10):
    osName = platform.system()

    if osName == "Linux":
        return _scanLinuxBle(seconds)
    elif osName == "Darwin":
        return _scanMacBle()
    else:
        print(f"  BLE scanning not supported on {osName}.")
        return []


# ── Linux ──────────────────────────────────────────────────────────────────

def _scanLinuxBle(seconds):
    devices = tryHcitool(seconds)
    if devices is not None:
        return devices

    devices = tryBluetoothctl(seconds)
    if devices is not None:
        return devices

    print("  No Bluetooth tools found.")
    print("  On Kali/Debian: sudo apt install bluez")
    return []


def tryHcitool(seconds):
    try:
        proc = subprocess.Popen(
            ["hcitool", "lescan"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(seconds)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        output = proc.stdout.read().decode(errors="replace")
        errOutput = proc.stderr.read().decode(errors="replace")

        if "permission" in errOutput.lower() or "operation not possible" in errOutput.lower():
            return None

        return parseHcitoolOutput(output)

    except FileNotFoundError:
        return None


def parseHcitoolOutput(output):
    devices = []
    seen = set()

    for line in output.splitlines():
        if line.startswith("LE Scan"):
            continue
        match = re.match(r'([0-9A-Fa-f:]{17})\s*(.*)', line.strip())
        if match:
            address = match.group(1).upper()
            name = match.group(2).strip() or "(unknown)"
            if address not in seen:
                seen.add(address)
                devices.append({"address": address, "name": name, "type": "BLE"})

    return devices


def tryBluetoothctl(seconds):
    """Scan via bluetoothctl, capturing only [NEW] devices found in this session."""
    try:
        proc = subprocess.Popen(
            ["bluetoothctl", "--timeout", str(seconds), "scan", "on"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        try:
            output, _ = proc.communicate(timeout=seconds + 5)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()

        return parseBluetoothctlOutput(output.decode(errors="replace"))

    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def parseBluetoothctlOutput(output):
    """Parse [NEW] Device lines — only devices discovered during this scan."""
    devices = []
    seen = set()

    for line in output.splitlines():
        # strip ANSI escape codes that bluetoothctl emits
        clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
        match = re.search(r'\[NEW\]\s+Device\s+([0-9A-Fa-f:]{17})\s+(.*)', clean)
        if match:
            address = match.group(1).upper()
            name = match.group(2).strip() or "(unknown)"
            if address not in seen:
                seen.add(address)
                devices.append({"address": address, "name": name, "type": "BLE"})

    return devices


# ── macOS ──────────────────────────────────────────────────────────────────

def _scanMacBle():
    """Use system_profiler to list nearby/connected BLE devices on macOS."""
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPBluetoothDataType", "-json"],
            text=True, stderr=subprocess.DEVNULL
        )
        data = json.loads(out)
        return _parseMacBleJson(data)
    except (FileNotFoundError, subprocess.CalledProcessError,
            json.JSONDecodeError, KeyError):
        return []


def _parseMacBleJson(data):
    devices = []
    seen = set()

    for section in data.get("SPBluetoothDataType", []):
        # device groups vary by macOS version
        for key in ("device_connected", "device_not_connected", "devices_list"):
            group = section.get(key, {})
            if isinstance(group, dict):
                for name, info in group.items():
                    addr = info.get("device_address", "").upper().replace("-", ":")
                    if addr and addr not in seen:
                        seen.add(addr)
                        devices.append({"address": addr, "name": name, "type": "BLE"})
            elif isinstance(group, list):
                for item in group:
                    if isinstance(item, dict):
                        name = item.get("device_name", "(unknown)")
                        addr = item.get("device_address", "").upper().replace("-", ":")
                        if addr and addr not in seen:
                            seen.add(addr)
                            devices.append({"address": addr, "name": name, "type": "BLE"})

    return devices
