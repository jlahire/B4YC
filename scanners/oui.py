# oui.py — OUI vendor lookup from local system files (no download required)
#
# Source priority:
#   1. ui/static/oui.json       — pre-built by install.py (IEEE download)
#   2. Wireshark manuf file     — ships with Wireshark on all platforms
#   3. ieee-data package        — apt install ieee-data  (Debian/Kali/Ubuntu)
#   4. nmap MAC prefix file     — ships with nmap
#   5. Empty dict               — JS falls back to built-in ~200-entry table

import csv
import gzip
import io
import json
import os
import re

_cache = None   # loaded once, reused for every request


# ── System file paths ──────────────────────────────────────────────────────
# Each entry: (path, format)
# Checked in order; first hit wins.

_SOURCES = [
    # Wireshark — most comprehensive, available on Linux/macOS/Windows
    ("/usr/share/wireshark/manuf",                                               "wireshark"),
    ("/usr/share/wireshark/manuf.gz",                                            "wireshark_gz"),
    ("/usr/lib/wireshark/manuf",                                                 "wireshark"),
    ("/usr/local/share/wireshark/manuf",                                         "wireshark"),
    ("/opt/homebrew/share/wireshark/manuf",                                      "wireshark"),  # macOS Homebrew
    ("/Applications/Wireshark.app/Contents/Resources/share/wireshark/manuf",    "wireshark"),  # macOS bundle
    ("C:/Program Files/Wireshark/manuf",                                         "wireshark"),  # Windows
    ("C:/Program Files (x86)/Wireshark/manuf",                                   "wireshark"),

    # ieee-data package (Debian / Ubuntu / Kali: apt install ieee-data)
    ("/usr/share/ieee-data/oui.csv",                                             "ieee_csv"),
    ("/usr/share/ieee-data/oui.txt",                                             "ieee_txt"),

    # nmap
    ("/usr/share/nmap/nmap-mac-prefixes",                                        "nmap"),
    ("/usr/local/share/nmap/nmap-mac-prefixes",                                  "nmap"),
    ("/opt/homebrew/share/nmap/nmap-mac-prefixes",                               "nmap"),       # macOS Homebrew
    ("/opt/local/share/nmap/nmap-mac-prefixes",                                  "nmap"),       # MacPorts
    ("C:/Program Files (x86)/Nmap/nmap-mac-prefixes",                            "nmap"),       # Windows
    ("C:/Program Files/Nmap/nmap-mac-prefixes",                                  "nmap"),
]


# ── Public API ─────────────────────────────────────────────────────────────

def loadOui(oui_json_path=None):
    """
    Return the OUI dict {AABBCC: "Vendor Name"}.
    Cached after first call — safe to call on every request.
    """
    global _cache
    if _cache is not None:
        return _cache

    # 1. Pre-built JSON from install.py
    if oui_json_path and os.path.isfile(oui_json_path):
        try:
            with open(oui_json_path, encoding="utf-8") as f:
                data = json.load(f)
            if data:
                _cache = data
                return _cache
        except Exception:
            pass

    # 2–4. System files
    for path, fmt in _SOURCES:
        if not os.path.isfile(path):
            continue
        try:
            data = _parse(path, fmt)
            if data:
                _cache = data
                return _cache
        except Exception:
            continue

    _cache = {}
    return _cache


def sourceInfo(oui_json_path=None):
    """
    Return a string describing which OUI source is/will be used.
    Useful for startup logging.
    """
    if oui_json_path and os.path.isfile(oui_json_path):
        size_kb = os.path.getsize(oui_json_path) // 1024
        return f"oui.json ({size_kb} KB, pre-built)"

    for path, fmt in _SOURCES:
        if os.path.isfile(path):
            size_kb = os.path.getsize(path) // 1024
            return f"{os.path.basename(path)} ({size_kb} KB, {fmt})"

    return "built-in table (~200 entries)"


# ── Parsers ────────────────────────────────────────────────────────────────

def _parse(path, fmt):
    if fmt == "wireshark_gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            return _parseWireshark(f.read())

    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    if fmt == "wireshark":
        return _parseWireshark(content)
    if fmt == "ieee_csv":
        return _parseIeeeCsv(content)
    if fmt == "ieee_txt":
        return _parseIeeeTxt(content)
    if fmt == "nmap":
        return _parseNmap(content)
    return {}


def _parseWireshark(content):
    """
    Tab-separated: prefix  short_name  [long_name]
    Lines starting with # are comments.
    Only 3-octet (6 hex char) OUI prefixes are kept.
    """
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        # prefix can be xx:xx:xx or xx:xx:xx:xx:xx:xx — skip full MACs
        oui = parts[0].replace(":", "").replace("-", "").upper()
        if len(oui) != 6:
            continue
        # prefer long name (col 3) over short name (col 2)
        vendor = (parts[2].strip() if len(parts) > 2 and parts[2].strip()
                  else parts[1].strip())
        if oui and vendor:
            result[oui] = vendor
    return result


def _parseIeeeCsv(content):
    """
    Standard IEEE MA-L CSV:
    Registry,Assignment,Organization Name,Organization Address
    MA-L,000000,XEROX CORPORATION,...
    """
    result = {}
    reader = csv.reader(io.StringIO(content))
    try:
        next(reader)    # skip header
    except StopIteration:
        return result
    for row in reader:
        if len(row) >= 3 and row[0].strip() == "MA-L":
            oui    = row[1].strip().upper()
            vendor = row[2].strip()
            if oui and vendor:
                result[oui] = vendor
    return result


def _parseIeeeTxt(content):
    """
    Old IEEE text format — OUI lines: AABBCC  (tab)  VENDOR NAME
    """
    result = {}
    for line in content.splitlines():
        m = re.match(r'^([0-9A-Fa-f]{6})\s{1,8}(.+)', line)
        if m:
            oui    = m.group(1).upper()
            vendor = m.group(2).strip()
            if oui and vendor:
                result[oui] = vendor
    return result


def _parseNmap(content):
    """
    nmap-mac-prefixes format: AABBCC Vendor Name
    """
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            oui    = parts[0].upper()
            vendor = parts[1].strip()
            if len(oui) == 6 and vendor:
                result[oui] = vendor
    return result
