# traffic.py — passive traffic stats for the active Wi-Fi interface
# everything is read-only, nothing is sent anywhere
#
# Linux:   /proc/net/dev  +  ip addr  +  nmcli
# macOS:   netstat -Ib    +  ipconfig +  airport
# Windows: netsh wlan     +  PowerShell Get-NetAdapterStatistics

import json
import platform
import re
import subprocess


def getTrafficStats():
    """
    Returns:
    {
        "interface": str,
        "ip":        str | None,
        "ssid":      str | None,
        "rx_bytes":  int,
        "tx_bytes":  int,
    }
    """
    osName = platform.system()
    if osName == "Linux":
        return _statsLinux()
    elif osName == "Darwin":
        return _statsMac()
    elif osName == "Windows":
        return _statsWindows()
    return {"interface": "", "ip": None, "ssid": None, "rx_bytes": 0, "tx_bytes": 0}


# ── Linux ──────────────────────────────────────────────────────────────────

def _statsLinux():
    iface = _wifiIfaceLinux()
    rx, tx = _procNetDev(iface)
    return {
        "interface": iface,
        "ip":        _ipLinux(iface),
        "ssid":      _ssidLinux(),
        "rx_bytes":  rx,
        "tx_bytes":  tx,
    }


def _wifiIfaceLinux():
    try:
        out = subprocess.check_output(["iw", "dev"], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r'Interface\s+(\S+)', out)
        if m:
            return m.group(1)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        out = subprocess.check_output(["ip", "link", "show"], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r'\d+:\s+(wl\S+):', out)
        if m:
            return m.group(1)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return "wlan0"


def _ipLinux(iface):
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", iface],
            text=True, stderr=subprocess.DEVNULL
        )
        m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out)
        if m:
            return m.group(1)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return None


def _ssidLinux():
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.strip().splitlines():
            # format: yes:SSID — SSID may contain colons
            if line.startswith("yes:"):
                return line[4:] or None
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return None


def _procNetDev(iface):
    """Read cumulative rx/tx bytes from /proc/net/dev."""
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if iface + ":" in line:
                    # iface: rx_bytes rx_pkts rx_errs ... tx_bytes tx_pkts ...
                    cols = line.split(":")[1].split()
                    return int(cols[0]), int(cols[8])
    except (IOError, IndexError, ValueError):
        pass
    return 0, 0


# ── macOS ──────────────────────────────────────────────────────────────────

def _statsMac():
    iface = _wifiIfaceMac()
    rx, tx = _netstatMac(iface)
    return {
        "interface": iface,
        "ip":        _ipMac(iface),
        "ssid":      _ssidMac(),
        "rx_bytes":  rx,
        "tx_bytes":  tx,
    }


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


def _ipMac(iface):
    try:
        out = subprocess.check_output(
            ["ipconfig", "getifaddr", iface],
            text=True, stderr=subprocess.DEVNULL
        )
        return out.strip() or None
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return None


def _ssidMac():
    airportPath = ("/System/Library/PrivateFrameworks/Apple80211.framework"
                   "/Versions/Current/Resources/airport")
    try:
        out = subprocess.check_output(
            [airportPath, "-I"], text=True, stderr=subprocess.DEVNULL
        )
        m = re.search(r'\s+SSID:\s+(.+)', out)
        if m:
            return m.group(1).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return None


def _netstatMac(iface):
    """
    netstat -I <iface> -b -n
    Columns: Name Mtu Network Address Ipkts Ierrs Ibytes Opkts Oerrs Obytes Coll
    """
    try:
        out = subprocess.check_output(
            ["netstat", "-I", iface, "-b", "-n"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.strip().splitlines()[1:]:    # skip header
            cols = line.split()
            if len(cols) >= 10 and cols[0].startswith(iface):
                return int(cols[6]), int(cols[9])
    except (FileNotFoundError, subprocess.CalledProcessError, IndexError, ValueError):
        pass
    return 0, 0


# ── Windows ────────────────────────────────────────────────────────────────

def _statsWindows():
    iface, ip, ssid = _wifiInfoWindows()
    rx, tx = _netstatWindows(iface)
    return {
        "interface": iface,
        "ip":        ip,
        "ssid":      ssid,
        "rx_bytes":  rx,
        "tx_bytes":  tx,
    }


def _wifiInfoWindows():
    iface = "Wi-Fi"
    ip    = None
    ssid  = None
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            s = line.strip()
            if re.match(r'Name\s*:', s):
                iface = s.split(":", 1)[1].strip()
            elif re.match(r'SSID\s*:', s) and "BSSID" not in s:
                ssid = s.split(":", 1)[1].strip()
            elif re.match(r'IPv4 Address\s*:', s, re.I):
                ip = s.split(":", 1)[1].strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return iface, ip, ssid


def _netstatWindows(iface):
    try:
        cmd = (
            f'Get-NetAdapterStatistics -Name "{iface}" | '
            f'Select-Object ReceivedBytes,SentBytes | ConvertTo-Json'
        )
        out = subprocess.check_output(
            ["powershell", "-Command", cmd],
            text=True, stderr=subprocess.DEVNULL
        )
        data = json.loads(out.strip())
        return int(data.get("ReceivedBytes", 0)), int(data.get("SentBytes", 0))
    except Exception:
        pass
    return 0, 0
