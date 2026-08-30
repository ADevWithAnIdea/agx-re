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
import casematrix as CM      # noqa: E402  (default matrix)

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


def _pred_f3_srcB(saturating):
    """AMENDMENT 08 -- M4 ARITH as a FULL-STATE PREDICTION.

    P3's register-role signature is a coarse PROXY for out-of-sample
    prediction, and for a saturating carrier it can fail for a reason that has
    nothing to do with the hardware: seed set 1 makes `saturate(a*b+c)` clamp to
    1.0 for nearly every srcB, so the destination looks unchanged. The direct
    test is strictly stronger -- predict the destination WORD, from the seeds
    alone, for every value of the field, in BOTH seed sets:

        srcB byte = (reg << 1) | is32,   reg = bits[1:7],   bit 7 inert
        B  = r[reg]  when is32, else 0.0 (a 16-bit read of a seed whose low
             halfword is zero)
        r0 = [saturate]( seed[0] * B + seed[4] )

    A field is allowed to satisfy P3 by this route instead, and when it does
    the hit/miss counts are recorded per seed set.
    """
    def f(seeds, v):
        B = seeds.get((v >> 1) & 63, 0.0) if (v & 1) else 0.0
        val = H.f32(H.f32(seeds[0] * B) + seeds[4])
        return fbits(sat(val) if saturating else val)
    return f


ARM_PRED = {"F3_SRCB": (_pred_f3_srcB(False),
                        "r0 = seed[0]*B + seed[4], B = r[(v>>1)&63] if (v&1) "
                        "else 0.0 (16-bit read)"),
            "F3E_SRCB": (_pred_f3_srcB(True),
                         "r0 = saturate(seed[0]*B + seed[4]), B = r[(v>>1)&63] "
                         "if (v&1) else 0.0 (16-bit read)")}


ORACLE = {"F2E_CTRL": oracle_F2E, "F3_OP": oracle_F3, "F3E_OP": oracle_F3E,
          "IMINMAX_SRCB": oracle_IMIN, "IMAD_SRCC": oracle_IMAD,
          "HALFPACK_SRC": oracle_HALF, "F2I_CTRLLO": oracle_F2I,
          "ISEL8_CMPMODE": None,   # structural only -- see RESULTS.md
          # Addendum A -- same carriers as F3_OP / F3E_OP, so same oracles
          "F3_SRCB": oracle_F3, "F3E_SRCB": oracle_F3E}

# Operand registers each arm's instruction actually names, read off the anchor.
ARM_OPERANDS = {"F2E_CTRL": (0, 2, None), "F3_OP": (0, 2, 4),
                "F3E_OP": (0, 2, 4), "IMINMAX_SRCB": (0, 2, None),
                "IMAD_SRCC": (0, 2, None), "HALFPACK_SRC": (1, 2, None),
                "F2I_CTRLLO": (0, None, None), "ISEL8_CMPMODE": (0, 7, None),
                "F3_SRCB": (0, 2, 4), "F3E_SRCB": (0, 2, 4)}


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


def load_confirm(rundirs):
    """Every repetition of every adjudication run, pooled: idx -> [record]."""
    reps = defaultdict(list)
    for rd in rundirs:
        p = Path(rd) / "confirm.jsonl"
        if not p.exists():
            continue
        for ln in p.open():
            try:
                reps[json.loads(ln)["idx"]].append(json.loads(ln))
            except Exception:
                continue
    return reps


