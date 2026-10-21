"""Step 1a: score candidate repositories on the runbook's eight criteria.

    uv run python tools/screen.py data/longlist.txt            # -> data/candidates.csv

One line per repository in the list (owner/name; # comments allowed). Each is cloned as a
partial clone into data/raw/REPO (the same clone Steps 1b and 1c use). Criteria 3 (tests) and
4 (repairs) are filled from data/tests.csv and reports/awareness-gap-baseline/summary.csv
when those exist, otherwise left "pending". Re-run any time; rows are rebuilt from evidence.

If `gh` is logged in, stars, archived, licence and the language bytes come from the GitHub API
(gh api repos/O/R, .../languages); otherwise licence comes from the LICENSE file and the Python
share is estimated from file sizes in the checkout (marked "~").
Use --no-checkout for very large repositories (no LOC; Python share from gh only).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path

from sarms.mining.common import (
    ADR_DIR,
    ADR_FILE,
    ADR_SKIP,
    IL_FILES,
    REPORTS,
    as_list,
    ensure_clone,
    find_il_config,
    git,
    has_il_section,
    norm_ignore,
    read_il_options,
    resolve_ref,
    show,
)

TODAY = dt.date.today()
SHEET = ["repo", "url", "stars", "default_branch", "first_commit", "n_first_parent", "contracts", "adrs",
         "tests_min", "loc_py", "licence", "last_commit", "criteria_met", "decision", "reason"]
EXTRA = ["python_share_pct", "contract_types", "exceptions", "contract_since", "lint_imports_in_ci",
         "archived", "drops_c4", "exception_removals", "adr_dirs"]
CODE_EXT = {".py": "Python", ".js": "JS", ".jsx": "JS", ".ts": "TS", ".tsx": "TS", ".java": "Java",
            ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".cs": "C#",
            ".rb": "Ruby", ".php": "PHP", ".kt": "Kotlin", ".scala": "Scala", ".swift": "Swift",
            ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".svelte": "Svelte",
            ".sh": "Shell", ".pyx": "Cython", ".ipynb": "Jupyter"}
OK_LICENCES = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD")


def gh_json(path):
    if not shutil.which("gh"):
        return None
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return json.loads(p.stdout) if p.returncode == 0 else None


def licence_from_file(d, sha):
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING", "LICENSE.rst"):
        t = show(d, sha, name)
        if t:
            t = t[:3000]
            for key, rx in (("Apache-2.0", r"Apache License,?\s+Version 2\.0"), ("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
                            ("BSD-3-Clause", r"Redistribution and use.*neither the name", ), ("BSD-2-Clause", r"Redistribution and use in source and binary forms"),
                            ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
                            ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("MPL-2.0", r"Mozilla Public License,?\s+v(ersion)?\.?\s*2\.0"),
                            ("LGPL", r"GNU LESSER GENERAL PUBLIC LICENSE")):
                if re.search(rx, t, re.I | re.S):
                    return key
            return "other"
    return ""


def contract_since(d, ref):
    log = git(d, "log", "--first-parent", "--reverse", "--format=%H%x09%cs", ref, "--", *IL_FILES)
    cands = [line.split("\t") for line in log.splitlines() if line.strip()]
    lo, hi, found = 0, len(cands) - 1, ""
    while lo <= hi:
        mid = (lo + hi) // 2
        if any(has_il_section(f, t) for f in IL_FILES if (t := show(d, cands[mid][0], f))):
            found, hi = cands[mid][1], mid - 1
        else:
            lo = mid + 1
    return found


def evidence_rows(path, key="repo"):
    return {r[key]: r for r in csv.DictReader(open(path))} if Path(path).exists() else {}


def screen(owner_repo, checkout=True, tests=None, base=None):
    d = ensure_clone(owner_repo, checkout=checkout)
    ref = resolve_ref(d)
    head = git(d, "rev-parse", ref).strip()
    branch = ref.split("/", 1)[1]
    first = git(d, "log", "--first-parent", "--reverse", "--format=%cs", ref).splitlines()[0]
    last = git(d, "log", "-1", "--format=%cs", ref).strip()
    nfp = int(git(d, "rev-list", "--first-parent", "--count", ref))
    files = git(d, "ls-tree", "-r", "--name-only", ref).splitlines()

    fname, text = find_il_config(d, head)
    contracts, types, exceptions = 0, [], 0
    if fname and (o := read_il_options(fname, text)):
        contracts = len(o.contracts_options)
        types = sorted({c.get("type", "?") for c in o.contracts_options})
        exceptions = sum(len({norm_ignore(e) for e in as_list(c.get("ignore_imports"))}) for c in o.contracts_options)
    adr = [f for f in files if ADR_DIR.search(f) and ADR_FILE.search(f) and not ADR_SKIP.search(f)]
    adr_dirs = sorted({f[:ADR_DIR.search(f).end()].rstrip("/") for f in adr})
    ci = []
    for f in files:
        if re.match(r"^(\.github/workflows/[^/]+\.ya?ml|Makefile|tox\.ini|noxfile\.py|\.pre-commit-config\.ya?ml|justfile)$", f):
            if re.search(r"lint-imports|import-linter|importlinter", show(d, head, f) or ""):
                ci.append(f)

    meta = gh_json(f"repos/{owner_repo}") or {}
    langs = gh_json(f"repos/{owner_repo}/languages")
    loc, share = "", ""
    if langs:
        tot = sum(langs.values())
        share = round(100 * langs.get("Python", 0) / tot, 1) if tot else ""
    if checkout and not any((d / f).is_file() for f in files[:50]):
        git(d, "checkout", "-q", "--force", head)        # partial clone made with --no-checkout
    if checkout and (d / ".git").exists():
        size, n = {}, 0
        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in CODE_EXT or not (d / f).is_file():
                continue
            b = (d / f).stat().st_size
            size[CODE_EXT[ext]] = size.get(CODE_EXT[ext], 0) + b
            if ext == ".py":
                with open(d / f, "rb") as fh:
                    n += sum(1 for _ in fh)
        loc = n
        if share == "" and size:
            share = f"~{100 * size.get('Python', 0) / sum(size.values()):.1f}"
    licence = (meta.get("license") or {}).get("spdx_id") or licence_from_file(d, head)
    archived = meta.get("archived", "")
    tmin = (tests or {}).get(owner_repo, {}).get("test_min", "")
    b = (base or {}).get(owner_repo, {})
    drops, removals = b.get("drops", ""), b.get("exception_removal_commits", "")

    age = (TODAY - dt.date.fromisoformat(first)).days / 365.25
    sh = float(str(share).lstrip("~")) if share != "" else None
    c = {
        1: contracts >= 2 or len(adr) >= 10,
        2: age >= 2 and nfp >= 1500,
        3: None if tmin == "" else float(tmin) < 10,
        4: None if drops == "" else int(drops) >= 20,
        5: None if sh is None else sh >= 90,
        6: None if loc == "" else 20_000 <= int(loc) <= 400_000,
        7: any(licence.startswith(x) for x in OK_LICENCES) if licence else None,
        8: (TODAY - dt.date.fromisoformat(last)).days <= 183 and archived is not True,
    }
    met = ",".join(str(k) for k, v in c.items() if v is True)
    failed = ",".join(str(k) for k, v in c.items() if v is False)
    pending = ",".join(str(k) for k, v in c.items() if v is None)
    return {
        "repo": owner_repo, "url": f"https://github.com/{owner_repo}", "stars": meta.get("stargazers_count", ""),
        "default_branch": branch, "first_commit": first, "n_first_parent": nfp, "contracts": contracts,
        "adrs": len(adr), "tests_min": tmin, "loc_py": loc, "licence": licence, "last_commit": last,
        "criteria_met": f"met {met or '-'}; failed {failed or '-'}; pending {pending or '-'}",
        "decision": "", "reason": "",
        "python_share_pct": share, "contract_types": " ".join(types), "exceptions": exceptions,
        "contract_since": contract_since(d, ref) if fname else "", "lint_imports_in_ci": " ".join(ci),
        "archived": archived, "drops_c4": drops, "exception_removals": removals,
        "adr_dirs": " ".join(adr_dirs[:3]) + (" …" if len(adr_dirs) > 3 else ""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("longlist")
    ap.add_argument("--out", default="data/candidates.csv")
    ap.add_argument("--no-checkout", action="store_true", help="skip the checkout (no LOC) for very large repositories")
    a = ap.parse_args()
    tests = evidence_rows("data/tests.csv")
    base = evidence_rows(REPORTS / "awareness-gap-baseline" / "summary.csv")
    keep = evidence_rows(a.out)          # keep decision/reason typed by hand
    rows = []
    for r in [line.split("#")[0].strip() for line in open(a.longlist)]:
        if not r:
            continue
        try:
            row = screen(r, checkout=not a.no_checkout, tests=tests, base=base)
        except Exception as e:
            row = {"repo": r, "reason": f"screening error: {str(e).splitlines()[0][:150]}"}
        if r in keep:
            row["decision"], row["reason"] = keep[r].get("decision", ""), keep[r].get("reason", "") or row.get("reason", "")
        rows.append(row)
        print(f"{r:40s} {row.get('criteria_met', row.get('reason'))}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET + EXTRA)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in SHEET + EXTRA})
    print(f"-> {a.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
