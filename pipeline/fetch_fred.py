"""No-key FRED fredgraph.csv fetchers: S&P 500 daily, weekly retail gasoline."""

import csv
import io
from datetime import datetime

import requests

FREDGRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fred_series(series_id, start=None):
    """Return [(date, float)] for a FRED series, skipping '.' placeholders."""
    params = {"id": series_id}
    if start:
        params["cosd"] = start.isoformat()
    resp = requests.get(FREDGRAPH, params=params, timeout=60)
    resp.raise_for_status()
    text = resp.text
    if text.lstrip().startswith("<"):
        raise RuntimeError("FRED returned HTML for %s (bad series id?)" % series_id)
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        val = row[series_id]
        if val in (".", "", None):
            continue
        d = datetime.strptime(row["observation_date"], "%Y-%m-%d").date()
        out.append((d, float(val)))
    return out


def sp500_daily(start):
    return fred_series("SP500", start)


def gas_weekly(start):
    """FRED GASREGW == EIA EMM_EPMR_PTE_NUS_DPG, weekly, Monday-dated."""
    return fred_series("GASREGW", start)
