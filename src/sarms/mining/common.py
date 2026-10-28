"""Shared helpers for Steps 1a-1c (runbook conventions).

Paths (run every command from the sarms repository root):
  data/raw/REPO/          clones (git-ignored); REPO is the repository name without the owner
  data/REPO/              derived files (Parquet is git-ignored this week)
  .salt                   the team's secret salt (git-ignored), or RMS_SALT in the environment

History is always the first-parent chain of the default branch, so every merge commit is
read as its diff against parents[0]: what that push added to the branch.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

DATA = Path("data")
RAW = DATA / "raw"
REPORTS = Path("reports")

# Files import-linter reads by default (its documentation: setup.cfg, .importlinter, pyproject.toml).
IL_FILES = [".importlinter", "setup.cfg", "pyproject.toml"]

ADR_DIR = re.compile(r"(^|/)(adr|adrs|decisions|decision-records|architecture[-_ ]?decisions?|"
                     r"architectural[-_ ]?decisions?|design[-_ ]?decisions?)/", re.I)
ADR_FILE = re.compile(r"\.(md|rst|adoc|txt)$", re.I)
ADR_SKIP = re.compile(r"(^|/)(readme|index|template|adr-template|_template)[^/]*$", re.I)


def worktree_path(repo_dir, kind: str) -> Path:
    """<repo>.<kind> next to the clone (wt = replay, draft = the draft step, fi = fault injection).
    SARMS_WT_SUFFIX (e.g. "-linux") keeps separate worktrees when two operating systems share one
    clone through a mounted folder, since a worktree's .git file holds an absolute path."""
    return Path(f"{repo_dir}.{kind}{os.environ.get('SARMS_WT_SUFFIX', '')}")


def repo_name(owner_repo: str) -> str:
    return owner_repo.rstrip("/").split("/")[-1]


def run(args, cwd=None, check=True) -> str:
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, args))}\n{p.stderr.strip()}")
    return p.stdout


def git(repo_dir, *args, check=True) -> str:
    return run(["git", "-C", str(repo_dir), *args], check=check)


def ensure_clone(owner_repo: str, checkout: bool = True) -> Path:
    """data/raw/REPO as a partial clone (--filter=blob:none): all commits and trees, file
    contents fetched only when something reads them."""
    d = RAW / repo_name(owner_repo)
    if d.exists():
        git(d, "fetch", "-q", "origin")
        return d
    RAW.mkdir(parents=True, exist_ok=True)
    args = ["git", "clone", "-q", "--filter=blob:none"] + ([] if checkout else ["--no-checkout"])
    run(args + [f"https://github.com/{owner_repo}.git", str(d)])
    return d


