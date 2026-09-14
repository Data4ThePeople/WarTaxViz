"""UPC-driven pre-war baseline lookup.

For each basket food: search the live Kroger catalog at the anchor store, keep the
plain-form products (same slug rules as wayback.py), build each product's kroger.com
URL from its name and UPC, ask the Wayback CDX index for captures of that exact URL in
the Dec 1 2025 to Mar 13 2026 window, fetch the capture nearest Feb 27 and parse its
price. Results land in the same cache as wayback.py (data/kroger/wayback_prices.json).

Run:  python analysis/kroger/find_baselines.py [--food KEY] [--per-food 8]
"""

import argparse
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_kroger
import wayback

BASKET = os.path.join(ROOT, "data", "kroger", "basket.json")
PRICES = wayback.PRICES


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower())
    return s.strip("-")


def cdx_captures(slug, upc):
    """(ts, url) captures of this product's page in the window; exact slug first, then a
    short prefix filtered by UPC in case Kroger's slug differs from the name."""
    base = {"from": wayback.WINDOW_FROM, "to": wayback.WINDOW_TO, "fl": "timestamp,original", "filter": "statuscode:200"}
    text = wayback.cdx_get(dict(base, url="kroger.com/p/%s/%s" % (slug, upc)))
    rows = [l.split(" ", 1) for l in (text or "").strip().splitlines() if " " in l]
    if not rows:
        prefix = "-".join(slug.split("-")[:3])
        text = wayback.cdx_get(dict(base, url="kroger.com/p/%s*" % prefix))
        rows = [l.split(" ", 1) for l in (text or "").strip().splitlines() if " " in l and "/%s" % upc in l]
    return [(ts, url.split("?")[0]) for ts, url in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--food")
    ap.add_argument("--per-food", type=int, default=8)
    a = ap.parse_args()
    basket = json.load(open(BASKET))
    cache = json.load(open(PRICES)) if os.path.exists(PRICES) else {"pages": {}, "by_food": {}}
    pages = cache["pages"]
    tok = fetch_kroger.token()
    for food in basket["foods"]:
        if a.food and food["key"] != a.food:
            continue
        seen, cands = set(), []
        for term in food["terms"][:4]:
            try:
                hits = fetch_kroger.search(tok, term.replace("-", " "), 30)
            except Exception as e:  # noqa: BLE001
                print("  search failed for %r: %s" % (term, e), flush=True)
                continue
            for h in hits:
                if h["upc"] in seen or h["regular"] is None:
                    continue
                slug = slugify(h["name"])
                if not wayback.slug_matches(food, slug, h["upc"]):
                    continue
                seen.add(h["upc"])
                cands.append((h, slug))
            time.sleep(0.2)
        cands = cands[:a.per_food]
        n_priced = 0
        for h, slug in cands:
            already = [p for k, p in pages.items() if p["upc"] == h["upc"] and p.get("regular")]
            if already:
                n_priced += 1
                continue
            caps = cdx_captures(slug, h["upc"])
            caps.sort(key=lambda c: abs(int(c[0][:8]) - int(wayback.WAR_START)))
            got = False
            for ts, url in caps[:3]:
                k = "%s@%s" % (h["upc"], ts)
                if k in pages:
                    if pages[k].get("regular"):
                        got = True
                        break
                    continue
                html = wayback.fetch_archived(ts, url)
                if html is None:
                    continue
                rec = wayback.parse_page(html) or {}
                m = wayback.UPC_RE.search(url)
                rec.update(upc=h["upc"], ts=ts, url=url, slug=m.group(1) if m else slug,
                           archive_url="http://web.archive.org/web/%s/%s" % (ts, url))
                pages[k] = rec
                wayback.save_cache(cache)
                if rec.get("regular"):
                    got = True
                    break
                time.sleep(0.5)
            n_priced += got
            print("  %-13s %-52s now $%5.2f  captures %d  %s" % (h["upc"], (h["name"] or "")[:52], h["regular"], len(caps),
                                                                 "PRE-WAR PRICE" if got else "-"), flush=True)
        print("%-28s live candidates %2d, with pre-war price %2d" % (food["name"], len(cands), n_priced), flush=True)
        wayback.save_cache(cache)


if __name__ == "__main__":
    sys.exit(main())
