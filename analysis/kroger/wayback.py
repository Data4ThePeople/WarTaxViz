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
# Stores the archive crawler priced at. Captures before about 2026-01-10 used Rio Hill;
# later ones used Harrisonburg. Every product keeps the store its baseline came from.
STORES = {
    "02900310": "Kroger #310, 1790 E Market St, Harrisonburg, VA 22801",
    "02900334": "Kroger #334 Rio Hill, 1980 Rio Hill Ctr, Charlottesville, VA 22901",
}
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
    """Raw archived page, "" if the archive has no such capture, None if it could not be reached."""
    wb = "http://web.archive.org/web/%sid_/%s" % (ts, url)
    for attempt in range(6):
        status, wait = "error", 10 * (2 ** attempt)
        try:
            r = requests.get(wb, headers=UA, timeout=120)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return ""
            status = r.status_code
            wait = int(r.headers.get("Retry-After", 0) or 0) or wait
        except requests.RequestException:
            pass
        print("  archive %s on %s, waiting %ds" % (status, url[-40:], wait), flush=True)
        time.sleep(min(wait, 600))
    return None


# Slug tokens that disqualify a candidate, globally and per food. The basket wants the
# plain form of each food (large white eggs, plain nonfat Greek yogurt, canned light tuna
# in water), not flavored, prepared, premium or non-food look-alikes.
EXCLUDE_ALL = ["organic", "cat", "dog", "kitten", "puppy", "treats", "candle", "scented", "scent",
               "lotion", "shampoo", "wash", "soap", "gummies", "candy", "toothpaste", "bar", "bars",
               "cereal", "cookie", "cookies", "seasoning", "meal", "dinner", "bowl", "kit", "soup",
               "chips", "ice-cream", "pudding", "muffin", "muffins", "cake", "pie", "protein", "smoothie"]
