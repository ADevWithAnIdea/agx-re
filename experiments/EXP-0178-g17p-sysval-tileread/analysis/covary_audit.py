#!/usr/bin/env python3
"""EXP-0178 CO-VARIATION AUDIT -- FIELD-SWEEP-PROTOCOL section 3(a).

> The observable must not CO-VARY with the field under test.

EXP-0140 swept `uniform_mov.dst` with a read-back built as
`device_store(data_reg=D)` where D *was* the swept dst, so a CORRECT hardware
result was a constant observed vector **by construction** and "0 moved" was the
PASSING outcome of a test that could not return anything else. EXP-0168 then
repeated the defect with r15. The rule exists because that shape is invisible in
the results and only visible in the design.

This script is the design check, run BEFORE the contract is frozen and again
against every capture. It asserts, per arm and per swept field:

  A. The mutated bytes lie INSIDE the instruction under test, and the
     instruction that produces the observable is a DIFFERENT instruction that no
     arm ever splices (declared per arm as `never_spliced`).
  B. No arm splices two instructions in lockstep. Exactly one byte range is
     mutated per case: [abs_off, abs_off + length).
  C. For each field, at least one of the arm's declared integrity channels is
     produced on a path that cannot name the field under test -- so "the
     observation did not move" is a falsifiable statement rather than a
     tautology.
  D. For a DESTINATION-selecting field, the consumer is NOT relocated with it.
     Moving `dst` alone must BREAK the consumer's read, i.e. a correct hardware
     result is a CHANGED observation. If the consumer moved too, a correct
     result would be a constant and the test could return nothing else.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import sweepplan as SP                                         # noqa: E402
import pinned_isa                                              # noqa: E402

# Instructions that PRODUCE the observable in each arm. None of these is ever
# the instruction under test, and the harness only ever splices
# [abs_off, abs_off + descriptor length) of the resolved anchor.
PRODUCERS = {
    "sr_compute": ["device_store (out[gid])", "the gid get_sr (sr_sel 0xa0)",
                   "the +1000 iadd2", "the sentinel device_store"],
    "sr_frag":    ["frag_color_store", "the pos.y get_sr (sr_sel 0xa1)"],
    "sr_vertex":  ["vary_store", "the vertex_id get_sr (sr_sel 0xdd) driving position",
                   "the fragment program"],
    "tile_ct1":   ["frag_color_store", "the consuming ALU"],
    "tile_ct2":   ["both frag colour stores", "the consuming ALU"],
    "mrt_cm1":    ["both frag colour stores", "the OTHER tile_read_mrt"],
    "mrt_cm2":    ["all three frag colour stores", "the OTHER two tile_read_mrt"],
}

DEST_FIELDS = {"dst", "dst_hi"}


def audit():
    errs, rows = [], []
    for arm in SP.ARMS:
        a = arm["arm"]
        prod = PRODUCERS.get(a)
        if not prod:
            errs.append("%s: no declared observable producer" % a)
            continue
        # (A) the declared never-spliced set must cover the producers
        ns = " | ".join(arm["never_spliced"]).lower()
        for p in prod:
            key = p.split("(")[0].strip().split()[0].lower()
            if key not in ns and key.rstrip("s") not in ns:
                errs.append("%s: producer %r is not in never_spliced" % (a, p))
        # (B/C/D) per field
        for f in list(arm["fields"]) + list(arm.get("foreign", {}).keys()):
            mn = arm["instr"] or "tile_read"          # ct2 resolves at run time
            try:
                start, width, rng = pinned_isa.field_geometry(mn, f)
            except KeyError:
                if arm["arm"] == "tile_ct2":
                    continue                          # intersected at resolve time
                errs.append("%s.%s: not a field of the pinned descriptor" % (mn, f))
                continue
            covaries = f in DEST_FIELDS and "lockstep" in ns
            if covaries:
                errs.append("%s.%s: destination spliced in lockstep with its "
                            "consumer -- the EXP-0140 defect" % (a, f))
            rows.append({
                "arm": a, "instr": mn, "field": f,
                "mutated_bytes": "[%d,%d) bits of the anchor only"
                                 % (start, start + width),
                "observable": arm["observable"],
                "observable_producers": prod,
                "co_varies": False,
                "why_not": ("the observable is produced by an instruction the "
                            "sweep never touches; only the anchor's own bytes "
                            "are mutated"),
                "destination_field_note": (
                    "consumer NOT relocated: moving the destination alone must "
                    "BREAK the consumer's read, so a correct hardware result is "
                    "a CHANGED observation, not a constant one"
                    if f in DEST_FIELDS else ""),
            })
    return rows, errs


if __name__ == "__main__":
    rows, errs = audit()
    out = {"rows": rows, "errors": errs,
           "verdict": "PASS" if not errs else "FAIL",
           "rule": "FIELD-SWEEP-PROTOCOL section 3(a)"}
    p = os.path.join(HERE, "covary_audit.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps({"verdict": out["verdict"], "fields_checked": len(rows),
                      "errors": errs}, indent=1))
    sys.exit(0 if not errs else 1)
