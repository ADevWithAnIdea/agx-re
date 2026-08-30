#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 8 EXP-0140-family field notes from EXP-0140's raw.

Rows: if_push.scope_kind, pop_reconverge.scope, pop_reconverge.scope_kind,
      psel.flag, psel.mode, psel.sel, mov_imm.dst, uniform_mov.usrc.

GATE.  EXP-0140's gated pair is run02 + run03 -- `analysis/verdicts.py:140`
defaults to `["m4_20260828_run02", "m4_20260828_run03"]` and
`analysis/field_verdicts.json["runs"]` confirms it.  raw/m4_20260828_run01 is a
third capture that is NOT the gate.  Pairing run01/run02 would be an artefact.

Definitions re-implemented from verdicts.py:215-238 (documented there):
  comparable = case pairs keyed by case index `i` present in both runs with
               neither side `invalid_run` or `skipped`
  stable     = comparable pairs whose (outcome, observed) are identical
  executed   = cases whose outcome is not `skipped`

Read-only.  Writes analysis/check_0140.json.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXP = os.path.join(ROOT, "experiments", "EXP-0140-m4-emit-mov-cf")
GATED = ("m4_20260828_run02", "m4_20260828_run03")

# validation.json key -> EXP-0140 case-group name (from verdicts.py's CF_FIELDS
# and analyse_psel / analyse_mov / analyse_regmove)
GROUP = {
    "if_push.scope_kind": "if_push.scope_kind@7",
    "pop_reconverge.scope": "pop_reconverge.scope@14",
    "pop_reconverge.scope_kind": "pop_reconverge.scope_kind@14",
    "psel.flag": "psel.flag",
    "psel.mode": "psel.mode",
    "psel.sel": "psel.sel",
    "mov_imm.dst": "mov_imm.dst",
    "uniform_mov.usrc": "regmove.usrc",
}
USRC_UNIFORM = None   # read from the harness's frozen case matrix below


def load(run):
    out = {}
    for l in open(os.path.join(EXP, "raw", run, "sweep.jsonl")):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        if r.get("kind") != "case":
            continue
        out[r["i"]] = r
    return out


def repair_signed_compare(cases):
    """verdicts.py:38-61.  The capture driver compared the raw u32 word against a
    SIGNED int32 oracle, so any expected value with bit 31 set (the bound uniform
    constant 0xA1B2C3D4, and the poison fill) scored a mismatch even when
    `observed` == `oracle` in the record itself.  The outcome is recomputed from
    the record's own fields; raw is not edited.  OMITTING THIS makes
    uniform_mov.usrc's `8/8 mapped uniform indices` read as 6/8."""
    n = 0
    for r in cases.values():
        if r["outcome"] in ("hang", "fault", "skipped", "invalid_run"):
            continue
        obs, orc = r["observed"], r["oracle"]
        if not orc or any(obs.get(k) is None for k in orc):
            continue
        match = all(obs.get(k) == v for k, v in orc.items())
        prim = obs[sorted(orc, key=int)[0]]
        outcome = "ok" if match else ("silent_zero" if prim == 0 else "wrong_value")
        if (match, outcome) != (r["match"], r["outcome"]):
            r["match"], r["outcome"] = match, outcome
            n += 1
    return n


def reclassify_no_store(a, b):
    """verdicts.py:64-94.  A case that is `invalid_run` in BOTH gated runs with
    every trial STATUS OK is a real encoding effect (the store never executed),
    not contamination, and is re-labelled `wrong_value`.  OMITTING THIS makes
    if_push.scope_kind's `242 comparable` read as 192."""
    n = 0
    for i, ra in a.items():
        rb = b.get(i)
        if rb is None:
            continue
        if ra["outcome"] != "invalid_run" or rb["outcome"] != "invalid_run":
            continue
        if not all(st == "OK" for r in (ra, rb) for st in r.get("trial_statuses", [])):
            continue
        for r in (ra, rb):
            r["outcome"] = "wrong_value"
        n += 1
    return n


A, B = load(GATED[0]), load(GATED[1])
N_REPAIR = repair_signed_compare(A) + repair_signed_compare(B)
N_NOSTORE = reclassify_no_store(A, B)


def rows(cases, group):
    return [r for r in cases.values() if r.get("group") == group]


def gate(group):
    ra = rows(A, group)
    ib = B
    comparable, stable = [], []
    for r in ra:
        s = ib.get(r["i"])
        if s is None:
            continue
        if r["outcome"] in ("invalid_run", "skipped") or s["outcome"] in ("invalid_run", "skipped"):
            continue
        comparable.append((r, s))
        if (r["outcome"], r["observed"]) == (s["outcome"], s["observed"]):
            stable.append(r)
    skipped = [r for r in ra if r["outcome"] == "skipped"]
    return {"n": len(ra), "executed": len(ra) - len(skipped), "skipped": len(skipped),
            "comparable": len(comparable), "stable": len(stable),
            "outcomes": dict(collections.Counter(r["outcome"] for r in ra))}