EXCLUDE = {
    "apples": ["sauce", "applesauce", "juice", "cider", "butter", "cinnamon", "dried", "caramel", "pouch", "pouches", "chip", "fritter"],
    "bananas": ["bread", "cream", "split", "nut", "flavored", "flavor", "instant", "dried", "plantain", "pepper", "peppers", "blueberry", "fruit", "frozen", "sliced", "strawberry", "chips"],
    "carrots": ["snack", "tray", "dip", "juice", "ranch", "celery", "broccoli", "medley", "blend", "peas"],
    "breaded_chicken": ["with", "mac", "sandwich", "buffalo", "wings", "wing", "bites", "fries", "popcorn", "dino"],
    "milk_1pct": ["chocolate", "lactose", "yogurt", "cheese", "shake", "creamer", "evaporated", "condensed", "powder", "dry", "almond", "oat", "coconut", "strawberry", "vanilla", "half"],
    "milk_2pct": ["chocolate", "lactose", "yogurt", "cheese", "shake", "creamer", "evaporated", "condensed", "powder", "dry", "almond", "oat", "coconut", "strawberry", "vanilla", "half", "cottage", "shredded", "mozzarella", "ricotta"],
    "milk_whole": ["chocolate", "lactose", "yogurt", "cheese", "shake", "creamer", "evaporated", "condensed", "powder", "dry", "almond", "oat", "coconut", "strawberry", "vanilla", "half", "cottage", "shredded", "mozzarella", "ricotta", "string"],
    "milk_skim": ["chocolate", "lactose", "yogurt", "cheese", "shake", "creamer", "evaporated", "condensed", "powder", "dry", "almond", "oat", "coconut", "strawberry", "vanilla", "half"],
    "tilapia": ["breaded", "seasoned", "battered", "fillets-with", "stuffed"],
    "potatoes": ["canned", "15oz", "whole-white", "skins", "salad", "wedges", "fries", "tots", "mashed", "hash", "sweet", "chip", "au-gratin", "scalloped", "seasoned", "roasted", "diced", "shredded", "instant", "flakes", "baby", "fingerling", "red", "gold", "yukon", "medley", "sticks"],
    "peanut_butter": ["cups", "chocolate", "chip", "pretzel", "crackers", "filled", "jelly", "sandwich", "snack", "pouch", "powder", "uncrustables", "granola", "dog", "spread-crunchy"],
    "broccoli_frozen": ["cheese", "sauce", "rice", "chicken", "stuffed", "coleslaw", "slaw", "tray", "dip", "cauliflower", "carrots", "stir-fry", "medley", "blend", "mix", "crowns", "salad", "tots", "bites"],
    "orange_juice": ["mango", "pineapple", "strawberry", "carrot", "cocktail", "drink", "soda", "sparkling", "vitamin", "cold-pressed", "frozen", "concentrate", "punch", "banana", "peach", "blend", "probiotic", "light"],
    "tuna": ["salad", "pouch", "creations", "sandwich", "flavored", "lunch", "ahi", "steak", "sushi", "poke", "oil", "albacore", "white", "solid", "yellowfin", "lemon", "pepper", "helper", "noodle"],
    "eggs": ["chocolate", "rolls", "roll", "whites", "liquid", "boiled", "substitute", "beaters", "pasture", "cage-free", "brown", "medium", "jumbo", "extra-large", "x-large", "omega", "nog", "bites", "noodles", "salad", "pickled"],
    "tomatoes": ["passata", "puree", "diced", "paste", "sauce", "ketchup", "sun-dried", "juice", "crushed", "stewed", "peeled", "fire-roasted", "pizza", "salsa", "cherry", "grape", "green", "canned", "chilies", "basil", "soup", "cocktail", "roasted", "pasta"],
    "drumsticks": ["turkey", "buffalo", "bbq", "seasoned", "cooked", "fried", "ice", "cream"],
    "lettuce": ["salad-kit", "romaine", "hearts", "leaf", "butter", "spring", "mix", "wrap", "wraps", "chopped-salad", "salad-mix", "salad"],
    "pinto_beans": ["refried", "dip", "seasoned", "chili", "salsa", "flavored", "bacon", "jalapeno"],
    "black_beans": ["refried", "dip", "seasoned", "chili", "salsa", "flavored", "burger", "burgers", "corn", "rice", "soup", "salad"],
    "pork": ["rinds", "pulled", "bbq", "sauce", "chops", "chop", "bacon", "sausage", "ground", "rib", "ribs", "cooked", "smoked", "tenderloin", "coating", "seasoned", "belly", "cutlets", "bites", "chicharrones", "carnitas", "sliders"],
    "white_bread": ["hot-dog", "hamburger", "buns", "rolls", "bagel", "bagels", "crumbs", "stuffing", "cubes", "french", "italian", "texas", "toast", "sourdough", "garlic", "dough", "mix", "flour", "sub", "hoagie", "pizza", "chocolate", "cheddar"],
    "wheat_bread": ["hot-dog", "hamburger", "buns", "rolls", "bagel", "bagels", "crumbs", "stuffing", "cubes", "french", "italian", "texas", "toast", "sourdough", "garlic", "dough", "mix", "flour", "sub", "hoagie", "pizza", "low-sodium", "thin", "thins", "tortilla", "tortillas", "pita", "english", "keto", "sprouted"],
    "quinoa": ["salad", "blend", "rice", "pasta", "flour", "cooked", "microwaveable", "ready", "crisps", "puffs", "chips", "granola", "with"],
    "oranges": ["juice", "mandarin", "mandarins", "clementine", "clementines", "cuties", "halos", "tangerine", "tangerines", "soda", "chicken", "flavored", "cream", "peel", "zest", "chocolate", "dark", "blood", "cara", "drink", "slices", "cups", "gelatin", "sherbet", "extract", "marmalade", "vitamin"],
    "cucumbers": ["pickles", "pickle", "body", "face", "mask", "water", "salad", "melon", "mint", "dill", "spears", "chips", "seltzer", "sparkling", "tea"],
    "corn_canned": ["cream", "creamed", "tortilla", "tortillas", "bread", "muffin", "dog", "dogs", "flakes", "syrup", "starch", "oil", "pops", "cob", "frozen", "chips", "nuts", "meal", "cushions", "bbq", "cornbread", "popcorn", "husks", "flour", "masa", "candy", "salsa", "relish", "roasted", "fire", "mexican", "street", "black", "beans", "dip", "chowder", "peas"],
    "chicken_breast": ["shredded", "premium", "nuggets", "patties", "patty", "strips", "tenders", "tenderloins", "breaded", "cooked", "grilled", "rotisserie", "chunk", "chunks", "pouch", "canned", "in-water", "sliced", "deli", "lunchmeat", "fajita", "seasoned", "marinated", "stuffed", "bacon", "wrapped", "cutlets", "thin", "diced", "fillets", "bites", "strips", "smoked", "oven-roasted", "buffalo", "cordon", "bone-in", "split", "with"],
    "greek_yogurt": ["blackberry", "bottom", "strawberry", "vanilla", "blueberry", "peach", "cherry", "honey", "key-lime", "mixed-berry", "raspberry", "coconut", "mango", "fruit", "chocolate", "flip", "drink", "kids", "tube", "tubes", "pouch", "whole-milk", "2", "5", "low-fat", "lowfat", "black-cherry", "lemon", "pineapple", "banana", "caramel", "cookies", "crunch", "with", "less-sugar", "zero", "triple", "toffee", "apple", "cinnamon", "pumpkin"],
    "soy_milk": ["sauce", "chocolate", "vanilla", "creamer", "yogurt", "unsweet", "unsweetened", "light", "very", "shelf", "aseptic", "protein", "nog", "cheese"],
    "watermelon": ["juice", "toothpaste", "body", "flavor", "flavored", "soda", "seltzer", "sparkling", "water", "chunks", "cubes", "spears", "cut", "seeds", "sour", "candy", "gum", "jolly", "rind", "lemonade", "popsicle", "ice", "energy", "drink", "gelatin", "jelly", "vape", "scented", "sugar"],
    "rice_white": ["instant", "microwaveable", "ready", "cooked", "jasmine", "basmati", "brown", "wild", "cake", "cakes", "krispies", "chex", "pudding", "noodles", "vinegar", "flour", "paper", "cereal", "cup", "cups", "sushi", "arborio", "fried", "pilaf", "seasoned", "mix", "a-roni", "cracker", "crackers", "milk", "drink", "chicken", "beans", "vermicelli", "spanish", "mexican", "cilantro", "lime", "coconut", "thai", "calrose", "sticky", "medium", "short", "parboiled", "boil-in-bag", "boil", "bag"],
}


