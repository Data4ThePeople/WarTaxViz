"""Recover pre-war Kroger shelf prices from the Wayback Machine.

Archived kroger.com product pages carry the page's server-side state as JSON, including
the regular shelf price for the crawler's default store (Kroger #310, Harrisonburg VA,
locationId 02900310). This script:

  1. builds an index of archived /p/ product URLs per brand slug via the CDX API
     (prefix queries; the whole-site query times out)   -> data/kroger/wayback_index.txt
  2. for each basket food, fetches candidate archived pages and parses price, size,
     brand and description                              -> data/kroger/wayback_prices.json

Both files are caches: rerunning skips anything already fetched.

Run:  python analysis/kroger/wayback.py [--index] [--prices] [--food KEY]
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASKET = os.path.join(ROOT, "data", "kroger", "basket.json")
INDEX = os.path.join(ROOT, "data", "kroger", "wayback_index.txt")
PRICES = os.path.join(ROOT, "data", "kroger", "wayback_prices.json")

UA = {"User-Agent": "Data4ThePeople research (eric@asaltollc.com)"}
CDX = "http://web.archive.org/cdx/search/cdx"
ANCHOR_LOCATION = "02900310"
WAR_START = "20260227"
# Baseline window: Dec 1 2025 .. Feb 26 2026 (pre-war); fallback Feb 27 .. Mar 13 (early war)
WINDOW_FROM, WINDOW_TO = "20251201", "20260313"

# Brand slugs to index. Kroger private labels first, then the national brands that carry
# the basket foods. Prefix queries return in seconds each.
BRAND_SLUGS = [
    "kroger", "simple-truth", "private-selection", "heritage-farm", "psst",
    # dairy / eggs / juice
    "eggland", "land-o-lakes", "horizon", "fairlife", "silk", "chobani", "dannon", "oikos", "fage",
    "tropicana", "simply", "minute-maid", "florida-s-natural",
    # bread / grains
    "nature-s-own", "sara-lee", "wonder", "pepperidge", "dave-s-killer", "aunt-millie",
    "mahatma", "uncle-ben", "ben-s-original", "carolina", "ancient-harvest", "bob-s-red-mill",
    # protein
    "tyson", "perdue", "foster-farms", "banquet", "just-bare", "smithfield", "hormel",
    "starkist", "bumble-bee", "chicken-of-the-sea", "gorton-s", "great-american",
    # pantry
    "jif", "skippy", "peter-pan", "bush-s", "goya", "del-monte", "green-giant", "birds-eye",
    "libby-s",
    # produce (loose produce often has no brand slug; also try generic words)
    "chiquita", "dole", "fresh-express", "bolthouse", "grimmway",
    "bananas", "banana", "russet", "potatoes", "apples", "gala", "fuji", "honeycrisp",
    "navel", "oranges", "cucumber", "tomatoes", "roma", "iceberg", "lettuce", "watermelon",
    "carrots", "broccoli", "tilapia",
]


def cdx_get(params):
    """One CDX request with long backoff; the archive answers 503 when it is busy or offline."""
    for attempt in range(7):
        status, wait = "error", 15 * (2 ** attempt)
        try:
            r = requests.get(CDX, params=params, headers=UA, timeout=180)
            if r.status_code == 200:
                return r.text
            status = r.status_code
            wait = int(r.headers.get("Retry-After", 0) or 0) or wait
        except requests.RequestException:
            pass
        print("  CDX %s, waiting %ds" % (status, wait), flush=True)
        time.sleep(min(wait, 600))
    return None


def cdx_prefix(slug, frm=WINDOW_FROM, to=WINDOW_TO):
    """All archived kroger.com/p/<slug>* URLs in the window, one row per (timestamp, url).

    CDX pages are slices of the prefix's whole history; the date filter is applied after
    paging, so a page can legitimately be empty. Iterate over the reported page count."""
    base = dict(url="kroger.com/p/%s*" % slug, **{"from": frm}, to=to)
    n = cdx_get(dict(base, showNumPages="true"))
    if n is None or not n.strip().isdigit():
        print("  ! CDX page count failed for %s" % slug)
        return []
    rows = []
    for page in range(int(n.strip())):
        text = cdx_get(dict(base, fl="timestamp,original", filter="statuscode:200", page=page))
        if text is None:
            print("  ! CDX gave up on %s page %d" % (slug, page))
            continue
        rows.extend(line.split(" ", 1) for line in text.strip().splitlines() if " " in line)
        time.sleep(0.5)
    return rows


def build_index():
    seen = set()
    if os.path.exists(INDEX):
        for line in open(INDEX):
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3:
                seen.add(parts[0])
    done_slugs = seen
    with open(INDEX, "a") as out:
        for slug in BRAND_SLUGS:
            if slug in done_slugs:
                continue
            rows = cdx_prefix(slug)
            for ts, url in rows:
                out.write("%s\t%s\t%s\n" % (slug, ts, url.strip()))
            out.flush()
            print("  %-22s %5d snapshots" % (slug, len(rows)), flush=True)
            time.sleep(1)


def load_index():
    rows = []
    for line in open(INDEX):
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


UPC_RE = re.compile(r"/p/([^/?#]+)/(\d{13})")


def parse_page(html):
    """Pull the product record out of an archived product page. Returns None if no price."""
    i = html.find('"storePrices":{"regular":{')
    if i < 0:
        return None
    reg = html[i:i + 1500]
    promo_at = reg.find('"promo":{')
    reg_only = reg if promo_at < 0 else reg[:promo_at]
    price = re.search(r'[,{]"price":"USD ([0-9.]+)"', reg_only)
    if not price:
        return None
    rec = {"regular": float(price.group(1))}
    sell = re.search(r'"sellBy":"([A-Za-z]+)"', reg)
    rec["sell_by"] = sell.group(1).upper() if sell else None
    loc = re.search(r'"sourceLocationId":"(\d+)"', reg)
    rec["location_id"] = loc.group(1) if loc else None
    eq = re.search(r'"equivalizedUnitPriceString":"([^"]+)"', reg)
    rec["unit_price_string"] = eq.group(1) if eq else None
    promo = re.search(r'[,{]"price":"USD ([0-9.]+)"', reg[promo_at:]) if promo_at >= 0 else None
    rec["promo"] = float(promo.group(1)) if promo else None
    size = re.search(r'"customerFacingSize":"([^"]+)"', html)
    rec["size"] = size.group(1) if size else None
    weight = re.search(r'"weight":"([0-9.]+) \[lb_av\]"', html)
    rec["weight_lb"] = float(weight.group(1)) if weight else None
    name = re.search(r'"@type":"Product","url":"[^"]*","name":"([^"]+)"', html)
    rec["name"] = json.loads('"%s"' % name.group(1)) if name else None
    brand = re.search(r'"brand":\{"@type":"Brand","name":"([^"]+)"', html)
    rec["brand"] = brand.group(1) if brand else None
    cat = re.search(r'"categories":\[(.{0,300}?)\]', html)
    rec["categories"] = re.findall(r'"name":"([^"]+)"', cat.group(1)) if cat else []
    return rec


def fetch_archived(ts, url):
    wb = "http://web.archive.org/web/%sid_/%s" % (ts, url)
    for attempt in range(3):
        try:
            r = requests.get(wb, headers=UA, timeout=120)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return ""
        except requests.RequestException:
            pass
        time.sleep(4 * (attempt + 1))
    return None


def candidates_for(food, index):
    """Archived (ts, url, upc) rows whose slug contains one of the food's search terms."""
    out = []
    for slug, ts, url in index:
        m = UPC_RE.search(url)
        if not m:
            continue
        name = m.group(1)
        if any(t in name for t in food["terms"]):
            out.append((ts, url.split("?")[0], m.group(2), name))
    return out


