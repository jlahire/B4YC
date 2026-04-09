# Linux:   hcitool, bluetoothctl (bluez)
# macOS:   system_profiler SPBluetoothDataType
# Windows: PowerShell + WinRT BluetoothLEAdvertisementWatcher (Win10 1703+)
#          fallback: Get-PnpDevice (paired/visible devices)
#
# everything is passive

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time


def scanBle(seconds=10):
    osName = platform.system()

    if osName == "Linux":
        return _scanLinuxBle(seconds)
    elif osName == "Darwin":
        return _scanMacBle()
    elif osName == "Windows":
        return _scanWindowsBle(seconds)
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


# ── Windows ────────────────────────────────────────────────────────────────

# PowerShell script that uses WinRT BluetoothLEAdvertisementWatcher.
# Requires Windows 10 version 1703 (Creators Update) or later.
# __SECS__ is replaced at runtime with the scan duration.
_BLE_PS_WINRT = """\
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime 2>$null
try {
    [void][Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher,
           Windows.Devices.Bluetooth, ContentType=WindowsRuntime]
} catch {
    Write-Output '[]'
    exit 0
}

$global:_b4ycDevs = [System.Collections.Concurrent.ConcurrentDictionary[string,string]]::new()

$w = [Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher]::new()
$w.ScanningMode = [Windows.Devices.Bluetooth.Advertisement.BluetoothLEScanningMode]::Active

$evtReg = Register-ObjectEvent -InputObject $w -EventName Received -Action {
    $raw = $Event.SourceEventArgs.BluetoothAddress
    $h   = ('{0:X12}' -f $raw).ToCharArray()
    $mac = (($h[0..1]  -join '') + ':' +
            ($h[2..3]  -join '') + ':' +
            ($h[4..5]  -join '') + ':' +
            ($h[6..7]  -join '') + ':' +
            ($h[8..9]  -join '') + ':' +
            ($h[10..11]-join '')).ToUpper()
    $n = $Event.SourceEventArgs.Advertisement.LocalName
    if ([string]::IsNullOrWhiteSpace($n)) { $n = '(unknown)' }
    $global:_b4ycDevs.TryAdd($mac, $n) | Out-Null
}

$w.Start()
Start-Sleep -Seconds __SECS__
$w.Stop()
Unregister-Event -SourceIdentifier $evtReg.Name -ErrorAction SilentlyContinue

if ($global:_b4ycDevs.Count -eq 0) { Write-Output '[]'; exit 0 }

$out = foreach ($k in $global:_b4ycDevs.Keys) {
    [PSCustomObject]@{ address = $k; name = $global:_b4ycDevs[$k]; type = 'BLE' }
}
$out | ConvertTo-Json -Compress -Depth 2
"""

# Fallback: enumerate paired/visible Bluetooth devices via Get-PnpDevice.
# No WinRT required; works on all Windows 10/11.
_BLE_PS_PNPDEVICE = """\
$ErrorActionPreference = 'SilentlyContinue'
$devs = Get-PnpDevice -Class Bluetooth |
    Select-Object FriendlyName, DeviceID, Status
if ($null -eq $devs) { Write-Output '[]'; exit 0 }
if ($devs -isnot [array]) { $devs = @($devs) }
$devs | ConvertTo-Json -Compress -Depth 2
"""


def _psExe():
    """Return the PowerShell executable (pwsh = PS7, powershell = PS5), or None."""
    for candidate in ("pwsh", "powershell"):
        if shutil.which(candidate):
            return candidate
    return None


def _runPS(script, timeout=60):
    """Write script to a temp .ps1 file and run it; return stdout string or None."""
    ps = _psExe()
    if not ps:
        return None
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".ps1")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)
        result = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", tmp],
            capture_output=True, timeout=timeout,
        )
        try:
            return result.stdout.decode("utf-8").strip()
        except UnicodeDecodeError:
            return result.stdout.decode(errors="replace").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _parseJsonDevices(raw):
    """Parse a JSON array (or single object) of BLE device dicts."""
    if not raw or raw in ("[]", "null", ""):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return None
    devices = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        addr = str(item.get("address") or "").strip().upper()
        name = str(item.get("name") or item.get("FriendlyName") or "(unknown)").strip()
        if not name:
            name = "(unknown)"
        key = addr or name
        if key and key not in seen:
            seen.add(key)
            devices.append({"address": addr, "name": name, "type": "BLE"})
    return devices


def _scanWindowsBle(seconds):
    """
    BLE scanning for Windows via PowerShell.

    Attempt 1 — WinRT BluetoothLEAdvertisementWatcher (Win10 1703+):
      Active advertisement scan; discovers all nearby broadcasting devices.

    Attempt 2 — Get-PnpDevice fallback:
      Returns paired / previously-seen devices only; no WinRT needed.
    """
    # Attempt 1: WinRT active advertisement scan
    script = _BLE_PS_WINRT.replace("__SECS__", str(max(1, seconds)))
    raw = _runPS(script, timeout=seconds + 30)
    if raw is not None:
        devices = _parseJsonDevices(raw)
        if devices is not None:
            return devices

    # Attempt 2: paired/visible devices via Get-PnpDevice
    raw = _runPS(_BLE_PS_PNPDEVICE, timeout=20)
    if raw is not None:
        devices = _parsePnpDevices(raw)
        if devices is not None:
            if not devices:
                print("  Bluetooth is on but no paired devices found.")
            return devices

    print("  BLE scan failed. Check that Bluetooth is enabled.")
    print("  Requires Windows 10 version 1703+ and PowerShell 5.1+.")
    return []


def _parsePnpDevices(raw):
    """Parse Get-PnpDevice JSON output into the standard device list format."""
    if not raw or raw in ("[]", "null", ""):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return None
    devices = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name   = str(item.get("FriendlyName") or "(unknown)").strip()
        dev_id = str(item.get("DeviceID") or "")
        # Extract MAC from DeviceID: BTHENUM\DEV_AABBCCDDEEFF\... or similar
        m = re.search(r'DEV_([0-9A-Fa-f]{12})', dev_id)
        addr = ""
        if m:
            h    = m.group(1).upper()
            addr = ":".join(h[i:i+2] for i in range(0, 12, 2))
        key = addr or name
        if key and key not in seen:
            seen.add(key)
            devices.append({"address": addr, "name": name, "type": "BLE"})
    return devices
