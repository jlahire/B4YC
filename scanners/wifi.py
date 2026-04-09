#   Linux:   iw, nmcli, iwlist (in that order)
#   macOS:   airport
#   Windows: netsh
#
# everything is passive

import subprocess
import platform
import re
import time


def scanWifi():
    osName = platform.system()

    if osName == "Linux":
        networks = scanLinux()
    elif osName == "Darwin":
        networks = scanMac()
    elif osName == "Windows":
        networks = scanWindows()
    else:
        print(f"  Sorry, {osName} is a nogo.....")
        return []

    return _dedupByBssid(networks)


def _dedupByBssid(networks):
    seen = set()
    result = []
    for n in networks:
        key = n["bssid"] or id(n)
        if key not in seen:
            seen.add(key)
            result.append(n)
    return result


# Linux — iw > nmcli > iwlist
def scanLinux():
    iface = findInterface()

    networks = tryIwScan(iface)
    if networks is not None:
        return networks

    networks = tryNmcliScan()
    if networks is not None:
        return networks

    networks = tryIwlistScan(iface)
    if networks is not None:
        return networks

    print("  Couldn't run the Wi-Fi scanner.")
    print("  Make sure you have iw, nmcli, or wireless-tools installed.")
    print("  On Kali/Debian: sudo apt install iw wireless-tools network-manager")
    return []


def findInterface():
    try:
        output = subprocess.check_output(
            ["iw", "dev"], text=True, stderr=subprocess.DEVNULL
        )
        match = re.search(r'Interface\s+(\S+)', output)
        if match:
            return match.group(1)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    try:
        output = subprocess.check_output(
            ["ip", "link", "show"], text=True, stderr=subprocess.DEVNULL
        )
        match = re.search(r'\d+:\s+(wl\S+):', output)
        if match:
            return match.group(1)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return "wlan0"


def tryIwScan(iface):
    try:
        output = subprocess.check_output(
            ["iw", "dev", iface, "scan"],
            text=True, stderr=subprocess.PIPE
        )
        return parseIwOutput(output)
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        return None


def parseIwOutput(output):
    networks = []
    blocks = re.split(r'^BSS ', output, flags=re.MULTILINE)

    for block in blocks[1:]:
        network = parseIwBlock("BSS " + block)
        if network:
            networks.append(network)
    return networks


def parseIwBlock(block):
    network = {
        "ssid": "", "bssid": "", "signal": 0,
        "channel": "", "security": "Open", "wps": False,
    }

    bssMatch = re.match(r'BSS ([0-9a-fA-F:]{17})', block)
    if bssMatch:
        network["bssid"] = bssMatch.group(1).lower()

    ssidMatch = re.search(r'SSID: (.+)', block)
    if ssidMatch:
        network["ssid"] = ssidMatch.group(1).strip()

    sigMatch = re.search(r'signal:\s*(-?[\d.]+)', block)
    if sigMatch:
        dBm = float(sigMatch.group(1))
        network["signal"] = min(max(int(2 * (dBm + 100)), 0), 100)

    chanMatch = re.search(r'DS Parameter set: channel (\d+)', block)
    if chanMatch:
        network["channel"] = chanMatch.group(1)
    else:
        freqMatch = re.search(r'freq:\s*(\d+)', block)
        if freqMatch:
            network["channel"] = freqToChannel(int(freqMatch.group(1)))

    if 'RSN:' in block:
        network["security"] = "WPA3" if 'SAE' in block else "WPA2"
    elif 'WPA:' in block:
        network["security"] = "WPA"

    if 'WPS:' in block:
        network["wps"] = True

    return network


