#!/usr/bin/env python3
"""EXP-0203 OFFLINE gates.  These are CODE tests; they are NOT evidence for any hardware
claim.  They exist so that a defect in the matrix, the oracle or the promotion gate is found
before a device is touched -- three of this corpus's worst results came from a criterion that
could not return "no", and two from a sweep whose values assembled to identical bytes.

Run:  python3 harness/selftest.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP / "analysis"))
import isa_helpers as H          # noqa: E402
import oracle as O               # noqa: E402
import casematrix as M           # noqa: E402
import verdicts as V             # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-46s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    cases = M.build_cases()

    # G1 -- every mutation differs from its anchor ONLY inside the field's db.json span.
    ok, bad = V.span_only_ok(cases)
    check("G1 span-only mutation", ok, str(bad[:3]))

    # G1 -- no aliasing: distinct values must give distinct bytes, per (arm, field).
    alias = []
    groups = {}
    for c in cases:
        if c["kind"] in ("field", "field_byte"):
            groups.setdefault((c["arm"], c["field"], c["byte_index"]), []).append(c)
    for k, g in groups.items():
        if len({c["bytes"] for c in g}) != len(g):
            alias.append(k)
    check("G1 non-aliased encodings", not alias, str(alias[:3]))

    # G2 -- the field spans really are db.json's.
    geom_ok = True
    for instr, fname, start, width in (("half_alu_fma12", "dst", 4, 4),
                                       ("half_alu_fma12", "ext", 32, 64),
                                       ("half_pack", "dstlo", 8, 8),
                                       ("half_pack", "b3", 24, 8)):
        geom_ok &= (M.field_geom(instr, fname) == (start, width))
    check("G2 field geometry == db.json", geom_ok)

    # G3 -- the oracle is DISCRIMINATING: distinct predictions across the swept values.
    disc = {}
    for arm in M.ARMS:
        lay = H.LAYOUTS[arm["layout"]]
        plan = H.seed_plan(arm["seeds"], arm["layout"])
        pre = [plan["words"].get(i, 0) for i in range(16)]
        for fname in arm["fields"]:
            preds = set()
            for c in cases:
                if c["arm"] != arm["id"] or c["field"] != fname:
                    continue
                blk = bytes.fromhex(c["bytes"])
                p = (O.fma12_predict(pre, blk, lay) if c["instr"] == "half_alu_fma12"
                     else O.halfpack_predict(pre, blk, lay))
                preds.add(O.digest(p["post"]))
            disc[(arm["id"], fname)] = len(preds)
    check("G3 oracle discriminates (>=2 predictions)",
          all(v >= 2 for v in disc.values()),
          json.dumps({"%s/%s" % k: v for k, v in sorted(disc.items())}))

    # G4 -- each falsifier is CAPABLE of producing an observation the oracle rejects.
    #       Note what this is NOT: for `__fals_F2_opsel` and `__fals_F1_null` the oracle's
    #       PREDICTION is deliberately unchanged (the model does not read opsel, and F1's
    #       oracle is the anchor's).  The falsifier works because the HARDWARE will do
    #       something else, so what has to be shown offline is that the alternative
    #       behaviour is DISTINGUISHABLE from the prediction under these seeds.
    fal_ok, fal_detail = True, {}
    for arm in M.ARMS:
        lay = H.LAYOUTS[arm["layout"]]
        plan = H.seed_plan(arm["seeds"], arm["layout"])
        pre = [plan["words"].get(i, 0) for i in range(16)]
        anc = M.anchor_bytes(arm["instr"], arm["layout"])
        if arm["instr"] == "half_alu_fma12":
            good = O.fma12_predict(pre, anc, lay)
            a = O.v16(H.hval(pre, anc[1])[0])
            b = O.v16(H.hval(pre, anc[3])[0])
            c = O.v16(H.hval(pre, anc[5])[0])
            # F2: an hadd in the same slot must be distinguishable from the hfma prediction
            alt = O.to_f16(a + b)[0]
            fal_detail["%s/F2_opsel_distinguishable" % arm["id"]] = (alt != good["result16"])
            fal_ok &= (alt != good["result16"])
            # F4: predicting a different destination must give a different post vector
            shifted = bytes([((M.DST_BY_LAYOUT[arm["layout"]] + 1) << 4) | (anc[0] & 0xF)]) + anc[1:]
            d4 = O.fma12_predict(pre, shifted, lay)["post"] != good["post"]
            fal_detail["%s/F4_dstshift" % arm["id"]] = d4
            fal_ok &= d4
        else:
            good = O.halfpack_predict(pre, anc, lay)
            B = O.v16(H.hval(pre, anc[1])[0])
            A = O.v16(H.hval(pre, anc[3])[0])
            alt = O.to_f16(B * A)[0]
            fal_detail["%s/F3_hp_opsel_distinguishable" % arm["id"]] = (alt != good["result16"])
            fal_ok &= (alt != good["result16"])
            shifted = bytes([((M.DST_BY_LAYOUT[arm["layout"]] + 1) << 4) | (anc[0] & 0xF)]) + anc[1:]
            d4 = O.halfpack_predict(pre, shifted, lay)["post"] != good["post"]
            fal_detail["%s/F4_dstshift" % arm["id"]] = d4
            fal_ok &= d4
    check("G4 falsifiers are DISTINGUISHABLE offline", fal_ok,
          str([k for k, v in fal_detail.items() if not v][:4]))

    # G5 -- the `__fals_F1_null` block writes nothing, so the NULL prediction differs from
    #       the model prediction (otherwise the falsifier is vacuous).
    nullok = True
    for arm in M.ARMS:
        lay = H.LAYOUTS[arm["layout"]]
        plan = H.seed_plan(arm["seeds"], arm["layout"])
        pre = [plan["words"].get(i, 0) for i in range(16)]
        anc = M.anchor_bytes(arm["instr"], arm["layout"])
        good = (O.fma12_predict(pre, anc, lay) if arm["instr"] == "half_alu_fma12"
                else O.halfpack_predict(pre, anc, lay))
        nullok &= (O.null_predict(pre, lay)["post"] != good["post"])
    check("G5 null prediction != model prediction", nullok)

    # G6 -- the promotion gate can return BOTH answers, and does not refuse a width-1 field
    #       by arithmetic (DEF-0178: `moved >= 2*max(disagree,1)` cannot promote width 1).
    def synth(moved, disagree, dispatched, oracle_rate=1.0, distinct_pred=2,
              ledger_ok=None, sem_checked=None, distinct_actual=None):
        ledger_ok = dispatched if ledger_ok is None else ledger_ok
        sem_checked = dispatched if sem_checked is None else sem_checked
        distinct_actual = dispatched if distinct_actual is None else distinct_actual
        return {"arm": "X", "dispatched": dispatched, "distinct_bytes": dispatched,
                "distinct_actual_encodings": distinct_actual,
                "ledger_ok": ledger_ok, "ledger_of": dispatched,
                "ledger_bytes_match": dispatched, "ledger_failures": [],
                "semantic_classes_run1": {"correct": sem_checked},
                "semantic_classes_run2": {"correct": sem_checked},
                "sem_checked_run1": sem_checked,
                "decidable_run1": dispatched, "decidable_run2": dispatched,
                "excluded": {}, "common": dispatched, "moved": moved,
                "disagree": disagree, "disagree_keys": [],
                "agreement": 1.0 - disagree / dispatched,
                "oracle_match_run1": int(dispatched * oracle_rate),
                "oracle_match_run2": int(dispatched * oracle_rate),
                "oracle_rate_run1": oracle_rate, "oracle_rate_run2": oracle_rate,
                "oracle_distinct_predictions": distinct_pred,
                "oracle_mismatch_keys": [], "alt2r_only_matches": 0,
                "oracle_subnormal": 0, "oracle_overflow": 0,
                "decidable_keys": [[i, None] for i in range(dispatched)],
                "anchor_digest_present": True}
    good_inst = {"X": {"falsifiers_all_mismatch": True, "ctl_live_ok": True}}
    lab_pass, _, _ = V.gate([synth(2, 0, 2)], good_inst, 2, True)
    check("G6a gate PROMOTES a clean width-1 field", lab_pass == "hardware-run", lab_pass)
    lab_c, _, _ = V.gate([synth(1, 0, 2)], good_inst, 2, True)
    check("G6b gate promotes moved=1,disagree=0 (width-1 arithmetic)",
          lab_c == "hardware-run", lab_c)
    lab_fail, _, _ = V.gate([synth(0, 0, 256, oracle_rate=1.0, distinct_pred=1)],
                            good_inst, 256, True)
    check("G6c gate REFUSES a constant oracle", lab_fail == "untested", lab_fail)
    lab_f2, _, _ = V.gate([synth(200, 0, 256, oracle_rate=0.5)], good_inst, 256, True)
    check("G6d gate REFUSES a low oracle rate", lab_f2 == "untested", lab_f2)
    bad_inst = {"X": {"falsifiers_all_mismatch": False, "ctl_live_ok": True}}
    lab_f3, _, _ = V.gate([synth(256, 0, 256)], bad_inst, 256, True)
    check("G6e gate REFUSES when a falsifier matched", lab_f3 == "untested", lab_f3)
    bad_ctl = {"X": {"falsifiers_all_mismatch": True, "ctl_live_ok": False}}
    lab_f4, _, _ = V.gate([synth(256, 0, 256)], bad_ctl, 256, True)
    check("G6f gate REFUSES without a liveness control", lab_f4 == "untested", lab_f4)
    lab_f5, _, _ = V.gate([synth(256, 0, 256)], good_inst, 1 << 64, True)
    check("G6g gate REFUSES `ext` (2^64 not dense)", lab_f5 != "hardware-run", lab_f5)
    lab_a1, _, _ = V.gate([synth(256, 0, 256, ledger_ok=255)], good_inst, 256, True)
    check("GA gate REFUSES an incomplete actual-byte ledger", lab_a1 == "untested", lab_a1)
    lab_a2, _, _ = V.gate([synth(256, 0, 256, distinct_actual=8)], good_inst, 256, True)
    check("GA gate REFUSES aliased ACTUAL encodings (8 bytes, 256 values)",
          lab_a2 == "untested", lab_a2)
    lab_c1, _, _ = V.gate([synth(256, 0, 256, sem_checked=0)], good_inst, 256, True)
    check("GC gate REFUSES sem_checked == 0", lab_c1 == "untested", lab_c1)
    check("G6h `ext` is FORCED to untested per PRE_REG 6",
          V.FORCE_LABEL.get(("half_alu_fma12", "ext")) == "untested")

    # G9 (GATE A, offline half) -- decoding the field back out of the BUILT bytes must
    #     return the requested value for every case in the matrix.  The on-hardware half of
    #     Gate A reads the bytes back from the dispatched artifact; this is the part that can
    #     be proved without a device.
    bad_led = []
    for c in cases:
        b = bytes.fromhex(c["bytes"])
        if c.get("byte_index") is not None:
            got = b[c["byte_index"]]
        elif c.get("fstart") is not None:
            got = M.get_field_bits(b, c["fstart"], c["fwidth"])
        else:
            continue
        if got != c["value"]:
            bad_led.append([c["arm"], c["field"], c["value"], got])
    check("G9 ledger decode == requested value", not bad_led, str(bad_led[:3]))

    # G10 -- the semantic classifier must be able to return every Gate C bucket, including
    #        the ones that are NOT a pass.
    lay = H.LAYOUTS["HI"]
    plan = H.seed_plan("A", "HI")
    pre = [plan["words"].get(i, 0) for i in range(16)]
    anc = M.anchor_bytes("half_alu_fma12", "HI")
    good = O.fma12_predict(pre, anc, lay)
    o_ok = {"pre": pre, "post": good["post"], "pre_sent": H.SENT_PRE,
            "post_sent": H.SENT_POST, "stray": [], "n_stray": 0}
    o_null = {"pre": pre, "post": O.null_predict(pre, lay)["post"], "pre_sent": H.SENT_PRE,
              "post_sent": H.SENT_POST, "stray": [], "n_stray": 0}
    weird = list(good["post"])
    weird[good["dst"]] = 0x12345678
    o_weird = {"pre": pre, "post": weird, "pre_sent": H.SENT_PRE, "post_sent": H.SENT_POST,
               "stray": [], "n_stray": 0}
    alt = O.fma12_predict(pre, anc, lay, "a*b+c")
    o_alt = {"pre": pre, "post": alt["post"], "pre_sent": H.SENT_PRE,
             "post_sent": H.SENT_POST, "stray": [], "n_stray": 0}
    buckets = {
        "correct": O.classify_semantics(o_ok, anc, lay, "half_alu_fma12", "ok", False, good)[0],
        "no_write": O.classify_semantics(o_null, anc, lay, "half_alu_fma12", "wrong_value",
                                         False, good)[0],
        "unexplained": O.classify_semantics(o_weird, anc, lay, "half_alu_fma12", "wrong_value",
                                            False, good)[0],
        "faulted": O.classify_semantics(o_ok, anc, lay, "half_alu_fma12", "fault", False,
                                        good)[0],
        "contaminated": O.classify_semantics(o_ok, anc, lay, "half_alu_fma12", "ok", True,
                                             good)[0],
        "measurement": O.classify_semantics(None, anc, lay, "half_alu_fma12",
                                            "measurement_failed", False, good)[0],
    }
    exp = {"correct": "correct", "no_write": "no_write", "unexplained": "unexplained",
           "faulted": "faulted_or_rejected", "contaminated": "contaminated",
           "measurement": "measurement_failure"}
    check("G10 semantic classifier reaches every Gate C bucket", buckets == exp, str(buckets))
    alt_cls = O.classify_semantics(o_alt, anc, lay, "half_alu_fma12", "wrong_value", False, good)
    check("G10b a different-but-coherent model is NOT scored `correct`",
          alt_cls[0] == "coherent_alt_model" and "a*b+c" in alt_cls[1], str(alt_cls))

    # G7 -- the program fits and is even-length for every (seeds, layout).
    sizes = {}
    for sid in ("A", "B"):
        for lay in ("HI", "LO"):
            plan = H.seed_plan(sid, lay)
            blk = M.anchor_bytes("half_alu_fma12") + H.marker_chain(plan["lay"])
            body = b"".join([b"".join(H.seed_instrs(plan))])
            prog, boff = H.synth_program(plan, blk, 1400)
            sizes["%s/%s" % (sid, lay)] = (len(prog), boff)
    check("G7 program synthesizes for all 4 (seed,layout)", len(sizes) == 4, str(sizes))

    # G8 -- SafePersistRunner reports a truncated response as MALFORMED, never a hang.
    sys.path.insert(0, str(_tools() / "agxtest"))
    import saferunner                                          # noqa: E402
    stub = EXP / "work" / "stub" / "fakerunner.py"
    ok_modes = {}
    for mode in ("good", "truncate"):
        cmd = str(EXP / "work" / "stub" / ("run_%s.sh" % mode))
        Path(cmd).write_text("#!/bin/sh\nexec %s %s %s\n"
                             % (sys.executable, stub, "--truncate" if mode == "truncate" else ""))
        Path(cmd).chmod(0o755)
        r = saferunner.SafePersistRunner(source=str(EXP / "kernels" / "carrier_a.metal"),
                                         function="k", fast_math=False, agxrun_persist=cmd)
        resp = r.request(archive="x", grid=1, tg=1, ins={0: "y"}, outs={0: 8}, timeout=5)
        ok_modes[mode] = resp["status"]
        r._kill()
    check("G8 truncated response -> MALFORMED (not hang)",
          ok_modes.get("good") == "OK" and ok_modes.get("truncate") == "MALFORMED",
          str(ok_modes))

    print("\n%d case(s) in the matrix, sha256 %s" % (len(cases), M.matrix_sha256(cases)))
    if FAILS:
        print("FAILED GATES: %s" % FAILS)
        sys.exit(1)
    print("ALL OFFLINE GATES PASS (code test, not evidence)")


def _tools():
    for cand in (EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"):
        if (cand / "agxtest" / "persistrun.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


if __name__ == "__main__":
    main()
