#!/usr/bin/env python3
"""EXP-0195 step 2: restrict the per-case record stream to the UNCITED evidence only.

EXP-0194's adjudicate2.py already sees uncited raw (its carrier groups are keyed on the
experiment), so running it on the full stream answers "does this row pass the gate at all".
It does NOT answer "does it pass ON THE EVIDENCE ITS LABEL FORGOT", because the passing
group could be a cited one.  Feeding the same, UNCHANGED script a stream containing only
records from non-cited experiments answers exactly that.  This narrows the input; it does
not touch the criterion.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ["E0195_RECORDS_IN"]
DST = os.environ["E0195_RECORDS_OUT"]

rows = json.load(open(os.path.join(HERE, "uncited_rows.json")))
allow = {(r["instr"], r["field"]): set(r["uncited_exps"]) for r in rows}

n = kept = 0
with open(DST, "w") as out:
    for line in open(SRC):
        n += 1
        r = json.loads(line)
        k = (str(r.get("instr")), str(r.get("field")))
        if k in allow and r.get("__exp") in allow[k]:
            out.write(line)
            kept += 1
print("records in %d -> uncited-only %d  (%d rows)" % (n, kept, len(rows)))
