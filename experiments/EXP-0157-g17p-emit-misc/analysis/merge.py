#!/usr/bin/env python3
"""EXP-0157: merge the per-gate verdict files into one `field_verdicts.json`.

Each gate group is an INDEPENDENT pair of captures of one frozen case list:

  * `RSH`  = raw/g17p_run01 + raw/g17p_run02   (the pre-registered arms R, S, H)
  * `B2`   = raw/g17p_raymove01 + raw/g17p_raymove02  (post-freeze `ray_move`
             arm in the 25 kB k_rq_prim carrier)

Every merged entry keeps the gate it came from and how many captures agreed, so
a reader can tell a two-run result from a one-run one without reading the raw.
A field present in more than one gate keeps the STRONGER (two-run) entry and
records the other under `also_measured_in`.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOOD = {"hardware-run", "isolated-byte-diff"}

# Per-field semantics, written from THIS experiment's observations only. Where a
# field turned out to be inert or pinned in every carrier, that is what is said;
# nothing is inherited from db.json's prose.
SEMANTICS = {
 "sr_read_wide.dst": "Destination nibble. PINNED in all three carriers: no value other than the "
   "compiler's own reproduces the getter's result, because the following code reads exactly that "
   "register. An emitter cannot choose the destination from this evidence.",
 "sr_read_wide.sel": "byte+1 bits 0-6. Load-bearing but NOT the property selector: the low three "
   "bits must be 0b001 and bits 3-6 are don't-care, so 16 different values all return the correct "
   "property. Differential compilation locates the actual ray-query property selector at "
   "rt_ray_mem byte+10 (0xc4 barycentric.x / 0xc6 barycentric.y / 0xc8 triangle distance).",
 "sr_read_wide.width": "byte+2. Load-bearing: only a masked subset reproduces the result and 32 "
   "of 256 values FAULT. The constraint shared by both carriers is (v & 0x8e) == 0x06; bit 6 "
   "varies per instance.",
 "sr_read_wide.operand": "HW-TESTED INERT across all 256 values in both candidate-getter carriers.",
 "sr_read_wide.phase": "HW-TESTED INERT across all 256 values in both candidate-getter carriers. "
   "db.json reads byte+7 0x80 as the CANDIDATE-vs-COMMITTED selector; that is not observable here.",
 "sr_read_wide.marshal": "HW-TESTED INERT, both constituent bytes dense.",
 "ray_move.dst": "Destination nibble: all 16 values reproduce the oracle.",
 "ray_move.src": "byte+1: all 256 values reproduce the oracle.",
 "ray_move.form": "byte+2: 223 of 256 values run; 32 FAULT. Load-bearing.",
 "ray_move.b3": "byte+3: all 256 values reproduce the oracle.",
 "rtq_state_move.src": "byte+1 IS a per-instance operand in rq_cdist -- only 39 of 256 values "
   "reproduce the oracle and 212 return a DIFFERENT value, the signature of a real register read. "
   "In rq_mtype and bb_commit the same field is almost entirely inert, so the claim is "
   "carrier-scoped.",
 "rtq_state_move.form": "byte+2: load-bearing; the rejected values split between silent zero and "
   "fault depending on the carrier.",
 "sfu_marker.byte+0": "QUADRANT / SIGN CONTROL for the SFU's argument reduction, refuting "
   "db.json's 'byte-INVARIANT ... fixed control token with no operand bits'. Accepted set "
   "(v & 0xf7) == 0x06 -- 2 of 256 -- identically in three carriers and identical to EXP-0146's "
   "M4 measurement. Classifying the REJECTED values by the shape of the eight-row fast::sin "
   "output partitions the byte exactly: (v & 0x60) == 0x00 (44 values) drops the quadrant "
   "correction for the single row in pi/2..pi; (v & 0x64) == 0x00 (16 values) inverts six of the "
   "eight rows; {0x16,0x1e} invert three; and any value with bit 5 set makes the SFU produce "
   "nothing at all (192 values).",
 "sfu_marker.byte+1": "Second quadrant/sign control byte. Accepted set (v & 0x13) == 0x02 -- 32 "
   "of 256 -- identically in three carriers and identical to EXP-0146's M4 measurement. "
   "(v & 0x10) == 0x00 (80 values) drops the same single-quadrant correction as byte+0; "
   "(v & 0x17) == 0x00 (16 values) inverts four rows; bit 4 set (128 values) silences the SFU.",
 "n2_op6.opsel": "byte+2, strongly constrained and the only field in the family that FAULTS on "
   "half its range in the SFU carriers. The accepted mask differs per carrier instance. Output-"
   "shape analysis in the fast::sin carrier resolves the rejected values: bit 1 SET (60 values) "
   "makes the SFU produce nothing; (v & 0xd7) == 0x13 (4 values) sign-flips one row; 122 values "
   "drop the quadrant correction for the range-reduced row. So in this lowering opsel is part of "
   "the SFU argument-reduction control, not a generic select.",
 "n2_op6.imm_sel": "byte+6. In the fast::sin carrier 240 of 255 values ZERO the range-reduced row "
   "while leaving the others correct, and (v & 0x7e) == 0x00 zeroes every row -- so it selects "
   "which reduced result survives. The accepted set is (v & 0x7e) == 0x06 here and differs per "
   "carrier instance.",
 "n2_op6.dst": "PINNED: no value other than the compiler's own reproduces the oracle.",
 "h_coord_hi.opsel": "byte+2 op-select. (v & 0xd7) == 0x06 in BOTH half carriers -- the one "
   "cross-carrier constant in this instruction. Faults on 76-80 of 256 values.",
 "h_coord_hi.srcA": "A real source-register field: 240 of 255 values return a DIFFERENT non-zero "
   "result. Only the compiler's own value (up to bit 7) reproduces the oracle, so it is pinned "
   "in this carrier.",
 "h_coord_hi.srcB": "Same shape as srcA: 254 of 255 values return a different result.",
 "op04_len8.dst": "Not promotable: the descriptor's LENGTH is refuted on hardware (12 bytes, not "
   "8), so this field's offset is measured against a wrong model.",
}


# A field this experiment characterised by DIFFERENTIAL COMPILATION rather than
# by splicing. It is not one of the twenty dispatched descriptors, but it is the
# answer to why sweeping `sr_read_wide.sel` never produced another property, so
# it is recorded here rather than lost.
EXTRA = {
 "rt_ray_mem.field_off": {
   "label": "isolated-byte-diff",
   "range": "three values observed: 0xc4, 0xc6, 0xc8 (the field's range was NOT swept)",
   "target": "G17P",
   "evidence": ["EXP-0157"],
   "gate": "differential-compilation",
   "captures_agreeing": 1,
   "carrier": "k_rq_getters.metal :: k_cand_baryx / k_cand_baryy / k_cand_td_dist",
   "semantics": ("byte+10 of the 14-byte rt_ray_mem is the RAY-QUERY PROPERTY SELECTOR. Three "
                 "intersection_query<triangle_data> kernels that differ ONLY in the getter they "
                 "read compile to programs that are byte-identical except at 14 offsets, each a "
                 "single byte taking 0xc4 (barycentric.x) / 0xc6 (barycentric.y) / 0xc8 "
                 "(triangle distance) -- the selector steps by 2 per property. Each of the three "
                 "programs was executed and returned its own host-computed oracle exactly, so the "
                 "byte change produced the predicted effect. db.json already models this byte as "
                 "`field_off` at `corpus-correlation`; this is an independent confirmation by a "
                 "second method, and it upgrades the label to isolated-byte-diff."),
   "note": ("This is why sweeping `sr_read_wide.sel` never yielded another property: on G17P the "
            "property selector is not in sr_read_wide at all. Raw: "
            "raw/g17p_census01/getter_diff.json plus the three committed .hex files, reproduced "
            "from the committed kernel source."),
   "outcomes": {"ok": 3},
   "ok_values": 3,
   "exact_rule": None,
   "anchor_live": True,
 },
}


def main():
    groups = [("RSH", "field_verdicts_RSH.json", "gate_report_RSH.json", 2),
              ("B2", "field_verdicts_B2.json", "gate_report_B2.json", 2)]
    out, gates = {}, {}
    for name, vf, gf, ncap in groups:
        vp, gp = HERE / vf, HERE / gf
        if not vp.exists():
            continue
        v = json.load(open(vp))
        gates[name] = json.load(open(gp)) if gp.exists() else None
        for k, e in v.items():
            if k == "db_defects":
                out.setdefault("db_defects", {}).update(e)
                continue
            base = k.split("@")[0]
            e = dict(e, gate=name, captures_agreeing=ncap)
            if not e.get("semantics") and base in SEMANTICS:
                e["semantics"] = SEMANTICS[base]
            if k in out:
                out[k].setdefault("also_measured_in", []).append(
                    {"gate": name, "outcomes": e.get("outcomes"),
                     "exact_rule": e.get("exact_rule")})
            else:
                out[k] = e
    for k, e in EXTRA.items():
        out.setdefault(k, e)
    out["_gates"] = gates
    Path(HERE / "field_verdicts_by_carrier.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n")

    # ------------------------------------------------------------------ #
    # MERGE-READY view. `work/merge_verdicts.py` (the orchestrator's merger)
    # requires keys of the exact form `<mnemonic>.<field>` where <field> is a
    # db.json field name, and keeps only label/range/target/evidence/note. A
    # `<mnemonic>.<field>@<carrier>` key is rejected outright -- which is very
    # likely why EXP-0146's verdicts, which use that convention, never landed in
    # validation.json. So this file is emitted in the form the merger accepts,
    # with everything else folded into `note`, and the per-carrier detail kept
    # beside it in field_verdicts_by_carrier.json.
    # ------------------------------------------------------------------ #
    import re as _re
    dbf = {}
    dbp = HERE.parents[2] / "tools" / "agx-isa" / "db.json"
    if dbp.exists():
        for i in json.load(open(dbp))["instructions"]:
            dbf[i["mnemonic"]] = {f["name"] for f in i["fields"]}
    STRENGTH = ["hardware-run", "isolated-byte-diff", "corpus-correlation",
                "tokenization-only", "single-template-inference",
                "api-accept-reject", "host-private", "untested"]
    rank = {l: i for i, l in enumerate(STRENGTH)}
    flat, dropped = {}, []
    for k, e in out.items():
        if k in ("db_defects", "_gates"):
            continue
        head = k.split("@")[0]
        m, _, f = head.partition(".")
        if not f or m not in dbf or f not in dbf[m]:
            dropped.append(k)
            continue
        bits = []
        if e.get("exact_rule"):
            bits.append("accepted set: %s" % e["exact_rule"])
        if e.get("outcomes"):
            bits.append("outcomes " + ", ".join("%s=%d" % (a, b) for a, b in
                                                 sorted(e["outcomes"].items())))
        bits.append("carrier %s, anchor +%s, %d agreeing captures (gate %s)"
                    % (e.get("carrier"), e.get("anchor"), e.get("captures_agreeing", 1),
                       e.get("gate")))
        if e.get("semantics"):
            bits.append(e["semantics"])
        if e.get("note"):
            bits.append(e["note"])
        cand = dict(e)
        cand["note"] = " | ".join(str(b) for b in bits)
        prev = flat.get(head)
        if prev is None or rank[cand["label"]] < rank[prev["label"]]:
            flat[head] = cand
        elif rank[cand["label"]] == rank[prev["label"]]:
            prev["note"] += "  ALSO: " + cand["note"]
    slim = {}
    for k, e in flat.items():
        slim[k] = {"label": e["label"], "range": e["range"], "target": e["target"],
                   "evidence": e["evidence"], "note": e["note"]}
    slim["db_defects"] = out.get("db_defects", {})
    Path(HERE / "field_verdicts.json").write_text(
        json.dumps(slim, indent=1, sort_keys=True) + "\n")
    n = sum(1 for k, e in slim.items() if k != "db_defects" and e["label"] in GOOD)
    print("merge-ready: %d <mnemonic>.<field> entries (%d at emitter grade); "
          "%d per-carrier/component keys kept only in field_verdicts_by_carrier.json"
          % (len(slim) - 1, n, len(dropped)))
    if dropped:
        print("  not mergeable (not a db.json field): %s"
              % ", ".join(sorted(dropped)[:8]) + (" ..." if len(dropped) > 8 else ""))


if __name__ == "__main__":
    main()
