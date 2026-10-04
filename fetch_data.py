"""On-demand refresh of the FRED CSVs in data/ used by train.py.

Usage:
    export FRED_API_KEY=...                 # free key from https://fred.stlouisfed.org/docs/api/api_key.html
    python3 fetch_data.py                   # refresh all default series
    python3 fetch_data.py UNRATE FEDFUNDS   # refresh only these series

Each series is written to data/<SERIES_ID>.csv with columns `date,<SERIES_ID>`;
missing values are written as `.`, matching FRED's own CSV downloads.
"""
import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
API_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_SERIES = ["DRCCLACBS", "UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]


def fetch(series_id, api_key):
    query = urllib.parse.urlencode(
        {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    )
    with urllib.request.urlopen(API_URL + "?" + query, timeout=30) as resp:
        return json.load(resp)["observations"]


def write_csv(series_id, observations):
    # CRLF terminator matches the existing files, so refreshes diff cleanly.
    with open(DATA / (series_id + ".csv"), "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\r\n")
        writer.writerow(["date", series_id])
        for obs in observations:
            writer.writerow([obs["date"], obs["value"]])


def main():
    parser = argparse.ArgumentParser(description="Refresh FRED CSVs in data/.")
    parser.add_argument(
        "series",
        nargs="*",
        help="series IDs to refresh (default: " + " ".join(DEFAULT_SERIES) + ")",
    )
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        sys.exit(
            "FRED_API_KEY is not set. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    DATA.mkdir(exist_ok=True)
    failed = []
    for series_id in args.series or DEFAULT_SERIES:
        try:
            observations = fetch(series_id, api_key)
        except urllib.error.HTTPError as e:
            # Don't print the URL: it contains the API key.
            print(series_id + ": failed (HTTP " + str(e.code) + ")", file=sys.stderr)
            failed.append(series_id)
            continue
        except (urllib.error.URLError, KeyError, ValueError) as e:
            print(series_id + ": failed (" + type(e).__name__ + ")", file=sys.stderr)
            failed.append(series_id)
            continue
        write_csv(series_id, observations)
        print(series_id + ": " + str(len(observations)) + " rows, latest " + observations[-1]["date"])
    if failed:
        sys.exit("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
