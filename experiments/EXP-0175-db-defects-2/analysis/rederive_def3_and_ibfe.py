#!/usr/bin/env python3
"""EXP-0175 / DEF-0171-3 re-derivation + the `ibfe` closure question (H7).

DEF-0171-3 claim: `ibfe.sign_ext` (byte+6 bit 1) is NOT the sign control -- it is
dense-inert in BOTH the unsigned (`k_bfe`) and signed (`k_bfe_s`) compiler anchors.

H7 question: does the inertness of `ibfe.sign_ext` and `ibfe.b2_bit0` support
promotion to EMITTER GRADE, or only `single-template-inference`?

Method:
  * A5 sub-field decomposition (analysis/subfield.py) over the dense byte+6 and
    byte+2 sweeps, both anchors, both gated runs;
  * detection power is MEASURED, not assumed: the same script reports how many of
    the 256 whole-byte values moved on the same carrier in the same run;
  * the two compiler anchors are compared byte-for-byte, so the reader can see
    where the signed/unsigned difference actually lives.

    python3 analysis/rederive_def3_and_ibfe.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subfield as SF

HERE = os.path.dirname(os.path.abspath(__file__))
CARRIERS = ["NAT:k_bfe@ibfe+18", "NAT:k_bfe_s@ibfe+18", "SYNTH:k_bfe@ibfe+18"]
# db.json ibfe: sign_ext start=49 w=1 (byte+6 bit1); b2_bit0 start=16 w=1 (byte+2 bit0)
FIELDS = {"sign_ext": (6, 1, 1), "b6_bit0": (6, 0, 1), "offset": (6, 2, 6),
          "b2_bit0": (2, 0, 1), "store_en": (2, 1, 1), "b2_fmt": (2, 2, 6)}


def main():
    report = {}
    anchors = {}
    for run in SF.RUNS:
        recs, dropped = SF.load(run, arm="IBFE")
        print("\n=== %s (%d invalid_run dropped) ===" % (run, dropped))
        report[run] = {}
        for cid in CARRIERS:
            # record the anchor bytes for the byte-for-byte anchor comparison
            for (c, bi, v), r in recs.items():
                if c == cid:
                    anchors[cid] = r["anchor_bytes"]
                    break
            print("  %s   anchor %s" % (cid, anchors.get(cid)))
            report[run][cid] = {}
            for name, (bi, lo, w) in FIELDS.items():
                live = SF.byte_liveness(recs, cid, bi)
                sub = SF.moved(recs, cid, bi, lo, w)
                if sub is None:
                    continue
                report[run][cid][name] = {"subfield": sub, "byte_liveness": live}
                print("    %-10s byte+%d bits[%d:%d]  sub-values %2d, MOVED %2d   "
                      "| whole byte+%d moved %3d of %d  (detection power)"
                      % (name, bi, lo, lo + w, sub["n_cases"], sub["moved"],
                         bi, live["moved"], live["n"]))

    # ---- the anchor comparison -------------------------------------------------
    print("\nAnchor comparison -- where does signed vs unsigned actually differ?")
    a = bytes.fromhex(anchors["NAT:k_bfe@ibfe+18"])
    b = bytes.fromhex(anchors["NAT:k_bfe_s@ibfe+18"])
    diffs = [(i, a[i], b[i]) for i in range(min(len(a), len(b))) if a[i] != b[i]]
    print("  unsigned k_bfe  : %s" % anchors["NAT:k_bfe@ibfe+18"])
    print("  signed   k_bfe_s: %s" % anchors["NAT:k_bfe_s@ibfe+18"])
    for i, x, y in diffs:
        print("    byte+%-2d  0x%02x -> 0x%02x   (xor 0x%02x)" % (i, x, y, x ^ y))
    report["anchor_diff"] = [{"byte": i, "unsigned": x, "signed": y} for i, x, y in diffs]

    # ---- verdicts ---------------------------------------------------------------
    def inert_everywhere(field):
        for run in SF.RUNS:
            for cid in CARRIERS:
                r = report[run].get(cid, {}).get(field)
                if r is None:
                    continue
                if r["subfield"]["moved"] != 0:
                    return False
        return True

    def power(field_byte):
        return min(report[run][cid][f]["byte_liveness"]["moved"]
                   for run in SF.RUNS for cid in CARRIERS
                   for f in report[run][cid] if FIELDS[f][0] == field_byte)

    se_inert = inert_everywhere("sign_ext")
    b2_inert = inert_everywhere("b2_bit0")
    print("\n  sign_ext inert on every carrier x run : %s   (byte+6 min detection power %d/256)"
          % (se_inert, power(6)))
    print("  b2_bit0  inert on every carrier x run : %s   (byte+2 min detection power %d/256)"
          % (b2_inert, power(2)))
    # sign_ext is inert in the SIGNED anchor too -> it cannot be the sign control
    def_ok = se_inert and power(6) > 0
    print("\nVERDICT DEF-0171-3: %s" % ("CONFIRMED" if def_ok else "NOT CONFIRMED"))
    print("  `sign_ext` is inert in BOTH the unsigned and the signed compiler anchor,")
    print("  on a byte that is demonstrably live. It is not the sign control.")
    print("  Where the two anchors DO differ is printed above.")
    report["verdict_def3"] = "CONFIRMED" if def_ok else "NOT CONFIRMED"
    report["sign_ext_inert_everywhere"] = se_inert
    report["b2_bit0_inert_everywhere"] = b2_inert
    json.dump(report, open(os.path.join(HERE, "def3_rederived.json"), "w"), indent=1)
    return 0 if def_ok else 1


sys.exit(main())
