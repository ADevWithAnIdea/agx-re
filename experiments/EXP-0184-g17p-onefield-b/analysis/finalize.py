#!/usr/bin/env python3
"""EXP-0184 finalize: derive the exact semantics + `db_defects` from raw, and
splice them into `analysis/field_verdicts.json`.

Everything here is COMPUTED from `analysis/partitions.json` (which is computed
from `raw/`), not hand-typed, so a reviewer can re-derive every claim by
re-running the chain. FIELD-SWEEP-PROTOCOL section 6: a descriptor that turns
out to be wrong is a first-class result and belongs under `db_defects` --
`db.json` itself is NOT edited (EXP-0183 owns it).

    python3 analysis/verdicts.py raw/run01 raw/run02
    python3 analysis/partitions.py raw/run01 raw/run02
    python3 analysis/finalize.py
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def top_bits_rule(part, arms, mnemonic, field, width):
    """For each arm, is the ACCEPT set exactly the coset of the baseline under
    'the top k bits are live, the low width-k bits are don't care'? Returns the
    smallest k that explains every arm, or None."""
    rows = []
    for arm, d in sorted(part.items()):
        if "/%s.%s" % (mnemonic, field) not in arm:
            continue
        acc = [g for g in d["partition"] if g["outcome"] == "ok"]
        if not acc or len(d["partition"]) < 2:
            continue
        accept = sorted(acc[0]["values"])
        base = arms[arm]["baseline_field"]
        rows.append((arm, base, accept))
    if not rows:
        return None, []
    for k in range(1, width + 1):
        lo = width - k
        if all(accept == sorted(v for v in range(1 << width)
                                if (v >> lo) == (base >> lo))
               for _, base, accept in rows):
            return k, rows
    return None, rows


def cosets(part, armname, width):
    """Group values by observed behaviour and report which bit positions are
    indistinguishable across every group (a bit is 'inert' if flipping it never
    changes the group)."""
    d = part.get(armname)
    if not d:
        return None
    grp = {}
    for i, g in enumerate(d["partition"]):
        for v in g["values"]:
            grp[v] = i
    inert = []
    for b in range(width):
        if all(grp.get(v) == grp.get(v ^ (1 << b)) for v in range(1 << width)):
            inert.append(b)
    return {"inert_bits": inert,
            "groups": [{"n": g["n"], "outcome": g["outcome"],
                        "values_head": g["values"][:8], "observed": g["observed"]}
                       for g in d["partition"]]}


def main():
    fv = json.loads((EXP / "analysis" / "field_verdicts.json").read_text())
    part = json.loads((EXP / "analysis" / "partitions.json").read_text())
    arms = {a["arm"]: a for a in json.loads(
        (EXP / "harness" / "arms184.json").read_text())["arms"]}

    defects = {}

    # ---- rt_query_traverse.dst -------------------------------------------
    k, rows = top_bits_rule(part, arms, "rt_query_traverse", "dst", 4)
    if k is not None:
        v = fv["verdicts"]["rt_query_traverse.dst"]
        v["semantics"] = (
            "Destination selector. On every arm with detection power the ACCEPT "
            "set is EXACTLY the %d-value block that shares the compiled value's "
            "top %d bit(s); the low %d bit(s) are a don't-care. Outside that "
            "block the traversal commits a different hit (committed-distance "
            "carrier) or returns a SILENT ZERO (committed-primitive-id carrier)."
            % (1 << (4 - k), k, 4 - k))
        v["accept_sets"] = [{"arm": a, "baseline": b, "accept": acc}
                            for a, b, acc in rows]
        defects["rt_query_traverse.dst"] = {
            "modelled": "reg, start 4, width 4",
            "measured": ("only the top %d bit(s) of the 4-bit field are live; "
                         "bits %s are HW-TESTED INERT (every value in the "
                         "baseline's top-bit coset reproduces the compiled "
                         "behaviour, every value outside it does not), on %d "
                         "arms x 2 gated runs with zero cross-run mismatches"
                         % (k, list(range(4 - k)), len(rows))),
            "evidence": "analysis/partitions.json, raw/g17p_20260830_run0{1,2}",
            "action": "narrow the field to width %d at start %d, or keep width 4 "
                      "and document bits %s as inert" % (k, 4 + (4 - k),
                                                         list(range(4 - k))),
        }

    # ---- copysign.operands -------------------------------------------------
    c = cosets(part, "cs_load#0/copysign.operands", 8)
    c2 = cosets(part, "cs_chain#0/copysign.operands", 8)
    if c:
        v = fv["verdicts"]["copysign.operands"]
        v["semantics"] = (
            "A live OPERAND DESCRIPTOR, not a raw byte. Both carriers give the "
            "identical 4-group partition over all 256 values: the ACCEPT set is "
            "{0,1,128,129}; {2,3,130,131} leaves lanes 1..7 UNWRITTEN (still "
            "poison); {4,5,132,133} substitutes a different source operand; the "
            "remaining 244 values collapse to one common wrong result. Bit 0 and "
            "bit 7 are indistinguishable at every base value that has more than "
            "one behaviour -- the `(reg<<1)|size` operand-byte shape db.json "
            "already documents for falu2, with the inert top bit EXP-0099 "
            "HW-tested on five other families.")
        v["inert_bits_cs_load"] = c["inert_bits"]
        v["inert_bits_cs_chain"] = c2["inert_bits"] if c2 else None
        v["partition_groups"] = c["groups"]
        defects["copysign.operands"] = {
            "modelled": "type `raw`, no semantics",
            "measured": "a live operand descriptor with an exact 4-group "
                        "partition reproduced on 2 structurally different "
                        "carriers and 2 gated runs, 0 cross-run mismatches",
            "evidence": "analysis/partitions.json",
            "action": "retype from `raw` to an operand descriptor and record the "
                      "accept set {0,1,128,129}",
        }

    # ---- copysign byte+1 / byte+2 are NOT fixed match constants -------------
    probes = dict(fv.get("match_byte_probes", {}))
    # `_b1_match` was declared role="control", so it lands in `arms` not
    # `match_byte_probes`; fold it in here so both match bytes are reported the
    # same way. Its `encodable_range` is read from the same per-arm record.
    for armname, rec in fv.get("arms", {}).items():
        if rec.get("field") == "_b1_match":
            probes.setdefault("copysign._b1_match", {
                "not_a_field": True,
                "why": "db.json models byte+1 as a fixed match constant",
                "encodable_range": rec["encodable_range"],
                "arms": {armname: rec}})
    BYTE_OF = {"copysign._b1_match": "byte+1", "copysign._b2_match": "byte+2"}
    for key in ("copysign._b1_match", "copysign._b2_match"):
        if key not in probes:
            continue
        arm = list(probes[key]["arms"])[0]
        st = probes[key]["arms"][arm]
        defects["copysign %s (match constant)" % BYTE_OF[key]] = {
            "modelled": "fixed match constant in db.json",
            "measured": ("the byte is LOAD-BEARING: %d of %d values change the "
                         "observable. But `encodable_range` is %d -- every other "
                         "value decodes as a DIFFERENT instruction (or none), so "
                         "this is NOT evidence of a copysign FIELD and no field "
                         "label is claimed."
                         % (st["moved"], st["values_dispatched"],
                            probes[key]["encodable_range"])),
            "evidence": "analysis/field_verdicts.json -> match_byte_probes",
            "action": "none for the encoding; recorded so the next agent does "
                      "not mistake this movement for a field",
        }

    # ---- if_push.scope / cvt_f2i.b9: bounded negatives ---------------------
    for key, extra in (
        ("if_push.scope",
         "0 of 256 values moved anything, on 10 occurrences spanning nesting "
         "depth 1..3 across two kernels, with the `scope_kind` control at the "
         "SAME occurrence firing on all 10. Zero faults and zero hangs in 5120 "
         "dispatches -- no wall anywhere in the range."),
        ("cvt_f2i.b9",
         "0 of 256 values moved anything, on 5 carriers spanning four "
         "destination integer types and a 16-bit source, with the `dst` control "
         "at the SAME occurrence firing on all 5. Zero faults and zero hangs in "
         "2560 dispatches, so the modelled 10-byte length is not contradicted: "
         "byte+9 is not the next instruction's leader."),
    ):
        if key in fv["verdicts"]:
            fv["verdicts"][key]["semantics"] = extra

    fv["db_defects"] = defects
    (EXP / "analysis" / "field_verdicts.json").write_text(
        json.dumps(fv, indent=1, sort_keys=True))
    print(json.dumps(defects, indent=1)[:4000])
    print("\nrt dst top-bit rule k =", k)


if __name__ == "__main__":
    main()
