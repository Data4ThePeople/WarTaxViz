"""Build the fixed grocery basket from the USDA Thrifty Food Plan, 2021.

Reads data/tfp/TFP-2021-Disaggregated-Market-Basket.xlsx (USDA FNS, the quantities
and costs of every food in the TFP market basket, reference family of four, June 2021
prices) with the standard library only, writes:

  data/tfp/tfp2021_disaggregated.json   every row (EC, description, form, category,
                                        lbs/week and $/week for the reference family)
  data/kroger/basket.json               the ~32 foods we price at Kroger, with their
                                        TFP quantity weights and unit rules

Run:  python analysis/kroger/tfp_basket.py
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XLSX = os.path.join(ROOT, "data", "tfp", "TFP-2021-Disaggregated-Market-Basket.xlsx")
OUT_ALL = os.path.join(ROOT, "data", "tfp", "tfp2021_disaggregated.json")
OUT_BASKET = os.path.join(ROOT, "data", "kroger", "basket.json")

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Pounds per retail unit, for turning a shelf price into a price per pound.
LB_PER_GALLON_MILK = 8.6          # USDA: a gallon of milk weighs about 8.6 lb
LB_PER_FL_OZ_JUICE = 8.7 / 128.0  # orange juice, about 1.04 g/mL
LB_PER_DOZEN_LARGE_EGGS = 1.5     # 12 large eggs, 24 oz net

# The basket. Each food maps to one or more TFP ensemble codes (EC) whose quantities are
# summed. "unit" is the basis the Kroger unit price is normalized to before averaging.
# "terms" are slug fragments used to find archived / live Kroger products.
BASKET = [
    dict(key="wheat_bread", name="Whole wheat bread", ecs=["51300110", "51301010"], unit="lb",
         note="TFP whole wheat + wheat/cracked wheat bread", terms=["wheat-bread"]),
    dict(key="apples", name="Apples", ecs=["9003"], unit="lb", terms=["apples", "gala", "fuji", "honeycrisp", "red-delicious", "granny-smith"]),
    dict(key="carrots", name="Carrots", ecs=["11124"], unit="lb", terms=["carrots"]),
    dict(key="breaded_chicken", name="Frozen breaded chicken", ecs=["24127202", "22974", "24198671"], unit="lb",
         note="TFP breaded chicken breast + nuggets + patties", terms=["chicken-nuggets", "chicken-patties", "chicken-strips", "chicken-tenders", "breaded-chicken", "crispy-chicken"]),
    dict(key="milk_1pct", name="Milk, 1%", ecs=["11112210"], unit="lb", lb_per_unit=("gallon", LB_PER_GALLON_MILK), terms=["1-lowfat-milk", "1-low-fat-milk", "1-milk", "lowfat-milk"]),
    dict(key="tilapia", name="Tilapia fillets", ecs=["15261"], unit="lb", terms=["tilapia"]),
    dict(key="potatoes", name="Potatoes", ecs=["11352"], unit="lb", terms=["russet-potatoes", "potatoes"]),
    dict(key="peanut_butter", name="Peanut butter", ecs=["42202000"], unit="lb", terms=["peanut-butter"]),
    dict(key="broccoli_frozen", name="Broccoli, frozen", ecs=["11092"], unit="lb", terms=["broccoli-florets", "broccoli-cuts", "frozen-broccoli", "broccoli"]),
    dict(key="orange_juice", name="Orange juice", ecs=["61210220"], unit="lb", lb_per_unit=("fl oz", LB_PER_FL_OZ_JUICE), terms=["orange-juice"]),
    dict(key="milk_skim", name="Milk, skim", ecs=["11113000"], unit="lb", lb_per_unit=("gallon", LB_PER_GALLON_MILK), terms=["skim-milk", "fat-free-milk"]),
    dict(key="tuna", name="Tuna, canned light", ecs=["15121"], unit="lb", terms=["chunk-light-tuna", "light-tuna", "tuna-in-water"]),
    dict(key="bananas", name="Bananas", ecs=["9040"], unit="lb", terms=["bananas", "banana"]),
    dict(key="eggs", name="Eggs, large", ecs=["1123"], unit="lb", lb_per_unit=("dozen", LB_PER_DOZEN_LARGE_EGGS), terms=["large-eggs", "large-white-eggs", "grade-a-eggs", "eggs"]),
    dict(key="milk_2pct", name="Milk, 2%", ecs=["11112110"], unit="lb", lb_per_unit=("gallon", LB_PER_GALLON_MILK), terms=["2-reduced-fat-milk", "reduced-fat-milk", "2-milk"]),
    dict(key="tomatoes", name="Tomatoes", ecs=["11529"], unit="lb", terms=["roma-tomatoes", "vine-tomatoes", "tomatoes-on-the-vine", "tomatoes", "tomato"]),
    dict(key="drumsticks", name="Chicken drumsticks", ecs=["5069"], unit="lb", terms=["drumsticks"]),
    dict(key="milk_whole", name="Milk, whole", ecs=["11111000"], unit="lb", lb_per_unit=("gallon", LB_PER_GALLON_MILK), terms=["whole-milk", "vitamin-d-milk"]),
    dict(key="lettuce", name="Lettuce, iceberg", ecs=["11252"], unit="lb", terms=["iceberg-lettuce", "iceberg"]),
    dict(key="pinto_beans", name="Pinto beans, canned", ecs=["41104020"], unit="lb", note="TFP weight is cooked; canned net weight used", terms=["pinto-beans"]),
    dict(key="pork", name="Pork loin / roast / shoulder", ecs=["22400110", "10020", "10080"], unit="lb",
         note="TFP pork roast + fresh loin + shoulder", terms=["pork-loin", "pork-roast", "pork-shoulder", "boston-butt", "pork-sirloin"]),
    dict(key="white_bread", name="White bread", ecs=["51101000"], unit="lb", terms=["white-bread", "sandwich-bread"]),
    dict(key="quinoa", name="Quinoa", ecs=["20137"], unit="lb", note="TFP weight is cooked; dry weight used", terms=["quinoa"]),
    dict(key="oranges", name="Oranges", ecs=["9200"], unit="lb", terms=["navel-oranges", "oranges"]),
    dict(key="cucumbers", name="Cucumbers", ecs=["11205"], unit="lb", terms=["cucumber"]),
    dict(key="corn_canned", name="Corn, canned", ecs=["11172"], unit="lb", terms=["whole-kernel-corn", "sweet-corn", "golden-corn"]),
    dict(key="chicken_breast", name="Chicken breast, boneless", ecs=["5062"], unit="lb", terms=["boneless-skinless-chicken-breast", "chicken-breast"]),
    dict(key="greek_yogurt", name="Greek yogurt, plain nonfat", ecs=["11411420"], unit="lb", terms=["plain-nonfat-greek-yogurt", "nonfat-plain-greek-yogurt", "plain-greek-yogurt", "greek-yogurt"]),
    dict(key="soy_milk", name="Soy milk", ecs=["11320000"], unit="lb", lb_per_unit=("fl oz", LB_PER_FL_OZ_JUICE), terms=["soymilk", "soy-milk"]),
    dict(key="watermelon", name="Watermelon", ecs=["9326"], unit="lb", terms=["watermelon"]),
    dict(key="black_beans", name="Black beans, canned", ecs=["41102020"], unit="lb", note="TFP weight is cooked; canned net weight used", terms=["black-beans"]),
    dict(key="rice_white", name="Rice, white long grain", ecs=["20044"], unit="lb", terms=["long-grain-white-rice", "white-rice", "enriched-rice"]),
]


def read_sheet(path):
    z = zipfile.ZipFile(path)
    shared = [
        "".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)
    ]
    root = ET.fromstring(z.read("xl/worksheets/sheet3.xml"))  # "Disaggregated Market Basket"
    rows = []
    for row in root.iter("{%s}row" % NS["m"]):
        vals = {}
        for c in row.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find("m:v", NS)
            if v is None:
                vals[col] = ""
            elif c.get("t") == "s":
                vals[col] = shared[int(v.text)]
            else:
                vals[col] = v.text
        rows.append(vals)
    header = rows[0]
    assert header["A"] == "EC" and header["F"] == "amount_reffam" and header["G"] == "cost_reffam", header
    items = []
    for r in rows[1:]:
        try:
            lbs, cost = float(r.get("F") or 0), float(r.get("G") or 0)
        except ValueError:
            continue
        items.append(dict(ec=r["A"], desc=r["B"], form=r["C"], form_desc=r["D"],
                          category=r["E"], lbs_week=lbs, cost_week=cost))
    return items


def main():
    items = read_sheet(XLSX)
    total_cost = sum(i["cost_week"] for i in items)
    total_lbs = sum(i["lbs_week"] for i in items)
    with open(OUT_ALL, "w") as f:
        json.dump({"source": "USDA FNS, Thrifty Food Plan, 2021: Disaggregated Market Basket (reference family of four, June 2021 prices)",
                   "url": "https://www.fna.usda.gov/cnpp/thrifty-food-plan-2021",
                   "total_cost_week": round(total_cost, 4), "total_lbs_week": round(total_lbs, 4),
                   "items": items}, f, indent=0)
    print("TFP rows %d, nonzero %d, reference family $%.2f/wk, %.1f lb/wk"
          % (len(items), sum(1 for i in items if i["cost_week"] > 0), total_cost, total_lbs))

    by_ec = defaultdict(lambda: dict(lbs=0.0, cost=0.0, desc="", category=""))
    for i in items:
        e = by_ec[i["ec"]]
        e["lbs"] += i["lbs_week"]; e["cost"] += i["cost_week"]
        e["desc"] = i["desc"]; e["category"] = i["category"]

    basket, covered = [], 0.0
    print("\n%-3s %-32s %7s %8s %6s" % ("#", "food", "lb/wk", "TFP$/wk", "share"))
    for n, food in enumerate(BASKET, 1):
        lbs = sum(by_ec[ec]["lbs"] for ec in food["ecs"])
        cost = sum(by_ec[ec]["cost"] for ec in food["ecs"])
        for ec in food["ecs"]:
            assert ec in by_ec, "unknown EC %s for %s" % (ec, food["key"])
        covered += cost
        row = dict(food)
        row.update(lbs_week=round(lbs, 4), tfp_cost_week=round(cost, 4),
                   tfp_share=round(cost / total_cost, 4),
                   tfp_desc=[by_ec[ec]["desc"] for ec in food["ecs"]],
                   category=by_ec[food["ecs"][0]]["category"])
        basket.append(row)
        print("%-3d %-32s %7.2f %8.2f %5.1f%%" % (n, food["name"], lbs, cost, cost / total_cost * 100))
    print("\nbasket: %d foods, %.2f lb/wk, $%.2f/wk of $%.2f (%.1f%% of TFP dollars)"
          % (len(basket), sum(b["lbs_week"] for b in basket), covered, total_cost, covered / total_cost * 100))

    with open(OUT_BASKET, "w") as f:
        json.dump({"source": "Foods chosen by weekly cost share in the TFP 2021 reference-family basket; quantities are TFP pounds per week",
                   "reference_family": "Male and female 20-50, children 6-8 and 9-11 (USDA TFP reference family)",
                   "tfp_total_cost_week": round(total_cost, 4),
                   "covered_cost_week": round(covered, 4),
                   "coverage_share": round(covered / total_cost, 4),
                   "lb_per_gallon_milk": LB_PER_GALLON_MILK,
                   "lb_per_fl_oz_juice": LB_PER_FL_OZ_JUICE,
                   "lb_per_dozen_eggs": LB_PER_DOZEN_LARGE_EGGS,
                   "foods": basket}, f, indent=1)
    print("wrote", OUT_ALL, "and", OUT_BASKET)


if __name__ == "__main__":
    sys.exit(main())
