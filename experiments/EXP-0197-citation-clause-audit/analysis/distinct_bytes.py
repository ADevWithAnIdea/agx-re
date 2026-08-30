#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 -- a byte-span sweep is only a per-VALUE record if the hardware actually
saw distinct encodings.  A harness can dispatch 256 `value`s and emit far fewer
distinct `bytes` (the value is the harness's intent; `bytes` is what ran).

For every CLAUSE-FALSE row whose evidence is a modern sweep.jsonl, this counts, per
(experiment, run, arm/carrier):
  * records
  * distinct `value`
  * distinct `bytes`                       <- the falsifier
  * distinct values OF THE FIELD'S OWN BITS extracted from `bytes`   <- the real one
  * outcome histogram
Read-only.  Writes work/distinct_bytes.json.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
EXPS = os.path.join(ROOT, "experiments")

# (row, exp, mnemonic, field, byte_index or None -> use named field)
TARGETS = [
    ("fspecial_est.subop", "EXP-0171-g17p-ilogic-srca", "fspecial_est", None, 3, 24, 8),
    ("iadd2.srcA", "EXP-0171-g17p-ilogic-srca", "iadd2", None, 7, 56, 8),
    ("ibfe.srcA", "EXP-0171-g17p-ilogic-srca", "ibfe", None, 8, 64, 8),
    ("ilogic.lut_a_z", "EXP-0171-g17p-ilogic-srca", "ilogic", None, 4, 37, 3),
    ("ilogic.outmod", "EXP-0171-g17p-ilogic-srca", "ilogic", None, 7, 56, 8),
    ("mov_zext16.src_reg", "EXP-0161-g17p-carry-fspecial", "mov_zext16", "src_reg", None, 4, 4),
    ("mov_zext16.src_reg(byte0)", "EXP-0161-g17p-carry-fspecial", "mov_zext16", None, 0, 4, 4),
    ("half_alu.dst(DSTNIB)", "EXP-0180-g17p-halfalu-rerecord", "half_alu_ext8", "__dst_nibble", None, 4, 4),
    ("half_alu.dst(named)", "EXP-0180-g17p-halfalu-rerecord", "half_alu_fma12", "dst", None, 4, 4),
]


def main():
    out = {}
    for row, expdir, mnem, fname, bidx, fstart, fwidth in TARGETS:
        per = {}
        for p in sorted(glob.glob(os.path.join(EXPS, expdir, "raw", "*", "sweep.jsonl"))):
            run = os.path.basename(os.path.dirname(p))
            cells = collections.defaultdict(lambda: {
                "n": 0, "values": set(), "bytes": set(), "fieldbits": set(),
                "outcomes": collections.Counter(), "first_line": None})
            for ln, line in enumerate(open(p, errors="replace"), 1):
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("instr") != mnem:
                    continue
                f = r.get("field")
                if fname is not None:
                    if f != fname:
                        continue
                else:
                    if not (f is None or (isinstance(f, str) and f.startswith("_"))):
                        continue
                    if r.get("byte_index") != bidx:
                        continue
                arm = "%s|%s" % (r.get("carrier"), r.get("arm"))
                c = cells[arm]
                c["n"] += 1
                c["values"].add(json.dumps(r.get("value")))
                b = r.get("bytes")
                if isinstance(b, str):
                    c["bytes"].add(b)
                    try:
                        v = int.from_bytes(bytes.fromhex(b), "little")
                        c["fieldbits"].add((v >> fstart) & ((1 << fwidth) - 1))
                    except ValueError:
                        pass
                oc = r.get("outcome")
                if oc is None:
                    at = r.get("attempts") or []
                    oc = at[0].get("outcome") if at else None
                c["outcomes"][str(oc)] += 1
                if c["first_line"] is None:
                    c["first_line"] = ln
            if cells:
                per[run] = {k: {"records": v["n"], "distinct_value": len(v["values"]),
                                "distinct_bytes": len(v["bytes"]),
                                "distinct_field_bit_values": len(v["fieldbits"]),
                                "outcomes": dict(v["outcomes"]),
                                "first_line": v["first_line"],
                                "file": os.path.relpath(p, ROOT)}
                            for k, v in sorted(cells.items())}
        out[row] = per
        print("== %s  (%s)" % (row, expdir))
        for run, arms in per.items():
            for arm, s in arms.items():
                print("   %-22s %-34s n=%-5d val=%-4d BYTES=%-4d fieldbits=%-4d line=%-6d %s"
                      % (run, arm, s["records"], s["distinct_value"],
                         s["distinct_bytes"], s["distinct_field_bit_values"],
                         s["first_line"], s["outcomes"]))
    json.dump(out, open(os.path.join(EXP, "work", "distinct_bytes.json"), "w"),
              indent=1, default=str)


if __name__ == "__main__":
    main()
