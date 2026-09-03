"""Search metadata for the War Tax pages, generated from the data snapshot.

Why this shape (same reasoning as the CPS explorer's build_schema.py):

  Article          the page as editorial: what the Prismic post already
                   carries, kept so nothing indexed is lost.
  Dataset          the substance. Google Dataset Search reads name,
                   description, variableMeasured, temporalCoverage,
                   distribution and dateModified. The old hand-written
                   Dataset froze its date range at "February-August 2026";
                   generating it here keeps coverage and figures current.
  WebApplication   the tool. Someone searching "war tax calculator" is
                   looking for a thing to use, and a Dataset alone does not
                   say the page is interactive and free.
  FAQPage          five stand-alone answers to the questions the page
                   answers. Google now limits FAQ rich results to
                   government and health sites, so this is a content and
                   entity lever, not a rich-result lever, and the questions
                   must also appear on the page as visible text.
  BreadcrumbList   site position.

The nodes are cross-linked by @id so a crawler reads one thing seen several
ways. Organization and Person are defined once and referenced.

Outputs, all produced by run.py:
  site/schema.json    the JSON-LD graph, for the Prismic post's `schema` field
  __SEO_HEAD__        title, description, canonical, Open Graph, Twitter and
                      the same JSON-LD, injected into both GitHub Pages files
                      so they point search engines at the canonical post
                      rather than competing with it.
"""
from __future__ import annotations

import html
import json

PAGE = "https://www.data4thepeople.com/p/war-tax-viz/"
SITE = "https://www.data4thepeople.com"
PUBLISHER_URL = "https://data4thepeople.com"          # house style: no www
REPO = "https://github.com/Data4ThePeople/WarTaxViz"
PAGES = "https://data4thepeople.github.io/WarTaxViz/site/"
DATA_URL = PAGES + "data.json"
SCREENSHOT = "https://data4thepeople.github.io/WarTaxViz/writeups/war-tax-viz-email.png"
LOGO = SITE + "/apple-touch-icon.png"                 # what the site itself uses
HERO = ("https://images.prismic.io/data4thepeople/"
        "WMQgaAyDuugIPVAZ_war-tax-hero-prismic.jpg")
HERO_ALT = ("Two boxers rest in their corners on a ring atop an oil tanker "
            "in the Strait of Hormuz.")
PRIOR_PIECE = SITE + "/p/iran-war-tax-v-war-windfall/"

PUBLISHED = "2026-08-14T09:00:00-04:00"
DEFAULT_TIME = "07:00:00-04:00"

TITLE = "War Tax Calculator: What the Iran War Has Cost You | Data 4 The People"
HEADLINE = "What has the war cost you? We did the math."
ALT_HEADLINE = "The War Tax, Updated: Six Months In"
DESCRIPTION = ("See your personal war tax from the 2026 Iran war: an interactive "
               "calculator weighs higher gas prices against stock market gains, "
               "and shows who's profiting.")

ORG_ID = PUBLISHER_URL + "/#organization"
PERSON_ID = SITE + "/authors/eric-pachman#person"
SITE_ID = SITE + "/#website"

KEYWORDS = [
    "war tax", "war tax calculator", "2026 Iran war", "Iran war cost",
    "cost of the Iran war", "gas prices 2026", "gasoline prices",
    "diesel prices", "grocery prices", "inflation", "S&P 500",
    "stock market gains", "wealth inequality", "top 1%", "household costs",
    "war windfall", "Data 4 The People",
]

