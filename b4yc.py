#!/usr/bin/env python3
# b4yc.py — Before You Connect
#
# scan your surroundings before connecting to any network
# everything runs locally
#
# usage: python b4yc.py <command>
# try:   python b4yc.py help

import sys

from scanners.wifi import scanWifi
from scanners.ble import scanBle
from analyzers.anomalies import detectAnomalies
from analyzers.summary import generateSummary, generateBleSummary, explainNetwork
from ui.web import startWeb
import config


def showHelp():
    print(f"\n  {config.appName}  v{config.version}")
    print(f"  Know what's around you before you go online.\n")
    print(f"  Usage: python b4yc.py <command>\n")
    print(f"  Commands:")
    print(f"    scan              Wi-Fi networks")
    print(f"    ble               Bluetooth devices")
    print(f"    anomalies         Check for anything weird")
    print(f"    summary           Self explanatory...")
    print(f"    explain <name>    Learn more about a specific network")
    print(f"    web               Localhost")
    print(f"    chat              Type commands and get answers")
    print(f"    help              You're looking at it")
    print()


def doScan():
    networks = scanWifi()
    if not networks:
        print("  No joy. No Wi-Fi networks found.")
        return
    print()
    for n in networks:
        ssid = n["ssid"] or "(hidden)"
        wps = " [WPS]" if n.get("wps") else ""
        print(f'  {ssid:28s}  {n["bssid"]}  {n["signal"]:3d}%  Ch {n["channel"]:4s}  {n["security"]}{wps}')
    print(f"\n  {len(networks)} network(s) found.")


def doBle():
    print(f"  Listening for Bluetooth ({config.bleScanSeconds} seconds)...")
    devices = scanBle(config.bleScanSeconds)
    print()
    print(generateBleSummary(devices))


def doAnomalies():
    networks = scanWifi()
    anomalies = detectAnomalies(networks)
    if not anomalies:
        print("  No joy found. But double check.")
        return
    print()
    for a in anomalies:
        print(f'  [{a["severity"].upper():6s}] {a["message"]}')


def doSummary():
    networks = scanWifi()
    anomalies = detectAnomalies(networks)
    print()
    print(generateSummary(networks, anomalies))


def doExplain(name):
    if not name:
        print("  Which network? Example: python b4yc.py explain CoffeeShopWifi")
        return
    networks = scanWifi()
    anomalies = detectAnomalies(networks)
    print()
    print(explainNetwork(name, networks, anomalies))


def handleCommand(command, args=None):
    args = args or []

    commands = {
        "scan":      lambda: doScan(),
        "ble":       lambda: doBle(),
        "anomalies": lambda: doAnomalies(),
        "summary":   lambda: doSummary(),
        "explain":   lambda: doExplain(" ".join(args)),
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

    command = args[0].lower()
    if command == "chat":
        startChat()
    else:
        handleCommand(command, args[1:])


if __name__ == "__main__":
    main()
