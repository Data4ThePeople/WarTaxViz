"""Scrape the AAA national average from gasprices.aaa.com. Decorative headline only;
fails soft (returns None) — the EIA/FRED weekly series is the numeric backbone."""

import re

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def aaa_national_average():
    try:
        resp = requests.get("https://gasprices.aaa.com/",
                            headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
        m = re.search(r"National Average\s*\$([0-9]+\.[0-9]+)", resp.text)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def aaa_state_averages():
    """Current AAA regular-gas average by state code, e.g. {"OH": 3.89}."""
    try:
        resp = requests.get("https://gasprices.aaa.com/state-gas-price-averages/",
                            headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
        rows = re.findall(
            r'state=([A-Z]{2})"[^<]*<[^$]*?class="regular"[^>]*>\$([0-9.]+)',
            resp.text, re.S)
        return {code: float(price) for code, price in rows} or None
    except Exception:
        return None