SOURCES = [
    {
        "@type": "Dataset",
        "name": "EIA Weekly Retail Gasoline and Diesel Prices",
        "description": "U.S. Energy Information Administration weekly retail "
                       "price survey: regular gasoline, all formulations "
                       "(series EMM_EPMR_PTE_NUS_DPG plus nine state and seven "
                       "PADD-district series) and on-highway diesel "
                       "(EMD_EPD2D_PTE_NUS_DPG), 2015 to present, dollars per "
                       "gallon.",
        "url": "https://www.eia.gov/petroleum/gasdiesel/",
        "license": "https://www.eia.gov/about/copyrights_reuse.php",
        "creator": {"@type": "Organization",
                    "name": "U.S. Energy Information Administration",
                    "url": "https://www.eia.gov"},
    },
    {
        "@type": "Dataset",
        "name": "BLS Consumer Price Index, Average Price Data, and Consumer "
                "Expenditure Survey",
        "description": None,   # filled from the basket at build time
        "url": "https://www.bls.gov/cpi/",
        "license": "https://www.bls.gov/bls/linksite.htm",
        "creator": {"@type": "Organization",
                    "name": "U.S. Bureau of Labor Statistics",
                    "url": "https://www.bls.gov"},
    },
    {
        "@type": "Dataset",
        "name": "S&P 500 Index via FRED",
        "description": "Daily S&P 500 closing values from the Federal Reserve "
                       "Bank of St. Louis FRED series SP500, February 2026 to "
                       "present, used to compute the index change from its "
                       "February 27, 2026 close of 6,878.88.",
        "url": "https://fred.stlouisfed.org/series/SP500",
        "license": "https://fred.stlouisfed.org/legal/",
        "creator": {"@type": "Organization",
                    "name": "Federal Reserve Bank of St. Louis",
                    "url": "https://www.stlouisfed.org"},
    },
    {
        "@type": "Dataset",
        "name": "Federal Reserve Distributional Financial Accounts",
        "description": "Federal Reserve Board quarterly estimates of the "
                       "distribution of U.S. household wealth by percentile "
                       "group; corporate equities and mutual fund shares line "
                       "(excludes holdings through DC pensions) and household "
                       "counts per group, from the networth-levels detail file.",
        "url": "https://www.federalreserve.gov/releases/z1/dataviz/dfa/",
        "license": "https://www.federalreserve.gov/disclaimer.htm",
        "creator": {"@type": "Organization",
                    "name": "Board of Governors of the Federal Reserve System",
                    "url": "https://www.federalreserve.gov"},
    },
]

CITATIONS = [
    "U.S. Energy Information Administration, Weekly Retail Gasoline and Diesel "
    "Prices, series EMM_EPMR_PTE_NUS_DPG and EMD_EPD2D_PTE_NUS_DPG, "
    "https://www.eia.gov/petroleum/gasdiesel/",
    "U.S. Bureau of Labor Statistics, Consumer Price Index, series "
    "CUSR0000SAF11, CUSR0000SEHF01 and CUSR0000SEHF02, https://www.bls.gov/cpi/",
    "U.S. Bureau of Labor Statistics, Average Price Data (APU series), "
    "https://www.bls.gov/cpi/",
    "U.S. Bureau of Labor Statistics, Consumer Expenditure Survey 2024, "
    "https://www.bls.gov/cex/",
    "Federal Reserve Bank of St. Louis, FRED series SP500, "
    "https://fred.stlouisfed.org/series/SP500",
    "Board of Governors of the Federal Reserve System, Distributional "
    "Financial Accounts, https://www.federalreserve.gov/releases/z1/dataviz/dfa/",
    "Board of Governors of the Federal Reserve System, Survey of Consumer "
    "Finances 2022, https://www.federalreserve.gov/econres/scfindex.htm",
]


# ---------------------------------------------------------------- helpers

def _money(x: float) -> str:
    return "${:,.0f}".format(x)


def _long_date(iso: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso)
    return "{} {}, {}".format(d.strftime("%B"), d.day, d.year)


def _month(iso_month: str) -> str:
    from datetime import date
    y, m = iso_month.split("-")
    return date(int(y), int(m), 1).strftime("%B %Y")


def _pct(x: float) -> str:
    return "{:+.1f}%".format(x * 100)


# ---------------------------------------------------------------- FAQ