# Products admitted by hand despite the exclusion rules (e.g. Silk's plain soy milk is only
# sold as organic). Food key -> UPCs.
ALLOW = {
    "soy_milk": ["0002529360023"],   # Silk Organic Unsweetened Plain Soy Milk, half gallon
}


def _contains_seq(tokens, phrase):
    ph = phrase.split("-")
    n = len(ph)
    return any(tokens[i:i + n] == ph for i in range(len(tokens) - n + 1))


def slug_matches(food, slug, upc=None):
    if upc and upc in ALLOW.get(food["key"], []):
        return True
    tokens = slug.split("-")
    if not any(_contains_seq(tokens, t) for t in food["terms"]):
        return False
    for ex in EXCLUDE_ALL + EXCLUDE.get(food["key"], []):
        if _contains_seq(tokens, ex):
            return False
    return True


def candidates_for(food, index):
    """Archived (ts, url, upc, slug) rows whose slug names the food's plain form."""
    out = []
    for slug, ts, url in index:
        m = UPC_RE.search(url)
        if not m:
            continue
        name = m.group(1)
        if slug_matches(food, name, m.group(2)):
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
            for ts, url, name in snaps[:2]:
                keys.append((upc, ts, url, name))
        n_new = 0
        for upc, ts, url, name in keys:
            k = "%s@%s" % (upc, ts)
            if k in pages:
                continue
            html = fetch_archived(ts, url)
            if html is None:
                print("  ! giving up on %s for now" % k, flush=True)
                continue
            else:
                rec = parse_page(html) or {}
                rec.update(upc=upc, ts=ts, url=url, slug=name, archive_url="http://web.archive.org/web/%s/%s" % (ts, url))
                pages[k] = rec
            n_new += 1
            if n_new % 10 == 0:
                json.dump(cache, open(PRICES, "w"), indent=1)
            time.sleep(0.5)
        priced = [p for k, p in pages.items() if p.get("regular") and p["upc"] in by_upc and p.get("location_id") in STORES]
        cache["by_food"][food["key"]] = sorted({p["upc"] for p in priced})
        print("%-28s candidates %3d UPCs / %3d snapshots, priced UPCs %2d"
              % (food["name"], len(by_upc), len(keys), len(cache["by_food"][food["key"]])), flush=True)
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
