"""Refresh the FRED CSVs in data/ on demand.

Usage:
    python3 fetch_data.py                  # all series
    python3 fetch_data.py UNRATE FEDFUNDS  # selected series

If FRED_API_KEY is set, the official FRED API is used. Otherwise the public
fredgraph.csv endpoint is used, which needs no key. Each file keeps the
`date,<SERIES_ID>` format that train.py reads; missing values are written as ".".
Standard library only.
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def fetch_rows(series_id, api_key=None):
    """Return a list of (date, value) string pairs; missing values are ".".

    Values are kept as the strings FRED returns so existing precision is preserved.
    """
    if api_key:
        query = urllib.parse.urlencode(
            {"series_id": series_id, "api_key": api_key, "file_type": "json"}
        )
        obs = json.loads(_get(f"{API_URL}?{query}"))["observations"]
        return [(o["date"], o["value"]) for o in obs]
    text = _get(f"{GRAPH_URL}?{urllib.parse.urlencode({'id': series_id})}")
    reader = csv.reader(io.StringIO(text))
    next(reader)  # header: observation_date,<SERIES_ID>
    return [(r[0], r[1] or ".") for r in reader if len(r) >= 2]


def write_csv(series_id, rows):
    path = DATA / f"{series_id}.csv"
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", series_id])
        w.writerows(rows)
    tmp.replace(path)  # only replace the old file once the new one is fully written
    return path


def main(argv):
    wanted = [s.upper() for s in argv] or SERIES
    unknown = [s for s in wanted if s not in SERIES]
    if unknown:
        print(f"Unknown series: {', '.join(unknown)}. Choose from: {', '.join(SERIES)}")
        return 2
    api_key = os.environ.get("FRED_API_KEY")
    print(f"Source: {'FRED API' if api_key else 'fredgraph.csv (no API key)'}")
    DATA.mkdir(exist_ok=True)
    failed = []
    for s in wanted:
        try:
            rows = fetch_rows(s, api_key)
            if not rows:
                raise ValueError("empty response")
            write_csv(s, rows)
            print(f"{s}: {len(rows)} rows, latest {rows[-1][0]}")
        except Exception as e:  # keep going so one bad series doesn't block the rest
            failed.append(s)
            print(f"{s}: FAILED ({e})", file=sys.stderr)
    if failed:
        print(f"Failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("Done. Next: python3 train.py && python3 build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
