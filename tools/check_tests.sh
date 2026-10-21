#!/usr/bin/env bash
# Criterion 3: time one documented test run at HEAD in a fresh virtual environment.
#
#   tools/check_tests.sh OWNER/REPO '<install command>' '<test command>'
#   tools/check_tests.sh kedro-org/kedro 'pip install -e ".[test]"' 'pytest -q --no-cov'
#
# Copy both commands from the project's CONTRIBUTING file or its CI workflow and keep them in
# the sheet. Appends one row to data/tests.csv (test_min < 10 meets criterion 3 if the run
# passes); logs and the JUnit file go to reports/tests/. Uses the clone in data/raw/REPO.
set -uo pipefail
repo="$1"; install="${2:-pip install -e .}"; tests="${3:-pytest -q}"
name="${repo##*/}"; d="data/raw/$name"; logs="reports/tests"; mkdir -p "$logs" data/raw
[ -d "$d" ] || git clone -q --filter=blob:none "https://github.com/$repo.git" "$d"
git -C "$d" fetch -q origin
git -C "$d" checkout -q --force "$(git -C "$d" rev-parse origin/HEAD)"
venv="data/raw/$name.testvenv"; rm -rf "$venv"; python3 -m venv "$venv"
. "$venv/bin/activate"; pip -q install --upgrade pip pytest > /dev/null
junit="$PWD/$logs/$name.junit.xml"; root="$PWD"
cd "$d"
t0=$(date +%s); timeout 30m bash -c "$install" > "$root/$logs/$name.install.log" 2>&1; irc=$?
t1=$(date +%s); timeout 15m bash -c "$tests --junitxml=$junit" > "$root/$logs/$name.tests.log" 2>&1; trc=$?
t2=$(date +%s); cd "$root"; deactivate
python3 - "$junit" "$repo" "$irc" "$trc" "$((t1-t0))" "$((t2-t1))" "$install" "$tests" <<'EOF'
import csv, os, sys, xml.etree.ElementTree as ET
junit, repo, irc, trc, isec, tsec, icmd, tcmd = sys.argv[1:]
t = f = e = s = 0
if os.path.exists(junit):
    root = ET.parse(junit).getroot()
    for ts in ([root] if root.tag == "testsuite" else root.iter("testsuite")):
        t += int(ts.get("tests", 0)); f += int(ts.get("failures", 0))
        e += int(ts.get("errors", 0)); s += int(ts.get("skipped", 0))
ran = t - s
rate = round((ran - f - e) / ran * 100, 1) if ran else 0.0
tmin = round(int(tsec) / 60, 1)
row = {"repo": repo, "install_rc": irc, "test_rc": trc, "install_min": round(int(isec) / 60, 1),
       "test_min": tmin, "tests": t, "failures": f, "errors": e, "skipped": s, "pass_rate_pct": rate,
       "meets_c3": irc == "0" and ran > 0 and rate >= 95 and tmin < 10 and trc != "124",
       "install_cmd": icmd, "test_cmd": tcmd}
path = "data/tests.csv"
rows = [r for r in csv.DictReader(open(path))] if os.path.exists(path) else []
rows = [r for r in rows if r["repo"] != repo] + [row]
with open(path, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(row)); w.writeheader(); w.writerows(rows)
print(row)
EOF
