"""EIA API v2 weekly retail gasoline (primary source; FRED GASREGW is the fallback)."""

import os
from datetime import datetime

import requests

from constants import EIA_GAS_SERIES

URL = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"


def series_weekly(series_id, start):
    """One EIA weekly series as [(date, price)]."""
    key = os.environ.get("EIA_key") or os.environ.get("EIA_KEY")
    if not key:
        raise RuntimeError("EIA_key not set")
    params = {
        "api_key": key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": series_id,
        "start": start.isoformat(),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 5000,
    }
    resp = requests.get(URL, params=params, timeout=60)
    resp.raise_for_status()
    rows = resp.json()["response"]["data"]
    out = []
    for r in rows:
        if r.get("value") is None:
            continue
        d = datetime.strptime(r["period"], "%Y-%m-%d").date()
        out.append((d, float(r["value"])))
    out.sort()
    return out


def gas_weekly(start):
    return series_weekly(EIA_GAS_SERIES, start)