def freqToChannel(freq):
    if 2412 <= freq <= 2484:
        return "14" if freq == 2484 else str((freq - 2407) // 5)
    elif 5170 <= freq <= 5825:
        return str((freq - 5000) // 5)
    return str(freq)


def _requestRescan():
    """Ask nmcli to trigger a fresh scan. Best-effort — ignore all errors."""
    try:
        subprocess.run(
            ["nmcli", "dev", "wifi", "rescan"],
            timeout=5, capture_output=True
        )
        time.sleep(1)
    except Exception:
        pass


def tryNmcliScan():
    _requestRescan()
    try:
        output = subprocess.check_output(
            ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,CHAN,SECURITY",
             "dev", "wifi", "list"],
            text=True, stderr=subprocess.DEVNULL
        )
        networks = []
        for line in output.strip().splitlines():
            parsed = parseNmcliLine(line)
            if parsed:
                networks.append(parsed)
        return networks
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def parseNmcliLine(line):
    parts = re.split(r'(?<!\\):', line)
    parts = [p.replace('\\:', ':').strip() for p in parts]

    if len(parts) < 5:
        return None

    signal = 0
    try:
        signal = int(parts[2])
    except ValueError:
        pass

    return {
        "ssid": parts[0],
        "bssid": parts[1].lower(),
        "signal": signal,
        "channel": parts[3],
        "security": parts[4] if parts[4] else "Open",
        "wps": False,
    }


def tryIwlistScan(iface):
    try:
        output = subprocess.check_output(
            ["iwlist", iface, "scan"],
            text=True, stderr=subprocess.PIPE
        )
        return parseIwlistOutput(output)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def parseIwlistOutput(output):
    networks = []
    current = None

    for line in output.splitlines():
        stripped = line.strip()

        cellMatch = re.match(r'Cell \d+ - Address: ([0-9A-Fa-f:]{17})', stripped)
        if cellMatch:
            if current:
                networks.append(current)
            current = {
                "ssid": "", "bssid": cellMatch.group(1).lower(),
                "signal": 0, "channel": "", "security": "Open", "wps": False,
            }
            continue

        if current is None:
            continue

        if 'ESSID:' in stripped:
            match = re.search(r'ESSID:"(.*)"', stripped)
            if match:
                current["ssid"] = match.group(1)

        elif 'Channel:' in stripped:
            match = re.search(r'Channel:(\d+)', stripped)
            if match:
                current["channel"] = match.group(1)

        elif 'Signal level' in stripped:
            dbmMatch = re.search(r'Signal level[=:](-?\d+)\s*dBm', stripped)
            if dbmMatch:
                dBm = int(dbmMatch.group(1))
                current["signal"] = min(max(2 * (dBm + 100), 0), 100)
            else:
                pctMatch = re.search(r'Signal level[=:](\d+)/100', stripped)
                if pctMatch:
                    current["signal"] = int(pctMatch.group(1))

        elif 'WPA2' in stripped:
            current["security"] = "WPA2"
        elif 'WPA' in stripped and current["security"] != "WPA2":
            current["security"] = "WPA"

    if current:
        networks.append(current)
    return networks



# macOS — airport

def scanMac():
    airportPath = ("/System/Library/PrivateFrameworks/Apple80211.framework"
                   "/Versions/Current/Resources/airport")
    try:
        output = subprocess.check_output(
            [airportPath, "-s"], text=True, stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  Couldn't run the airport.")
        print("  You may need to locate the airport utility on your macOS version.")
        return []

    networks = []
    lines = output.strip().splitlines()
    if len(lines) < 2:
        return []

    for line in lines[1:]:
        parsed = parseMacLine(line)
        if parsed:
            networks.append(parsed)
    return networks


def parseMacLine(line):
    match = re.match(
        r'\s*(.+?)\s{2,}([0-9a-fA-F:]{17})\s+(-?\d+)\s+(\S+)\s+\S+\s+\S+\s+(.*)',
        line
    )
    if not match:
        return None

    ssid, bssid, rssi, channel, security = match.groups()
    dBm = int(rssi)
    signal = min(max(2 * (dBm + 100), 0), 100)

    securityClean = security.strip()
    isOpen = not securityClean or securityClean.upper() == "NONE"

    return {
        "ssid": ssid.strip(),
        "bssid": bssid.lower(),
        "signal": signal,
        "channel": channel,
        "security": "Open" if isOpen else securityClean,
        "wps": False,
    }


# Windows — netsh

def scanWindows():
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            text=True, stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  Wi-Fi scan failed. Make sure Wi-Fi is turned on.")
        return []

    return parseWindowsOutput(output)


def parseWindowsOutput(output):
    networks = []
    currentSsid = ""
    currentSecurity = ""
    currentBssid = ""
    currentSignal = 0
    currentChannel = ""

    for line in output.splitlines():
        stripped = line.strip()

        if stripped.startswith("SSID") and "BSSID" not in stripped:
            match = re.match(r'SSID \d+ : (.+)', stripped)
            if match:
                currentSsid = match.group(1).strip()
        elif stripped.startswith("Authentication"):
            currentSecurity = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("BSSID"):
            if currentBssid:
                networks.append({
                    "ssid": currentSsid, "bssid": currentBssid.lower(),
                    "signal": currentSignal, "channel": currentChannel,
                    "security": currentSecurity or "Open", "wps": False,
                })
            bssidMatch = re.match(r'BSSID \d+\s*:\s*(.+)', stripped)
            if bssidMatch:
                currentBssid = bssidMatch.group(1).strip()
            currentSignal = 0
            currentChannel = ""

        elif stripped.startswith("Signal"):
            signalStr = stripped.split(":", 1)[1].strip().replace("%", "")
            try:
                currentSignal = int(signalStr)
            except ValueError:
                currentSignal = 0

        elif stripped.startswith("Channel"):
            currentChannel = stripped.split(":", 1)[1].strip()

    if currentBssid:
        networks.append({
            "ssid": currentSsid, "bssid": currentBssid.lower(),
            "signal": currentSignal, "channel": currentChannel,
            "security": currentSecurity or "Open", "wps": False,
        })

    return networks
