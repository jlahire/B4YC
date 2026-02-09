# simple rules
# no AI

import config


def detectAnomalies(networks):
    anomalies = []
    anomalies += checkEvilTwins(networks)
    anomalies += checkOpenNetworks(networks)
    anomalies += checkHiddenNetworks(networks)
    anomalies += checkSuspiciousNames(networks)
    anomalies += checkStrongSignals(networks)
    anomalies += checkWps(networks)
    return anomalies


def checkEvilTwins(networks):
    """
    The big one. An evil twin is a fake access point that copies a real
    network's name to trick you into connecting to it.

    We catch this two ways:
    1. Same name but different security (e.g. one is WPA2, one is Open)
       This is a strong sign — legitimate APs don't do this.
    2. Same name but made by different manufacturers (different OUI prefix)
       Real multi-AP setups usually use the same brand of equipment.
    """
    hits = []
    ssidGroups = {}

    for net in networks:
        ssid = net["ssid"]
        if not ssid:
            continue
        if ssid not in ssidGroups:
            ssidGroups[ssid] = []
        ssidGroups[ssid].append(net)

    for ssid, group in ssidGroups.items():
        if len(group) < 2:
            continue

        securityTypes = set(n["security"] for n in group)
        if len(securityTypes) > 1:
            hits.append({
                "type": "evilTwin",
                "severity": "high",
                "ssid": ssid,
                "message": (f'"{ssid}" shows up with different security '
                            f'({", ".join(securityTypes)}). '
                            f'This is a strong sign of an evil twin.'),
            })
            continue

        ouis = set(n["bssid"][:8] for n in group)
        if len(ouis) > 1:
            hits.append({
                "type": "evilTwin",
                "severity": "medium",
                "ssid": ssid,
                "message": (f'"{ssid}" has access points from different '
                            f'manufacturers. Could be normal, or could be '
                            f'a rogue device copying this network.'),
            })

    return hits


def checkOpenNetworks(networks):
    hits = []
    for net in networks:
        if net["security"].lower() == "open":
            name = net["ssid"] or "(hidden)"
            hits.append({
                "type": "openNetwork",
                "severity": "medium",
                "ssid": net["ssid"],
                "message": (f'"{name}" has no encryption. Anything you send '
                            f'can be read by anyone nearby.'),
            })
    return hits


def checkHiddenNetworks(networks):
    hits = []
    for net in networks:
        if not net["ssid"]:
            hits.append({
                "type": "hiddenNetwork",
                "severity": "low",
                "ssid": "",
                "message": (f'Hidden network at {net["bssid"]}. '
                            f'Broadcasting but hiding its name.'),
            })
    return hits


def checkSuspiciousNames(networks):
    hits = []
    for net in networks:
        if net["ssid"].lower() in config.suspiciousNames:
            hits.append({
                "type": "suspiciousName",
                "severity": "medium",
                "ssid": net["ssid"],
                "message": (f'"{net["ssid"]}" is a name commonly used by '
                            f'fake hotspots and honeypots. Be careful.'),
            })
    return hits


def checkStrongSignals(networks):
    hits = []
    for net in networks:
        if net["signal"] >= config.suspiciousSignalFloor:
            name = net["ssid"] or "(hidden)"
            hits.append({
                "type": "strongSignal",
                "severity": "low",
                "ssid": net["ssid"],
                "message": (f'"{name}" is blasting at {net["signal"]}% signal. '
                            f'That device is very close to you.'),
            })
    return hits


def checkWps(networks):
    hits = []
    for net in networks:
        if net.get("wps"):
            name = net["ssid"] or "(hidden)"
            hits.append({
                "type": "wpsEnabled",
                "severity": "medium",
                "ssid": net["ssid"],
                "message": (f'"{name}" has WPS enabled. WPS has known '
                            f'vulnerabilities that can be exploited.'),
            })
    return hits