def resolve_ref(repo_dir, branch: str | None = None) -> str:
    """origin/<branch> if it exists (fresh after a fetch), else the branch; default branch if None."""
    if not branch:
        ref = git(repo_dir, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", check=False).strip()
        if not ref:
            git(repo_dir, "remote", "set-head", "origin", "--auto", check=False)
            ref = git(repo_dir, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", check=False).strip()
        if not ref:  # no remote (a local repository, the Term 2 CI checkout): the current branch
            ref = git(repo_dir, "symbolic-ref", "-q", "--short", "HEAD", check=False).strip() or "HEAD"
        return ref
    if git(repo_dir, "rev-parse", "-q", "--verify", f"origin/{branch}", check=False).strip():
        return f"origin/{branch}"
    return branch


def first_parent(repo_dir, ref: str, since: str | None = None):
    """[(idx, sha, committer_iso, subject)] oldest -> newest; idx = position on the full chain."""
    # -z: NUL between records, because a subject line can hold characters str.splitlines() treats
    # as line breaks (PostHog has a subject with U+001D), which split a record in two.
    out = git(repo_dir, "log", "-z", "--first-parent", "--reverse", "--format=%H%x1f%cI%x1f%s", ref)
    rows = []
    for idx, rec in enumerate(r for r in out.split("\0") if r):
        sha, ts, subj = rec.split("\x1f", 2)
        rows.append((idx, sha, ts, subj.replace("\n", " ")))
    if since:
        rows = [r for r in rows if r[2][:10] >= since]
    return rows


def show(repo_dir, sha: str, path: str):
    p = subprocess.run(["git", "-C", str(repo_dir), "show", f"{sha}:{path}"], capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def salt() -> str:
    s = os.environ.get("RMS_SALT")
    if not s and Path(".salt").exists():
        s = Path(".salt").read_text().strip()
    if not s:
        sys.exit("No salt: put the team's secret in .salt (git-ignored) or set RMS_SALT.")
    return s


def pseudonym(email: str) -> str:
    """Runbook Step 1b: salted SHA-256 of the lower-cased e-mail, first 16 hex characters."""
    return hashlib.sha256((salt() + email.lower()).encode()).hexdigest()[:16]


def has_il_section(fname: str, text: str) -> bool:
    if fname.endswith(".toml"):
        try:
            return "importlinter" in tomllib.loads(text).get("tool", {})
        except Exception:
            return "[tool.importlinter" in text
    return re.search(r"^\[importlinter\]", text, re.M) is not None


def find_il_config(repo_dir, sha: str, files=IL_FILES):
    """(path, text) of the first file at `sha` that holds an import-linter section."""
    for f in files:
        t = show(repo_dir, sha, f)
        if t and has_il_section(f, t):
            return f, t
    return None, None


def read_il_options(fname: str, text: str):
    """Parse a config with import-linter's own readers, so we read exactly what lint-imports
    reads. Returns importlinter UserOptions or None. Tested with import-linter 2.15."""
    from importlinter import configuration
    configuration.configure()
    from importlinter.application import use_cases as uc
    suffix = ".toml" if fname.endswith(".toml") else ".ini"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as fh:
        fh.write(text)
        tmp = fh.name
    try:
        return uc.read_user_options(tmp)
    except Exception:
        return None
    finally:
        os.unlink(tmp)


def norm_ignore(entry: str) -> str:
    entry = entry.split("#")[0].strip().strip('"').strip("'").rstrip(",")
    return re.sub(r"\s*->\s*", " -> ", entry)


def as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.splitlines() if x.strip()]
    return list(v)


# ---- import-linter contract normalisation (shared by the replay, the rule compiler and the Differ)

def optional_layers(layers):
    """Wrap every layer name in parentheses (import-linter's optional-layer syntax) so a contract
    can be checked at commits where some layers do not exist yet."""
    out = []
    for line in layers:
        parts = re.split(r"(\s*[|:]\s*)", str(line).strip())
        out.append("".join(p if re.fullmatch(r"\s*[|:]\s*", p) or p.startswith("(") or not p
                           else f"({p})" for p in parts))
    return out


def normalize_contracts(opts, strict: bool):
    """(session_options, contracts) ready for the lint worker. strict=True removes every
    ignore_imports entry (the strict record); layers are made optional either way; a contract
    without a name gets its id."""
    contracts = []
    for c in opts.contracts_options:
        c = dict(c)
        if strict:
            c.pop("ignore_imports", None)
        c["unmatched_ignore_imports_alerting"] = "none"
        if c.get("type") == "layers" and c.get("layers"):
            c["layers"] = optional_layers(as_list(c["layers"]))
        c.setdefault("name", c.get("id", "?"))
        contracts.append(c)
    session = dict(opts.session_options)
    if "root_packages" not in session:
        session["root_packages"] = [session.pop("root_package")]
    return session, contracts


def module_matches(pattern: str, module: str) -> bool:
    """Does `module` fall under `pattern`? A plain dotted name matches itself and its
    descendants (import-linter's reading of a contract module); `*` matches one dotted level
    and `**` any depth (rules.schema.yaml)."""
    pattern, module = pattern.strip(), module.strip()
    if "*" not in pattern:
        return module == pattern or module.startswith(pattern + ".")
    rx = "".join("[^.]+" if t == "*" else ".+" if t == "**" else re.escape(t)
                 for t in re.split(r"(\*\*|\*)", pattern) if t)
    return re.fullmatch(rx, module) is not None or re.fullmatch(rx + r"\..+", module) is not None
