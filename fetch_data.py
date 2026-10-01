"""On-demand FRED data refresh for the FinTechCo demo dashboard.

Downloads the full history of each series from the FRED API and rewrites the
CSVs in data/ (same file names, `date,<SERIES_ID>` columns) used by train.py.

Usage:
    export FRED_API_KEY=...   # free key: https://fredaccount.stlouisfed.org/apikeys
    python fetch_data.py [SERIES_ID ...]
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
SERIES = ["DRCCLACBS", "UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]
API_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch(series_id, api_key):
    query = urllib.parse.urlencode(
        {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    )
    with urllib.request.urlopen(f"{API_URL}?{query}", timeout=30) as resp:
        obs = json.load(resp)["observations"]
    df = pd.DataFrame(obs)[["date", "value"]]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # "." -> NaN
    df = df.dropna().rename(columns={"value": series_id})
    if df.empty:
        raise ValueError(f"FRED returned no observations for {series_id}")
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("series", nargs="*", default=SERIES, help="series IDs (default: all)")
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        sys.exit("Set FRED_API_KEY (free key: https://fredaccount.stlouisfed.org/apikeys)")

    # Fetch everything first so a failure doesn't leave the CSVs half-updated.
    frames = {}
    for sid in args.series:
        try:
            frames[sid] = fetch(sid, api_key)
        except (urllib.error.URLError, ValueError, KeyError) as e:
            sys.exit(f"Failed to fetch {sid}: {e}")

    DATA.mkdir(exist_ok=True)
    for sid, df in frames.items():
        df.to_csv(DATA / f"{sid}.csv", index=False)
        print(f"{sid}: {len(df)} rows, {df['date'].iloc[0]} to {df['date'].iloc[-1]}")


if __name__ == "__main__":
    main()
