"""Fed Distributional Financial Accounts: equity holdings + household counts by
wealth percentile group, from the official dfa.zip (direct CSV URLs 404)."""

import csv
import io
import zipfile

import requests

ZIP_URL = "https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip"
DETAIL_CSV = "dfa-networth-levels-detail.csv"


def dfa_equity_by_group():
    """Return (latest_quarter, {category: {"equities_musd": x, "households": n}})."""
    resp = requests.get(ZIP_URL, timeout=120)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    name = next(n for n in zf.namelist() if n.endswith(DETAIL_CSV))
    with zf.open(name) as f:
        rows = list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

    cols = rows[0].keys()
    eq_col = next(c for c in cols if "corporate equities" in c.lower())
    hh_col = next(c for c in cols if "household count" in c.lower())
    date_col = next(c for c in cols if c.lower() in ("date", "quarter"))
    cat_col = next(c for c in cols if c.lower() == "category")

    latest = max(r[date_col] for r in rows)
    groups = {}
    for r in rows:
        if r[date_col] != latest:
            continue
        groups[r[cat_col]] = {
            "equities_musd": float(r[eq_col]),
            "households": float(r[hh_col]),
        }
    return latest, groups
