#!/usr/bin/env python3
"""EXP-0165 FUNCTIONAL CHECK: does the repaired descriptor EMIT the encodings the
HARDWARE accepted, and REFUSE to mis-place operands the way the old one did?

For every generated encoding EXP-0161 executed successfully on G17P
(raw/g17p_20260830_gen03), assemble the same instruction from the documented
field model through isadb.assemble() and require byte identity; then decode the
hardware-accepted bytes back and require the field values name the right
registers.  Run against any tools/agx-isa-shaped tree:

  python3 analysis/functional_check.py <tree> [...]
"""
from __future__ import print_function
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
GEN = os.path.join(REPO, "experiments", "EXP-0161-g17p-carry-fspecial",
                   "raw", "g17p_20260830_gen03", "sweep.jsonl")


def load(d):
    spec = importlib.util.spec_from_file_location("isadb_%d" % abs(hash(d)),
                                                  os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
    spec.loader.exec_module(m); return m


def cases():
    """(kind, hw_bytes, description, harness verdict) for the generated cases."""
    out = []
    for l in open(GEN):
        r = json.loads(l)
        g = r.get("gen")
        if not g or r.get("desc") == "__baseline":
            continue
        blk = bytes.fromhex(r["block"])
        if g == "fspecial":
            b = blk[0:10]; p = r["params"]
            out.append(("fspecial", b, r["desc"], r.get("verdict"),
                        {"dst_reg": p["src_field"] >> 1,
                         "src_reg": p["src_ext_field"] >> 2}))
        elif g == "mov_zext16":
            b = blk[0:4]; p = r["params"]
            out.append(("mov_zext16", b, r["desc"], r.get("verdict"),
                        {"reg": p["n"]}))
        elif g == "carry_gen":
            b = blk[10:16]; p = r["params"]
            out.append(("carry_gen", b, r["desc"], r.get("verdict"),
                        {"a": p["a"], "b": p["b"], "is32": p["is32"]}))
    return out


def check(m, tree):
    res = {"tree": tree, "emit_ok": 0, "emit_bad": [], "decode_ok": 0,
           "decode_bad": [], "skipped_failing_hw_cases": 0}
    for kind, hw, desc, verdict, meta in cases():
        if verdict != "pass":
            res["skipped_failing_hw_cases"] += 1
            continue
        # --- decode the HW-accepted bytes and read the operands back --------
        try:
            rec, ln = m.decode_one(hw, 0)
        except Exception as e:
            res["decode_bad"].append({"desc": desc, "err": str(e)[:70]}); continue
        f = rec["fields"]
        got = None
        if kind == "fspecial":
            got = {"dst_reg": f.get("dst", -2) >> 1, "src_reg": f.get("src", -4) >> 2}
        elif kind == "mov_zext16":
            got = {"reg": f.get("src_reg", -1)}
        elif kind == "carry_gen":
            got = {"a": (f.get("srcA", 0) >> 1) & 0x3F,
                   "b": (f.get("srcB", 0) >> 1) & 0x3F,
                   "is32": f.get("srcA", 0) & 1}
        if rec["mnemonic"] == kind and got == meta:
            res["decode_ok"] += 1
        else:
            res["decode_bad"].append({"desc": desc, "hex": hw.hex(),
                                      "mnemonic": rec["mnemonic"],
                                      "want": meta, "got": got})
        # --- re-emit from the documented model and require byte identity ----
        try:
            back = m.assemble(rec["mnemonic"], f)
        except Exception as e:
            res["emit_bad"].append({"desc": desc, "err": str(e)[:70]}); continue
        if back == hw:
            res["emit_ok"] += 1
        else:
            res["emit_bad"].append({"desc": desc, "want": hw.hex(),
                                    "got": back.hex()})
    return res


def main():
    for tree in sys.argv[1:]:
        r = check(load(tree), tree)
        print("%-46s decode %d ok / %d bad   re-emit %d ok / %d bad   (skipped %d "
              "HW-failing cases)" % (os.path.basename(tree.rstrip('/')),
              r["decode_ok"], len(r["decode_bad"]), r["emit_ok"],
              len(r["emit_bad"]), r["skipped_failing_hw_cases"]))
        for b in r["decode_bad"][:6]:
            print("    DECODE", b)
        for b in r["emit_bad"][:6]:
            print("    EMIT  ", b)


main()
