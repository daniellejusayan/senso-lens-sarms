"""Draw the package-level import graph that sarms.graph.extract wrote, with the record on top.

    uv run python tools/render_graph.py data/kedro/graph/738830bbf026 reports/figures/kedro-head
    uv run python tools/render_graph.py data/kedro/graph/9039f82a31c5 reports/figures/kedro-2020-07 --title "kedro, 16 Jul 2020"

Needs Graphviz (`dot`) on PATH (Windows: winget install Graphviz; then reopen the terminal).
Boxes are packages (second dotted level); edge labels are import counts. Grey dashed boxes are
packages no layer or rule names (drift indicator "unassigned module"). Red edges carry at least
one violating *direct* import under the strict record at that commit (forbidden contracts also
fail on indirect chains, e.g. runner -> framework -> config, which a package graph cannot show) (from data/REPO/violations_sample.parquet
when it exists). Writes <out>.svg and <out>.png.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph_dir")
    ap.add_argument("out", help="output path without extension")
    ap.add_argument("--title")
    a = ap.parse_args()
    g = Path(a.graph_dir)
    s = json.loads((g / "summary.json").read_text())
    pk = pd.read_csv(g / "packages.csv")
    mods = pd.read_csv(g / "modules.csv")
    unassigned = set(mods[mods.is_unassigned.fillna(False).astype(bool) & (mods.module.str.count(r"\.") == 1)].module)
    # violating package pairs at this commit, if the replay data is there
    red = set()
    v = g.parent.parent / "violations_sample.parquet"
    if v.exists():
        vv = pd.read_parquet(v)
        commits = pd.read_parquet(g.parent.parent / "commits.parquet")
        idx = commits.loc[commits.sha == s["sha"], "idx"]
        if len(idx):
            here = vv[vv.idx == int(idx.iloc[0])]
            pkg = lambda m: ".".join(m.split(".")[:2])  # noqa: E731
            red = {(pkg(f), pkg(t)) for f, t in zip(here.edge_from, here.edge_to, strict=True)}
    title = a.title or f"{s['repo']} @ {s['sha'][:8]}"
    lines = [f'digraph "{title}" {{', 'rankdir=LR; splines=true; nodesep=0.35; ranksep=0.9;',
             f'label="{title}: {s["modules"]} modules, {s["distinct_module_edges"]} import edges, {s["cycles"]} cycle(s)"; labelloc=t; fontname=Helvetica; fontsize=14;',
             'node [shape=box, style="rounded,filled", fillcolor="#F4F6F8", color="#3A4250", fontname=Helvetica, fontsize=11];',
             'edge [color="#7A8290", fontname=Helvetica, fontsize=9, arrowsize=0.7];']
    for p in sorted(set(pk.package_from) | set(pk.package_to) | unassigned):
        if p in unassigned:
            lines.append(f'"{p}" [style="rounded,dashed", fillcolor="white", color="#9AA3AD", fontcolor="#7A8290"];')
        else:
            lines.append(f'"{p}";')
    for r in pk.itertuples(index=False):
        if (r.package_from, r.package_to) in red:
            lines.append(f'"{r.package_from}" -> "{r.package_to}" [label="{r.n_imports}", color="#C0392B", fontcolor="#C0392B", penwidth=2.2];')
        else:
            lines.append(f'"{r.package_from}" -> "{r.package_to}" [label="{r.n_imports}"];')
    lines.append("}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dot = out.with_suffix(".dot")
    dot.write_text("\n".join(lines))
    if not shutil.which("dot"):
        print(f"wrote {dot}; Graphviz not found, so no image (install it and rerun, or paste the .dot into an online viewer)")
        return
    for ext in ("svg", "png"):
        subprocess.run(["dot", f"-T{ext}", "-Gdpi=160" if ext == "png" else "-Gdpi=96", str(dot), "-o", str(out.with_suffix("." + ext))], check=True)
    direct = {(r.package_from, r.package_to) for r in pk.itertuples(index=False)} & red
    print(f"-> {out}.svg, {out}.png ({len(direct)} of {len(red)} violating package pairs are direct imports and drawn red; "
          f"the rest are indirect chains, which forbidden contracts also count; {len(unassigned)} unassigned packages dashed)")


if __name__ == "__main__":
    main()