def faq_entries(data: dict) -> list[tuple[str, str]]:
    """Questions the page answers, with answers that stand alone.

    Written to stay true week to week: the figures that change carry an
    as-of date, and the methodology answers do not change at all.
    """
    costs = data["costs"]
    gas = data["gas"]
    mk = data["market"]
    p = data["personas"]
    asof = _long_date(gas["latest_date"])
    return [
        ("What is the War Tax?",
         "The War Tax is what the 2026 Iran war has cost an average American "
         "household in higher prices, minus what it would have paid had prewar "
         "patterns held. It counts gasoline, groceries and home energy, "
         "accumulated week by week since the first strikes on February 27, "
         "2026, and sets that cost against the after-tax stock-market gains a "
         "household has seen over the same period. As of {}, the cost side "
         "stands at {} per household, almost all of it at the pump."
         .format(asof, _money(costs["total"]))),
        ("How much has the Iran war raised gas prices?",
         "Regular gasoline went from {} a gallon the week before the war to a "
         "peak of {} on {}, and was {} in the week of {}. The War Tax "
         "compares each week's actual EIA retail price with a no-war path, "
         "the median 2015 to 2025 seasonal trajectory projected from the last "
         "prewar price, and multiplies the gap by about {:.0f} gallons a month "
         "of average household consumption. That is {} of extra gasoline "
         "spending per household so far."
         .format("${:.2f}".format(gas["baseline_price"]),
                 "${:.2f}".format(gas["peak_price"]), _long_date(gas["peak_date"]),
                 "${:.2f}".format(gas["latest_price"]), asof,
                 gas["gallons_per_month"], _money(costs["gas"]))),
        ("Who has come out ahead financially from the war?",
         "Households with money in the stock market before the war. The S&P "
         "500 has moved {} since its February 27, 2026 close, and that gain, "
         "taxed at short-term rates, dwarfs the war's household costs for "
         "anyone with substantial holdings. The average top 1% household held "
         "about {} in stocks and mutual funds outside retirement accounts; the "
         "average top 0.1% household held about {}. The median American "
         "family holds no stock outside retirement accounts, so it pays the "
         "costs and collects no offsetting gain."
         .format(_pct(mk["gain_pct"]), _money(p["top1"]["invested"]),
                 _money(p["top01"]["invested"]))),
        ("Does the War Tax calculator count 401(k)s and retirement accounts?",
         "No. The wealth-group figures use the Federal Reserve's "
         "Distributional Financial Accounts line for corporate equities and "
         "mutual fund shares held directly, which excludes pensions and "
         "401(k)s and also excludes private business equity, so it "
         "understates the wealthy's total market exposure. Gains are taxed as "
         "if realized today at short-term ordinary rates so that they are "
         "after-tax, like the costs. You can enter your own prewar holdings "
         "and tax rate to compute your personal ledger."),
        ("How often is the War Tax updated?",
         "Weekly. Gasoline and diesel follow the EIA's Monday retail price "
         "release, the S&P 500 updates through the latest trading day, and "
         "grocery and home-energy costs update when the Bureau of Labor "
         "Statistics publishes each month's Consumer Price Index. The latest "
         "figures cover gasoline through {} and the S&P 500 through {}."
         .format(asof, _long_date(mk["latest_date"]))),
    ]


def faq_html(data: dict) -> str:
    """Visible FAQ block for the full page, so the FAQPage markup is honest."""
    items = []
    for q, a in faq_entries(data):
        items.append("    <details class=\"faq-item\">\n      <summary>{}</summary>\n"
                     "      <p>{}</p>\n    </details>"
                     .format(html.escape(q), html.escape(a)))
    return ("<section class=\"faq col\" aria-labelledby=\"faq-h\">\n"
            "  <h2 id=\"faq-h\">Questions this page answers</h2>\n"
            "{}\n</section>".format("\n".join(items)))


