#!/usr/bin/env python3
"""EXP-0160 analysis: raw sweep records -> per-field verdicts (G17P).

  python3 analysis/verdicts.py raw/<runA> raw/<runB> [--confirm raw/<confirmNN>]

Applies the promotion rule frozen in PRE_REGISTRATION.md section 7 (P1..P5) and
writes `analysis/field_verdicts.json` in FIELD-SWEEP-PROTOCOL section 5 schema,
plus a `db_defects` block (protocol section 6).

Nothing here re-runs hardware; it is a pure function of the committed raw logs.
"""
from __future__ import print_function

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP / "harness"))
import modelfit as MF        # noqa: E402
import isa_helpers as H      # noqa: E402
import casematrix as CM      # noqa: E402

POISON = H.POISON
SUSPECT = ("fault", "hang", "undecodable")


# --------------------------------------------------------------------------
# Independent host-computed oracles (PRE_REGISTRATION section 5).
# Each returns {reg: expected_word} for the UNMUTATED block, computed from the
# seed table alone -- no GPU involved. Operand registers are read off the
# anchor bytes, which are recorded in CAPTURE_CONTRACT.json.
# --------------------------------------------------------------------------
def fbits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def sat(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def oracle_F2E(s):      # falu2_ext: r0 = saturate(r0 + r2); r2 released
    return {0: fbits(sat(s[0] + s[2])), 2: 0}


def oracle_F3(s):       # falu3: r0 = r0*r2 + r4; r2, r4 released
    return {0: fbits(H.f32(H.f32(s[0] * s[2]) + s[4])), 2: 0, 4: 0}


def oracle_F3E(s):      # falu3_ext: r0 = saturate(r0*r2 + r4)
    return {0: fbits(sat(H.f32(H.f32(s[0] * s[2]) + s[4]))), 2: 0, 4: 0}


def oracle_IMIN(s):     # iminmax: r0 = min(r0, r2); r2 released
    return {0: min(s[0], s[2]) & 0xFFFFFFFF, 2: 0}


def oracle_IMAD(s):     # imad: r0 = r0*r2 + K, K seed-independent (K==1 here)
    return {0: (s[0] * s[2] + 1) & 0xFFFFFFFF, 2: 0}


def oracle_HALF(s):
    # half_alu on fp16 DENORMALS: an integer seed <= 127 is the fp16 significand
    # 0x00xx, and denormal+denormal is exact significand addition, so the packed
    # low half of r1 becomes seed[1] + seed[2].
    return {1: (s[1] + s[2]) & 0xFFFFFFFF, 2: 0}


def oracle_F2I(s):
    # falu2i anchor 09 c9 14 01 80 c0: r0 = r0 + imm_decode(0xc9, sign=0)
    k = H.isadb.imm_decode(0xC9, 0)
    return {0: fbits(H.f32(s[0] + k))}


ORACLE = {"F2E_CTRL": oracle_F2E, "F3_OP": oracle_F3, "F3E_OP": oracle_F3E,
          "IMINMAX_SRCB": oracle_IMIN, "IMAD_SRCC": oracle_IMAD,
          "HALFPACK_SRC": oracle_HALF, "F2I_CTRLLO": oracle_F2I,
          "ISEL8_CMPMODE": None}   # structural only -- see RESULTS.md

# Operand registers each arm's instruction actually names, read off the anchor.
ARM_OPERANDS = {"F2E_CTRL": (0, 2, None), "F3_OP": (0, 2, 4),
                "F3E_OP": (0, 2, 4), "IMINMAX_SRCB": (0, 2, None),
                "IMAD_SRCC": (0, 2, None), "HALFPACK_SRC": (1, 2, None),
                "F2I_CTRLLO": (0, None, None), "ISEL8_CMPMODE": (0, 7, None)}


def arith_library(kind, s, ops):
    """Candidate host-computed functions of the anchor's own operands."""
    a, b, c = ops
    out = {}

    def put(name, val):
        if val is None:
            return
        out[name] = val & 0xFFFFFFFF

    if kind == "float":
        A = s.get(a) if a is not None else None
        B = s.get(b) if b is not None else None
        C = s.get(c) if c is not None else None
        if A is not None:
            put("a", fbits(A)); put("-a", fbits(-A))
        if B is not None:
            put("b", fbits(B)); put("-b", fbits(-B))
        if C is not None:
            put("c", fbits(C))
        if A is not None and B is not None:
            put("a+b", fbits(H.f32(A + B))); put("a*b", fbits(H.f32(A * B)))
            put("a-b", fbits(H.f32(A - B))); put("b-a", fbits(H.f32(B - A)))
            put("sat(a+b)", fbits(sat(H.f32(A + B))))
            put("sat(a*b)", fbits(sat(H.f32(A * B))))
            put("min(a,b)", fbits(min(A, B))); put("max(a,b)", fbits(max(A, B)))
        if A is not None and B is not None and C is not None:
            put("a*b+c", fbits(H.f32(H.f32(A * B) + C)))
            put("a*b+a", fbits(H.f32(H.f32(A * B) + A)))
            put("a*b+b", fbits(H.f32(H.f32(A * B) + B)))
            put("a*b-c", fbits(H.f32(H.f32(A * B) - C)))
            put("-(a*b)+c", fbits(H.f32(C - H.f32(A * B))))
            put("a+b+c", fbits(H.f32(H.f32(A + B) + C)))
            put("sat(a*b+c)", fbits(sat(H.f32(H.f32(A * B) + C))))
            put("a*c", fbits(H.f32(A * C))); put("b*c", fbits(H.f32(B * C)))
            put("a+c", fbits(H.f32(A + C)))
    else:
        A = s.get(a) if a is not None else None
        B = s.get(b) if b is not None else None
        if A is not None:
            put("a", A)
        if B is not None:
            put("b", B)
        if A is not None and B is not None:
            put("a+b", A + B); put("a*b", A * B); put("a-b", A - B)
            put("a*b+1", A * B + 1); put("min(a,b)", min(A, B))
            put("max(a,b)", max(A, B)); put("a&b", A & B); put("a|b", A | B)
            put("a^b", A ^ B)
    put("zero", 0)
    return out


def identify(word, lib):
    return sorted(n for n, v in lib.items() if v == word)


# --------------------------------------------------------------------------
def load_sweep(rundir):
    recs = {}
    for ln in (Path(rundir) / "sweep.jsonl").open():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        recs[r["idx"]] = r          # last write wins (resume-safe)
    return recs


def load_confirm(rundir):
    """Isolated verdicts, FIELD-SWEEP-PROTOCOL 7A: idx -> majority outcome
    over the lease-held repetitions, plus the digest if it is unanimous."""
    reps = defaultdict(list)
    p = Path(rundir) / "confirm.jsonl"
    if not p.exists():
        return {}
    for ln in p.open():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        reps[r["idx"]].append(r)
    out = {}
    for idx, rs in reps.items():
        oc = Counter(r["outcome"] for r in rs)
        best, n = oc.most_common(1)[0]
        digs = set(r["observed"]["digest"] for r in rs if r["outcome"] == best)
        out[idx] = {"outcome": best, "n": len(rs), "agree": n,
                    "digest": (digs.pop() if len(digs) == 1 else None),
                    "regs": next((r["observed"]["regs"] for r in rs
                                  if r["outcome"] == best), None),
                    "spread": dict(oc)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--out", default=str(HERE / "field_verdicts.json"))
    a = ap.parse_args()

    runs = [load_sweep(EXP / r if not Path(r).is_absolute() else r)
            for r in a.runs]
    conf = load_confirm(EXP / a.confirm) if a.confirm else {}
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = {c["idx"]: c for c in CM.build_cases(rep)}

    # ---- P5 then P2: isolated verdicts override, then the cross-run gate ----
    gated, disagree, unresolved = {}, Counter(), Counter()
    for idx, c in cases.items():
        rs = [R.get(idx) for R in runs]
        rs = [r for r in rs if r is not None]
        if len(rs) < len(runs):
            unresolved[(c["arm"], c["field"])] += 1
            continue
        ocs = [r["outcome"] for r in rs]
        digs = [r["observed"]["digest"] for r in rs]
        if any(o in SUSPECT for o in ocs):
            if idx in conf:
                cf = conf[idx]
                gated[idx] = {"outcome": cf["outcome"], "digest": cf["digest"],
                              "regs": cf["regs"], "source": "isolated",
                              "confirm": cf}
                continue
            unresolved[(c["arm"], c["field"])] += 1
            continue
        if len(set(ocs)) > 1 or len(set(digs)) > 1:
            disagree[(c["arm"], c["field"])] += 1
            continue
        gated[idx] = {"outcome": ocs[0], "digest": digs[0],
                      "regs": rs[0]["observed"]["regs"], "source": "gated",
                      "poison_words": rs[0].get("poison_words"),
                      "frame": rs[0].get("frame")}

    # ---- per-arm baselines, falsifiers, oracles ---------------------------
    base_regs = {}                # (arm, sset) -> regs
    for idx, g in gated.items():
        c = cases[idx]
        k = (c["arm"], c["sset"])
        if k not in base_regs:
            for R in runs:
                r = R.get(idx)
                if r and r["oracle"]["digest"]:
                    d = r["oracle"]["digest"]
                    base_regs[k] = [int(d[i * 8:(i + 1) * 8], 16) for i in range(16)]
                    break
    fals = defaultdict(dict)
    for idx, g in gated.items():
        c = cases[idx]
        if c["field"] == "__falsifier_byte0":
            fals[c["arm"]][c["sset"]] = g["outcome"]

    arm_report = {}
    for (arm, fn, lo, hi, tgt, mn, kind, field) in CM.resolve_arms(rep):
        orc = ORACLE.get(arm)
        rows = {}
        for ss in CM.SEED_SETS:
            b = base_regs.get((arm, ss))
            if b is None:
                rows[ss] = {"baseline": None, "oracle": "no baseline"}
                continue
            if orc is None:
                rows[ss] = {"baseline": b, "oracle": "structural-only",
                            "oracle_ok": None}
                continue
            want = orc(H.seeds_for(kind, ss))
            bad = {r: [b[r], v] for r, v in want.items() if b[r] != v}
            rows[ss] = {"baseline": b, "oracle": {str(k): v for k, v in want.items()},
                        "oracle_ok": not bad,
                        "oracle_mismatch": {str(k): v for k, v in bad.items()}}
        arm_report[arm] = {
            "instr": mn, "field": field, "probe": fn, "block": [lo, hi],
            "tgt": tgt, "seed_kind": kind,
            "falsifier_outcome": fals.get(arm, {}),
            "falsifier_fired": all(o != "ok" for o in fals.get(arm, {}).values())
                               and len(fals.get(arm, {})) == len(CM.SEED_SETS),
            "per_seed_set": rows,
        }

    # ---- group the dense sweeps ------------------------------------------
    groups = defaultdict(lambda: defaultdict(dict))   # (arm,instr,field) -> sset -> v -> g
    extras = defaultdict(list)
    for idx, g in gated.items():
        c = cases[idx]
        if c["field"].startswith("__falsifier"):
            continue
        if c["field"].startswith("__"):
            extras[(c["arm"], c["field"])].append((c, g))
            continue
        groups[(c["arm"], c["instr"], c["field"])][c["sset"]][c["value"]] = g

    out = {}
    for (arm, instr, field), by_ss in sorted(groups.items()):
        c0 = next(iter(cases[i] for i in cases
                       if cases[i]["arm"] == arm and cases[i]["field"] == field))
        w = c0["fwidth"]
        anchor_v = c0["anchor_value"]
        kind = c0["kind"]
        ar = arm_report[arm]

        sigs, outs, dumps = {}, {}, {}
        for ss in CM.SEED_SETS:
            b = base_regs.get((arm, ss))
            sigs[ss], outs[ss], dumps[ss] = {}, {}, {}
            for v, g in by_ss.get(ss, {}).items():
                outs[ss][v] = g["outcome"]
                dumps[ss][v] = g["regs"]
                sigs[ss][v] = (MF.sig(g["regs"], b) if (g["regs"] and b)
                               else "X:" + g["outcome"])

        # P2 density / coverage
        full = set(range(1 << w))
        cover = {ss: sorted(full - set(outs[ss])) for ss in CM.SEED_SETS}
        dense = all(not cover[ss] for ss in CM.SEED_SETS)

        # P3 out-of-sample structural prediction
        common = set(sigs[1]) & set(sigs[2])
        p3_bad = sorted(v for v in common if sigs[1][v] != sigs[2][v])
        p3 = (not p3_bad) and bool(common)

        # P1 arm validity
        anchor_ok = all(outs[ss].get(anchor_v) == "ok" for ss in CM.SEED_SETS)
        oracles_ok = all(ar["per_seed_set"][ss].get("oracle_ok") is not False
                         for ss in CM.SEED_SETS)
        p1 = ar["falsifier_fired"] and anchor_ok and oracles_ok

        # P4 model class, fitted on seed set 1 (the sigs are identical under P3)
        sm = sigs[1]
        okv = [v for v in outs[1] if outs[1][v] == "ok"]
        m, val, exc = MF.mask_rule(okv, list(sm), w)
        relb = MF.relevant_bits(sm, w)
        tab, texc, sup, relb = MF.class_table(sm, relb, w)
        m1 = (exc == 0 and dense and bool(okv))
        m2 = (texc == 0 and len(relb) <= w - 2 and dense and sup >= 4)
        sc = MF.regmap_score(dumps[1], base_regs.get((arm, 1), [0] * 16))
        bm_rel = MF.best_regmodel(sc["released"])
        bm_wr = MF.best_regmodel(sc["written"])
        m3 = bool(bm_rel or bm_wr)

        # M4 ARITH: identify the value written to each changed register, in BOTH
        # seed sets, and keep only identifications that agree.
        arith = {}
        for v in sorted(common):
            names = None
            for ss in CM.SEED_SETS:
                b = base_regs.get((arm, ss))
                regs = dumps[ss][v]
                if not regs or not b:
                    names = None
                    break
                lib = arith_library(kind, H.seeds_for(kind, ss), ARM_OPERANDS[arm])
                got = {}
                for i in range(16):
                    if regs[i] != b[i] and regs[i] != POISON:
                        got[i] = set(identify(regs[i], lib))
                if names is None:
                    names = got
                else:
                    names = {i: names.get(i, set()) & got.get(i, set())
                             for i in set(names) & set(got)}
            if names:
                nm = {str(i): sorted(s) for i, s in names.items() if s}
                if nm:
                    arith[str(v)] = nm
        m4 = len(arith) > 0

        # --- M4 extension, integer arms: is the destination AFFINE in the
        # product?  r0(v, seedset) = m(v) * (srcA*srcB) + A(v), with m(v) in
        # {0,1} and A(v) required to be the SAME under both seed sets.
        # The two seed sets give two equations for two unknowns *plus one
        # constraint*, so this is a test, not a fit: r0_1 - r0_2 must be either
        # 0 (no product term) or P_1 - P_2 (product term), and nothing else.
        affine = None
        if kind == "int" and ARM_OPERANDS[arm][1] is not None:
            oa, ob, _ = ARM_OPERANDS[arm]
            P = {}
            for ss in CM.SEED_SETS:
                sd = H.seeds_for(kind, ss)
                P[ss] = (sd[oa] * sd[ob]) & 0xFFFFFFFF
            dP = (P[1] - P[2]) & 0xFFFFFFFF
            tab_aff, exc_aff = {}, []
            for v in sorted(common):
                r1, r2 = dumps[1][v], dumps[2][v]
                if not r1 or not r2 or POISON in r1 or POISON in r2:
                    continue
                d = (r1[0] - r2[0]) & 0xFFFFFFFF
                if d == 0:
                    mm = 0
                elif d == dP:
                    mm = 1
                else:
                    exc_aff.append(v)
                    continue
                A1 = (r1[0] - mm * P[1]) & 0xFFFFFFFF
                A2 = (r2[0] - mm * P[2]) & 0xFFFFFFFF
                if A1 != A2:
                    exc_aff.append(v)
                    continue
                tab_aff[v] = [mm, A1]
            affine = {"model": "r0 = m(v)*(srcA*srcB) + A(v), m in {0,1}, "
                               "A seed-independent",
                      "tested": len(tab_aff) + len(exc_aff),
                      "explained": len(tab_aff),
                      "exceptions": exc_aff[:32],
                      "n_exceptions": len(exc_aff),
                      "product": {str(k): vv for k, vv in P.items()},
                      "map": {str(k): vv for k, vv in sorted(tab_aff.items())},
                      "distinct_addends": sorted(set(t[1] for t in tab_aff.values())),
                      "addend_depends_only_on_high5":
                          len(set((v >> 3, tab_aff[v][1]) for v in tab_aff)) ==
                          len(set(v >> 3 for v in tab_aff)),
                      "product_flag_depends_only_on_low2":
                          len(set((v & 3, tab_aff[v][0]) for v in tab_aff)) ==
                          len(set(v & 3 for v in tab_aff)),
                      "addend_by_K": {str(k): vv for k, vv in
                                      sorted({v >> 3: tab_aff[v][1]
                                              for v in tab_aff}.items())}}

        inert = [b for b in range(w) if b not in relb]
        oc = Counter(outs[1].values())
        model, semantics = None, None
        if m1:
            model = "M1 MASK"
            semantics = "ok <=> (v & 0x%02x) == 0x%02x, 0 exceptions over the dense %d-value range" % (m, val, 1 << w)
        elif m2:
            model = "M2 CLASS TABLE"
            semantics = ("complete %d-class behaviour table over the non-inert bits %s "
                         "(bits %s inert); every class confirmed by >=%d distinct field values"
                         % (len(tab), relb, inert, sup))
        if m1 and m2:
            model = "M1 MASK + M2 CLASS TABLE"

        if not p1:
            label = "untested"
            why = ("arm %s failed P1 (falsifier_fired=%s anchor_value_ok=%s host_oracle_ok=%s)"
                   % (arm, ar["falsifier_fired"], anchor_ok, oracles_ok))
        elif not dense:
            label = "untested"
            why = ("P2 failed: %s of %d values missing from the gated set "
                   "(seed set 1: %d, seed set 2: %d) -- see `uncovered`"
                   % (max(len(cover[1]), len(cover[2])), 1 << w,
                      len(cover[1]), len(cover[2])))
        elif not p3:
            label = "untested"
            why = ("P3 failed: the register-role signature differs between the two "
                   "seed sets at %d values %s" % (len(p3_bad), p3_bad[:12]))
        elif model is None and not m3:
            label = "untested"
            why = ("P4 failed: no 0-exception model in the frozen class. Mask rule "
                   "(v & 0x%02x)==0x%02x has %s exceptions; %d of %d bits are live "
                   "(class table needs <=%d) -- reported as a finding, not promoted."
                   % (m, val, exc, len(relb), w, w - 2))
        elif len(okv) == len(outs[1]) and not any(s != sm[okv[0]] for s in sm.values()):
            label = "hardware-run"
            why = "INERT across the whole encodable range (all %d values reproduce the anchor)" % (1 << w)
        else:
            label = "hardware-run"
            why = model or ("M3 REGMAP: %s" % ((bm_rel or bm_wr)[0]))

        entry = {
            "label": label, "target": "G17P",
            "range": ("0..%d dense (all %d values), each under TWO independent seed sets"
                      % ((1 << w) - 1, 1 << w)) if dense else
                     ("%d of %d values gated" % (len(outs[1]), 1 << w)),
            "evidence": ["EXP-0160"],
            "semantics": semantics or why,
            "note": ("carrier %s; outcomes(seed set 1) %s; anchor value 0x%02x; "
                     "P1=%s P2=%s P3=%s model=%s"
                     % ("SYNTH+LIFTED:%s@%s[%d:%d]" % (c0["probe"], instr,
                                                       c0["block_lo"], c0["block_hi"]),
                        dict(oc), anchor_v, p1, dense, p3, model)),
            "why": why,
            "arm": arm,
            "p1_arm_valid": p1, "p2_dense_and_gated": dense,
            "p3_cross_seed_signature_stable": p3,
            "p3_mismatches": p3_bad[:32],
            "p4_model": model,
            "mask_rule": {"mask": m, "value": val, "exceptions": exc},
            "relevant_bits": relb, "inert_bits": inert,
            "class_table": {str(k): v for k, v in tab.items()},
            "class_min_support": sup,
            "regmodel_released": (bm_rel[0] if bm_rel else None),
            "regmodel_written": (bm_wr[0] if bm_wr else None),
            "regmodel_scores": sc,
            "arith_identified": arith,
            "affine_in_product": affine,
            "outcomes_seed1": dict(oc),
            "outcomes_seed2": dict(Counter(outs[2].values())),
            "uncovered": {"seed1": cover[1][:32], "seed2": cover[2][:32]},
            "isolated_verdicts_used": sorted(
                cases[i]["value"] for i in gated
                if gated[i]["source"] == "isolated" and cases[i]["arm"] == arm
                and cases[i]["field"] == field and cases[i]["sset"] == 1),
            "cross_run_disagreements": disagree.get((arm, field), 0),
            "unresolved_cases": unresolved.get((arm, field), 0),
        }
        out["%s.%s" % (instr, field)] = entry

    # ---- extra structural probes -----------------------------------------
    ex = {}
    for (arm, fldname), lst in sorted(extras.items()):
        rows = []
        for c, g in sorted(lst, key=lambda t: (t[0]["value"], t[0]["sset"])):
            b = base_regs.get((arm, c["sset"]))
            rows.append({"value": c["value"], "sset": c["sset"],
                         "outcome": g["outcome"],
                         "sig": MF.sig(g["regs"], b) if (g["regs"] and b) else None,
                         "regs": g["regs"], "bytes": c["bytes"]})
        ex["%s.%s" % (arm, fldname)] = rows

    doc = {"_meta": {"experiment": "EXP-0160-g17p-last-field", "target": "G17P",
                     "runs": a.runs, "confirm": a.confirm,
                     "promotion_rule": "PRE_REGISTRATION.md section 7 (P1..P5)",
                     "gated_cases": len(gated),
                     "cross_run_disagreements": sum(disagree.values()),
                     "unresolved_cases": sum(unresolved.values()),
                     "isolated_verdicts": sum(1 for g in gated.values()
                                              if g["source"] == "isolated")},
           "arms": arm_report,
           "extra_probes": ex}
    doc.update(out)
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True))
    print("wrote", a.out)
    for k, v in sorted(out.items()):
        print("  %-22s %-20s %s" % (k, v["label"], v["why"][:110]))


if __name__ == "__main__":
    main()
