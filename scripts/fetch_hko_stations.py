"""Build config/hko_stations.json: where each HKO temperature and wind station is.

Run from the repo root:
    python3 scripts/fetch_hko_stations.py           rewrite the file
    python3 scripts/fetch_hko_stations.py --check   exit 1 if the file is out of date

Coordinates come from HKO's "Information of Weather Station" page. The current weather report
(rhrread) names its stations differently, so PLACES maps each report name to a station code.

The 10-minute wind report names its stations in Chinese only. HKO's English wind report lists the same
stations in the same order, and HKO's wind page gives the code of each English name, so the script
derives every code from HKO itself and fails if WIND_PLACES no longer matches.
"""
import csv
import html
import io
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
WIND_PAGE = "https://www.hko.gov.hk/en/wxinfo/ts/display_element_ff.htm"
WIND_CSV = "https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_10min_wind_uc.csv"
WIND_CSV_EN = "https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_10min_wind.csv"

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

# 10-minute wind report station -> HKO station code (codes from WIND_PAGE, checked by derive_wind_codes).
WIND_PLACES = {
    "中環碼頭": "CP1",
    "赤鱲角": "HKA",  # Hong Kong International Airport
    "長洲": "CCH",
    "長洲泳灘": "CCB",
    "青洲": "GI",
    "香港航海學校": "HSS",  # on HKO's wind page but not on the station page, so it has no coordinates
    "啟德": "SE",
    "京士柏": "KP",
    "南丫島": "LAM",
    "流浮山": "LFS",
    "昂坪": "NGP",
    "北角": "NP",
    "坪洲": "PEN",
    "西貢": "SKG",
    "沙洲": "SC",
    "沙田": "SHA",
    "石崗": "SEK",
    "赤柱": "BHD",  # Bluff Head, which HKO's wind page calls Stanley
    "天星碼頭": "SF",
    "打鼓嶺": "TKL",
    "大美督": "PLC",
    "大埔滘": "TPK",
    "塔門": "TME",  # Tap Mun East; Tap Mun (TAP) measures temperature only
    "大老山": "TC",
    "將軍澳": "JKB",
    "青衣": "SHL",  # Shell Oil Depot, which HKO's wind page calls Tsing Yi
    "屯門": "TUN",  # Tuen Mun Government Offices
    "橫瀾島": "WGL",
    "濕地公園": "WLP",
    "黃竹坑": "HKS",
}
# Wind stations HKO lists without coordinates. They can be a site's fallback but are never "nearest".
NO_COORDINATES = {"HSS"}


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


def _station_name(cell):
    match = re.fullmatch(r"(.*?)\s*\(([A-Z0-9]+)\) \(\d\d/\d\d/\d{4}\)", cell)
    if not match:
        raise ValueError(f"unexpected station row: {cell!r}")
    name, code = match.groups()
    return re.sub(r"(?<=\S)\(", " (", name.rstrip("*").strip()), code


def parse_stations(page):
    """code -> {nameEn, lat, lon, elevation, wind, temp} for the weather and wind station tables."""
    parser = _Tables()
    parser.feed(page)
    found = {}
    # tables[1] = manned stations, tables[2] = automatic weather stations; row 0-1 are headings.
    # Columns after the elevation are wind, then air temperature.
    for table in parser.tables[1:3]:
        for row in table[2:]:
            name, code = _station_name(row[0])
            found[code] = {
                "nameEn": name,
                "lat": degrees(row[1]),
                "lon": degrees(row[2]),
                "elevation": round(float(row[3])),
                "wind": row[4] == "✔",
                "temp": row[5] == "✔",
            }
    # tables[4] = automatic wind stations: name, latitude, longitude, anemometer height above sea level.
    if not parser.tables[4][0][0].startswith("Automatic Wind Station"):
        raise ValueError("the automatic wind station table has moved")
    for row in parser.tables[4][2:]:
        name, code = _station_name(row[0])
        found.setdefault(
            code,
            {
                "nameEn": name,
                "lat": degrees(row[1]),
                "lon": degrees(row[2]),
                "elevation": round(float(row[3])),
                "wind": True,
                "temp": False,
            },
        )
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


