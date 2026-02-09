# B4YC — Before You Connect

Scan before connecting to any network. Everything runs local. 

## How to use

```
python b4yc.py <command>
```

| Command | What it does |
|---|---|
| `scan` | See nearby Wi-Fi networks |
| `ble` | See nearby Bluetooth devices |
| `anomalies` | Check for anything suspicious |
| `summary` | Plain-English overview of your area |
| `explain <name>` | Learn more about a specific network **WIP**|
| `web` | Open the browser interface |
| `help` | Show available commands |

## What runs where

| | Linux | macOS | Windows |
|---|---|---|---|
| Wi-Fi scan | yes | yes | yes |
| BLE scan | yes | no | no |
| Web UI | yes | yes | yes |

On Linux it tries `iw`, then `nmcli`, then `iwlist`. Works on Debian, Ubuntu, Kali, and anything else with a wireless adapter. macOS uses the built-in `airport` utility. Windows uses `netsh`. Probably wont try to expand this much more than it already is. The focus was to be able to check WiFi at a coffeeshop before connecting. 

BLE is Linux-only for now. It looks for `hcitool` or `bluetoothctl` (both from `bluez`). It was also just something thrown in there because why not. I haven't done much troubleshooting on ble so if you want to take a stab at it just fork the repo and have at it.

## Requirements

- Python 3
- A Wi-Fi adapter (if you're using a VM)
- For BLE on Linux: `sudo apt install bluez`

## Privacy

No data leaves your machine. Ever. Made everything to be as simple as possible, just read the code yourself.
