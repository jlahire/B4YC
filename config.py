# change anything here to make B4YC work the way you want

# where the web interface runs (localhost only)
webPort = 8484
version = "0.2.0"
appName = "B4YC - Before You Connect"

# how long to listen for Bluetooth devices (seconds)
bleScanSeconds = 10

# SSIDs that scammers and attackers commonly use as bait
suspiciousNames = [
    "free wifi", "free internet", "xfinitywifi", "attwifi",
    "google starbucks", "default", "linksys", "netgear",
    "wifi free", "open", "public wifi", "free hotspot",
]

# shows strength of signal, if its over 90 it might be close by
suspiciousSignalFloor = 90

# substrings (case-insensitive) used to identify mobile hotspots
hotspotPatterns = [
    "hotspot", "iphone", "ipad", "androidap",
    "galaxy", "pixel", "huawei", "oneplus", "xiaomi", "oppo",
]
