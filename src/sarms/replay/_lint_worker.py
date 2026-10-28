"""Checks import-linter contracts against one checked-out tree. Run by proxy_lint.py and by
the Differ in a fresh process per commit (reads a JSON spec on stdin, prints a JSON result on
stdout), so that sys.path and import caches never leak from one commit to the next.

Spec keys: pythonpath, session_options, contracts (checked; the strict record), cache_dir,
and optionally contracts_asis (the contracts as written, checked on the same graph; the
Differ marks a strict violation absent here as acknowledged), want_edges (return every
module-level import of the graph) and want_details (line numbers of each violating import)."""
import copy
import json
import sys


def edges_of(chain):
    out = []
    for e in chain or []:
        if isinstance(e, dict) and "importer" in e:
            out.append(f'{e["importer"]}->{e["imported"]}')
    return out


def extract(ctype, md):
    """Normalise import-linter's metadata into violations keyed (importer, imported):
    importer = the module that must not depend on `imported`."""
    md = md or {}
    viols = []
    for dep in md.get("invalid_dependencies", []) or []:            # layers
        es, n = set(), 0
        for r in dep.get("routes", []):
            n += 1
            for k in ("chain", "extra_firsts", "extra_lasts"):
                es.update(edges_of(r.get(k)))
        viols.append({"importer": dep.get("importer", ""), "imported": dep.get("imported", ""),
                      "n_routes": n, "edges": sorted(es)})
    for ch in md.get("invalid_chains", []) or []:                   # forbidden, independence
        es, n = set(), 0
        for c in ch.get("chains", []) or []:
            n += 1
            if isinstance(c, dict):
                for k in ("chain", "extra_firsts", "extra_lasts"):
                    es.update(edges_of(c.get(k)))
            else:
                es.update(edges_of(c))
        viols.append({"importer": ch.get("downstream_module", ""), "imported": ch.get("upstream_module", ""),
                      "n_routes": n, "edges": sorted(es)})
    return viols


def main():
    spec = json.load(sys.stdin)
    # Import the checker BEFORE the subject's source is on sys.path, so the subject cannot
    # shadow the checker's own packages (e.g. replaying grimp itself).
    from importlinter import configuration
    configuration.configure()
    from importlinter.application import use_cases as uc
    from importlinter.application.user_options import UserOptions
    taken = {m.split(".")[0] for m in sys.modules}
    clash = [r for r in spec["session_options"]["root_packages"] if r.split(".")[0] in taken]
    if clash:
        print(json.dumps({"graph_error": f"root package {clash} has the same name as a module the "
                                         f"checker itself uses; this repository cannot be replayed here"}))
        return
    for p in reversed(spec["pythonpath"]):
        sys.path.insert(0, p)

    uo = UserOptions(session_options=spec["session_options"], contracts_options=spec["contracts"])
    try:
        uc._register_contract_types(uo)
    except Exception as e:  # e.g. a custom contract type whose module is not importable here
        print(json.dumps({"graph_error": f"contract types: {type(e).__name__}: {e}"[:400]}))
        return
    try:
        graph = uc._build_graph(
            root_package_names=spec["session_options"]["root_packages"],
            include_external_packages=uc._get_include_external_packages(uo),
            exclude_type_checking_imports=uc._get_exclude_type_checking_imports(uo),
            verbose=False, cache_dir=spec.get("cache_dir"))
    except Exception as e:
        print(json.dumps({"graph_error": f"{type(e).__name__}: {e}"[:400]}))
        return
    def check_all(contracts):
        results = []
        for co in contracts:
            r = {"contract": co["name"], "type": co["type"], "status": "", "error": "", "violations": []}
            try:
                cls = uc.registry.get_contract_class(co["type"])
                c = cls(name=co["name"], session_options=uo.session_options, contract_options=co)
                chk = c.check(copy.deepcopy(graph), verbose=False)
                r["status"] = "kept" if chk.kept else "broken"
                r["violations"] = extract(co["type"], chk.metadata)
                if not chk.kept and not r["violations"]:
                    r["violations"] = [{"importer": "", "imported": "", "n_routes": 1, "edges": [],
                                        "note": ",".join(sorted((chk.metadata or {}).keys()))}]
            except Exception as e:
                r["status"], r["error"] = "error", f"{type(e).__name__}: {e}"[:400]
            results.append(r)
        return results

    out = {"modules": len(graph.modules), "results": check_all(spec["contracts"])}
    if spec.get("contracts_asis") is not None:
        out["results_asis"] = check_all(spec["contracts_asis"])
    if spec.get("want_edges"):
        out["edges"] = sorted((m, n) for m in graph.modules for n in graph.find_modules_directly_imported_by(m))
    if spec.get("want_details"):
        seen = set()
        for r in out["results"]:
            for v in r["violations"]:
                seen.update(v["edges"])
        details = {}
        for e in sorted(seen):
            a, b = e.split("->", 1)
            try:
                details[e] = [{"line_number": d["line_number"], "line_contents": d["line_contents"]}
                              for d in graph.get_import_details(importer=a, imported=b)]
            except Exception:
                details[e] = []
        out["details"] = details
    print(json.dumps(out))


if __name__ == "__main__":
    main()