def faq_markdown(data: dict) -> str:
    """The same FAQ as Markdown for the Prismic post.

    The importer harvests `### question?` plus a paragraph into FAQPage,
    and Google requires FAQ markup to match visible text.
    """
    out = ["## Questions this page answers", ""]
    for q, a in faq_entries(data):
        out += ["### " + q, "", a, ""]
    return "\n".join(out)


# ---------------------------------------------------------------- graph

def build_graph(data: dict) -> dict:
    costs, gas, mk = data["costs"], data["gas"], data["market"]
    food, diesel = data["food"], data["diesel"]
    modified = data["generated"] + "T" + DEFAULT_TIME
    latest = gas["latest_date"]
    basket_names = [b["name"] for b in data["basket"]]

    org = {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": "Data 4 The People",
        "url": PUBLISHER_URL,
        "logo": {"@type": "ImageObject", "url": LOGO, "width": 180, "height": 180},
        "sameAs": ["https://github.com/Data4ThePeople"],
    }
    person = {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": "Eric Pachman",
        "url": SITE + "/authors/eric-pachman",
        "worksFor": {"@id": ORG_ID},
        "sameAs": ["https://www.linkedin.com/in/eric-pachman/",
                   "https://x.com/EricPachman/",
                   "https://www.instagram.com/eric.pachman/"],
    }
    website = {
        "@type": "WebSite",
        "@id": SITE_ID,
        "name": "Data 4 The People",
        "url": SITE,
        "publisher": {"@id": ORG_ID},
    }

    # Google's Article guidance: multiple aspect ratios, each at least 1200px.
    hero = HERO + "?auto=format,compress&fit=crop&w=1200&h={}"
    images = [hero.format(675), hero.format(900), hero.format(1200)]

    sources = json.loads(json.dumps(SOURCES))
    sources[1]["description"] = (
        "Bureau of Labor Statistics monthly CPI series (seasonally adjusted "
        "food at home CUSR0000SAF11, electricity CUSR0000SEHF01, utility piped "
        "gas CUSR0000SEHF02), average retail price series for {} grocery "
        "staples ({}), and Consumer Expenditure Survey 2024 average annual "
        "household spending on gasoline, food at home, electricity and "
        "natural gas.".format(len(basket_names),
                              ", ".join(n.lower() for n in basket_names)))

    variables = [
        {"@type": "PropertyValue",
         "name": "Cumulative war-attributable household cost, total",
         "description": "Gasoline plus food at home plus home energy, versus "
                        "the no-war counterfactual, per average U.S. household "
                        "since February 27, 2026",
         "unitText": "U.S. dollars", "value": costs["total"]},
        {"@type": "PropertyValue",
         "name": "Cumulative war-attributable gasoline cost per household",
         "unitText": "U.S. dollars", "value": costs["gas"]},
        {"@type": "PropertyValue",
         "name": "Cumulative war-attributable food-at-home cost per household",
         "unitText": "U.S. dollars", "value": costs["food"]},
        {"@type": "PropertyValue",
         "name": "Cumulative war-attributable home energy cost per household",
         "unitText": "U.S. dollars", "value": costs["energy"]},
        {"@type": "PropertyValue",
         "name": "Weekly U.S. retail regular gasoline price, actual",
         "unitText": "U.S. dollars per gallon", "value": gas["latest_price"]},
        {"@type": "PropertyValue",
         "name": "Weekly U.S. retail regular gasoline price, no-war counterfactual",
         "unitText": "U.S. dollars per gallon"},
        {"@type": "PropertyValue",
         "name": "Weekly regional retail gasoline price, nine states and seven "
                 "PADD districts, actual and counterfactual",
         "unitText": "U.S. dollars per gallon"},
        {"@type": "PropertyValue",
         "name": "Weekly U.S. on-highway diesel price, actual and no-war "
                 "counterfactual",
         "unitText": "U.S. dollars per gallon", "value": diesel["latest_price"]},
        {"@type": "PropertyValue",
         "name": "Grocery staple average retail price change since February 2026",
         "description": "{} items: {}".format(len(basket_names),
                                              ", ".join(basket_names)),
         "unitText": "percent"},
        {"@type": "PropertyValue",
         "name": "CPI food at home change since February 2026",
         "unitText": "percent", "value": food["since_feb_pct"]},
        {"@type": "PropertyValue",
         "name": "S&P 500 index change since February 27, 2026",
         "unitText": "percent", "value": round(mk["gain_pct"] * 100, 2)},
        {"@type": "PropertyValue",
         "name": "After-tax stock-market gain by prewar holdings and marginal "
                 "tax rate",
         "unitText": "U.S. dollars"},
        {"@type": "PropertyValue",
         "name": "Break-even prewar investment",
         "description": "Holdings at which after-tax market gains equal the "
                        "household's war cost",
         "unitText": "U.S. dollars"},
        {"@type": "PropertyValue",
         "name": "Average corporate equities and mutual fund holdings per "
                 "household, top 1% and top 0.1%",
         "description": "Federal Reserve Distributional Financial Accounts, "
                        + data["dfa_quarter"],
         "unitText": "U.S. dollars"},
    ]

    dataset = {
        "@type": "Dataset",
        "@id": PAGE + "#dataset",
        "name": "U.S. War Tax Ledger: Household Costs vs. Stock Market Gains "
                "from the 2026 Iran War, Weekly, February 2026 to Present",
        "alternateName": ["The War Tax", "War Tax Calculator data",
                          "Iran war household cost tracker"],
        "description": (
            "Weekly ledger of war-attributable household costs versus "
            "after-tax stock-market gains since February 27, 2026, updated "
            "through {latest}. Gasoline cost is the actual EIA weekly retail "
            "price (series EMM_EPMR_PTE_NUS_DPG nationally; nine state series "
            "and seven PADD-district series for the state picker) minus a "
            "no-war counterfactual built from the median 2015 to 2025 seasonal "
            "price trajectory projected from the last prewar price, multiplied "
            "by average household consumption of about {gal:.0f} gallons a "
            "month derived from BLS Consumer Expenditure Survey 2024 gasoline "
            "spending. Grocery and home energy costs use seasonally adjusted "
            "CPI (CUSR0000SAF11 food at home; CUSR0000SEHF01 electricity; "
            "CUSR0000SEHF02 utility piped gas) against each category's "
            "trailing-12-month prewar trend, applied to CEX 2024 household "
            "spending; categories below trend count as negative cost. A "
            "grocery basket of {nb} BLS average-price staples ({basket}) is "
            "tracked from February 2026. On-highway diesel "
            "(EMD_EPD2D_PTE_NUS_DPG) is tracked as a leading indicator with "
            "the same counterfactual and excluded from the cost total. Market "
            "gains apply the S&P 500 change from its February 27, 2026 close "
            "(6,878.88, via FRED series SP500) to prewar holdings, taxed at "
            "short-term ordinary rates. Wealth-group holdings are corporate "
            "equities and mutual fund shares per household from the Federal "
            "Reserve Distributional Financial Accounts, {dfa}, which exclude "
            "pension and 401(k) holdings. As of {latest} the cumulative cost "
            "per household is {total}, of which {gascost} is gasoline; the "
            "S&P 500 is {gain} from its prewar close."
            .format(latest=_long_date(latest), gal=gas["gallons_per_month"],
                    nb=len(basket_names),
                    basket=", ".join(n.lower() for n in basket_names),
                    dfa=data["dfa_quarter"], total=_money(costs["total"]),
                    gascost=_money(costs["gas"]), gain=_pct(mk["gain_pct"]))),
        "url": PAGE,
        "sameAs": REPO,
        "license": SITE + "/terms-of-use",
        "isAccessibleForFree": True,
        "inLanguage": "en-US",
        "datePublished": PUBLISHED,
        "dateModified": modified,
        "version": latest,
        "temporalCoverage": "{}/{}".format(data["war_start"], latest),
        "spatialCoverage": {"@type": "Place", "name": "United States"},
        "measurementTechnique": (
            "Counterfactual accounting: actual weekly and monthly official "
            "prices minus a no-war projection (median 2015 to 2025 seasonal "
            "path for gasoline and diesel; trailing-12-month prewar trend for "
            "CPI categories), scaled by BLS Consumer Expenditure Survey 2024 "
            "average household consumption. Market gains are the S&P 500 "
            "change from its February 27, 2026 close, taxed at short-term "
            "ordinary rates."),
        "creator": {"@id": ORG_ID},
        "publisher": {"@id": ORG_ID},
        "keywords": KEYWORDS,
        "image": images[0],
        "variableMeasured": variables,
        "distribution": [{
            "@type": "DataDownload",
            "name": "War Tax data snapshot (JSON)",
            "description": "The weekly snapshot behind the page: gasoline, "
                           "diesel, regional gasoline, CPI, grocery basket, "
                           "S&P 500 series and wealth-group holdings, with "
                           "the computed costs. Refreshed weekly.",
            "encodingFormat": "application/json",
            "contentUrl": DATA_URL,
        }],
        "isBasedOn": sources,
        "citation": CITATIONS,
    }

    app = {
        "@type": "WebApplication",
        "@id": PAGE + "#calculator",
        "name": "War Tax Calculator",
        "alternateName": "The War Tax",
        "url": PAGE,
        "description": "Enter what you had in the stock market on February 27, "
                       "2026 and your tax rate, pick your state, and see the "
                       "2026 Iran war's cost to your household in gas, "
                       "groceries and home energy set against your after-tax "
                       "market gains, beside the median American, the top 1% "
                       "and the top 0.1%.",
        "applicationCategory": "FinanceApplication",
        "applicationSubCategory": "Data visualization",
        "operatingSystem": "Any",
        "browserRequirements": "Requires JavaScript",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "featureList": [
            "Personal war ledger: your prewar stock holdings and tax rate "
            "against your household's war-attributable costs",
            "Three households side by side: the median American, the average "
            "top 1% household and the average top 0.1% household",
            "State picker repricing gasoline for all 50 states and DC from "
            "EIA state and PADD-district series",
            "Weekly gasoline and diesel price charts, actual versus a no-war "
            "counterfactual",
            "Grocery basket of {} BLS staples tracked since February 2026"
            .format(len(basket_names)),
            "Break-even calculator: the prewar investment at which market "
            "gains cover the war's cost",
            "Updated weekly from EIA, BLS, FRED and Federal Reserve data",
        ],
        "creator": {"@id": ORG_ID},
        "provider": {"@id": ORG_ID},
        "author": {"@id": PERSON_ID},
        "inLanguage": "en-US",
        "datePublished": PUBLISHED,
        "dateModified": modified,
        "screenshot": SCREENSHOT,
        "image": images[0],
        "license": SITE + "/terms-of-use",
        "audience": {"@type": "Audience",
                     "audienceType": "The general public, journalists, "
                                     "researchers and policy analysts"},
        "about": {"@id": PAGE + "#dataset"},
        "sameAs": REPO,
        # No aggregateRating: the field means real user ratings, and the
        # tool collects none. Inventing one is a manual-action risk.
    }

    article = {
        "@type": "Article",
        "@id": PAGE + "#article",
        "headline": HEADLINE,
        "alternativeHeadline": ALT_HEADLINE,
        "description": DESCRIPTION,
        "image": images,
        "datePublished": PUBLISHED,
        "dateModified": modified,
        "articleSection": "Data 4 Thought",
        "isPartOf": {"@type": "CreativeWorkSeries", "name": "Data 4 Thought"},
        "inLanguage": "en-US",
        "isAccessibleForFree": True,
        "keywords": KEYWORDS,
        "author": {"@id": PERSON_ID},
        "publisher": {"@id": ORG_ID},
        "mainEntityOfPage": {"@id": PAGE},
        "about": [
            {"@type": "Event", "name": "2026 Iran war",
             "startDate": data["war_start"],
             "location": {"@type": "Place", "name": "Iran"}},
            {"@id": PAGE + "#dataset"},
        ],
        "mainEntity": {"@id": PAGE + "#calculator"},
        "hasPart": {"@id": PAGE + "#calculator"},
        "isBasedOn": {"@id": PAGE + "#dataset"},
        "citation": [{"@type": "Article",
                      "name": "The Iran War: A War Tax for the Average "
                              "American, a Windfall for the 1%",
                      "url": PRIOR_PIECE}],
    }

    webpage = {
        "@type": "WebPage",
        "@id": PAGE,
        "url": PAGE,
        "name": TITLE,
        "description": DESCRIPTION,
        "isPartOf": {"@id": SITE_ID},
        "about": {"@id": PAGE + "#dataset"},
        "mainEntity": {"@id": PAGE + "#article"},
        "primaryImageOfPage": {"@type": "ImageObject", "url": images[0],
                               "caption": HERO_ALT},
        "inLanguage": "en-US",
        "datePublished": PUBLISHED,
        "dateModified": modified,
        "breadcrumb": {"@id": PAGE + "#breadcrumb"},
    }

    faq = {
        "@type": "FAQPage",
        "@id": PAGE + "#faq",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq_entries(data)],
    }

    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": PAGE + "#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE},
            {"@type": "ListItem", "position": 2, "name": HEADLINE, "item": PAGE},
        ],
    }

    return {"@context": "https://schema.org",
            "@graph": [org, person, website, webpage, article, dataset, app,
                       faq, breadcrumb]}


