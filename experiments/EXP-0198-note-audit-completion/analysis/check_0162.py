#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 12 EXP-0162-family notes from EXP-0162's raw.

Two independent claim shapes are tested:
  (a) the per-field outcome histogram  "outcomes {...}" / "Outcomes: {...}"
  (b) the shared "detection power" sentence's own numbers:
        cvt_bf16        "71 of 1816 cases fault"
        cvt_f2h_dst     "86 of 1304 cases fault and 115 silently zero"
        packed_half2_hi "212 of 1304 cases fault and one dst value leaves the
                         read-back word at its 0xDEADBEEF poison"
      -- claims about the WHOLE arm's raw file, so they are checked once per arm.

EXP-0162 has no cross-run gate (single capture per arm, run01); the histogram is
a straight count over `kind == "sweep"` records at the field's byte, which is
what analysis/make_verdicts.py:135-162 prints.  Re-derived here directly from raw.

Read-only.  Writes analysis/check_0162.json.
"""
import ast, collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RAW = os.path.join(ROOT, "experiments", "EXP-0162-g17p-pack-and-splices", "raw")
CFG = {"cvt_bf16": {1: "srcw", 2: "opsel", 3: "src", 4: "fmt", 5: "b5", 6: "dir", 7: "b7"},
       "cvt_f2h_dst": {1: "srcfmt", 2: "opsel", 3: "src", 4: "dhalf", 5: "tail"},
       "packed_half2_hi": {1: "srcA", 2: "opsel", 3: "srcB", 4: "mods_lo", 5: "mods_hi"}}
RUN = "g17p_20260829_run01"


def load(arm):
    p = os.path.join(RAW, "%s__%s" % (RUN, arm), "sweep.jsonl")
    return [json.loads(l) for l in open(p)]


RX_OC = re.compile(r"[Oo]utcomes:? (\{[^}]*\})")
RX_FAULT_OF = re.compile(r"(\d+) of (\d+) cases fault")
RX_AND_ZERO = re.compile(r"(\d+) of (\d+) cases fault and (\d+) silently zero")


def main():
    val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
    nc = set(json.load(open(os.path.join(
        ROOT, "experiments/EXP-0196-note-integrity-audit/work/not_checked.json"))))
    armraw = {a: load(a) for a in CFG}
    # arm-level detection-power figures, re-derived
    armstats = {}
    for a, recs in armraw.items():
        sw = [d for d in recs if d.get("kind") == "sweep"]
        sem = [d for d in recs if d.get("kind") == "semantic"]
        c = collections.Counter(d["outcome"] for d in sw)
        armstats[a] = {"sweep_cases": len(sw), "fault": c.get("fault", 0),
                       "silent_zero": c.get("silent_zero", 0),
                       "semantic_vectors": len(sem),
                       "semantic_matched": sum(1 for d in sem if d.get("match")),
                       "all_outcomes": dict(c)}
    out = {}
    for m, e in sorted(val["instructions"].items()):
        for f, r in sorted(e.items()):
            k = "%s.%s" % (m, f)
            if k not in nc or not isinstance(r, dict) or m not in CFG:
                continue
            note = r.get("note") or ""
            claims = []
            # (a) per-field histogram
            mo = RX_OC.search(note)
            if mo:
                claimed = ast.literal_eval(mo.group(1))
                recs = armraw[m]
                if f == "dst":
                    rs = [d for d in recs if d.get("kind") == "sweep" and d.get("field") == "dst"]
                else:
                    bi = [b for b, n in CFG[m].items() if n == f]
                    rs = [d for d in recs if d.get("kind") == "sweep"
                          and d.get("byte") == (bi[0] if bi else None)] if bi else []
                got = dict(collections.Counter(d["outcome"] for d in rs))
                claims.append({"claim": "outcome_histogram", "claimed": claimed,
                               "raw": got, "n_records": len(rs), "ok": claimed == got})
            # (b) detection-power arm figures
            mo = RX_AND_ZERO.search(note)
            if mo:
                claims.append({"claim": "arm_fault_and_zero",
                               "claimed": {"fault": int(mo.group(1)),
                                           "cases": int(mo.group(2)),
                                           "silent_zero": int(mo.group(3))},
                               "raw": {"fault": armstats[m]["fault"],
                                       "cases": armstats[m]["sweep_cases"],
                                       "silent_zero": armstats[m]["silent_zero"]},
                               "ok": (int(mo.group(1)) == armstats[m]["fault"]
                                      and int(mo.group(2)) == armstats[m]["sweep_cases"]
                                      and int(mo.group(3)) == armstats[m]["silent_zero"])})
            else:
                mo = RX_FAULT_OF.search(note)
                if mo:
                    claims.append({"claim": "arm_fault_of_cases",
                                   "claimed": {"fault": int(mo.group(1)),
                                               "cases": int(mo.group(2))},
                                   "raw": {"fault": armstats[m]["fault"],
                                           "cases": armstats[m]["sweep_cases"]},
                                   "ok": (int(mo.group(1)) == armstats[m]["fault"]
                                          and int(mo.group(2)) == armstats[m]["sweep_cases"])})
            mo = re.search(r"(\d+) semantic vectors", note)
            if mo:
                claims.append({"claim": "semantic_vector_count",
                               "claimed": int(mo.group(1)),
                               "raw": armstats[m]["semantic_vectors"],
                               "raw_matched": armstats[m]["semantic_matched"],
                               "ok": int(mo.group(1)) == armstats[m]["semantic_vectors"]})
            if not claims:
                continue
            out[k] = {"label": r.get("label"), "note": note, "claims": claims,
                      "verdict": "SUPPORTED" if all(c["ok"] for c in claims)
                                 else "CONTRADICTED"}
    json.dump({"per_note": out, "arm_stats": armstats},
              open(os.path.join(HERE, "check_0162.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0162 family:", len(out), dict(c))
    print("arm stats:", json.dumps(armstats, sort_keys=True))
    for k, v in sorted(out.items()):
        if v["verdict"] != "SUPPORTED":
            print("\n%s" % k)
            for cl in v["claims"]:
                if not cl["ok"]:
                    print("   ", json.dumps(cl))


if __name__ == "__main__":
    main()
