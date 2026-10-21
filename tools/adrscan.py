"""Fast first pass over a long list: does the repository keep ADRs in a common folder?

    uv run python tools/adrscan.py data/longlist.txt

Probes the usual ADR locations on raw.githubusercontent.com (no clone). A miss here is not
proof of absence: tools/screen.py reads the whole tree.
"""
import concurrent.futures as cf
import sys
import urllib.error
import urllib.request

PATHS = [
    "doc/adr/0001-record-architecture-decisions.md", "docs/adr/0001-record-architecture-decisions.md",
    "docs/adr/README.md", "docs/adr/index.md", "docs/decisions/README.md", "docs/decisions/index.md",
    "docs/architecture/decisions/0001-record-architecture-decisions.md", "adr/README.md", "docs/adrs/README.md",
    "docs/decisions/0001-record-architecture-decisions.md", "docs/decisions/0001-record-architecture-decisions.rst",
    "docs/arch/README.md", "architecture/decisions/README.md",
]


def head(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "sarms-scan"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def scan(repo):
    return repo, [p for p in PATHS if head(f"https://raw.githubusercontent.com/{repo}/HEAD/{p}") == 200]


def main():
    repos = [x.split("#")[0].strip() for x in open(sys.argv[1]) if x.split("#")[0].strip()]
    with cf.ThreadPoolExecutor(32) as ex:
        for repo, hits in ex.map(scan, repos):
            if hits:
                print(repo, hits)


if __name__ == "__main__":
    main()