def is_valid(obs):
    """AMENDMENT 06 -- the evidence-validity filter, and the rule this analysis
    actually gates on.

    An observation is EVIDENCE ABOUT THE ENCODING only if the dispatch actually
    ran and reported a coherent architectural state:

      * the command buffer must not have failed (`fault`/`hang`/`undecodable`);
      * it must not be flagged `victim` (…ErrorInnocentVictim class);
      * and the read-back must not show that the dispatch produced NO STORES AT
        ALL -- all 16 registers AND both integrity sentinels still holding the
        0xDEADBEEF poison. 25 such observations occurred here WITH command-buffer
        status OK, so the status string alone does not catch them.

    The justification is physical, not statistical: contamination can only ever
    DESTROY an observation. A discarded or reset command buffer writes nothing;
    it cannot fabricate a complete, coherent 16-register dump that independently
    agrees with another run's. So a coherent dump reproduced across independent
    runs is positive evidence, while a failure is evidence only when nothing
    ever succeeds.

    This REPLACES amendment 05, which is hereby RETRACTED: amendment 05 let a
    5-repetition re-run overrule two agreeing clean observations, and with the
    GPU lease removed from the protocol mid-experiment that re-run had no
    isolation and was manufacturing `fault`s of its own (e.g. imad srcC_desc
    v=186 seed set 2: `silent_zero` in BOTH gated runs, `fault` 3/5 on re-run).
    """
    if obs.get("victim"):
        return False
    if obs["outcome"] in SUSPECT:
        return False
    o = obs.get("observed") or {}
    if o.get("regs") is None:
        return False
    if (obs.get("poison_words") == 16
            and o.get("pre") == POISON and o.get("post") == POISON):
        return False
    return True


FAULT_PRONE_RATE = 0.60      # see adjudicate(): the midpoint of a measured
FAULT_PRONE_MIN_OBS = 20     # bimodal gap, not a tuned threshold


