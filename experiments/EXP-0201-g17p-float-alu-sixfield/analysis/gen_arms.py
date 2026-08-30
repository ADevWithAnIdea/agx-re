#!/usr/bin/env python3
"""EXP-0201 census + arm generation. RUNS ON THE DEVICE (it must compile our MSL).

    python3 analysis/gen_arms.py            # -> work/census.json, harness/arms201.json

For every carrier it compiles our own MSL, locates every occurrence of the
target mnemonic by the PINNED descriptor's `match` constraints, cross-checks the
occurrence against the pinned tokenizer, and emits one arm per (occurrence,
field).

THE ALIASING HARD STOP (PRE_REGISTRATION section 4 / AMENDMENT A2). `opsel` was
swept before with `match`-pinned bits an assembler could not clear, so nominal
values 4 and 6 assembled to IDENTICAL bytes and the oracle described a program
that never ran. This generator therefore computes the mutated bytes for EVERY
value of EVERY arm on the host and REFUSES to emit the arm unless

  (a) the byte strings are pairwise DISTINCT  -- distinct_bytes == len(values);
  (b) every XOR against the baseline is a SUBSET of the field's own bit mask.

`distinct_bytes < values` is a hard stop here, before any device time, not a
note in the analysis afterwards.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is scanned.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

import carriers201 as C          # noqa: E402
import locate201 as L            # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work"

TARGETS = {                       # carrier -> (mnemonic, [target fields])
    "f3_fma":    ("falu3", ["op"]),
    "f3_chain":  ("falu3", ["op"]),
    "f3_two":    ("falu3", ["op"]),
    "f3e_sat":   ("falu3_ext", ["op"]),
    "f3e_chain": ("falu3_ext", ["op"]),
    "f3e_two":   ("falu3_ext", ["op"]),
    "f12_abs":   ("falu3_srcmod12", ["opsel", "ctrl"]),
    "f12_abs2":  ("falu3_srcmod12", ["opsel", "ctrl"]),
    "fsp_rsqrt": ("fspecial_est", ["srcA"]),
    "fsp_rcp":   ("fspecial_est", ["srcA"]),
    "fsp_sqrt":  ("fspecial_est", ["srcA"]),
    "fsp_two":   ("fspecial_est", ["srcA"]),
    "cs_load":   ("copysign", ["operands"]),
    "cs_swap":   ("copysign", ["operands"]),
    "cs_alu":    ("copysign", ["operands"]),
    "cs_chain":  ("copysign", ["operands"]),
}

# detection-power control at the SAME occurrence, on a field already established
# live, and the pre-registered falsifier that MUST break the program.
CONTROL = {
    "falu3":           ("srcA", 8, 8, list(range(0, 256, 16)) + [0x05, 0x85]),
    "falu3_ext":       ("srcA", 8, 8, list(range(0, 256, 16)) + [0x05, 0x85]),
    "falu3_srcmod12":  ("srcA_reg", 9, 7, list(range(0, 128, 8))),
    "fspecial_est":    ("subop", 24, 8, sorted(set(list(range(0, 256, 16))
                                                   + [9, 11, 13, 15]))),
    # `copysign`'s descriptor pins bits 0..23 by `match`, so no second field
    # exists at the occurrence. The control is therefore OCCURRENCE
    # REACHABILITY: overwrite byte0's low nibble and the read-back must change.
    # EXP-0184 rightly criticised a byte+1 control as "firing by encoding a
    # different opcode"; this control is labelled for what it is and proves the
    # arm can SEE this occurrence, not that it can see this field.
    "copysign":        ("__occ_reach", 0, 8, [0x00, 0x01, 0x02, 0x0f, 0x3a, 0xff]),
}

FALSIFIER = {                     # field span + values pre-registered to FAIL
    "falu3":          ("__falsifier_op", 16, 8, [0x05]),
    "falu3_ext":      ("__falsifier_op", 16, 8, [0x05]),
    "falu3_srcmod12": ("__falsifier_op", 16, 8, [0x05]),
    "fspecial_est":   ("__falsifier_subop", 24, 8, [0x00]),
    "copysign":       ("__falsifier_byte0", 0, 8, [0x00]),
}

VALUES = {
    ("falu3", "op"):             list(range(256)),
    ("falu3_ext", "op"):         list(range(256)),
    ("fspecial_est", "srcA"):    list(range(256)),
    ("falu3_srcmod12", "opsel"): list(range(8)),
    ("falu3_srcmod12", "ctrl"):  list(range(128)),
    ("copysign", "operands"):    list(range(256)),
}


def patch(raw, start, width, value):
    v = int.from_bytes(raw, "little")
    mask = ((1 << width) - 1) << start
    v = (v & ~mask) | ((value & ((1 << width) - 1)) << start)
    return v.to_bytes(len(raw), "little")


def check_arm(base_bytes, start, width, values, tag):
    """(a) pairwise distinct encodings, (b) XOR confined to the field's span."""
    mask = ((1 << width) - 1) << start
    seen, errs = {}, []
    for v in values:
        b = patch(base_bytes, start, width, v)
        x = int.from_bytes(b, "little") ^ int.from_bytes(base_bytes, "little")
        if x & ~mask:
            errs.append("%s: value %d perturbs bits outside [%d,%d): xor=%#x"
                        % (tag, v, start, start + width, x))
        if b in seen:
            errs.append("%s: values %d and %d ALIAS to identical bytes %s"
                        % (tag, seen[b], v, b.hex()))
        seen[b] = v
    return len(seen), errs


