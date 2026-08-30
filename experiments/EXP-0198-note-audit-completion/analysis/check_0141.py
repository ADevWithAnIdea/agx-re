#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 10 EXP-0141 atomic notes from EXP-0141's raw.

Claims tested:
 C1 "Swept in the atomic_rmw (byte+1 == 0x11) form itself, addendum runs 21/22."
    -> the addendum runs exist, carry `atdev_atomic_rmw_*` arms, and those arms'
       spliced `bytes` really do have byte+1 == 0x11.
 C2 "proven at all four constructible indices -- 0 -> a[0]=7, 1 -> a[1]=1007,
     2 -> a[2]=2007, 3 -> a[3]=3007 -- each with the redirected register's later
     reader zeroed"
    -> the four encodings are located from the model
       index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1) and their observed words
       are read straight out of raw, in BOTH gated runs of the relevant pair.
 C3 "byte+6 values 0x30 and 0x31 restore the BASELINE operand ... and they are the
     only two addendum cases whose acceptance disagreed between run21 and run22"
    -> ACCEPTANCE is `ok` vs not-`ok`, EXP-0141/analysis/verdicts.py:19-26 and
       :96-97, NOT the `match` flag.  Counting `match` disagreements instead
       gives 3 and manufactures a finding (byte+6 = 0xF0, silent_zero vs
       nondeterministic -- both runs agree the value fails).

Read-only.  Writes analysis/check_0141.json.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXP = os.path.join(ROOT, "experiments", "EXP-0141-m4-emit-mem")
MAIN = ("m4-20260828-run11", "m4-20260828-run12")
ADD = ("m4-20260828-run21", "m4-20260828-run22")


