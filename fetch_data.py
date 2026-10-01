"""On-demand refresh of the FRED CSVs in data/ used by train.py.

Downloads each series from FRED's public CSV endpoint (no API key needed) and
overwrites data/<SERIES_ID>.csv, keeping the `date,<SERIES_ID>` format.
Uses only the standard library.

Usage:
    python3 fetch_data.py                 # refresh all series
    python3 fetch_data.py UNRATE FEDFUNDS # refresh selected series
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
SERIES = ["DRCCLACBS", "UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"


def fetch(series_id):
    req = urllib.request.Request(
        URL.format(series_id), headers={"User-Agent": "fintechco-demo/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    lines = text.replace("\r\n", "\n").strip().split("\n")
    # FRED's header is `observation_date,<ID>` (older: `DATE,<ID>`); normalize it.
    header = lines[0].split(",")
    if len(header) != 2 or header[1] != series_id or len(lines) < 2:
        raise ValueError(f"unexpected response for {series_id}: {lines[0][:80]!r}")
    return "\n".join([f"date,{series_id}"] + lines[1:]) + "\n"


def main(argv):
    ids = argv or SERIES
    unknown = [s for s in ids if s not in SERIES]
    if unknown:
        sys.exit(f"Unknown series: {', '.join(unknown)} (known: {', '.join(SERIES)})")

    failed = []
    for sid in ids:
        try:
            csv_text = fetch(sid)
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            print(f"{sid}: FAILED ({e})")
            failed.append(sid)
            continue
        path = DATA / f"{sid}.csv"
        old = path.read_text() if path.exists() else ""
        path.write_text(csv_text)
        n = csv_text.count("\n") - 1
        last = csv_text.strip().split("\n")[-1].split(",")[0]
        print(f"{sid}: {n} rows, latest {last}" + ("" if csv_text != old else " (unchanged)"))
    if failed:
        sys.exit(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main(sys.argv[1:])
