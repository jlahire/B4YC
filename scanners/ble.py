# uses tools that come with most Linux(kali):
#   hcitool
#   bluetoothctl
#
# everything is passive

import subprocess
import re
import time


def scanBle(seconds=10):
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
                devices.append({
                    "address": address,
                    "name": name,
                    "type": "BLE",
                })

    return devices


def tryBluetoothctl(seconds):
    try:
        scanProc = subprocess.Popen(
            ["bluetoothctl", "--timeout", str(seconds), "scan", "on"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        scanProc.wait(timeout=seconds + 5)

        output = subprocess.check_output(
            ["bluetoothctl", "devices"],
            text=True, stderr=subprocess.DEVNULL
        )
        return parseBluetoothctlOutput(output)

    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def parseBluetoothctlOutput(output):
    """Pull device info from bluetoothctl's device list."""
    devices = []

    for line in output.splitlines():
        # format: Device AA:BB:CC:DD:EE:FF DeviceName
        match = re.match(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line.strip())
        if match:
            devices.append({
                "address": match.group(1).upper(),
                "name": match.group(2).strip() or "(unknown)",
                "type": "BLE",
            })

    return devices
