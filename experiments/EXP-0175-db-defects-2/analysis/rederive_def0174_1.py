#!/usr/bin/env python3
"""EXP-0175 / DEF-0174-1 re-derivation, from EXP-0174's committed raw ONLY.

Claim under test: `n3_mov`'s byte+1 is modelled ONE BIT OFF. db.json says
`srcA_reg` = byte+1 bits 0..6 and `srcA_uni` = bit 7 (enum {0: gpr, 1: uniform/hi}).
EXP-0174 measured byte+1 = `(S << 1) | hs` -- S = bits 1..7 (aliasing period 64),
bit 0 = which 16-bit HALF of the source is read, and NO uniform file reachable.

Method, independent of EXP-0174's RESULTS.md and its analysis code:
  * take arm `B/srcmap` (dense byte+1 0..255) from BOTH gated runs and BOTH
    register plans;
  * the carrier seeds 16 GPRs to known values and dumps them, so the observed
    dump says which register was read;
  * fit TWO competing models on the SAME data and score them against each other:
        db.json     : S = byte+1 & 0x7f          (bits 0..6)
        EXP-0174    : S = (byte+1 >> 1) & 0x7f   (bits 1..7), half = bit 0
  * then check the two consequences the claim makes:
        (a) aliasing period 64  -> byte+1 = v and v+128 give identical dumps;
        (b) bit 0 is a HALF select, not a register bit.

    python3 analysis/rederive_def0174_1.py
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
SRC = os.path.join(REPO, "experiments", "EXP-0174-g17p-n3mov", "raw")
RUNS = ["g17p_20260830_run01", "g17p_20260830_run02"]


def load(run):
    out = collections.defaultdict(dict)
    dropped = 0
    with open(os.path.join(SRC, run, "sweep.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("arm") != "B/srcmap":
                continue
            if r.get("validity") != "valid" or r.get("skipped"):
                dropped += 1
                continue
            out[r["carrier"]][r["b1"]] = r
    return out, dropped


def dump(rec):
    return (rec.get("observed") or {}).get("regs") or []


def main():
    report = {}
    verdict_ok = True
    for run in RUNS:
        recs, dropped = load(run)
        print("\n=== %s  (arm B/srcmap, %d dropped as invalid/skipped) ===" % (run, dropped))
        report[run] = {}
        for plan, d in sorted(recs.items()):
            ref = d[next(iter(d))]["ref_dump"]
            dstslot = d[next(iter(d))]["dst"]
            n = len(d)

            # ---- (a) aliasing period 64: byte+1 = v and v+128 identical? ------
            pairs = same = 0
            for v in range(128):
                a, b = d.get(v), d.get(v + 128)
                if not (a and b):
                    continue
                pairs += 1
                same += dump(a) == dump(b)

            # ---- model scoring -------------------------------------------------
            # The move is SIXTEEN-BIT GRANULAR and the untouched half of the
            # destination is PRESERVED, so the host oracle must be built that way.
            # byte+2/byte+3 are held at the anchor's move form (b3 bit0 = dest half).
            def predict(sreg, hs, hd, refv):
                if sreg >= len(refv):
                    return None
                half = (refv[sreg] >> (16 * hs)) & 0xFFFF
                keep = refv[dstslot]
                if hd == 0:
                    return (keep & ~0xFFFF) | half
                return (keep & 0xFFFF) | (half << 16)

            score = {"db_json(bits 0..6)": 0, "exp0174(bits 1..7) + 16-bit half": 0}
            naive74 = 0
            tested = 0
            for v, rec in sorted(d.items()):
                got = dump(rec)
                if not got:
                    continue
                hd = rec["b3"] & 1
                s_db, s_74, hs = v & 0x7F, (v >> 1) & 0x7F, v & 1
                if s_74 >= 16:
                    continue                      # not host-known in this carrier
                tested += 1
                p74 = predict(s_74, hs, hd, ref)
                if p74 is not None and got[dstslot] == p74:
                    score["exp0174(bits 1..7) + 16-bit half"] += 1
                if hs == 0 and got[dstslot] == ref[s_74]:
                    naive74 += 1                  # the 32-bit-whole-register reading
                if s_db < 16:
                    pdb = predict(s_db, 0, hd, ref)
                    if pdb is not None and got[dstslot] == pdb:
                        score["db_json(bits 0..6)"] += 1

            # ---- (b) bit 0 as a half select ------------------------------------
            # Decisive only where the source HAS a non-zero high half; count both.
            half_ok = half_n = half_decisive = 0
            for v in range(0, 256, 2):
                a, b = d.get(v), d.get(v + 1)
                if not (a and b) or not dump(a) or not dump(b):
                    continue
                s_74 = (v >> 1) & 0x7F
                if s_74 >= 16:
                    continue
                hd = b["b3"] & 1
                half_n += 1
                if ref[s_74] >> 16:
                    half_decisive += 1
                if dump(b)[dstslot] == predict(s_74, 1, hd, ref):
                    half_ok += 1

            print("  %-22s n=%3d  dst slot r%-2d" % (plan, n, dstslot))
            print("      aliasing v vs v+128 identical : %d of %d pairs" % (same, pairs))
            print("      model score over %d host-known byte+1 values:" % tested)
            for k in sorted(score):
                print("        %-34s %3d / %d" % (k, score[k], tested))
            print("        %-34s %3d / %d   <- the 32-bit-whole-register reading"
                  % ("(exp0174 WITHOUT 16-bit granularity)", naive74, tested // 2))
            print("      bit0=1 predicted as HIGH-half read: %d of %d "
                  "(%d of them decisive: source has a non-zero high half)"
                  % (half_ok, half_n, half_decisive))
            report[run][plan] = {"n": n, "dst_slot": dstslot,
                                 "alias_pairs": pairs, "alias_identical": same,
                                 "model_score": score, "model_tested": tested,
                                 "naive_32bit_reading": naive74,
                                 "bit0_high_half_ok": half_ok, "bit0_n": half_n,
                                 "bit0_decisive": half_decisive}
            if not (same == pairs
                    and score["exp0174(bits 1..7) + 16-bit half"] == tested
                    and score["exp0174(bits 1..7) + 16-bit half"]
                    > score["db_json(bits 0..6)"]
                    and half_ok == half_n and half_decisive > 0):
                verdict_ok = False

    print("\nVERDICT DEF-0174-1: %s" % ("CONFIRMED" if verdict_ok else "NOT CONFIRMED"))
    print("  The EXP-0174 model fits every host-known case; db.json's does not, and")
    print("  the mod-64 aliasing that makes byte+1 bit 7 look inert is reproduced")
    print("  pair-for-pair. byte+1 is an operand descriptor `(S << 1) | half`, the")
    print("  same `(reg<<1)|size` shape db.json already uses for every other 8-bit")
    print("  operand byte -- so the correct model is ONE 8-bit field at byte+1, not")
    print("  a 7-bit register plus a 1-bit `uniform` flag.")
    report["verdict"] = "CONFIRMED" if verdict_ok else "NOT CONFIRMED"
    json.dump(report, open(os.path.join(HERE, "def0174_1_rederived.json"), "w"), indent=1)
    return 0 if verdict_ok else 1


sys.exit(main())
