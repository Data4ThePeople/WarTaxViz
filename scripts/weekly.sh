#!/bin/zsh
# Unattended weekly refresh, run by launchd (Tuesday and Wednesday at 11:00).
# EIA posts the weekly gas price Monday afternoon, or Tuesday after a Monday
# holiday; Wednesday is the backup run.
#   1. pipeline/run.py fetches everything and rewrites site/ and the FAQ.
#   2. If the EIA gas week moved forward: commit and push. GitHub Pages then
#      serves the new numbers on the full page and the Prismic embed.
#      S&P, AAA and CPI change between gas weeks too, so the gas week is what
#      decides whether there is a new weekly update.
# Success and failure each show a macOS alert box; details are in logs/weekly.log.
set -u
ROOT="${0:A:h:h}"
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/logs/weekly.log"
URL="https://data4thepeople.github.io/WarTaxViz/site/index.html"
OUTPUTS=(site writeups/war-tax-faq.md)
mkdir -p "$ROOT/logs"
exec >>"$LOG" 2>&1
cd "$ROOT" || exit 1
echo "\n=== $(date '+%Y-%m-%d %H:%M %Z') ==="

# An alert box stays on screen until clicked; a banner notification can come
# and go unseen. "Open viz" opens the live page.
alert() {
  b=$(osascript -e "display alert \"$1\" message \"$2\" buttons {\"Open viz\", \"OK\"} default button \"OK\" giving up after 86400" 2>/dev/null)
  [[ "$b" == *"Open viz"* ]] && open "$URL"
}

fail() {
  echo "FAILED: $1"
  git checkout -q -- $OUTPUTS 2>/dev/null
  alert "War Tax weekly update failed" "$1. Details in logs/weekly.log."
  exit 1
}

field() { "$PY" -c "import json;d=json.load(open('site/data.json'));print($1)"; }

git pull -q --rebase || fail "git pull"
before=$(field "d['gas']['latest_date']")
"$PY" pipeline/run.py || fail "pipeline/run.py"
gas=$(field "d['gas']['latest_date']")

if [[ "$gas" == "$before" ]]; then
  git checkout -q -- $OUTPUTS
  if [[ $(date +%u) -ge 3 ]]; then
    fail "No new EIA gas week yet (still $gas)"
  fi
  echo "no new gas week (still $gas)"; exit 0
fi

sp=$(field "d['market']['latest_date']")
total=$(field "'\$%.2f' % d['costs']['total']")
git add $OUTPUTS
git commit -q -m "Weekly data refresh: gas through $gas, S&P through $sp

Automatic weekly update (scripts/weekly.sh)." || fail "git commit"
git push -q || fail "git push"
echo "pushed: gas through $gas, S&P through $sp, cost $total"
alert "War Tax viz updated" "Gas through $gas, S&P through $sp. Household cost of the war so far: $total. Live on GitHub Pages in a minute or two."
