"""Build config/hko_stations.json: where each HKO temperature station is.

Run from the repo root:
    python3 scripts/fetch_hko_stations.py           rewrite the file
    python3 scripts/fetch_hko_stations.py --check   exit 1 if the file is out of date

Coordinates come from HKO's "Information of Weather Station" page. The current weather report
(rhrread) names its stations differently, so PLACES maps each report name to a station code.
"""
import json
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "hko_stations.json"
STATION_PAGE = "https://www.hko.gov.hk/en/cis/stn.htm"
RHRREAD = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc"

# rhrread temperature `place` -> HKO station code (stn.htm). Only stations that measure air temperature.
PLACES = {
    "京士柏": "KP",
    "香港天文台": "HKO",
    "黃竹坑": "HKS",
    "打鼓嶺": "TKL",
    "流浮山": "LFS",
    "大埔": "YCT",  # Tai Po (Yuen Chau Tsai Park); the station moved there on 2022-04-01
    "沙田": "SHA",
    "屯門": "TU1",  # Tuen Mun Children and Juvenile Home; Tuen Mun Government Offices (TUN) is wind only
    "將軍澳": "JKB",
    "西貢": "SKG",
    "長洲": "CCH",
    "赤鱲角": "HKA",  # Hong Kong International Airport
    "青衣": "TY1",  # New Tsing Yi Station; Ching Pak House (CPH) measures no air temperature
    "石崗": "SEK",
    "荃灣可觀": "TWN",  # "Tsuen Wan", opened 2006-04-25 with the Ho Koon centre; the other one is 城門谷
    "荃灣城門谷": "TW",
    "香港公園": "HKP",
    "筲箕灣": "SKW",
    "九龍城": "KLT",
    "跑馬地": "HPV",
    "黃大仙": "WTS",
    "赤柱": "STY",
    "觀塘": "KTG",
    "深水埗": "SSP",
    "啟德跑道公園": "SE1",
    "元朗公園": "YLP",
    "大美督": "PLC",
}


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._table, self._row, self._cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "hk-site-display station fetch"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        return resp.read().decode("utf-8")


def degrees(dms):
    match = re.fullmatch(r"(\d+)°(\d+)'(\d+)\"", dms)
    if not match:
        raise ValueError(f"not a DMS coordinate: {dms!r}")
    d, m, s = map(int, match.groups())
    return round(d + m / 60 + s / 3600, 5)


def parse_stations(page):
    """code -> {nameEn, lat, lon, temp} for the manned and automatic weather station tables."""
    parser = _Tables()
    parser.feed(page)
    found = {}
    # tables[1] = manned stations, tables[2] = automatic weather stations; row 0-1 are headings.
    # Columns after the elevation are wind, then air temperature.
    for table in parser.tables[1:3]:
        for row in table[2:]:
            match = re.fullmatch(r"(.*?)\s*\(([A-Z0-9]+)\) \(\d\d/\d\d/\d{4}\)", row[0])
            if not match:
                raise ValueError(f"unexpected station row: {row[0]!r}")
            name, code = match.groups()
            name = re.sub(r"(?<=\S)\(", " (", name.rstrip("*").strip())
            found[code] = {
                "nameEn": name,
                "lat": degrees(row[1]),
                "lon": degrees(row[2]),
                "temp": row[5] == "✔",
            }
    return found


def build(found):
    stations = []
    for place, code in PLACES.items():
        station = found.get(code)
        if station is None:
            raise SystemExit(f"{place}: station code {code} is not on {STATION_PAGE}")
        if not station["temp"]:
            raise SystemExit(f"{place}: station {code} does not measure air temperature")
        stations.append(
            {"name": place, "nameEn": station["nameEn"], "code": code, "lat": station["lat"], "lon": station["lon"]}
        )
    return stations


def report_gaps():
    """(places in the live report that PLACES lacks, places in PLACES the live report lacks)."""
    report = json.loads(get(RHRREAD))
    reported = [t["place"] for t in report["temperature"]["data"]]
    return [p for p in reported if p not in PLACES], [p for p in PLACES if p not in reported]


def main(argv):
    check = "--check" in argv
    stations = build(parse_stations(get(STATION_PAGE)))
    new, gone = report_gaps()
    if new:
        print(f"in the live report but not in PLACES (add a station code): {', '.join(new)}")
    if gone:
        print(f"note: not in the live report right now: {', '.join(gone)}")
    current = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    changed = current.get("stations") != stations
    if check:
        if changed:
            print(f"{OUT.relative_to(ROOT)} differs from {STATION_PAGE}")
        ok = not new and not changed
        print("up to date" if ok else "out of date")
        return 0 if ok else 1
    document = {"source": STATION_PAGE, "checked": date.today().isoformat(), "stations": stations}
    OUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(stations)} stations")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