def build_wind(found, english):
    """The wind table in WIND_PLACES order; `english` maps each report name to its English name."""
    stations = []
    for place, code in WIND_PLACES.items():
        station = found.get(code)
        if station is None and code not in NO_COORDINATES:
            raise SystemExit(f"{place}: wind station code {code} is not on {STATION_PAGE}")
        if station is not None and not station["wind"]:
            raise SystemExit(f"{place}: station {code} does not measure wind")
        stations.append(
            {
                "name": place,
                "nameEn": station["nameEn"] if station else english.get(place, ""),
                "code": code,
                "lat": station["lat"] if station else None,
                "lon": station["lon"] if station else None,
                "elevation": station["elevation"] if station else None,
            }
        )
    return stations


def _csv_rows(text):
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    return [row for row in rows[1:] if len(row) >= 2]


def derive_wind_codes():
    """(report name -> code, report name -> English name), from HKO's own wind page and reports."""
    codes = {
        html.unescape(name).strip(): code.upper()
        for code, name in re.findall(r'<option value="#([a-z0-9]+)">([^<]+)</option>', get(WIND_PAGE))
    }
    for _ in range(3):  # the two reports can straddle a 10-minute update
        tc, en = _csv_rows(get(WIND_CSV)), _csv_rows(get(WIND_CSV_EN))
        if len(tc) == len(en) and all(a[0] == b[0] for a, b in zip(tc, en)):
            break
    else:
        raise SystemExit("the Chinese and English wind reports do not line up")
    english = {a[1]: b[1] for a, b in zip(tc, en)}
    return {place: codes.get(name) for place, name in english.items()}, english


def check_wind_codes(derived):
    """Problems with WIND_PLACES against the codes HKO publishes, as text lines."""
    problems = []
    for place, code in derived.items():
        if place not in WIND_PLACES:
            problems.append(f"in the live wind report but not in WIND_PLACES: {place} ({code or 'no code on HKO wind page'})")
        elif WIND_PLACES[place] != code:
            problems.append(f"{place}: WIND_PLACES says {WIND_PLACES[place]}, HKO's wind page says {code}")
    for place in WIND_PLACES:
        if place not in derived:
            print(f"note: not in the live wind report right now: {place}")
    return problems


def report_gaps():
    """(places in the live report that PLACES lacks, places in PLACES the live report lacks)."""
    report = json.loads(get(RHRREAD))
    reported = [t["place"] for t in report["temperature"]["data"]]
    return [p for p in reported if p not in PLACES], [p for p in PLACES if p not in reported]


def main(argv):
    check = "--check" in argv
    found = parse_stations(get(STATION_PAGE))
    stations = build(found)
    new, gone = report_gaps()
    if new:
        print(f"in the live report but not in PLACES (add a station code): {', '.join(new)}")
    if gone:
        print(f"note: not in the live report right now: {', '.join(gone)}")
    derived, english = derive_wind_codes()
    wind_problems = check_wind_codes(derived)
    for line in wind_problems:
        print(line)
    wind = build_wind(found, english)
    current = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    changed = current.get("stations") != stations or current.get("windStations") != wind
    if check:
        if changed:
            print(f"{OUT.relative_to(ROOT)} differs from {STATION_PAGE}")
        ok = not new and not wind_problems and not changed
        print("up to date" if ok else "out of date")
        return 0 if ok else 1
    if wind_problems:
        return 1
    document = {
        "source": STATION_PAGE,
        "windSource": WIND_PAGE,
        "checked": date.today().isoformat(),
        "stations": stations,
        "windStations": wind,
    }
    OUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(stations)} temperature and {len(wind)} wind stations")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