def fetch_prices(only_food=None):
    basket = json.load(open(BASKET))
    index = load_index()
    cache = json.load(open(PRICES)) if os.path.exists(PRICES) else {"pages": {}, "by_food": {}}
    pages = cache["pages"]
    for food in basket["foods"]:
        if only_food and food["key"] != only_food:
            continue
        cands = candidates_for(food, index)
        # one fetch per (upc, ts); prefer at most 4 snapshots per UPC, nearest the war start
        by_upc = {}
        for ts, url, upc, name in cands:
            by_upc.setdefault(upc, []).append((ts, url, name))
        keys = []
        for upc, snaps in by_upc.items():
            snaps.sort(key=lambda s: abs(int(s[0][:8]) - int(WAR_START)))
            for ts, url, name in snaps[:4]:
                keys.append((upc, ts, url, name))
        n_new = 0
        for upc, ts, url, name in keys:
            k = "%s@%s" % (upc, ts)
            if k in pages:
                continue
            html = fetch_archived(ts, url)
            if html is None:
                pages[k] = {"upc": upc, "ts": ts, "url": url, "slug": name, "error": "fetch failed"}
            else:
                rec = parse_page(html) or {}
                rec.update(upc=upc, ts=ts, url=url, slug=name, archive_url="http://web.archive.org/web/%s/%s" % (ts, url))
                pages[k] = rec
            n_new += 1
            if n_new % 10 == 0:
                json.dump(cache, open(PRICES, "w"), indent=1)
            time.sleep(0.5)
        priced = [p for k, p in pages.items() if p.get("regular") and p["upc"] in by_upc and p.get("location_id") == ANCHOR_LOCATION]
        cache["by_food"][food["key"]] = sorted({p["upc"] for p in priced})
        print("%-28s candidates %3d UPCs / %3d snapshots, priced UPCs %2d"
              % (food["name"], len(by_upc), len(keys), len(cache["by_food"][food["key"]])))
        json.dump(cache, open(PRICES, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--prices", action="store_true")
    ap.add_argument("--food")
    a = ap.parse_args()
    if not (a.index or a.prices):
        a.index = a.prices = True
    if a.index:
        build_index()
    if a.prices:
        fetch_prices(a.food)


if __name__ == "__main__":
    sys.exit(main())