RX_CF = re.compile(r"(\d+)/(\d+) values executed \((\d+) skipped by the hang budget\); "
                   r"(\d+) comparable across the two gated runs [^;]*, (\d+) of those identical")
RX_PSEL = re.compile(r"(\d+)/(\d+) comparable values reproduced identically across both "
                     r"gated runs \(of (\d+) swept\)")
RX_MOVDST = re.compile(r"all (\d+) values executed with a host-computed oracle; "
                       r"(\w+) 12-register aliasing scans confirm no second register changes; "
                       r"(\d+)/(\d+) values reproduced identically across both gated runs")
RX_USRC = re.compile(r"(\d+)/128 immediate-region values matched their host-computed oracle "
                     r"exactly; (\d+)/8 mapped uniform indices returned the bound magic constant")


def main():
    val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
    nc = set(json.load(open(os.path.join(
        ROOT, "experiments/EXP-0196-note-integrity-audit/work/not_checked.json"))))
    out = {}
    for k, grp in sorted(GROUP.items()):
        if k not in nc:
            continue
        m, f = k.split(".", 1)
        r = val["instructions"][m][f]
        note = r.get("note") or ""
        g = gate(grp)
        claims = []
        mo = RX_CF.search(note)
        if mo:
            claims.append({"claim": "cf_executed_comparable_identical",
                           "claimed": {"executed": int(mo.group(1)), "n": int(mo.group(2)),
                                       "skipped": int(mo.group(3)),
                                       "comparable": int(mo.group(4)),
                                       "identical": int(mo.group(5))},
                           "raw": g,
                           "ok": (int(mo.group(1)) == g["executed"] and int(mo.group(2)) == g["n"]
                                  and int(mo.group(3)) == g["skipped"]
                                  and int(mo.group(4)) == g["comparable"]
                                  and int(mo.group(5)) == g["stable"])})
        mo = RX_PSEL.search(note)
        if mo:
            claims.append({"claim": "psel_stable_of_comparable_of_swept",
                           "claimed": {"stable": int(mo.group(1)),
                                       "comparable": int(mo.group(2)),
                                       "n": int(mo.group(3))},
                           "raw": g,
                           "ok": (int(mo.group(1)) == g["stable"]
                                  and int(mo.group(2)) == g["comparable"]
                                  and int(mo.group(3)) == g["n"])})
        mo = RX_MOVDST.search(note)
        if mo:
            scan = gate("mov_imm.dst.alias_scan")
            claims.append({"claim": "mov_imm_dst",
                           "claimed": {"values": int(mo.group(1)),
                                       "scans": mo.group(2),
                                       "identical": int(mo.group(3)),
                                       "of": int(mo.group(4))},
                           "raw": g, "raw_alias_scan": scan,
                           "ok": (int(mo.group(1)) == g["n"]
                                  and int(mo.group(3)) == g["stable"]
                                  and int(mo.group(4)) == g["n"]
                                  and scan["n"] > 0
                                  and scan["stable"] == scan["comparable"])})
        mo = RX_USRC.search(note)
        if mo:
            ra = rows(A, grp)
            st = {r["i"] for r in gate_stable(grp)}
            imm_ok = [r for r in ra if r["i"] in st and r["value"] >= 0x80
                      and r["outcome"] == "ok"]
            uni_ok = [r for r in ra if r["i"] in st and r["value"] < 0x80
                      and r["outcome"] == "ok"]
            claims.append({"claim": "uniform_mov_usrc",
                           "claimed": {"imm_ok": int(mo.group(1)),
                                       "uniform_ok": int(mo.group(2))},
                           "raw": {"imm_region_ok_stable": len(imm_ok),
                                   "uniform_region_ok_stable": len(uni_ok),
                                   "uniform_ok_values": sorted(r["value"] for r in uni_ok)},
                           "ok": (len(imm_ok) == int(mo.group(1))
                                  and len(uni_ok) == int(mo.group(2)))})
        out[k] = {"label": r.get("label"), "group": grp, "note": note, "claims": claims,
                  "verdict": ("NO-INSTRUMENT" if not claims else
                              "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED")}
    json.dump(out, open(os.path.join(HERE, "check_0140.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0140 family:", len(out), dict(c),
          "| repaired_signed_compare=%d reclassified_no_store=%d" % (N_REPAIR, N_NOSTORE))
    for k, v in sorted(out.items()):
        print("  %-28s %s" % (k, v["verdict"]))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("       FAILS", json.dumps(cl)[:400])


def gate_stable(group):
    ra = rows(A, group)
    st = []
    for r in ra:
        s = B.get(r["i"])
        if s is None:
            continue
        if r["outcome"] in ("invalid_run", "skipped") or s["outcome"] in ("invalid_run", "skipped"):
            continue
        if (r["outcome"], r["observed"]) == (s["outcome"], s["observed"]):
            st.append(r)
    return st


if __name__ == "__main__":
    main()
