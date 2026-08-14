# The War Tax

An interactive visualization of what the 2026 Iran war (Feb 27, 2026 – ) has cost — and
paid — an American household, depending on how much stock it owned when the war began.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python pipeline/run.py      # fetches all data, writes site/data.json + site/index.html
open site/index.html
```

API keys live in `.env` (`BLS_API_KEY`, `EIA_key`). Both are free registrations
(BLS works unauthenticated at lower rate limits; gasoline falls back to FRED's
`GASREGW` mirror if the EIA key is missing).

## Methodology

**Costs are counterfactual, not raw inflation** — actual prices paid since Feb 27
minus a projected "no-war" path, accumulated per average household:

- **Gasoline** — EIA weekly US regular retail vs. a seasonal path: the median
  week-by-week trajectory of 2015–2025 (median across years is robust to the 2020
  crash and 2022 Ukraine spike), projected from the last prewar weekly price.
  Consumption ≈ 61 gal/month, derived from CEX 2024 gasoline spend ÷ 2024 average
  price (EIA's economy-wide top-down estimate, ~85 gal/month/household, is an upper
  bound that includes commercial use). A **state picker** reprices the gas line:
  EIA publishes weekly prices for 9 states individually (CA CO FL MA MN NY OH TX
  WA); the other 41 + DC use their PADD subdistrict series, labeled as such. Each
  of the 17 areas gets its own seasonal curve and prewar baseline; consumption is
  held at the national average. AAA's current state average appears as a headline.
- **Diesel (tracked, not charged)** — same counterfactual for US on-highway
  diesel (EIA `EMD_EPD2D_PTE_NUS_DPG`, FRED `GASDESW` fallback), shown as a
  leading indicator for grocery prices (freight pass-through lags months); it adds
  nothing to the cost total.
- **Groceries** — CPI food-at-home (seasonally adjusted) vs. its trailing-12-month
  prewar trend (Feb 2025 → Feb 2026, which cleanly straddles the Oct 2025 shutdown
  data hole), applied to CEX 2024 food-at-home spend ($6,224/yr).
- **Home energy** — same construction for CPI electricity ($1,833/yr) and utility
  piped gas ($493/yr) separately, summed.
- Categories running *below* their prewar trend count as negative cost.

**Gains** — S&P 500 change from its Feb 27, 2026 close (6,878.88), applied to the
user's prewar invested amount, taxed as if realized today at short-term (ordinary)
rates: 22% default, 35% top 1%, 40.8% (37% + 3.8% NIIT) top 0.1% — so gains are
after-tax, like the costs.

**Wealth groups** — corporate equities + mutual fund shares per household from the
Fed's Distributional Financial Accounts (the detail file includes per-group household
counts). The median American reflects the SCF 2022 finding that the median family
holds no stock outside retirement accounts (21% hold any directly; conditional
median $15,000).

## Data sources

| Data | Source |
|---|---|
| Weekly retail gasoline | EIA API v2 `EMM_EPMR_PTE_NUS_DPG` (fallback: FRED `GASREGW`) |
| AAA national average (headline) | gasprices.aaa.com (scrape, fails soft) |
| CPI + grocery average prices | BLS API v2 |
| S&P 500 daily closes | FRED `SP500` (no key) |
| Wealth distribution | Fed DFA `dfa.zip` → networth-levels-detail |
| Household spend constants | BLS Consumer Expenditure Survey 2024 |
| Stock-ownership constants | Fed Survey of Consumer Finances 2022 |

## Layout

- `pipeline/` — fetchers (one per source), `compute.py` (counterfactual math),
  `run.py` (orchestrates; injects JSON into both pages)
- `site/template.html` — the full page source (edit this, not `index.html`)
- `site/embed-template.html` — the fixed-height embed source (edit this, not `embed.html`)
- `site/index.html` / `site/embed.html` — built outputs, fully self-contained
- `site/data.json` — the data snapshot, for inspection

## Prismic embed (`site/embed.html`)

Built for a fixed-height oEmbed iframe: **height 800px, width 100%**. Five
tabbed panels (Your ledger · Three households · The pump · Groceries · Method)
with ‹ › arrows and keyboard navigation; each panel scrolls internally if it
ever overflows, so nothing clips at fixed height. Responsive layout uses
**container queries** (`.wrap { container-type: inline-size }`, breakpoint at
830px container width) — no viewport media queries, per the embed constraints.
