#!/usr/bin/env python3
# b4yc.py — Before You Connect
#
# scan your surroundings before connecting to any network
# everything runs locally
#
# usage: python b4yc.py <command> [--json]
# try:   python b4yc.py help

import json
import sys

from scanners.wifi import scanWifi
from scanners.ble import scanBle
from scanners.known import getKnownWifi, getKnownBle, tagNetworks, tagDevices
from analyzers.anomalies import detectAnomalies
from analyzers.summary import generateSummary, generateBleSummary, explainNetwork
from ui.web import startWeb
import config


def signalBar(pct):
    filled = round(pct / 20)
    return "▓" * filled + "░" * (5 - filled)


def showHelp():
    print(f"\n  {config.appName}  v{config.version}")
    print(f"  Know what's around you before you go online.\n")
    print(f"  Usage: python b4yc.py <command> [--json]\n")
    print(f"  Commands:")
    print(f"    scan              Wi-Fi networks")
    print(f"    ble               Bluetooth devices")
    print(f"    anomalies         Check for anything weird")
    print(f"    summary           Self explanatory...")
    print(f"    explain <name>    Learn more about a specific network")
    print(f"    web               Localhost")
    print(f"    chat              Type commands and get answers")
    print(f"    help              You're looking at it")
    print(f"\n  Add --json to any command for machine-readable output.")
    print()


def doScan(jsonMode=False):
    networks = scanWifi()
    knownSsids = getKnownWifi()
    tagNetworks(networks, knownSsids)

    if jsonMode:
        print(json.dumps(networks, indent=2))
        return

    if not networks:
        print("  No joy. No Wi-Fi networks found.")
        return

    print()
    for n in networks:
        ssid = n["ssid"] or "(hidden)"
        wps  = " [WPS]" if n.get("wps") else ""
        bar  = signalBar(n["signal"])
        tag  = f'[{n["tag"].upper()}]'
        print(f'  {ssid:28s}  {n["bssid"]}  {bar} {n["signal"]:3d}%  Ch {n["channel"]:4s}  {n["security"]}{wps}  {tag}')
    print(f"\n  {len(networks)} network(s) found.")


def doBle(jsonMode=False):
    print(f"  Listening for Bluetooth ({config.bleScanSeconds}s)...")
    devices = scanBle(config.bleScanSeconds)
    knownAddrs = getKnownBle()
    tagDevices(devices, knownAddrs)

    if jsonMode:
        print(json.dumps(devices, indent=2))
        return

    print()
    print(generateBleSummary(devices))


def doAnomalies(jsonMode=False):
    networks = scanWifi()
    knownSsids = getKnownWifi()
    tagNetworks(networks, knownSsids)
    anomalies = detectAnomalies(networks)

    if jsonMode:
        print(json.dumps({"networks": networks, "anomalies": anomalies}, indent=2))
        return

    if not anomalies:
        print("  No anomalies detected. But stay alert.")
        return
    print()
    for a in anomalies:
        print(f'  [{a["severity"].upper():6s}] {a["message"]}')


def doSummary(jsonMode=False):
    networks = scanWifi()
    knownSsids = getKnownWifi()
    tagNetworks(networks, knownSsids)
    anomalies = detectAnomalies(networks)

    if jsonMode:
        print(json.dumps({"summary": generateSummary(networks, anomalies)}, indent=2))
        return

    print()
    print(generateSummary(networks, anomalies))


def doExplain(name, jsonMode=False):
    if not name:
        print("  Which network? Example: python b4yc.py explain CoffeeShopWifi")
        return
    networks = scanWifi()
    knownSsids = getKnownWifi()
    tagNetworks(networks, knownSsids)
    anomalies = detectAnomalies(networks)

    if jsonMode:
        print(json.dumps({"explanation": explainNetwork(name, networks, anomalies)}, indent=2))
        return

    print()
    print(explainNetwork(name, networks, anomalies))


def handleCommand(command, args=None, jsonMode=False):
    args = args or []

    commands = {
        "scan":      lambda: doScan(jsonMode),
        "ble":       lambda: doBle(jsonMode),
        "anomalies": lambda: doAnomalies(jsonMode),
        "summary":   lambda: doSummary(jsonMode),
        "explain":   lambda: doExplain(" ".join(args), jsonMode),
        "web":       lambda: startWeb(),
        "help":      lambda: showHelp(),
    }

    handler = commands.get(command)
    if handler:
        handler()
    else:
        print(f'  Don\'t know "{command}". Type "help" to see what\'s available.')


def startChat():
    print(f"\n  {config.appName}  v{config.version}")
    print(f"  type commands, get answers")
    print(f'  type "help" for commands, "exit" to leave.\n')

    while True:
        try:
            raw = input("  b4yc > ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not raw:
            continue
        if raw.lower() in ("exit", "quit"):
            break
        parts = raw.split()
        handleCommand(parts[0].lower(), parts[1:])
        print()

    print("\n  forks don't belong in outlets...stay safe out there!")


def main():
    args = sys.argv[1:]
    if not args:
        showHelp()
        return

    jsonMode = "--json" in args
    args = [a for a in args if a != "--json"]

    command = args[0].lower()
    if command == "chat":
        startChat()
    else:
        handleCommand(command, args[1:], jsonMode=jsonMode)


if __name__ == "__main__":
    main()
