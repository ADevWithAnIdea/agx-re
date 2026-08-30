#!/usr/bin/env python3
"""EXP-0187 SINGLE-RUN summary -- explicitly NOT the gate.

`analysis/verdicts.py` implements the two-run gate and is the only thing that may
promote. This script exists because the gated PAIR was not completed inside the
run window (see RESULTS.md section 3): it reports coverage and movement from the
ONE complete run, in the flat per-field shape FIELD-SWEEP-PROTOCOL section 5
requires, and it hard-codes `label: untested` / `verdict: NOT-GATED`. It CANNOT
promote anything, and it must never be given the same run twice -- passing one
run as both halves of a pair would fabricate 100 % agreement.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate187 as L        # noqa: E402


def vkey(r):
    o = r.get("observed") or {}
    v = o.get("vals_u32")
    return "%s|%s" % (r.get("outcome"),
                      hashlib.sha256(json.dumps(v, sort_keys=True).encode())
                      .hexdigest()[:16] if v is not None else "none")


def main(run):
    recs = [json.loads(l) for l in (Path(run) / "sweep.jsonl").read_text().splitlines() if l.strip()]
    arms = collections.defaultdict(list)
    base = {}
    for r in recs:
        a = r.get("arm")
        if not a:
            continue
        if r.get("role") == "baseline":
            if str(r.get("note", "")).endswith(":open"):
                base[a.split(":")[0]] = vkey(r)
            continue
        arms[a].append(r)
    out = {}
    for a, cs in sorted(arms.items()):
        role = cs[0].get("role")
        mn = cs[0]["instr"]
        bk = base.get(a)
        moved = sum(1 for c in cs if vkey(c) != bk)
        out[a] = {
            "role": role, "instr": mn, "field": cs[0]["field"],
            "carrier": cs[0]["carrier"], "occ": cs[0]["occ"],
            "off": cs[0]["off"], "start": cs[0]["start"], "width": cs[0]["width"],
            "values_dispatched": len({c["value"] for c in cs
                                      if c["outcome"] != "measurement_failure"}),
            "distinct_bytes": len({c["bytes"] for c in cs if c.get("bytes")}),
            "encodable_range": len({c["value"] for c in cs
                                    if (c.get("token") or {}).get("mnemonic") == mn}),
            "moved": moved,
            "outcomes": dict(collections.Counter(c["outcome"] for c in cs)),
            "tokenized_mnemonics": dict(collections.Counter(
                str((c.get("token") or {}).get("mnemonic")) for c in cs)),
            "fault_classes": dict(collections.Counter(
                fc for c in cs for fc in (c.get("fault_classes") or []))),
        }
    start, width = L.field_span("n4_rt_word", "dst")
    tgt = {k: v for k, v in out.items() if v["role"] == "target"}
    doc = {
        "n4_rt_word.dst": {
            "label": "untested",
            "verdict": "NOT-GATED (one complete run; the second gated run did "
                       "not finish inside the window -- see RESULTS.md 3)",
            "range": "0..255 dense (all 256 values) on %d occurrences" % len(tgt),
            "target": "G17P",
            "evidence": ["EXP-0187"],
            "start": start, "width": width,
            "values_dispatched": max((v["values_dispatched"] for v in tgt.values()),
                                     default=0),
            "distinct_bytes": sum(v["distinct_bytes"] for v in tgt.values()),
            "encodable_range": max((v["encodable_range"] for v in tgt.values()),
                                   default=0),
            "carriers": sorted({v["carrier"] for v in tgt.values()}),
            "moved_total": sum(v["moved"] for v in tgt.values()),
            "note": "NOT INERT: the field moves. Promotion still requires the "
                    "two-run gate, which was not completed; the label is NOT "
                    "rounded up (FIELD-SWEEP-PROTOCOL section 5).",
        },
        "_single_run": str(run),
        "_not_the_gate": "analysis/verdicts.py implements the gate; this file "
                         "cannot promote anything.",
        "arms": out,
    }
    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in doc["n4_rt_word.dst"].items()}, indent=1))
    for k, v in sorted(tgt.items()):
        print("%-32s moved=%-4d disp=%-4d bytes=%-4d enc=%-4d %s"
              % (k, v["moved"], v["values_dispatched"], v["distinct_bytes"],
                 v["encodable_range"], v["outcomes"]))
    print("wrote", p)


if __name__ == "__main__":
    main(sys.argv[1])
