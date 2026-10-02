"""Refresh the FRED CSVs in data/ from FRED's public CSV download (no API key).

Usage:
    python fetch_data.py                  # refresh all series
    python fetch_data.py UNRATE FEDFUNDS  # refresh only some

Each file keeps the format train.py expects: a `date,<SERIES_ID>` header, with
missing values written as `.`. Files are only replaced after the download has
been parsed and validated, so a failed fetch never clobbers existing data.
"""
import csv
import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
SERIES = ["CPIAUCSL", "DRCCLACBS", "FEDFUNDS", "UMCSENT", "UNRATE"]
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"


def fetch(series_id):
    req = urllib.request.Request(
        URL.format(series_id), headers={"User-Agent": "fintechco-demo/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")

    rows = list(csv.reader(io.StringIO(text)))
    # FRED has used both "DATE" and "observation_date" for the first column.
    if len(rows) < 2 or len(rows[0]) != 2 or rows[0][1] != series_id:
        raise ValueError(f"unexpected response for {series_id}: {text[:80]!r}")

    out = [["date", series_id]]
    for date, value in rows[1:]:
        out.append([date, value.strip() or "."])
    return out


def write(series_id, rows):
    path = DATA / f"{series_id}.csv"
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    tmp.replace(path)
    return path


def main(argv):
    ids = argv or SERIES
    unknown = [s for s in ids if s not in SERIES]
    if unknown:
        sys.exit(f"Unknown series: {', '.join(unknown)} (expected: {', '.join(SERIES)})")

    failed = []
    for sid in ids:
        try:
            rows = fetch(sid)
            write(sid, rows)
            print(f"{sid}: {len(rows) - 1} observations, latest {rows[-1][0]}")
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            print(f"{sid}: FAILED ({e})", file=sys.stderr)
            failed.append(sid)
    if failed:
        sys.exit(f"Failed to refresh: {', '.join(failed)}")


if __name__ == "__main__":
    main(sys.argv[1:])
