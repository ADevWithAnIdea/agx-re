# EXP-0195: byte-for-byte copy of EXP-0194/analysis/extract_candidates.py.  The ONLY changes are
# the two paths: blocked_rows.json is read from EXP-0194 (not modified), and the 244 MB
# intermediate is written to $E0195_RECORDS_OUT so nothing is written into EXP-0194.
#!/usr/bin/env python3
"""EXP-0194 step 2: pull EVERY raw per-case record for the 566 blocked (instr,field)
rows out of experiments/**/raw/**.jsonl into one file, so step 3 can adjudicate them
without re-walking 1.7 GB.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.dirname(os.path.abspath(__file__))
blocked = json.load(open(os.path.join(ROOT, "experiments", "EXP-0194-desk-promotion-audit", "analysis", "blocked_rows.json")))
keys = {(r["mn"], r["field"]) for r in blocked}
out = open(os.environ["E0195_RECORDS_OUT"], "w")
n = 0
for dp, dn, fn in os.walk(os.path.join(ROOT, "experiments")):
    if os.sep + "raw" + os.sep not in dp + os.sep:
        continue
    for f in sorted(fn):
        if not f.endswith(".jsonl"):
            continue
        path = os.path.join(dp, f)
        rel = os.path.relpath(path, ROOT)
        exp = rel.split(os.sep)[1]
        for line in open(path, errors="replace"):
            if '"field"' not in line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if not isinstance(r, dict):
                continue
            ins = r.get("instr") or r.get("instruction") or r.get("mnemonic")
            fld = r.get("field")
            if (str(ins), str(fld)) in keys:
                r["__exp"] = exp
                r["__file"] = rel
                out.write(json.dumps(r) + "\n")
                n += 1
out.close()
sys.stderr.write("extracted %d records\n" % n)
