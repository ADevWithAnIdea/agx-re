#!/usr/bin/env python3
"""EXP-0162 locate-only pilot: compile OUR OWN carriers on the target and print
the tokenization of each `_agc.main`, so the frozen contract can name the exact
byte offset and anchor bytes of every instruction under test.

NO GPU DISPATCH happens here -- this is a compile + static-tokenize step.
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NEOTOOLS = Path(os.environ.get("AGXRE_TOOLS", str(Path.home() / "agxre" / "tools")))
sys.path.insert(0, str(NEOTOOLS / "agx-isa"))
sys.path.insert(0, str(NEOTOOLS / "shdump"))
import isadb      # noqa: E402
import agxparse   # noqa: E402

BIN = EXP / "work" / "bin"

COMPUTE = [("kernels/carriers.metal", f) for f in
           ["c_pack", "c_unpack", "c_i2f", "c_i2f_src", "c_f2i",
            "c_f2h", "c_f2h_dst", "c_f2bf", "c_ph2"]]
RENDER = [("kernels/render_probe.metal", "v_rog", "f_rog"),
          ("kernels/render_probe.metal", "v_kill", "f_kill"),
          ("kernels/render_probe.metal", "v_vary", "f_vary")]


def tokens(main):
    out, off = [], 0
    while off < len(main):
        L = isadb.instr_length(main, off)
        if not L:
            out.append((off, "<no-length>", main[off:off + 8].hex()))
            break
        recs, _ = isadb.disassemble(main[off:off + L])
        m = recs[0]["mnemonic"] if recs else "<undecoded>"
        out.append((off, m, main[off:off + L].hex()))
        off += L
    return out


def main():
    rep = {}
    (EXP / "work" / "pilot").mkdir(parents=True, exist_ok=True)
    for src, fn in COMPUTE:
        outp = EXP / "work" / "pilot" / ("c_%s.bin" % fn)
        r = subprocess.run([str(BIN / "shdump"), "-o", str(outp), "-f", fn,
                            "--no-fast-math", str(EXP / src)],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            rep[fn] = {"status": "COMPILE_FAIL", "err": r.stderr[-400:]}
            continue
        arch = outp.read_bytes()
        _, pieces = agxparse.extract_agx(arch)
        m = pieces["_agc.main"]
        rep[fn] = {"status": "OK", "main_len": len(m), "main": m.hex(),
                   "tokens": tokens(m)}
    for src, vs, fs in RENDER:
        outp = EXP / "work" / "pilot" / ("r_%s.bin" % fs)
        r = subprocess.run([str(BIN / "shdump2"), "-o", str(outp), "--render",
                            "--vertex", vs, "--fragment", fs,
                            "--color-format", "125", "--nrt", "1", "--samples", "1",
                            "--no-fast-math", str(EXP / src)],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            rep[fs] = {"status": "COMPILE_FAIL", "err": r.stderr[-600:]}
            continue
        arch = outp.read_bytes()
        for stage in ("vertex", "fragment"):
            loc = agxparse.locate_region(arch, "_agc.main", stage=stage)
            key = "%s.%s" % (fs, stage)
            _, pieces = agxparse.extract_agx(arch, stage=stage)
            m = pieces.get("_agc.main")
            if m is None:
                rep[key] = {"status": "NO_MAIN"}
                continue
            rep[key] = {"status": "OK", "main_len": len(m), "main": m.hex(),
                        "loc": loc, "tokens": tokens(m)}
    print(json.dumps(rep, indent=1))


main()
