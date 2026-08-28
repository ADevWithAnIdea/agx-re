#!/usr/bin/env python3
"""PILOT (non-recorded): compile kernels/anchors.metal for each entry point,
extract _agc.main, tokenize with tools/agx-isa, and print the instruction
stream so the nine target instructions' anchor encodings can be read off."""
import subprocess, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP  = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb, agxparse

FUNCS = ["k_pack_unorm","k_pack_snorm","k_pack_unorm4","k_unpack_unorm","k_unpack_snorm",
         "k_i2f","k_u2f","k_i2f_src","k_f2i","k_f2u","k_f2h","k_f2h_multi",
         "k_f2bf","k_bf2h","k_h2bf","k_packh2",
         "k_ph2_add","k_ph2_mul","k_ph2_max","k_ph2_chain","k_ph4"]
SRC = EXP / "kernels" / "anchors.metal"
BIN = EXP / "work" / "bin" / "shdump"
out = {}
for f in FUNCS:
    dest = HERE / ("%s.bin" % f)
    r = subprocess.run([str(BIN), "-o", str(dest), "-f", f, "--no-fast-math", str(SRC)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("== %-16s COMPILE FAIL: %s" % (f, r.stderr.strip()[:200])); continue
    buf = dest.read_bytes()
    loc = agxparse.locate_region(buf, "_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    main = pieces["_agc.main"]
    recs, leftover = isadb.disassemble(main)
    print("== %-16s archive=%dB main=%dB region_off=0x%x len=%d" % (f, len(buf), len(main), loc[0], loc[1]))
    off = 0
    for rec in recs:
        L = rec.get("length") or isadb.instr_length(main, off) or 0
        if not L:
            print("    +0x%02x %-18s LENGTH-UNKNOWN rest=%s %s" % (off, rec.get("mnemonic"), main[off:].hex(), rec)); break
        print("    +0x%02x %-18s %s  %s" % (off, rec["mnemonic"], main[off:off+L].hex(),
              {k: v for k, v in rec["fields"].items()}))
        off += L
    if leftover:
        print("    LEFTOVER %s" % leftover.hex())
    out[f] = {"main": main.hex(), "region_off": loc[0], "region_len": loc[1]}
(HERE / "anchors.json").write_text(json.dumps(out, indent=1))
