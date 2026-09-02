import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_CFG = json.loads((ROOT / "config" / "warning_priority.json").read_text(encoding="utf-8"))

HEADLINE = {
    "P0": "極端天氣：停工／勿外出",
    "P1": "極端天氣：限制戶外工作",
    "P2": "工作暑熱警告（紅／黑）",
    "P3": "工作暑熱或天氣警告生效",
    "P4": "現時無極端天氣警告",
}


def classify(hko_codes: list[str], hsww_level: str) -> dict:
    codes = set(hko_codes or [])
    if codes & set(_CFG["P0"]):
        band = "P0"
    elif codes & set(_CFG["P1"]):
        band = "P1"
    elif hsww_level in _CFG["P2_hsww"]:
        band = "P2"
    elif hsww_level in _CFG["P3_hsww"] or codes & set(_CFG["P3_hko"]):
        band = "P3"
    else:
        band = "P4"
    return {"band": band, "headlineZh": HEADLINE[band]}
