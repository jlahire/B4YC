# connect.py — connect to a Wi-Fi network
# only runs on localhost, password never leaves the machine
#
# Linux:   nmcli  (network-manager)
# macOS:   networksetup
# Windows: netsh wlan + temp profile XML for new networks

import os
import platform
import re
import subprocess
import tempfile


def connectWifi(ssid, password=None):
    """
    Connect to a Wi-Fi network.
    Returns (success: bool, message: str).
    """
    if not ssid:
        return False, "No SSID provided."

    osName = platform.system()
    if osName == "Linux":
        return _connectLinux(ssid, password or None)
    elif osName == "Darwin":
        return _connectMac(ssid, password or None)
    elif osName == "Windows":
        return _connectWindows(ssid, password or None)
    return False, f"Unsupported OS: {osName}"


# ── Linux ──────────────────────────────────────────────────────────────────

def _connectLinux(ssid, password):
    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = result.stdout.strip() or result.stderr.strip()
        if result.returncode == 0:
            return True, out or f"Connected to {ssid}"
        return False, out or "Connection failed."
    except FileNotFoundError:
        return False, "nmcli not found — install network-manager."
    except subprocess.TimeoutExpired:
        return False, "Connection timed out."


# ── macOS ──────────────────────────────────────────────────────────────────

def _connectMac(ssid, password):
    iface = _wifiIfaceMac()
    cmd = ["networksetup", "-setairportnetwork", iface, ssid]
    if password:
        cmd.append(password)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Connected to {ssid}"
        out = result.stdout.strip() or result.stderr.strip()
        return False, out or "Connection failed."
    except FileNotFoundError:
        return False, "networksetup not found."
    except subprocess.TimeoutExpired:
        return False, "Connection timed out."


def _wifiIfaceMac():
    try:
        out = subprocess.check_output(
            ["networksetup", "-listallhardwareports"],
            text=True, stderr=subprocess.DEVNULL
        )
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if "Wi-Fi" in line or "Airport" in line:
                if i + 1 < len(lines):
                    m = re.search(r'Device:\s+(\S+)', lines[i + 1])
                    if m:
                        return m.group(1)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return "en0"


# ── Windows ────────────────────────────────────────────────────────────────

def _connectWindows(ssid, password):
    # Try connecting with an existing saved profile first
    try:
        result = subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, f"Connected to {ssid}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # No saved profile — create a temporary one
    if password:
        ok, err = _createWpa2ProfileWindows(ssid, password)
    else:
        ok, err = _createOpenProfileWindows(ssid)

    if not ok:
        return False, err or "Could not create a connection profile."

    try:
        result = subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, f"Connected to {ssid}"
        out = result.stdout.strip() or result.stderr.strip()
        return False, out or "Connection failed."
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def _createOpenProfileWindows(ssid):
    xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>manual</connectionMode>
  <MSM><security>
    <authEncryption>
      <authentication>open</authentication>
      <encryption>none</encryption>
      <useOneX>false</useOneX>
    </authEncryption>
  </security></MSM>
</WLANProfile>"""
    return _addProfileWindows(xml)


def _createWpa2ProfileWindows(ssid, password):
    xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>manual</connectionMode>
  <MSM><security>
    <authEncryption>
      <authentication>WPA2PSK</authentication>
      <encryption>AES</encryption>
      <useOneX>false</useOneX>
    </authEncryption>
    <sharedKey>
      <keyType>passPhrase</keyType>
      <protected>false</protected>
      <keyMaterial>{password}</keyMaterial>
    </sharedKey>
  </security></MSM>
</WLANProfile>"""
    return _addProfileWindows(xml)


def _addProfileWindows(xml):
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".xml")
        with os.fdopen(fd, "w") as f:
            f.write(xml)
        result = subprocess.run(
            ["netsh", "wlan", "add", "profile", f"filename={tmp}"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0, result.stderr.strip()
    except Exception as e:
        return False, str(e)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
