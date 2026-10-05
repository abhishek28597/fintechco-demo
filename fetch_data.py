"""On-demand refresh of the FRED CSVs in data/ used by train.py.

Usage:
    python3 fetch_data.py                  # refresh all series
    python3 fetch_data.py UNRATE FEDFUNDS  # refresh selected series

If FRED_API_KEY is set, the official FRED API is used. Otherwise the public
fredgraph.csv endpoint is used, which needs no key. Files keep the
`date,<SERIES_ID>` format, and a file is only rewritten after a successful,
non-empty download. Uses only the standard library.
"""
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
SERIES = ["DRCCLACBS", "UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]
API_URL = "https://api.stlouisfed.org/fred/series/observations"
GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "fintechco-demo/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch(series_id, api_key):
    """Return [(date, value)] rows; missing values are '.' as in FRED CSVs."""
    if api_key:
        qs = urllib.parse.urlencode(
            {"series_id": series_id, "api_key": api_key, "file_type": "json"}
        )
        obs = json.loads(_get(API_URL + "?" + qs))["observations"]
        return [(o["date"], o["value"]) for o in obs]
    text = _get(GRAPH_URL + "?" + urllib.parse.urlencode({"id": series_id}))
    reader = csv.reader(io.StringIO(text))
    next(reader)  # header name varies by endpoint version, so ignore it
    return [(r[0], r[1]) for r in reader if len(r) >= 2]


def write(series_id, rows):
    with (DATA / (series_id + ".csv")).open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", series_id])
        w.writerows(rows)


def main(argv):
    ids = argv or SERIES
    unknown = [s for s in ids if s not in SERIES]
    if unknown:
        print("Unknown series: %s (known: %s)" % (", ".join(unknown), ", ".join(SERIES)))
        return 2
    api_key = os.environ.get("FRED_API_KEY")
    print("Source:", "FRED API" if api_key else "fredgraph.csv (no API key)")
    DATA.mkdir(exist_ok=True)
    failed = 0
    for sid in ids:
        try:
            rows = fetch(sid, api_key)
            if not rows:
                raise ValueError("no observations returned")
            write(sid, rows)
            print("%s: %d rows, latest %s" % (sid, len(rows), rows[-1][0]))
        except Exception as e:  # keep going so one bad series doesn't block the rest
            failed += 1
            print("%s: FAILED (%s); existing file left unchanged" % (sid, e))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