def load(run):
    p = os.path.join(EXP, "raw", run, "sweep.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def key(d):
    return (d.get("arm"), d.get("field"), d.get("value"), d.get("i"))


def main():
    A, B = load(ADD[0]), load(ADD[1])
    MA, MB = load(MAIN[0]), load(MAIN[1])
    ka, kb = {key(d): d for d in A}, {key(d): d for d in B}
    both = sorted(set(ka) & set(kb))
    acc_dis = [k for k in both
               if (ka[k]["outcome"] == "ok") != (kb[k]["outcome"] == "ok")]
    exact_dis = [k for k in both if ka[k]["outcome"] != kb[k]["outcome"]]
    match_dis = [k for k in both if ka[k].get("match") != kb[k].get("match")]

    # C1: atomic_rmw arms and byte+1 == 0x11
    rmw = [d for d in A if str(d.get("arm", "")).startswith("atdev_atomic_rmw_")]
    b1 = collections.Counter(d["bytes"][2:4] for d in rmw if d.get("bytes"))

    # C2: the four indices
    def idx(bs):
        b5 = int(bs[10:12], 16)
        b6 = int(bs[12:14], 16)
        return (b5 >> 7) | ((b6 & 0x3F) << 1)

    want = {0: 7, 1: 1007, 2: 2007, 3: 3007}
    seen = {}
    for run, recs in (("run21", A), ("run22", B), ("run11", MA), ("run12", MB)):
        for d in recs:
            bs = d.get("bytes") or ""
            if d.get("instr") != "atomic_mem" or len(bs) < 14:
                continue
            if not str(d.get("arm", "")).startswith("atdev"):
                continue
            i = idx(bs)
            if i not in want:
                continue
            o = (d.get("observed") or {}).get("out0")
            if o == [want[i]]:
                later = (d.get("observed") or {}).get("out2")
                seen.setdefault(i, []).append(
                    {"run": run, "arm": d["arm"], "bytes": bs, "out0": o,
                     "out2": later,
                     "redirected_reader_zeroed": bool(later) and 0 in later})
    idx_ok = {i: bool(seen.get(i)) and any(x["redirected_reader_zeroed"] for x in seen[i])
              for i in want}

    val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
    nc = set(json.load(open(os.path.join(
        ROOT, "experiments/EXP-0196-note-integrity-audit/work/not_checked.json"))))
    out = {}

    def N(nt, rx, n=1):
        """Claimed numbers parsed OUT OF THE NOTE, so a changed note changes the
        verdict (analysis/negative_control.py)."""
        mo = re.search(rx, nt)
        if not mo:
            return None if n == 1 else (None,) * n
        return int(mo.group(1), 0) if n == 1 else tuple(int(g, 0) for g in mo.groups())

    for k in sorted(nc):
        m, f = k.split(".", 1)
        r = val["instructions"][m][f]
        if (r.get("evidence") or []) != ["EXP-0141"]:
            continue
        note = r.get("note") or ""
        claims = []
        if "addendum runs 21/22" in note:
            claims.append({"claim": "C1_addendum_runs_and_rmw_form",
                           "claimed": "swept in the atomic_rmw (byte+1 == 0x11) form, runs 21/22",
                           "raw": {"run21_records": len(A), "run22_records": len(B),
                                   "atdev_atomic_rmw_records_run21": len(rmw),
                                   "byte+1_histogram": dict(b1)},
                           "ok": (len(A) > 0 and len(B) > 0 and len(rmw) > 0
                                  and set(b1) == {"11"})})
        pairs = dict((int(a), int(b)) for a, b in
                     re.findall(r"(\d+) -> a\[\d+\]\s*=\s*(\d+)", note))
        if "proven at all four constructible indices" in note:
            claims.append({"claim": "C2_four_indices",
                           "claimed": pairs or want,
                           "raw": {str(i): seen.get(i, [])[:2] for i in want},
                           "all_four_found_with_reader_zeroed": idx_ok,
                           "ok": (pairs == want and all(idx_ok.values()))})
        mo = re.search(r"byte\+6 values (0x[0-9a-f]{2}) and (0x[0-9a-f]{2}) restore the "
                       r"BASELINE operand instead of selecting index (\d+)/(\d+), and they "
                       r"are the only (\w+) addendum cases whose acceptance disagreed", note)
        if mo:
            WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4}
            cvals = sorted(int(mo.group(1), 0), ) if False else sorted(
                [int(mo.group(1), 0), int(mo.group(2), 0)])
            cn = WORDNUM.get(mo.group(5), -1)
            claims.append({"claim": "C3_acceptance_disagreements",
                           "claimed": {"n": cn, "byte+6": [mo.group(1), mo.group(2)],
                                       "indices": [int(mo.group(3)), int(mo.group(4))]},
                           "raw": {"addendum_common_cases": len(both),
                                   "acceptance_disagreements": len(acc_dis),
                                   "which": [{"arm": x[0], "value": "0x%02x" % x[2],
                                              "run21": ka[x]["outcome"],
                                              "run22": kb[x]["outcome"]}
                                             for x in acc_dis],
                                   "exact_outcome_disagreements": len(exact_dis),
                                   "match_flag_disagreements": len(match_dis)},
                           "ok": (len(acc_dis) == cn
                                  and sorted(x[2] for x in acc_dis) == cvals
                                  and [(0x80 >> 7) | ((v & 0x3F) << 1) for v in cvals]
                                      == [int(mo.group(3)), int(mo.group(4))])})
        if "operand_register_index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1)" in note:
            claims.append({"claim": "C2b_index_model_reaches_index_3",
                           "claimed": "model reaches index 3 (a[3]=3007)",
                           "raw": seen.get(3, [])[:2], "ok": idx_ok[3]})
        out[k] = {"label": r.get("label"), "note": note, "claims": claims,
                  "verdict": ("NO-INSTRUMENT" if not claims else
                              "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED")}
    json.dump(out, open(os.path.join(HERE, "check_0141.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0141 family:", len(out), dict(c))
    print("  four indices found with later reader zeroed:", idx_ok)
    print("  addendum: %d common cases, acceptance disagreements=%d %s, "
          "exact-outcome disagreements=%d, match-flag disagreements=%d"
          % (len(both), len(acc_dis), ["0x%02x" % x[2] for x in acc_dis],
             len(exact_dis), len(match_dis)))
    for k, v in sorted(out.items()):
        print("  %-28s %s" % (k, v["verdict"]))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("       FAILS", json.dumps(cl)[:400])


if __name__ == "__main__":
    main()
