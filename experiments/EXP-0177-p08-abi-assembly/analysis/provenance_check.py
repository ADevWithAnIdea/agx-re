#!/usr/bin/env python3
"""EXP-0177 analysis: for every experiment this P0.8 assembly cites, check the three
things the closure rules depend on:

  * closure rule 2 — does the experiment exist with committed RESULTS.md, and is it
    QUARANTINED (i.e. non-evidence)?
  * closure rule 3 — does it OWN a row in PROVENANCE.md (its own evidence cell names it),
    as opposed to merely being mentioned inside another experiment's row?
  * closure rule 4 — is it cited anywhere under docs/ (the normative deliverable)?

Read-only. Writes analysis/provenance_check.json next to this script.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# Every experiment cited by EXP-0177's assembly, grouped by P0.8 sub-area.
CITED = {
    "inputs": ["EXP-0109", "EXP-0031", "EXP-0092", "EXP-0137"],
    "outputs": ["EXP-0109", "EXP-0117", "EXP-0111", "EXP-0091", "EXP-0121", "EXP-0155", "EXP-0163", "EXP-0050"],
    "sysvals": ["EXP-0092", "EXP-0031", "EXP-0117", "EXP-0137", "EXP-G1a"],
    "interpolation": ["EXP-0029", "EXP-0109", "EXP-0117", "EXP-0137", "EXP-0155", "EXP-0163", "EXP-0121"],
    "tilebuffer": ["EXP-0029", "EXP-0130", "EXP-0108", "EXP-0048", "EXP-0147", "EXP-0117", "EXP-0155"],
    "calls": ["EXP-0035", "EXP-0109", "EXP-0117", "EXP-0137", "EXP-0172", "EXP-0156"],
    "scratch": ["EXP-0041", "EXP-0107", "EXP-0125", "EXP-0035", "EXP-0057"],
    "linking": ["EXP-0109", "EXP-0137", "EXP-0131", "EXP-0042"],
    "sideband": ["EXP-G1a", "EXP-0097", "EXP-0024"],
    "epilogs": ["EXP-0117", "EXP-0137", "EXP-0130", "EXP-0102"],
}


def find_dir(exp):
    root = os.path.join(REPO, "experiments")
    for name in sorted(os.listdir(root)):
        if name.startswith(exp + "-") or name == exp:
            return name
    return None


def main():
    prov = open(os.path.join(REPO, "PROVENANCE.md")).read().split("\n")

    def owns_provenance_row(exp):
        lines = []
        for i, line in enumerate(prov, 1):
            if exp not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 3:
                continue
            evidence = cells[-2]
            if evidence.startswith(exp):
                lines.append(i)
        return lines

    def mentioned_only(exp):
        return [i for i, line in enumerate(prov, 1) if exp in line]

    def docs_citations(exp):
        try:
            out = subprocess.run(
                ["grep", "-rl", exp, os.path.join(REPO, "docs")],
                capture_output=True, text=True, check=False,
            ).stdout.strip()
        except Exception:
            return []
        if not out:
            return []
        return sorted(os.path.relpath(p, REPO) for p in out.split("\n"))

    seen = {}
    for sub, exps in CITED.items():
        for exp in exps:
            if exp in seen:
                continue
            d = find_dir(exp)
            path = os.path.join(REPO, "experiments", d) if d else None
            own = owns_provenance_row(exp)
            docs = docs_citations(exp)
            seen[exp] = {
                "dir": ("experiments/" + d) if d else None,
                "has_results_md": bool(path and os.path.exists(os.path.join(path, "RESULTS.md"))),
                "quarantined": bool(path and os.path.exists(os.path.join(path, "QUARANTINE.md"))),
                "owns_provenance_row": bool(own),
                "provenance_row_lines": own,
                "provenance_mentions": mentioned_only(exp),
                "docs_citations": docs,
                "cited_in_docs": bool(docs),
            }

    out = {
        "_source": "PROVENANCE.md, experiments/, docs/",
        "_rules": {
            "rule2": "complete authored probe/commands/raw/failures/analysis committed",
            "rule3": "evidence chain recorded in PROVENANCE.md",
            "rule4": "normative docs carry exact fields, ranges, fallbacks, target status",
        },
        "subarea_citations": CITED,
        "experiments": seen,
        "summary": {
            "n_cited": len(seen),
            "quarantined": sorted(k for k, v in seen.items() if v["quarantined"]),
            "no_provenance_row": sorted(k for k, v in seen.items() if not v["owns_provenance_row"]),
            "not_cited_in_docs": sorted(k for k, v in seen.items() if not v["cited_in_docs"]),
        },
    }

    dst = os.path.join(HERE, "provenance_check.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")

    print(f"cited experiments: {out['summary']['n_cited']}")
    print(f"QUARANTINED (non-evidence): {out['summary']['quarantined']}")
    print(f"NO PROVENANCE.md row of their own: {out['summary']['no_provenance_row']}")
    print(f"NOT cited anywhere in docs/: {out['summary']['not_cited_in_docs']}")
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
