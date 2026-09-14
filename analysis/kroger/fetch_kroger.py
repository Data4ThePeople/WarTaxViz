"""Current shelf prices from the Kroger Products API for the frozen basket products.

Needs KROGER_CLIENT_ID and KROGER_CLIENT_SECRET in ~/.claude/d4tp-process/.env
(client-credentials grant, scope product.compact).

  python analysis/kroger/fetch_kroger.py                 price every UPC in products.json
                                                         -> data/kroger/snapshots/YYYY-MM-DD.json
  python analysis/kroger/fetch_kroger.py --search "peanut butter" [--limit 20]
                                                         live catalog search at the anchor store
  python analysis/kroger/fetch_kroger.py --upc 0001111009853   one product
  python analysis/kroger/fetch_kroger.py --location         the anchor store's details
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import date

import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.expanduser("~/.claude/d4tp-process/.env"))

PRODUCTS = os.path.join(ROOT, "data", "kroger", "products.json")
SNAPSHOTS = os.path.join(ROOT, "data", "kroger", "snapshots")
API = "https://api.kroger.com/v1"
ANCHOR_LOCATION = "02900310"   # Kroger #310, 1790 E Market St, Harrisonburg VA (default for searches)
# each frozen product carries the location_id its pre-war baseline was archived at; prices
# are always fetched from that same store
UA = "Data4ThePeople WarTax (eric@asaltollc.com)"


def token():
    cid, sec = os.environ.get("KROGER_CLIENT_ID"), os.environ.get("KROGER_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("KROGER_CLIENT_ID / KROGER_CLIENT_SECRET missing; add them to ~/.claude/d4tp-process/.env")
    auth = base64.b64encode(("%s:%s" % (cid, sec)).encode()).decode()
    r = requests.post(API + "/connect/oauth2/token",
                      headers={"Authorization": "Basic " + auth, "User-Agent": UA,
                               "Content-Type": "application/x-www-form-urlencoded"},
                      data={"grant_type": "client_credentials", "scope": "product.compact"},
                      timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def get(tok, path, params=None):
    r = requests.get(API + path, params=params, timeout=30,
                     headers={"Authorization": "Bearer " + tok, "Accept": "application/json", "User-Agent": UA})
    if r.status_code == 429:
        time.sleep(5)
        r = requests.get(API + path, params=params, timeout=30,
                         headers={"Authorization": "Bearer " + tok, "Accept": "application/json", "User-Agent": UA})
    r.raise_for_status()
    return r.json()


def flatten(p):
    """One product record from the API's shape."""
    item = (p.get("items") or [{}])[0]
    price = item.get("price") or {}
    return dict(upc=p.get("upc") or p.get("productId"), name=p.get("description"), brand=p.get("brand"),
                size=item.get("size"), sold_by=item.get("soldBy"),
                regular=price.get("regular"), promo=price.get("promo") or None,
                regular_per_unit=price.get("regularPerUnitEstimate"),
                categories=p.get("categories") or [],
                fulfillment=item.get("fulfillment") or {})


def search(tok, term, limit=20, location=ANCHOR_LOCATION):
    js = get(tok, "/products", {"filter.term": term, "filter.locationId": location, "filter.limit": limit})
    return [flatten(p) for p in js.get("data", [])]


def lookup(tok, upc, location=ANCHOR_LOCATION):
    js = get(tok, "/products", {"filter.productId": upc, "filter.locationId": location})
    data = js.get("data", [])
    return flatten(data[0]) if data else None


def snapshot(tok):
    products = json.load(open(PRODUCTS))
    today = date.today().isoformat()
    out = {"date": today, "source": "Kroger Products API v1", "prices": {}}
    missing = []
    for food in products["foods"]:
        for prod in food["products"]:
            loc = prod.get("location_id") or ANCHOR_LOCATION
            rec = lookup(tok, prod["upc"], loc)
            if rec is None or rec["regular"] is None:
                missing.append((food["key"], prod["upc"], prod.get("name")))
                out["prices"][prod["upc"]] = {"regular": None, "promo": None, "size": None, "food": food["key"], "location_id": loc}
            else:
                rec["food"] = food["key"]
                rec["location_id"] = loc
                out["prices"][prod["upc"]] = rec
            print("%-26s %-13s %-52s %s" % (food["key"], prod["upc"], (rec or {}).get("name") or prod.get("name"),
                                            "$%.2f" % rec["regular"] if rec and rec["regular"] is not None else "NO PRICE"))
            time.sleep(0.2)
    os.makedirs(SNAPSHOTS, exist_ok=True)
    path = os.path.join(SNAPSHOTS, today + ".json")
    json.dump(out, open(path, "w"), indent=1)
    print("wrote", path)
    if missing:
        print("\n%d products returned no price at the anchor store:" % len(missing))
        for m in missing:
            print("  ", m)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--upc")
    ap.add_argument("--location", action="store_true")
    a = ap.parse_args()
    tok = token()
    if a.location:
        for loc in ("02900310", "02900334"):
            print(json.dumps(get(tok, "/locations/" + loc), indent=1))
        return 0
    if a.search:
        for r in search(tok, a.search, a.limit):
            print("%-13s %-8s %-55s %-10s %s" % (r["upc"], r["sold_by"] or "", (r["name"] or "")[:55], r["size"] or "",
                                                 "$%.2f" % r["regular"] if r["regular"] is not None else "-"))
        return 0
    if a.upc:
        print(json.dumps(lookup(tok, a.upc), indent=1))
        return 0
    return snapshot(tok)


if __name__ == "__main__":
    sys.exit(main())
