"""Fetch the latest FRED series on demand and overwrite the CSVs in data/.

Usage:
    FRED_API_KEY=<key> python3 fetch_data.py [SERIES_ID ...]

Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html.
With no arguments, all series used by train.py are refreshed. Uses only the
standard library. Missing observations are written as "." like FRED downloads.
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
SERIES = ["DRCCLACBS", "UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]
URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch(series_id, api_key):
    query = urllib.parse.urlencode(
        {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    )
    with urllib.request.urlopen(URL + "?" + query, timeout=30) as resp:
        obs = json.load(resp)["observations"]
    if not obs:
        raise ValueError(series_id + ": FRED returned no observations")
    return [(o["date"], o["value"]) for o in obs]


def write_csv(series_id, rows):
    path = DATA / (series_id + ".csv")
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", series_id])
        w.writerows(rows)
    tmp.replace(path)  # only replace the old CSV once the new one is complete
    return path


def main():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        sys.exit("Set FRED_API_KEY (free key: https://fred.stlouisfed.org/docs/api/api_key.html)")
    ids = sys.argv[1:] or SERIES
    unknown = [s for s in ids if s not in SERIES]
    if unknown:
        sys.exit("Unknown series %s; expected any of %s" % (unknown, SERIES))
    failed = False
    for sid in ids:
        try:
            rows = fetch(sid, api_key)
        except Exception as e:  # keep going so one bad series doesn't block the rest
            msg = "%s: FAILED (%s: %s)" % (sid, type(e).__name__, e)
            print(msg.replace(api_key, "***"), file=sys.stderr)
            failed = True
            continue
        write_csv(sid, rows)
        print("%s: %d rows, latest %s = %s" % (sid, len(rows), rows[-1][0], rows[-1][1]))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
