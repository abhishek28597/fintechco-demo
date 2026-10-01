"""On-demand refresh of the FRED CSVs in data/.

Downloads each series from FRED's public CSV endpoint (no API key needed) and
rewrites data/<SERIES_ID>.csv with `date,<SERIES_ID>` columns, the format
train.py expects. Uses only the standard library. A file is only replaced
after its download has been validated, so a failed fetch never clobbers data.

Usage: python3 fetch_data.py [SERIES_ID ...]   (default: all series)
"""
import csv
import io
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
SERIES = ["DRCCLACBS", "UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="


def fetch(series_id):
    req = urllib.request.Request(URL + series_id, headers={"User-Agent": "fintechco-demo"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    # FRED's header is `observation_date,<ID>` (older: `DATE,<ID>`); require the ID column.
    if len(rows) < 2 or len(rows[0]) != 2 or rows[0][1] != series_id:
        raise ValueError(f"unexpected response for {series_id}: {text[:80]!r}")
    return [("date", series_id)] + [tuple(r) for r in rows[1:] if r]


def main(ids):
    unknown = [s for s in ids if s not in SERIES]
    if unknown:
        sys.exit(f"Unknown series: {', '.join(unknown)} (known: {', '.join(SERIES)})")
    failed = []
    for sid in ids:
        path = DATA / f"{sid}.csv"
        try:
            rows = fetch(sid)
        except Exception as exc:
            print(f"{sid}: FAILED ({exc})")
            failed.append(sid)
            continue
        old = path.read_text().count("\n") - 1 if path.exists() else 0
        with open(path, "w", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        print(f"{sid}: {len(rows) - 1} rows (was {old}), last {rows[-1][0]}")
    if failed:
        sys.exit(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main(sys.argv[1:] or SERIES)
