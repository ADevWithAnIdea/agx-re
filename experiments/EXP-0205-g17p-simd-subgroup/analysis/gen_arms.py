#!/usr/bin/env python3
"""EXP-0205 arm construction (runs ON THE NEO; the result is pulled back and
FROZEN into CAPTURE_CONTRACT.json before any gated run).

    python3 analysis/gen_arms.py

Each carrier is compiled with `shdump` and scanned for its target descriptor's
`match` signature.  Calibration established that every carrier contains EXACTLY
ONE occurrence, parcel-aligned and agreeing with the pinned tokenizer; this
script REFUSES to emit an arm for any carrier where that is no longer true,
because an arm that cannot name the occurrence whose result reaches the output
proves nothing (FIELD-SWEEP-PROTOCOL section 3.2).

ARM ROLES
  target       the field under test.
  control      a field on the SAME instruction at the SAME occurrence that is
               already `hardware-run` (`psrc` / `src` / `lane`).  It measures
               DETECTION POWER: an arm whose control never moves cannot support
               a verdict, inert or live (protocol section 5a).
  control_dim  the IN-DIMENSION control for the two `cache` fields.  Sweeping
               `dst` densely must at some value make the instruction write the
               register its own source occupies, which changes what the LATER
               read of that source returns -- so out[32..63] moves.  That is a
               positive control in the exact dimension `cache` is claimed to
               control (the content of the source register after the
               instruction), which is what protocol section 9 rule 1 demands and
               what no previous `cache` sweep had.

CLEAN-ROOM: OWN-SHADER.  Only our own compiled MSL is scanned.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

import carriers205 as C          # noqa: E402
import locate205 as L            # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work"

CTRL16 = [0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
LANE16 = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
DENSE256 = list(range(256))

PLAN = {
    "sb_ballot":  [("pred", "target"), ("cache", "target"), ("psrc", "control")],
    "sb_ballot2": [("pred", "target"), ("cache", "target"), ("psrc", "control")],
    "sb_active":  [("pred", "target"), ("cache", "target"), ("psrc", "control")],
    "sb_reuse":   [("pred", "target"), ("cache", "target"), ("psrc", "control"),
                   ("dst", "control_dim")],
    "sr_sum":     [("op", "target"), ("dtype", "target"), ("src", "control")],
    "sr_scan":    [("op", "target"), ("dtype", "target"), ("src", "control")],
    "sr_max":     [("op", "target"), ("dtype", "target"), ("src", "control")],
    "sr_fsum":    [("op", "target"), ("dtype", "target"), ("src", "control")],
    "sh_bc":      [("dir", "target"), ("cache", "target"), ("lane", "control")],
    "sh_xor":     [("dir", "target"), ("cache", "target"), ("lane", "control")],
    "sh_reuse":   [("dir", "target"), ("cache", "target"), ("lane", "control"),
                   ("dst", "control_dim")],
}

CONTROL_VALUES = {"psrc": CTRL16, "src": CTRL16, "lane": LANE16,
                  "dst": DENSE256}

GROUP = {"simd_ballot": "ballot", "simd_reduce": "reduce",
         "simd_shuffle": "shuffle"}


def main():
    arms, meta = [], {}
    for carrier, plan in PLAN.items():
        spec = C.CARRIERS[carrier]
        mn = C.CARRIER_TARGET[carrier]
        arch, moff, main = L.compile_carrier(
            BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
        occs = L.find_occurrences(main, mn)
        meta[carrier] = {"main_len": len(main), "n_occ": len(occs),
                         "occ": [o["off"] for o in occs]}
        if len(occs) != 1:
            meta[carrier]["REFUSED"] = (
                "expected exactly 1 occurrence of %s; found %d. An arm that "
                "cannot name the occurrence on the output path proves nothing."
                % (mn, len(occs)))
            continue
        o = occs[0]
        tok = L.token_at(main, o["off"])
        if tok.get("mnemonic") != mn:
            meta[carrier]["REFUSED"] = (
                "pinned tokenizer calls the located bytes %r, not %s"
                % (tok.get("mnemonic"), mn))
            continue
        raw = bytes.fromhex(o["bytes"])
        meta[carrier]["baseline_bytes"] = o["bytes"]
        for field, role in plan:
            start, width = L.field_span(mn, field)
            if role == "target":
                values = list(range(1 << width))          # dense, always
            else:
                values = [v for v in CONTROL_VALUES[field] if v < (1 << width)]
            base = L.get_bits(raw, start, width)
            # ALIASING CHECK, done here and re-checked in the raw: distinct
            # field values must produce DISTINCT instruction bytes, differing
            # ONLY inside the field's own span.  `match`-pinned bits that the
            # assembler cannot clear have made different values assemble to
            # identical bytes elsewhere; this experiment patches bytes directly,
            # and proves it rather than asserting it.
            enc = {}
            for v in values:
                enc[v] = L.patch_instr(raw, start, width, v).hex()
            distinct = len(set(enc.values()))
            spans_ok = all(
                (int.from_bytes(bytes.fromhex(enc[v]), "little")
                 ^ int.from_bytes(raw, "little")) & ~(((1 << width) - 1) << start) == 0
                for v in values)
            arms.append({
                "arm": "%s#%s.%s" % (carrier, mn, field),
                "carrier": carrier, "instr": mn, "field": field, "role": role,
                "group": GROUP[mn], "occ": 0,
                "off": o["off"], "len": o["len"],
                "start": start, "width": width,
                "values": values,
                "baseline_field": base, "baseline_bytes": o["bytes"],
                "distinct_encodings": distinct,
                "encodings_confined_to_field": spans_ok,
                "note": "",
            })
    doc = {"_generated_by": "analysis/gen_arms.py", "arms": arms, "meta": meta,
           "n_cases": sum(len(a["values"]) for a in arms)}
    p = EXP / "harness" / "arms205.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps({"n_arms": len(arms), "n_cases": doc["n_cases"],
                      "meta": meta}, indent=1))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
