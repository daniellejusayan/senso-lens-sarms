"""What the model is told. Our code chooses every line of it; the model only answers.

The prompt carries: the rule (and the sentence it was compiled from), the violation and the
exact import lines behind it, the importer file(s) in full (or a window when very long), the
public names of the imported module for context, the fix strategies a developer would use,
the moves that are banned, and the strict output format (FIND/REPLACE blocks, which small
local models get right far more often than unified diffs). Retries append what the gate said.
"""
from __future__ import annotations

from pathlib import Path

SYSTEM = ("You are a careful Python maintainer fixing an architecture-rule violation in a real open-source "
          "project. You change as little as possible, you never change behaviour, and you answer only in the "
          "exact format requested.")

STRATEGIES = """Ways a developer fixes this, in order of preference:
1. Delete the import if the imported names are no longer used.
2. Pass the needed object in (as a function parameter or constructor argument) so this module no longer
   imports it; the caller that is allowed to import it supplies it.
3. Move the small shared piece the importer needs into a module both sides may import, and import it from there.
4. Import the same object from a module the rules allow, if it is re-exported there.
"""

BANNED = """Never do these (they are rejected automatically):
- hide the import: moving it inside a function, wrapping it in try/except, importlib, __import__, or
  string-based module loading; the dependency still exists and the checker still counts it
- change, delete or weaken any test, or edit test files
- change the rules (pyproject.toml, .importlinter, setup.cfg, ignore_imports)
- edit files you were not shown, except to create a new small module for strategy 3
- change public behaviour, signatures callers rely on, or error messages
"""

FORMAT = """Reply ONLY with one or more blocks in exactly this format, then one REASON line:

FILE: <path relative to the repository root>
<<<<<<< FIND
<exact lines copied from the file, enough to be unique>
=======
<the replacement lines>
>>>>>>> REPLACE

REASON: <one sentence: which strategy and why>

Rules for the blocks: FIND text must match the file exactly (same indentation, no line numbers);
a block may delete lines by leaving the REPLACE part empty; to create a new file use an empty FIND.
No prose, no markdown fences, no explanations outside REASON.
"""


def module_path(tree: Path, module: str, roots_paths):
    """kedro.runner.task -> <tree>/kedro/runner/task.py (or .../__init__.py), searching the source roots."""
    rel = module.replace(".", "/")
    for base in roots_paths:
        for cand in (Path(base) / f"{rel}.py", Path(base) / rel / "__init__.py"):
            if cand.exists():
                return cand
    return None


def file_block(tree: Path, path: Path, lines_of_interest=(), max_lines=400, window=60):
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(tree).as_posix()
    rows = text.splitlines()
    if len(rows) <= max_lines or not lines_of_interest:
        return f"FILE {rel} ({len(rows)} lines, shown in full):\n```\n{text}\n```\n"
    keep = set()
    for ln in lines_of_interest:
        keep.update(range(max(1, ln - window), min(len(rows), ln + window) + 1))
    keep.update(range(1, 41))  # the import header
    out, last = [], 0
    for i in sorted(keep):
        if i != last + 1:
            out.append("... (lines omitted) ...")
        out.append(rows[i - 1])
        last = i
    return f"FILE {rel} ({len(rows)} lines; the relevant parts, the file is longer):\n```\n" + "\n".join(out) + "\n```\n"


def public_names(path: Path, limit=60):
    """Top-level def/class/CONSTANT names of a module, for context."""
    names = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if line[:1] not in (" ", "\t") and (s.startswith(("def ", "class ", "async def ")) or
                                              (s[:1].isupper() and "=" in s and s.split("=")[0].strip().isidentifier())):
            names.append(s.split("(")[0].split(":")[0].split("=")[0].replace("async def", "def").strip())
        if len(names) >= limit:
            break
    return names


def build(violation, rule, tree: Path, roots_paths, examples=None, feedback=None):
    """-> (prompt text, {importer file paths})."""
    rel_rule = (f"RULE {rule['id']}: {rule['kind']} import {rule['from']} -> {rule['to']}\n"
                f"  from the team's contract '{rule['source']['id']}': {rule['source'].get('sentence', '')}\n") if rule \
        else f"RULE (contract '{violation['contract']}'): {violation['edge_from']} must not import {violation['edge_to']}\n"
    lines = violation.get("lines", [])
    if lines:
        viol = "THE VIOLATING IMPORT LINES (this is what must go away):\n" + "".join(
            f"  {ln['edge'].split('->')[0]}  line {ln['line_number']}:  {ln['line_contents'].strip()}\n" for ln in lines)
    else:
        viol = (f"THE VIOLATION: {violation['edge_from']} reaches {violation['edge_to']} through a chain of imports: "
                + " ; ".join(violation.get("edges", [])) + "\n")
    importers = {}
    for ln in lines:
        mod = ln["edge"].split("->")[0]
        p = module_path(tree, mod, roots_paths)
        if p:
            importers.setdefault(p, []).append(ln["line_number"])
    shown = "".join(file_block(tree, p, lns) for p, lns in importers.items())
    target = module_path(tree, violation["edge_to"], roots_paths)
    ctx = ""
    if target:
        ctx = (f"CONTEXT: the imported module {violation['edge_to']} lives at {target.relative_to(tree).as_posix()} "
               f"and defines: {', '.join(public_names(target)) or '(nothing at top level)'}\n")
    ex = ""
    if examples:
        ex = "EXAMPLE of how this project fixed a similar violation before:\n" + "\n".join(examples) + "\n"
    fb = ""
    if feedback:
        fb = ("YOUR PREVIOUS ANSWER WAS REJECTED. What the checks said:\n" + feedback +
              "\nAnswer again, fixing that. Keep the same format.\n")
    label = "INVERTED (a lower layer imports a higher one)" if violation.get("label") == "INVERTED" else \
        "ADDITIONAL (an import a rule forbids)"
    prompt = (f"Project rule violation to fix. Label: {label}.\n\n{rel_rule}\n{viol}\n{shown}{ctx}\n{ex}{STRATEGIES}\n{BANNED}\n{fb}{FORMAT}")
    return prompt, set(importers)