def main():
    census, arms, errors = {}, [], []
    for cname, (mnem, fields) in TARGETS.items():
        spec = C.CARRIERS[cname]
        try:
            arch, off, main_bytes = L.compile_carrier(
                BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
        except Exception as e:                                  # noqa: BLE001
            census[cname] = {"error": str(e)[:400]}
            errors.append("%s: compile failed: %s" % (cname, str(e)[:200]))
            continue
        occ = L.find_occurrences(main_bytes, mnem)
        # A shared signature is not enough, in TWO ways.
        # (1) falu3 / falu3_ext / falu3_srcmod12 / falu_srcmod12b all match
        #     [0,4,9]+[17,1,1] and differ only by length, so `decode_one` must
        #     name the target mnemonic at that exact offset.
        # (2) the scan runs at byte granularity, so it also reports offsets
        #     INSIDE another instruction -- `f3_two` yielded an "09 .. " at
        #     offset 79, three bytes into a real 6-byte falu2_uni at 76, which
        #     decode_one confirms as `falu3`. Splicing there would corrupt two
        #     real instructions and the resulting movement would be about
        #     neither field. So the occurrence must also be a TRUE boundary of a
        #     tokenizer walk from offset 0.
        walk, reach, clean = L.walk_offsets(main_bytes)
        good, rejected = [], []
        for o in occ:
            tok = L.token_at(main_bytes, o["off"])
            o["token"] = tok
            o["walk_boundary"] = (walk.get(o["off"]) == (mnem, o["len"]))
            if tok.get("mnemonic") == mnem and tok.get("length") == o["len"] \
                    and o["walk_boundary"]:
                good.append(o)
            else:
                rejected.append({"off": o["off"], "bytes": o["bytes"],
                                 "token": tok,
                                 "walk_boundary": o["walk_boundary"],
                                 "why": ("not a walk boundary"
                                         if tok.get("mnemonic") == mnem
                                         else "tokenizes as %s"
                                              % tok.get("mnemonic"))})
        census[cname] = {"main_len": len(main_bytes), "main_off": off,
                         "mnemonic": mnem, "n_signature_hits": len(occ),
                         "n_admitted": len(good),
                         "walk_clean": clean, "walk_reach": reach,
                         "rejected_occurrences": rejected,
                         "occurrences": occ[:64]}
        for k, o in enumerate(good):
            base = bytes.fromhex(o["bytes"])
            for fld in fields:
                s, w = L.field_span(mnem, fld)
                vals = VALUES[(mnem, fld)]
                nb, errs = check_arm(base, s, w, vals,
                                     "%s#%d/%s.%s" % (cname, k, mnem, fld))
                if errs:
                    errors.extend(errs)
                    continue                       # HARD STOP: arm not emitted
                arms.append({"group": mnem, "carrier": cname,
                             "arm": "%s#%d/%s.%s" % (cname, k, mnem, fld),
                             "instr": mnem, "field": fld, "occ": k,
                             "off": o["off"], "len": o["len"],
                             "start": s, "width": w, "values": vals,
                             "role": "target", "distinct_bytes_host": nb,
                             "baseline_bytes": o["bytes"],
                             "note": "target field, dense full range"})
            cf, cs, cw, cv = CONTROL[mnem]
            nb, errs = check_arm(base, cs, cw, cv, "%s#%d/ctrl" % (cname, k))
            if errs:
                errors.extend(errs)
            else:
                arms.append({"group": mnem, "carrier": cname,
                             "arm": "%s#%d/_live_control" % (cname, k),
                             "instr": mnem, "field": "_live_control",
                             "control_field": cf, "occ": k,
                             "off": o["off"], "len": o["len"],
                             "start": cs, "width": cw, "values": cv,
                             "role": "control", "distinct_bytes_host": nb,
                             "baseline_bytes": o["bytes"],
                             "note": "detection power at the same occurrence"})
            ff, fs, fw, fv = FALSIFIER[mnem]
            arms.append({"group": mnem, "carrier": cname,
                         "arm": "%s#%d/_falsifier" % (cname, k),
                         "instr": mnem, "field": "_falsifier",
                         "control_field": ff, "occ": k,
                         "off": o["off"], "len": o["len"],
                         "start": fs, "width": fw, "values": fv,
                         "role": "falsifier", "distinct_bytes_host": len(fv),
                         "baseline_bytes": o["bytes"],
                         "note": "pre-registered to FAIL"})

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "census.json").write_text(json.dumps(census, indent=1))
    out = {"arms": arms, "errors": errors,
           "n_arms": len(arms),
           "n_cases": sum(len(a["values"]) for a in arms)}
    (EXP / "harness" / "arms201.json").write_text(json.dumps(out, indent=1))
    print("carriers=%d arms=%d cases=%d aliasing/span errors=%d"
          % (len(TARGETS), len(arms), out["n_cases"], len(errors)))
    for e in errors[:40]:
        print("  HARD STOP", e)
    for c, v in census.items():
        print("  %-10s %-16s hits=%s admitted=%s %s"
              % (c, v.get("mnemonic", "-"), v.get("n_signature_hits"),
                 v.get("n_admitted"), v.get("error", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
