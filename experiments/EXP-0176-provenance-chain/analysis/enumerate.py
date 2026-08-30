#!/usr/bin/env python3
"""EXP-0176: independently re-derive which committed experiments have no PROVENANCE.md row.

Deliberately does NOT reuse EXP-0173's script: this is an independent second method.
Covers EVERY experiments/EXP-* directory (numeric, M4, M5, G1, O2), not just EXP-NNNN.

CLEAN-ROOM: reads only our own committed markdown in this repo.
    python3 experiments/EXP-0176-provenance-chain/analysis/enumerate.py
"""
import json, os, re, subprocess, glob

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXPDIR))

prov = open(os.path.join(ROOT, "PROVENANCE.md")).read()

docs_files = []
for rd, _d, fs in os.walk(os.path.join(ROOT, "docs")):
    for fn in fs:
        docs_files.append(os.path.join(rd, fn))
docs_blob = {}
for p in docs_files:
    try:
        docs_blob[os.path.relpath(p, ROOT)] = open(p, errors="ignore").read()
    except Exception:
        pass

def committed(relpath):
    return subprocess.call(["git", "-C", ROOT, "ls-files", "--error-unmatch", relpath],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

rows = []
for d in sorted(glob.glob(os.path.join(ROOT, "experiments", "EXP-*"))):
    if not os.path.isdir(d):
        continue
    base = os.path.basename(d)
    rel = os.path.relpath(d, ROOT)
    # canonical id: EXP-0123 / EXP-M4-01 / EXP-M5-23 / EXP-G1a / EXP-O2A
    m = re.match(r"(EXP-(?:[0-9]{4}|M4-[0-9]+|M5-[0-9]+|G1[a-z]|O2[A-Z]))", base)
    eid = m.group(1) if m else base
    is_committed = committed(rel)
    # a row "cites" the experiment if the id appears anywhere in PROVENANCE.md
    has_row = eid in prov
    n_rows = len(re.findall(re.escape(eid) + r"\b", prov))
    cited_docs = sorted([k for k, v in docs_blob.items() if eid in v])
    files = sorted(os.path.relpath(os.path.join(r, f), ROOT)
                   for r, _dd, ff in os.walk(d) for f in ff)
    rows.append({
        "id": eid, "dir": rel, "committed": is_committed,
        "has_provenance_row": has_row, "provenance_mentions": n_rows,
        "cited_in_docs": bool(cited_docs), "docs_files": cited_docs,
        "has_results": os.path.exists(os.path.join(d, "RESULTS.md")),
        "has_raw": os.path.isdir(os.path.join(d, "raw")),
        "n_files": len(files),
        "has_quarantine": os.path.exists(os.path.join(d, "QUARANTINE.md")),
    })

missing = [r for r in rows if r["committed"] and not r["has_provenance_row"]]
missing_docs = [r for r in missing if r["cited_in_docs"]]
out = {
    "_meta": {
        "experiment": "EXP-0176",
        "total_exp_dirs": len(rows),
        "committed": sum(1 for r in rows if r["committed"]),
        "uncommitted": sum(1 for r in rows if not r["committed"]),
        "committed_without_row": len(missing),
        "committed_without_row_and_cited_in_docs": len(missing_docs),
    },
    "missing": missing,
    "all": rows,
}
json.dump(out, open(os.path.join(HERE, "enumerate.json"), "w"), indent=1)
print(json.dumps(out["_meta"], indent=1))
print("\n=== CITED IN docs/ BUT NO PROVENANCE ROW (worst class) ===")
for r in missing_docs:
    print("  %-14s %-52s docs: %s" % (r["id"], r["dir"], ", ".join(r["docs_files"])))
print("\n=== NO ROW, NOT CITED IN docs/ ===")
for r in missing:
    if not r["cited_in_docs"]:
        print("  %-14s %-52s raw=%s results=%s files=%d" %
              (r["id"], r["dir"], r["has_raw"], r["has_results"], r["n_files"]))
print("\n=== UNCOMMITTED (out of scope for the CODEX s9 count) ===")
for r in rows:
    if not r["committed"]:
        print("  %-14s %s" % (r["id"], r["dir"]))
