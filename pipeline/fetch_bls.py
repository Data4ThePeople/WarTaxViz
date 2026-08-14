"""BLS API v2 multi-series fetch for CPI and Average Price (APU) series."""

import json
import os

import requests

URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def bls_series(series_ids, start_year, end_year):
    """Return {series_id: {(year, month): value}}.

    Skips non-numeric values — Oct 2025 is a known hole (value "-", footnote X,
    2025 lapse in appropriations).
    """
    payload = {
        "seriesid": list(series_ids),
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    key = os.environ.get("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key
    resp = requests.post(URL, json=payload,
                         headers={"Content-Type": "application/json"}, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError("BLS API: %s" % json.dumps(body.get("message")))
    out = {}
    for series in body["Results"]["series"]:
        points = {}
        for item in series["data"]:
            period = item["period"]  # M01..M12; M13 = annual average
            if not period.startswith("M") or period == "M13":
                continue
            try:
                val = float(item["value"])
            except ValueError:
                continue
            points[(int(item["year"]), int(period[1:]))] = val
        out[series["seriesID"]] = points
    return out