def adjudicate(obs_list):
    """Pool every observation of one case and decide what the encoding does.

    The asymmetry does most of the work and removes every tuned threshold:
    contamination can only DESTROY an observation -- a discarded or reset
    command buffer writes nothing -- it can never fabricate a complete,
    coherent 16-register dump that independently agrees with another run's.

      * failure rate above FAULT_PRONE_RATE over >= FAULT_PRONE_MIN_OBS pooled
        observations -> `fault-prone`;
      * else >= 2 valid observations that agree                  -> `clean-agreed`;
      * else >= 2 valid observations that DISAGREE               -> `clean-disagree`
        (genuine nondeterminism; excluded, never averaged);
      * else >= 3 failures of one class                          -> `reproducible-failure`;
      * else                                                     -> `insufficient`.

    **Why `fault-prone` is measured and not tuned.** Pooled over five
    independent runs, the per-case failure rate in the two falu3 arms is
    sharply BIMODAL with an empty gap:

        (v & 7) == 7   (128 cases): failure rate 0.714 .. 0.980
        every other v  (896 cases): failure rate 0.000 .. 0.500

    Nothing lies between 0.500 and 0.714, so any cut in that gap gives the same
    partition; 0.60 is its midpoint. Ambient sibling contamination cannot be
    value-selective, so a rate that tracks one specific field value is a
    property of the ENCODING. `opsel == 7` fails 50 of 51 dispatches per value
    and completes about 2% of the time; when it does complete it always shows
    the same state. Both halves are recorded.

    `n_valid`/`n_failed` are on every gated case, so a reviewer can re-decide
    any value from the committed raw records.
    """
    valid = [o for o in obs_list if is_valid(o)]
    failed = [o for o in obs_list if not is_valid(o)]
    nv, nf = len(valid), len(failed)
    n = nv + nf
    if n >= FAULT_PRONE_MIN_OBS and nf / float(n) > FAULT_PRONE_RATE:
        oc = Counter(o["outcome"] for o in failed)
        return (oc.most_common(1)[0][0], "FAULT-PRONE", None, "fault-prone", nv, nf)
    digs = set(o["observed"]["digest"] for o in valid)
    if nv >= 2:
        if len(digs) > 1:
            return (None, None, None, "clean-disagree", nv, nf)
        v = valid[0]
        return (v["outcome"], v["observed"]["digest"], v["observed"]["regs"],
                "clean-agreed", nv, nf)
    if nf >= 3:
        oc = Counter(o["outcome"] for o in failed)
        best, cnt = oc.most_common(1)[0]
        if cnt >= 3:
            return (best, None, None, "reproducible-failure", nv, nf)
    return (None, None, None, "insufficient", nv, nf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--out", default=str(HERE / "field_verdicts.json"))
    ap.add_argument("--matrix", default="casematrix",
                    help="case-matrix module: `casematrix` (the frozen eight "
                         "arms) or `casematrix_ext` (Addendum A's srcB arms)")
    a = ap.parse_args()

    global CM
    if a.matrix != "casematrix":
        import importlib
        CM = importlib.import_module(a.matrix)
    runs = [load_sweep(EXP / r if not Path(r).is_absolute() else r)
            for r in a.runs]
    cdirs = [(EXP / c if not Path(c).is_absolute() else Path(c))
             for c in (a.confirm.split(",") if a.confirm else [])]
    conf = load_confirm(cdirs)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = {c["idx"]: c for c in CM.build_cases(rep)}

    # ---- pooled, validity-filtered gate (P2/P3/P5, amendment 06) ----------
    gated, decisions, strict_ok = {}, Counter(), {}
    per_field_dec = defaultdict(Counter)
    resolved_by_filter = defaultdict(list)
    for idx, c in cases.items():
        obs = [R[idx] for R in runs if idx in R] + conf.get(idx, [])
        if not obs:
            continue
        oc, dig, regs, how, nv, nf = adjudicate(obs)
        decisions[how] += 1
        per_field_dec[(c["arm"], c["field"])][how] += 1
        # what the STRICT frozen P2 (the two gated runs must agree outright)
        # would have said for this case, recorded so a reviewer sees both
        rs = [R.get(idx) for R in runs]
        rs = [r for r in rs if r is not None]
        strict = (len(rs) == len(runs)
                  and len(set(r["outcome"] for r in rs)) == 1
                  and len(set(r["observed"]["digest"] for r in rs)) == 1
                  and not any(r["outcome"] in SUSPECT for r in rs))
        strict_ok[idx] = strict
        if oc is None:
            continue
        gated[idx] = {"outcome": oc, "digest": dig, "regs": regs,
                      "source": how, "n_valid": nv, "n_failed": nf}
        if not strict:
            resolved_by_filter[(c["arm"], c["field"])].append(c["value"])
    disagree = Counter()
    unresolved = Counter()
    for k, cnt in per_field_dec.items():
        disagree[k] = cnt.get("clean-disagree", 0)
        unresolved[k] = cnt.get("insufficient", 0)

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
                               else ("FAULT-PRONE"
                                     if g["source"] == "fault-prone"
                                     else "X:" + g["outcome"]))

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

        m4full = None
        if arm in ARM_PRED:
            fn_pred, desc = ARM_PRED[arm]
            per = {}
            for ss in CM.SEED_SETS:
                sd = H.seeds_for(kind, ss)
                hit = miss = 0
                for v, regs in dumps[ss].items():
                    if not regs:
                        continue
                    if regs[0] == fn_pred(sd, v):
                        hit += 1
                    else:
                        miss += 1
                per[str(ss)] = {"hit": hit, "miss": miss}
            m4full = {"model": desc, "per_seed_set": per,
                      "exact": all(x["miss"] == 0 and x["hit"] == (1 << w)
                                   for x in per.values())}

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
        elif not p3 and not (m4full and m4full["exact"]):
            label = "untested"
            why = ("P3 failed: the register-role signature differs between the two "
                   "seed sets at %d values %s" % (len(p3_bad), p3_bad[:12]))
        elif model is None and not m3 and not (m4full and m4full["exact"]):
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
            why = model or ("M4 FULL-STATE PREDICTION: %s" % m4full["model"]
                            if (m4full and m4full["exact"])
                            else "M3 REGMAP: %s" % ((bm_rel or bm_wr)[0]))
            if m4full and m4full["exact"]:
                why += ("; destination word predicted from the seeds for ALL %d "
                        "values in BOTH seed sets (0 misses)" % (1 << w))
                if not p3:
                    why += ("; P3's signature proxy did not apply here -- seed set "
                            "1 saturates, so the destination looks unchanged")

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
            "m4_full_state_prediction": m4full,
            "affine_in_product": affine,
            "outcomes_seed1": dict(oc),
            "outcomes_seed2": dict(Counter(outs[2].values())),
            "uncovered": {"seed1": cover[1][:32], "seed2": cover[2][:32]},
            "values_fault_prone": sorted(set(
                cases[i]["value"] for i in gated
                if gated[i]["source"] == "fault-prone" and cases[i]["arm"] == arm
                and cases[i]["field"] == field)),
            "values_from_reproducible_failure": sorted(set(
                cases[i]["value"] for i in gated
                if gated[i]["source"] == "reproducible-failure"
                and cases[i]["arm"] == arm and cases[i]["field"] == field)),
            "values_clean_agreed_minority": sorted(set(
                cases[i]["value"] for i in gated
                if gated[i]["source"] == "clean-agreed-minority"
                and cases[i]["arm"] == arm and cases[i]["field"] == field)),
            "observation_counts": {str(cases[i]["value"]) + "/s%d" % cases[i]["sset"]:
                                   [gated[i]["n_valid"], gated[i]["n_failed"],
                                    gated[i]["source"]]
                                   for i in gated
                                   if cases[i]["arm"] == arm
                                   and cases[i]["field"] == field
                                   and (gated[i]["source"] != "clean-agreed"
                                        or gated[i]["n_failed"])},
            "clean_disagreements": disagree.get((arm, field), 0),
            "unresolved_cases": unresolved.get((arm, field), 0),
            "gate_decisions": dict(per_field_dec.get((arm, field), {})),
            "values_needing_validity_filter":
                sorted(set(resolved_by_filter.get((arm, field), []))),
            "strict_frozen_gate_would_gate":
                sum(1 for i in cases
                    if cases[i]["arm"] == arm and cases[i]["field"] == field
                    and strict_ok.get(i)),
            "cases_in_field": sum(1 for i in cases
                                  if cases[i]["arm"] == arm
                                  and cases[i]["field"] == field),
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

    DB_DEFECTS = {
     "DEF-0160-1": {
      "instr": ["falu3", "falu3_ext"], "field": "op",
      "claim_in_db": "byte+2 modelled as one 8-bit `op` field",
      "corrected": ("byte+2 is TWO fields, at falu2's own absolute bit positions "
                    "and with falu2's own roles: `opsel` = instruction bits 16..18 "
                    "(byte value bits 0..2) and `opflags` = bits 19..23 (byte value "
                    "bits 3..7)."),
      "evidence": ("Dense 256-value sweep x 2 seed sets on G17P. The low 3 bits "
                   "select the OPERATION, identified against a host-computed "
                   "function library and required to agree in BOTH seed sets: "
                   "0 = a+b, 1 = a*b, 2 = a*b+a, 4 = -b, 5 = 0, 6 = a*b+c (the "
                   "anchor's fma), 7 = reproducible fault. Byte value bit 4 "
                   "(instruction bit 20) is the srcB RELEASE flag: clearing it "
                   "leaves srcB's register holding its seed instead of being "
                   "zeroed by release-on-read. Byte value bits 6,7 (instruction "
                   "bits 22,23) are the silent corruptors. Bit 5 is the only inert "
                   "bit. Exact ok-rule (v & 0xd7) == 0x16, 0 exceptions."),
      "why_it_matters": ("An emitter treating byte+2 as one opaque opcode cannot "
                         "set the release/publication flags, which are what make "
                         "a register reusable.")},
     "DEF-0160-2": {
      "instr": ["iminmax"], "field": "srcB",
      "claim_in_db": "byte+1 = `dst_full`, byte+3 = `srcA`, byte+5 = `srcB`",
      "corrected": ("The 6-byte `iminmax` uses the SAME slot layout as `falu2`: "
                    "byte+1 = srcA descriptor, byte+3 = srcB descriptor, byte+5 = "
                    "the source-class / modifier byte (falu2's srcA_class bit0, "
                    "srcB_class bits1-2, srcB_neg bit3, mod_hi bits4-7). db.json's "
                    "operand names are shifted by one slot."),
      "evidence": ("byte+5 has FOUR inert bits (3,5,6,7) over a dense 256-value "
                   "sweep and no value->register model reaches the >=90%/>=6-register "
                   "bar, so it cannot be a register selector. Its live bits are "
                   "exactly falu2's byte+5 roles, and its anchor value 0xc0 is "
                   "falu2's standard `mods` default. Meanwhile min(seed[0], seed[2]) "
                   "reproduces the measured baseline in BOTH seed sets with "
                   "byte+1 -> r0 and byte+3 -> r2."),
      "why_it_matters": ("An emitter following db.json would put the second "
                         "operand's register number in the modifier byte and get a "
                         "silent zero.")},
     "DEF-0160-3": {
      "instr": ["imad"], "field": "srcC_desc",
      "claim_in_db": "(K<<3) = immediate addend, K in b7[3:8] + mulsel[0:3]",
      "corrected": ("byte+7 is a 2-bit MODE (bits 0,1) plus a 5-bit ADDEND-SOURCE "
                    "SELECT (bits 3..7); bit 2 is inert. The addend is NOT in the "
                    "instruction: it is read from an external (uniform/constant) "
                    "source that byte+7[3:8] indexes."),
      "evidence": ("(a) The 12 imad bytes were lifted VERBATIM from a kernel whose "
                   "MSL adds 12345; run in our carrier the same bytes add 1. An "
                   "inline immediate cannot change. (b) A dense 256-value sweep x 2 "
                   "seed sets fits r0 = m(v)*(srcA*srcB) + A(v) with 0 exceptions "
                   "over all 181 non-fault values, m(v) in {0,1} determined by bits "
                   "0,1 and A(v) seed-independent and determined by bits 3..7. "
                   "(c) The recovered A values are exactly the 16-bit halves of THE "
                   "CARRIER'S OWN float constants: 0x3F800001 (= 1.0000001f) gives "
                   "A = 1 at K in {1,12} and A = 16256 (0x3F80) at K = 13; "
                   "0xB3D6BF95 (= -1e-7f) gives A = 49045 (0xBF95) at K = 14 and "
                   "A = 46038 (0xB3D6) at K = 15. K in {3..11, 16..31} read 0. "
                   "(d) (v & 3) == 3 faults reproducibly (64 values, unanimous "
                   "across four independent runs)."),
      "why_it_matters": ("EXP-M4-13 saw K co-vary with the source constant because "
                         "the compiler allocates a slot per constant. Adopted as "
                         "'the immediate is K<<3', an emitter would emit an imad "
                         "that adds whatever happens to occupy slot K -- silently "
                         "wrong code, far from its cause.")},
     "DEF-0160-4": {
      "instr": ["half_pack"], "field": "src / length rule",
      "claim_in_db": ("byte0 0x18 is a 4-byte half_pack only when byte+1 == 0x05; "
                      "byte+2 = source register"),
      "corrected": ("`half_pack` IS 4 bytes, unconditionally; byte+1 is an operand "
                    "descriptor and must not gate the length. byte+2 is not a "
                    "register selector either."),
      "evidence": ("Splice controls in the same block. Replacing bytes +2..+3 with "
                   "our own 2-byte `mov_imm` leaves the ENTIRE 16-register state "
                   "identical to the anchor -- the mov_imm never executes, so those "
                   "bytes are consumed by the instruction at +0. Replacing BOTH "
                   "2-byte halves with two `mov_imm`s executes both (r6 = 77 AND "
                   "r7 = 99): the positive control proving the probe can see a "
                   "difference in exactly that slot. So DEF-0154-1's A18 "
                   "`18 05 18 03` vs G17P `18 03 18 05` is an operand swap INSIDE "
                   "one 4-byte instruction (register allocation), not two 2-byte "
                   "instructions reordered. Separately, byte+2 has three inert bits "
                   "(3,4,5) over a dense sweep, so it cannot carry a register index."),
      "why_it_matters": ("The over-constrained length rule leaves 22 bytes of our "
                         "own G17P `half2 add` undecodable (DEF-0154-1); the fix is "
                         "to drop the byte+1 condition, not to add a special case.")},
     "DEF-0160-6": {
      "instr": ["imad"], "field": "srcC_lo (byte+6)",
      "claim_in_db": ("byte+6 = `srcC_lo`, the low byte of the immediate addend; "
                      "the descriptor has NO srcA field at all"),
      "corrected": ("byte+6 is the **srcA (first multiplicand) REGISTER SELECTOR**: "
                    "reg = (byte+6) >> 3, and bit 0 = 1 makes the source read 0. "
                    "Bits 1 and 2 are inert."),
      "evidence": ("The `__2d_desc_lo` probe (12 srcC_desc points x 11 srcC_lo "
                   "points x 2 seed sets). Solving obs = m(desc)*(X * srcB) + "
                   "A(desc>>3) for X gives a SINGLE multiplicand per srcC_lo "
                   "value, identical across every srcC_desc that keeps the "
                   "product, and it tracks the register the model names in BOTH "
                   "seed sets: 0x00/0x02/0x04 -> r0 (10 and 7), 0x08 -> r1 "
                   "(21 and 13), 0x10 -> r2 (34 and 19), 0x20 -> r4 (58 and 37), "
                   "0x40 -> r8 (94 and 73), 0x7f -> r15 (0), 0x01/0x03 -> reads 0."),
      "why_it_matters": ("This is the larger finding. An emitter using db.json "
                         "cannot choose the FIRST OPERAND of an integer multiply "
                         "at all -- the field is not modelled, and the byte that "
                         "carries it is documented as part of an immediate that "
                         "does not exist (DEF-0160-3). EXP-0154 labelled this "
                         "field `hardware-run` from the ok-set alone (`ok at "
                         "{0x0, 0x2, 0x4, 0x6}`) without identifying its role; "
                         "those four values are exactly the ones naming r0.")},
     "DEF-0160-7": {
      "instr": ["imad"], "field": "mulsel (byte+8)",
      "claim_in_db": "K (the immediate addend) spans b7[3:8] PLUS mulsel[0:3]",
      "corrected": "mulsel does not participate in the addend at all.",
      "evidence": ("The `__2d_desc_mul` probe (12 srcC_desc points x 8 mulsel "
                   "points x 2 seed sets): the recovered addend is a single value "
                   "per srcC_desc, unchanged across every mulsel point "
                   "(0x00, 0x10, 0x40, 0x50, 0x80, 0x90, 0xc0, 0xd0)."),
      "why_it_matters": ("Half of db.json's stated addend encoding is inert; the "
                         "other half selects an external source (DEF-0160-3).")},
     "DEF-0160-5": {
      "instr": ["(methodological)"], "field": "n/a",
      "claim_in_db": "n/a",
      "corrected": ("A contaminated dispatch can report command-buffer status OK "
                    "and write NOTHING. 25 observations here (18 in run01, 7 in "
                    "run02) returned status OK with all 16 registers AND both "
                    "integrity sentinels still holding 0xDEADBEEF. No "
                    "`...ErrorInnocentVictim` string fired. Only a poisoned "
                    "read-back buffer catches this class, and a zero-initialised "
                    "buffer would have recorded 25 confident `silent_zero`s."),
      "evidence": "raw/g17p_20260830_run01,02 -- fields `poison_words`, `sentinel_bad`.",
      "why_it_matters": ("FIELD-SWEEP-PROTOCOL 7/7A tells agents to segregate "
                         "victim-class failures by the OS fault string. This class "
                         "has no fault string at all.")},
    }

    doc = {"_meta": {"experiment": "EXP-0160-g17p-last-field", "target": "G17P",
                     "runs": a.runs, "confirm": a.confirm,
                     "promotion_rule": "PRE_REGISTRATION.md section 7 (P1..P5)",
                     "gated_cases": len(gated),
                     "gate": "amendment 06 evidence-validity filter (see analysis/verdicts.py is_valid)",
                     "gate_decisions": dict(decisions),
                     "clean_disagreements": sum(disagree.values()),
                     "unresolved_cases": sum(unresolved.values())},
           "arms": arm_report,
           "db_defects": DB_DEFECTS,
           "extra_probes": ex}
    doc.update(out)
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True))
    print("wrote", a.out)
    for k, v in sorted(out.items()):
        print("  %-22s %-20s %s" % (k, v["label"], v["why"][:110]))


if __name__ == "__main__":
    main()
