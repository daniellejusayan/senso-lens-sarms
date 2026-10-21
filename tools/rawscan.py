"""Fast first pass over a long list: does the repository keep import-linter contracts at its root?

    uv run python tools/rawscan.py data/longlist.txt

Reads pyproject.toml, setup.cfg and .importlinter from raw.githubusercontent.com (no clone);
prints one line per hit with the contract count, types and ignore_imports entries, and writes
data/rawscan.json. Monorepos keep configs in subfolders: use tools/screen.py for those.
"""
import concurrent.futures as cf
import json
import re
import sys
import urllib.error
import urllib.request

FILES = ["pyproject.toml", "setup.cfg", ".importlinter"]


def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sarms-scan"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError:
        return None
    except Exception as e:  # network errors are evidence too
        return "ERR:" + str(e)


def scan(repo):
    out = {"repo": repo, "files": {}, "contracts": 0, "ignore_lines": 0, "types": []}
    for f in FILES:
        t = get(f"https://raw.githubusercontent.com/{repo}/HEAD/{f}")
        if t is None:
            continue
        if t.startswith("ERR:"):
            out["files"][f] = t
            continue
        if "importlinter" in t.lower():
            out["files"][f] = "importlinter"
            out["contracts"] += len(re.findall(r"\[importlinter:contract|\[\[tool\.importlinter\.contracts\]\]", t))
            out["types"] += re.findall(r"^\s*type\s*=\s*\"?([a-z_]+)\"?", t, re.M)
            out["ignore_lines"] += len(re.findall(r"^\s*\"?[\w\.\*]+\s*->\s*[\w\.\*]+\"?,?\s*$", t, re.M))
        else:
            out["files"][f] = "present"
    return out


def main():
    repos = [x.split("#")[0].strip() for x in open(sys.argv[1]) if x.split("#")[0].strip()]
    with cf.ThreadPoolExecutor(24) as ex:
        res = list(ex.map(scan, repos))
    hits = [r for r in res if any(v == "importlinter" for v in r["files"].values())]
    json.dump(res, open("data/rawscan.json", "w"), indent=1)
    print(f"scanned {len(res)}; import-linter at root: {len(hits)}")
    for r in sorted(hits, key=lambda r: -r["contracts"]):
        files = [k for k, v in r["files"].items() if v == "importlinter"]
        print(f'{r["repo"]:45s} contracts={r["contracts"]:3d} ignore~{r["ignore_lines"]:4d} files={files} types={sorted(set(r["types"]))}')
    errs = [r["repo"] for r in res if any(str(v).startswith("ERR") for v in r["files"].values())]
    if errs:
        print("errors:", errs[:20])


if __name__ == "__main__":
    main()
