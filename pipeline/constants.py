"""Hard-coded constants with citations. Everything else is fetched live."""

from datetime import date

# The war: US/Israel strikes on Iran began Feb 27-28, 2026 (US time).
WAR_START = date(2026, 2, 27)

# S&P 500 close on the last pre-war trading day (FRED SP500; sanity-asserted in compute.py).
SP500_BASE_DATE = date(2026, 2, 27)
SP500_BASE_EXPECTED = 6878.88

# --- BLS Consumer Expenditure Survey, 2024 (average annual $ per consumer unit) ---
# Food at home / electricity / natural gas verified via FRED CXUFOODHOMELB0101M,
# CXUELECTRICLB0101M, CXUNATRLGASLB0101M (2024 observations). Gasoline from the
# BLS CE 2024 news release (FRED's CXUGASOILLB0101M 2023-24 rows are corrupt).
CEX_FOOD_AT_HOME_ANNUAL = 6224.0
CEX_GASOLINE_ANNUAL = 2411.0
CEX_ELECTRICITY_ANNUAL = 1833.0
CEX_NATURAL_GAS_ANNUAL = 493.0

# --- Fed Survey of Consumer Finances, 2022 (2025 SCF publishes late 2026) ---
# "Changes in U.S. Family Finances 2019-2022", Table 3. Directly held = non-retirement.
SCF_PCT_FAMILIES_DIRECT_STOCK = 0.21
SCF_MEDIAN_DIRECT_STOCK_HOLDERS = 15000.0  # conditional median, holders only
SCF_MEDIAN_DIRECT_STOCK_ALL = 0.0          # median family holds none directly

# Short-term gains = ordinary income. Approximate marginal rates by persona.
TAX_RATES = {
    "you": 0.22,      # default for the slider persona
    "median": 0.22,
    "top1": 0.35,
    "top01": 0.408,   # 37% top bracket + 3.8% net investment income tax
}

# --- BLS series IDs (all verified live through Jul 2026) ---
CPI_SERIES = {
    "food_sa": "CUSR0000SAF11",       # CPI food at home, seasonally adjusted
    "food_nsa": "CUUR0000SAF11",      # NSA fallback
    "electricity_sa": "CUSR0000SEHF01",
    "electricity_nsa": "CUUR0000SEHF01",
    "gas_utility_sa": "CUSR0000SEHF02",
    "gas_utility_nsa": "CUUR0000SEHF02",
}

BASKET_SERIES = [
    ("APU0000708111", "Eggs", "dozen"),
    ("APU0000709112", "Whole milk", "gallon"),
    ("APU0000702111", "White bread", "lb"),
    ("APU0000703112", "Ground beef", "lb"),
    ("APU0000FF1101", "Chicken breast", "lb"),
    ("APU0000717311", "Ground coffee", "lb"),
]

# Weekly US regular retail gasoline (EIA series; FRED mirrors it as GASREGW).
EIA_GAS_SERIES = "EMM_EPMR_PTE_NUS_DPG"

# Weekly US on-highway diesel (EIA; FRED mirrors it as GASDESW).
EIA_DIESEL_SERIES = "EMD_EPD2D_PTE_NUS_DPG"

# EIA publishes weekly retail gasoline for 9 states individually; every other
# state is covered by its PADD (sub)district. duoarea code -> display label.
GAS_AREAS = {
    "R1X": "New England (PADD 1A)",
    "R1Y": "Central Atlantic (PADD 1B)",
    "R1Z": "Lower Atlantic (PADD 1C)",
    "R20": "Midwest (PADD 2)",
    "R30": "Gulf Coast (PADD 3)",
    "R40": "Rocky Mountain (PADD 4)",
    "R50": "West Coast (PADD 5)",
    "SCA": "California", "SCO": "Colorado", "SFL": "Florida",
    "SMA": "Massachusetts", "SMN": "Minnesota", "SNY": "New York",
    "SOH": "Ohio", "STX": "Texas", "SWA": "Washington",
}

def gas_series_for_area(area):
    return "EMM_EPMR_PTE_%s_DPG" % area

STATE_TO_AREA = {
    "CT": "R1X", "ME": "R1X", "NH": "R1X", "RI": "R1X", "VT": "R1X", "MA": "SMA",
    "DE": "R1Y", "DC": "R1Y", "MD": "R1Y", "NJ": "R1Y", "PA": "R1Y", "NY": "SNY",
    "GA": "R1Z", "NC": "R1Z", "SC": "R1Z", "VA": "R1Z", "WV": "R1Z", "FL": "SFL",
    "IL": "R20", "IN": "R20", "IA": "R20", "KS": "R20", "KY": "R20", "MI": "R20",
    "MO": "R20", "NE": "R20", "ND": "R20", "OK": "R20", "SD": "R20", "TN": "R20",
    "WI": "R20", "MN": "SMN", "OH": "SOH",
    "AL": "R30", "AR": "R30", "LA": "R30", "MS": "R30", "NM": "R30", "TX": "STX",
    "ID": "R40", "MT": "R40", "UT": "R40", "WY": "R40", "CO": "SCO",
    "AK": "R50", "AZ": "R50", "HI": "R50", "NV": "R50", "OR": "R50",
    "CA": "SCA", "WA": "SWA",
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# Years used to build the average seasonal price curve.
SEASONAL_YEARS = list(range(2015, 2026))