# ---------------------------------------------------------------- head

def build_head(data: dict, graph: dict, title: str) -> str:
    """<head> metadata for a GitHub Pages copy of the page.

    Both copies canonicalize to the Prismic post so signals consolidate
    there instead of three URLs competing for the same query.
    """
    mk = data["market"]
    modified = data["generated"] + "T" + DEFAULT_TIME
    og_image = HERO + "?auto=format,compress&fit=crop&w=1200&h=630"
    e = html.escape
    lines = [
        "<title>{}</title>".format(e(title)),
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="description" content="{}">'.format(e(DESCRIPTION)),
        '<meta name="keywords" content="{}">'.format(e(", ".join(KEYWORDS))),
        '<meta name="author" content="Eric Pachman">',
        '<link rel="canonical" href="{}">'.format(PAGE),
        '<meta property="og:type" content="article">',
        '<meta property="og:title" content="{}">'.format(e(TITLE)),
        '<meta property="og:description" content="{}">'.format(e(DESCRIPTION)),
        '<meta property="og:image" content="{}">'.format(e(og_image)),
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="{}">'.format(e(HERO_ALT)),
        '<meta property="og:url" content="{}">'.format(PAGE),
        '<meta property="og:site_name" content="Data 4 The People">',
        '<meta property="og:locale" content="en_US">',
        '<meta property="article:published_time" content="{}">'.format(PUBLISHED),
        '<meta property="article:modified_time" content="{}">'.format(modified),
        '<meta property="article:section" content="Data 4 Thought">',
        '<meta property="article:author" content="Eric Pachman">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="{}">'.format(e(HEADLINE)),
        '<meta name="twitter:description" content="{}">'.format(e(DESCRIPTION)),
        '<meta name="twitter:image" content="{}">'.format(e(og_image)),
        '<meta name="twitter:image:alt" content="{}">'.format(e(HERO_ALT)),
        '<script type="application/ld+json">{}</script>'.format(
            json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")),
    ]
    return "\n".join(lines)


def schema_json(graph: dict) -> str:
    return json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
