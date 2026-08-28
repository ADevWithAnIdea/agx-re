#!/usr/bin/env python3
"""EXP-0147 analysis: two gated runs -> analysis/field_verdicts.json.

Applies the labelling rule frozen in PRE_REGISTRATION.md section 8. Nothing here
touches the GPU; it is a pure function of the two raw sweep files.

  python3 analysis/verdicts.py --run01 m4_20260828_run01 --run02 m4_20260828_run02
"""
import argparse, collections, json, os, sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(EXP, "harness"))
import sweepplan as SP  # noqa: E402

CONTROLS = ("_baseline", "_liveness_src_alt", "_liveness_dst_alt", "_liveness_vp_alt",
            "_liveness_spatial", "_litmus_power", "_identity_splice", "_sensitivity")


def load(run_id):
    p = os.path.join(EXP, "raw", run_id, "sweep.jsonl")
    return [json.loads(l) for l in open(p)]


def rngstr(vals):
    """Compact contiguous-range description of an integer value set."""
    iv = sorted(v for v in vals if isinstance(v, int))
    if not iv: return ""
    out, s, p = [], iv[0], iv[0]
    for x in iv[1:]:
        if x == p + 1: p = x; continue
        out.append((s, p)); s = p = x
    out.append((s, p))
    return ",".join(f"0x{a:02x}" if a == b else f"0x{a:02x}-0x{b:02x}" for a, b in out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    ap.add_argument("--out", default=os.path.join(EXP, "analysis", "field_verdicts.json"))
    a = ap.parse_args()
    r1, r2 = load(a.run01), load(a.run02)

    def index(recs):
        ctrl, sweep, meta = {}, {}, {}
        for r in recs:
            if r.get("kind") == "arm_meta": meta[r["arm"]] = r
            if "field" not in r: continue
            k = (r["carrier"], r["field"])
            if r["field"] in CONTROLS: ctrl[k] = r
            elif r["field"] == "_baseline_recheck": ctrl.setdefault(k, []).append(r) \
                if isinstance(ctrl.get(k), list) else ctrl.setdefault(k, [r])
            else: sweep[(r["carrier"], r["field"], str(r["value"]))] = r
        return ctrl, sweep, meta

    c1, s1, m1 = index(r1)
    c2, s2, m2 = index(r2)

    # ---- cross-run agreement ------------------------------------------------
    common = set(s1) & set(s2)
    agree = sum(1 for k in common if s1[k]["outcome"] == s2[k]["outcome"])
    xrun = {"cases_in_both_runs": len(common), "same_outcome": agree,
            "agreement_pct": round(100.0 * agree / max(1, len(common)), 3),
            "only_in_run01": len(set(s1) - set(s2)),
            "only_in_run02": len(set(s2) - set(s1))}

    verdicts = {}
    # Corrected models found by the sweeps. NOT applied to db.json -- the
    # orchestrator owns that file (FIELD-SWEEP-PROTOCOL section 6).
    defects = {
        "pixel_order.flags": {
            "severity": "descriptor is self-contradictory AND over-constrains the hardware",
            "db_says": "field `flags` at bits[32:40] (byte+4), while match constant "
                       "[32,8,6] pins those SAME bits to 0x06",
            "measured": "with the acquire member spliced, the program stays byte-exactly "
                        "correct (texel = 8*src, pixel = clear + 36*src) for 112 of the 256 "
                        "values of byte+4, and for 224 of 256 on the release member. byte+4 "
                        "is therefore a REAL field with a large legal set, not a constant.",
            "consequence": "as modelled, every legal encoding with byte+4 != 0x06 fails to "
                           "match `pixel_order` at all, so it is neither decodable nor "
                           "emittable; and `flags` can never be given a value by an emitter.",
            "suggested": "drop the [32,8,6] match constant, keep `flags` as a field, and "
                         "record the measured legal sets (see fields.pixel_order.flags)."},
        "scoreboard_fence.kind": {
            "severity": "enum incomplete",
            "db_says": "kind in {0x00, 0x02, 0x22, 0xc0, 0xc2}",
            "measured": "our own MSL (kernels/pipe_compute.metal :: k_atomic, a device "
                        "atomic RMW plus a device+texture fence) compiles to `07 42 02 00`, "
                        "i.e. kind = 0x42, which the enum does not list.",
            "suggested": "add 0x42; its role is not established here."},
        "matrix_mac.dst_desc": {
            "severity": "typed `raw`, but the hardware rule is simple and now known",
            "measured": "correct result iff bit6 == 1 and bit7 == 0 (0x40..0x7f, 64/64 "
                        "values); bits 0-5 are don't-care. 0x00-0x3f and 0x80-0xbf give a "
                        "SILENT ZERO, 0xc0-0xff give a wrong value.",
            "suggested": "split into a 2-bit control (bits 6-7) plus 6 don't-care bits."},
        "matrix_mac.b11hi": {
            "severity": "typed `raw`, but two of its bits are semantic",
            "measured": "correct a*b+c iff bits 0 and 1 of the field (byte+11 bits 1 and 2) "
                        "are both 0 -- 32/128 values, exactly those with (v & 3) == 0. "
                        "Either bit alone inverts the sign of the C addend (a*b-c); both set "
                        "cancel back to a*b+c. Bits 2-6 are don't-care.",
            "suggested": "split into two accumulator-sign bits plus 5 don't-care bits."},
        "tile_read.b6 / tile_read_mrt.b6": {
            "severity": "typed `raw` with no semantics; bit0 is an enable",
            "measured": "all 128 ODD values give the correct read; all 128 EVEN values give "
                        "a SILENT ZERO (the pixel collapses to the no-read oracle). Bits 1-7 "
                        "are don't-care. Identical on both instructions.",
            "suggested": "model byte+6 bit0 as a read-enable."},
    }
    for arm in SP.ARMS:
        an, instr = arm["arm"], arm["instr"]
        # ---- per-arm control gate (PRE_REGISTRATION section 8) --------------
        def ctrl_ok(name, want_match, runs=(c1, c2)):
            got = []
            for c in runs:
                r = c.get((an, name))
                if r is None: return None
                got.append(bool(r["match"]) == want_match)
            return all(got)

        gate = {
            "baseline_ok": ctrl_ok("_baseline", True),
            "identity_splice_ok": ctrl_ok("_identity_splice", True),
            "sensitivity_failed_as_preregistered": ctrl_ok("_sensitivity", False),
            "litmus_power": ctrl_ok("_litmus_power", True),
        }
        for lv in ("_liveness_src_alt", "_liveness_dst_alt", "_liveness_vp_alt", "_liveness_spatial"):
            if (an, lv) in c1: gate[lv.lstrip("_")] = ctrl_ok(lv, True)
        rechecks = [r for r in r1 + r2 if r.get("carrier") == an and r.get("field") == "_baseline_recheck"]
        gate["baseline_rechecks"] = len(rechecks)
        gate["baseline_rechecks_all_ok"] = all(r["match"] for r in rechecks) if rechecks else None
        promotable = bool(gate["baseline_ok"] and gate["identity_splice_ok"]
                          and gate["sensitivity_failed_as_preregistered"] and gate["litmus_power"])

        for f in arm["fields"]:
            fn = f["name"]
            cases1 = {k[2]: v for k, v in s1.items() if k[0] == an and k[1] == fn}
            cases2 = {k[2]: v for k, v in s2.items() if k[0] == an and k[1] == fn}
            both = set(cases1) & set(cases2)
            stable = [k for k in both if cases1[k]["outcome"] == cases2[k]["outcome"]]
            intra = [k for k in both if cases1[k].get("stable") is not False
                     and cases2[k].get("stable") is not False]
            oc = collections.Counter(cases1[k]["outcome"] for k in both)
            expected = (f["nbytes"] * 256 + len(SP.wide_values(f["width"]))) if f.get("nbytes") \
                       else (1 << f["width"])
            complete = len(both) >= expected

            # value partition, for byte-wide fields only (multi-byte fields are
            # reported per constituent byte in `note`)
            part = {}
            if not f.get("nbytes"):
                for k in both:
                    part.setdefault(cases1[k]["outcome"], []).append(int(k))

            # PRE_REGISTRATION section 8 clause (4) is an INTRA-run condition
            # ("every non-ok case reproduced across its 3 replicates"). We apply
            # it, and additionally require CROSS-run agreement before saying
            # `hardware-run` -- strictly tighter than the frozen rule, never
            # looser, so it cannot over-promote. Both readings are reported.
            intra_clean = (len(intra) == len(both))
            cross_clean = (len(stable) == len(both))
            if promotable and complete and intra_clean and cross_clean:
                label = "hardware-run"
            elif promotable and complete and intra_clean:
                label = "isolated-byte-diff"
            elif promotable and complete:
                label = "isolated-byte-diff"
            else:
                label = "untested"
            label_frozen = ("hardware-run" if (promotable and complete and intra_clean)
                            else ("isolated-byte-diff" if (promotable and complete) else "untested"))

            v = {
                "label": label,
                "range": (f"full {f['width']}-bit range, dense ({expected} cases) x2 runs"
                          if complete else f"PARTIAL: {len(both)}/{expected} cases"),
                "target": "M4",
                "evidence": ["EXP-0147"],
                "outcomes": dict(oc),
                "label_under_frozen_rule_literal": label_frozen,
                "cross_run_reproduced": f"{len(stable)}/{len(both)}",
                "intra_run_replicates_stable": f"{len(intra)}/{len(both)}",
                "carrier": an,
                "instruction_liveness_proven": promotable,
                "control_gate": gate,
            }
            if part:
                v["value_partition"] = {k: rngstr(vv) for k, vv in sorted(part.items())}
            key = f"{instr}.{fn}"
            if key in verdicts:
                # The pixel_order acquire and release members are two arms over
                # the SAME db field. The acquire arm is the primary record; the
                # release arm is the pre-registered adversarial second method.
                verdicts[key]["adversarial_second_method"] = {
                    "carrier": an, "outcomes": dict(oc),
                    "value_partition": {k: rngstr(vv) for k, vv in sorted(part.items())} if part else None,
                    "control_gate": gate,
                    "label_under_frozen_rule_literal": label_frozen,
                "cross_run_reproduced": f"{len(stable)}/{len(both)}",
                }
            else:
                verdicts[key] = v

    out = {
        "_spec": "docs/evidence-classification.md section 2 labels; "
                 "promotion rule frozen in PRE_REGISTRATION.md section 8",
        "_runs": {"run01": a.run01, "run02": a.run02},
        "_cross_run": xrun,
        "_outcome_vocabulary": {
            "ok": "matched the host oracle",
            "silent_zero": "matched the zero-oracle: the instruction contributed 0",
            "wrong_value": "ran, produced neither the oracle nor the zero-oracle",
            "no_draw": "runner returned OK but the integrity sentinel proves nothing was "
                       "drawn; confirmed twice with a healthy device in between",
            "no_dispatch": "same, compute stage",
            "fault": "OS reported 'Caused GPU Hang Error' for THIS submission after retries",
            "invalid_run": "collateral damage from another process's GPU errors "
                           "('Discarded (victim...)' / 'Ignored (for causing prior...)'); "
                           "NOT evidence about the encoding",
            "unstable": "the 3 intra-run replicates disagreed",
            "hang": "watchdog expired",
        },
        "fields": verdicts,
        "db_defects": defects,
    }
    with open(a.out, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True); f.write("\n")
    print(json.dumps({"cross_run": xrun,
                      "labels": dict(collections.Counter(v["label"] for v in verdicts.values()))},
                     indent=2))


if __name__ == "__main__":
    main()
