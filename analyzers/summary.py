
def generateSummary(networks, anomalies):
    total = len(networks)
    if total == 0:
        return "No joy..didn\'t find any WiFi networks nearby."

    openCount = sum(1 for n in networks if n["security"].lower() == "open")
    hiddenCount = sum(1 for n in networks if not n["ssid"])
    securedCount = total - openCount
    wpsCount = sum(1 for n in networks if n.get("wps"))

    lines = []
    lines.append(f"found {total} WiFi networks nearby.")
    lines.append(f"  {securedCount} secured, {openCount} open, {hiddenCount} hidden.")

    if wpsCount:
        lines.append(f"  {wpsCount} have WPS enabled")

    if anomalies:
        highCount = sum(1 for a in anomalies if a["severity"] == "high")
        medCount = sum(1 for a in anomalies if a["severity"] == "medium")
        lowCount = sum(1 for a in anomalies if a["severity"] == "low")

        lines.append(f"\n  {len(anomalies)} things look off:")
        if highCount:
            lines.append(f"    {highCount} serious concerns")
        if medCount:
            lines.append(f"    {medCount} worth watching")
        if lowCount:
            lines.append(f"    {lowCount} minor notes")

        lines.append("")
        for a in anomalies:
            tag = a["severity"].upper()
            lines.append(f"  [{tag}] {a['message']}")
    else:
        lines.append("\n  Nothing strange detected. But check yourself...")

    return "\n".join(lines)


def generateBleSummary(devices):
    total = len(devices)
    if total == 0:
        return "No Bluetooth devices found."

    named = [d for d in devices if d["name"] != "(unknown)"]
    unnamed = total - len(named)

    lines = []
    lines.append(f"Found {total} Bluetooth devices.")

    if named:
        lines.append(f"  {len(named)} identified themselves:")
        for d in named:
            lines.append(f"    {d['name']}  ({d['address']})")

    if unnamed:
        lines.append(f"  {unnamed} are unnamed or hiding...")

    return "\n".join(lines)


def explainNetwork(ssid, networks, anomalies):
    matches = [n for n in networks if n["ssid"].lower() == ssid.lower()]

    if not matches:
        return f'We didn\'t find a network called "{ssid}" in the latest scan.'

    lines = []
    for net in matches:
        lines.append(f'Network: {net["ssid"]}')
        lines.append(f'  BSSID:    {net["bssid"]}')
        lines.append(f'  Signal:   {net["signal"]}%')
        lines.append(f'  Channel:  {net["channel"]}')
        lines.append(f'  Security: {net["security"]}')
        if net.get("wps"):
            lines.append(f'  WPS:      Enabled (known vulnerability)')

    related = [a for a in anomalies if a["ssid"].lower() == ssid.lower()]
    if related:
        lines.append("\n  Concerns:")
        for a in related:
            lines.append(f"    [{a['severity'].upper()}] {a['message']}")
    else:
        lines.append("\n  No issues found with this network.")

    return "\n".join(lines)
