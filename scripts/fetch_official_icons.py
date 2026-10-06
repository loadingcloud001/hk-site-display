"""Download the official HKO icons the gate screen uses.

Run from the repo root:  python3 scripts/fetch_official_icons.py
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "apps" / "kiosk" / "public" / "official"
WARNING_BASE = "https://www.hko.gov.hk/images/HKOWarningSymbols/"
WX_BASE = "https://www.hko.gov.hk/images/HKOWxIconOutline/"

# local file name -> HKO file name (from HKO homepage script, images/HKOWarningSymbols/)
WARNING_FILES = {
    "tc1.png": "warn800_01_tc1.png",
    "tc3.png": "warn800_02_tc3.png",
    "tc8ne.png": "warn800_03_tc08ne.png",
    "tc8nw.png": "warn800_04_tc08nw.png",
    "tc8se.png": "warn800_05_tc08se.png",
    "tc8sw.png": "warn800_06_tc08sw.png",
    "tc9.png": "warn800_07_tc09.png",
    "tc10.png": "warn800_08_tc10.png",
    "raina.png": "warn800_09_rain amber.png",
    "rainr.png": "warn800_10_rain red.png",
    "rainb.png": "warn800_11_rain black.png",
}


def fetch(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "hk-site-display icon fetch"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        data = resp.read()
    if not data.startswith(b"\x89PNG"):
        raise RuntimeError(f"{url} did not return a PNG")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"saved {dest.relative_to(ROOT)} ({len(data)} bytes)")


def main():
    for local, remote in WARNING_FILES.items():
        fetch(WARNING_BASE + urllib.parse.quote(remote), OFFICIAL / "warning" / local)
    codes = json.loads((ROOT / "config" / "wx_icons.json").read_text(encoding="utf-8"))["icons"]
    for code in codes:
        fetch(f"{WX_BASE}pic{code}.png", OFFICIAL / "wxicon" / f"pic{code}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
