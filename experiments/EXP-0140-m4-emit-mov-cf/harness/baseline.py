#!/usr/bin/env python3
"""EXP-0140 baseline: re-derive every carrier fact fresh (compile + static
disassemble only -- no GPU dispatch) instead of trusting a constant.  Run
before every capture; run.py calls it and hard-fails on any drift.

The trap this defends against is EXP-0112's own documented one: base_slot
assignment is decided by the compiler from the WHOLE kernel body, so it must
be read off the actual carrier's own compile, never a stand-in probe.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb      # noqa: E402
import agxparse   # noqa: E402
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402

CARRIERS = {"uni": "carrier_uni.metal", "dsel5": "dsel5.metal",
            "gsel4": "gsel4.metal", "cf": "carrier_cf.metal"}


def compile_carrier(bin_dir, kernel_path, out_path):
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(out_path),
                     "--no-fast-math", str(kernel_path), "-f", "k"],
                    check=True, capture_output=True)
    buf = Path(out_path).read_bytes()
    roff, rlen = agxparse.locate_region(buf, "_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    return buf, roff, pieces["_agc.main"]


def tokenize(main):
    out, off = [], 0
    while off < len(main):
        try:
            rec, L = isadb.decode_one(main, off)
        except ValueError as e:
            out.append({"off": off, "mnemonic": "<undecodable>", "error": str(e)})
            break
        out.append({"off": off, "mnemonic": rec["mnemonic"], "hex": rec["hex"],
                    "base_slot": rec["fields"].get("base_slot")})
        off += L
    return out


def derive(bin_dir, work_dir):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    facts = {}
    for name, fn in CARRIERS.items():
        kp = EXP / "kernels" / fn
        buf, roff, main = compile_carrier(bin_dir, kp, work_dir / (name + ".bin"))
        toks = tokenize(main)
        facts[name] = {
            "kernel": fn,
            "kernel_sha256": hashlib.sha256(kp.read_bytes()).hexdigest(),
            "main_len": len(main),
            "main_sha256": hashlib.sha256(main).hexdigest(),
            "region_off": roff,
            "load_slots": [t.get("base_slot") for t in toks if t["mnemonic"] == "device_load"],
            "store_slots": [t.get("base_slot") for t in toks if t["mnemonic"] == "device_store"],
            "tokens": toks,
        }
    # frozen expectations
    for name, expect in C.CARRIER_MAINLEN_EXPECT.items():
        got = facts[name]["main_len"]
        assert got == expect, "carrier %s _agc.main length drifted: %d != %d" % (name, got, expect)
    assert facts["uni"]["load_slots"] == [C.UNI_SLOT_MEM], facts["uni"]["load_slots"]
    assert facts["uni"]["store_slots"] == [C.UNI_SLOT_OUT], facts["uni"]["store_slots"]
    import isa_helpers as H
    assert facts["cf"]["load_slots"] == [H.CF_SLOT_A, H.CF_SLOT_N], facts["cf"]["load_slots"]
    assert facts["cf"]["store_slots"] == [H.CF_SLOT_OUT], facts["cf"]["store_slots"]
    # the two select instructions must sit at their frozen offsets
    d5 = [t for t in facts["dsel5"]["tokens"] if t["off"] == C.SEL_INSTR_OFF]
    assert d5 and d5[0]["mnemonic"] == "sel" and d5[0]["hex"][:2] == "16", d5
    assert bytes.fromhex(d5[0]["hex"])[1:] == bytes(C.SEL_BASE_BODY), d5
    g4 = [t for t in facts["gsel4"]["tokens"] if t["off"] == C.PSEL_INSTR_OFF]
    assert g4 and g4[0]["mnemonic"] == "psel" and g4[0]["hex"][:2] == "05", g4
    assert bytes.fromhex(g4[0]["hex"])[1:] == bytes(C.PSEL_BASE_BODY), g4
    return facts


if __name__ == "__main__":
    f = derive(sys.argv[1] if len(sys.argv) > 1 else str(EXP / "work" / "bin"),
               sys.argv[2] if len(sys.argv) > 2 else str(EXP / "work" / "baseline_bin"))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "tokens"}
                      for k, v in f.items()}, indent=1))
