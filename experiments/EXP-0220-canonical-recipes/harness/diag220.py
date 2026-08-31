#!/usr/bin/env python3
"""EXP-0220 PRE-FREEZE DIAGNOSTIC -- runs on the neo, writes only under work/.

Not a gated capture and not evidence for any claim: it exists to isolate, one
variable at a time, WHY a building block of the recipe behaves differently from
the documented rule, before the contract is frozen.  Everything it finds is
re-measured inside the frozen matrix.

    python3 harness/diag220.py <name>
"""
import hashlib
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import synth220 as S      # noqa: E402
import prog220 as P       # noqa: E402
import runner220 as RN     # noqa: E402
import run220 as RUN      # noqa: E402

SLOTS = {"out": 0, "mem": 1, "imem": 2}


def build():
    bindir = RUN.build_bins(EXP / "work" / "bin")
    agxparse = RUN.load_agxparse()
    work = EXP / "work" / "diag"
    work.mkdir(parents=True, exist_ok=True)
    base_archive = work / "base.bin"
    r = RUN.sh([str(bindir / "shdump"), "-o", str(base_archive), "-f", "k",
                "--no-fast-math", str(EXP / "kernels" / "carrier220.metal")])
    assert base_archive.exists(), r.stderr[-1500:]
    base = base_archive.read_bytes()
    off, clen = agxparse.locate_region(base, "_agc.main")
    return bindir, work, base, off, clen - (clen % 2)


def make_probes():
    """(name, builder) pairs.  Each builder returns a Prog; the dump is added
    by the driver."""
    out = []

    def mk(name, fn):
        out.append((name, fn))

    # D1: the two-step ALU operand, with the intermediate KEPT in its own reg
    def d1(pg):
        pg.falu2(3, "fmul", P.LOW_CODEWORD and 13, srcB_class=2, mod_hi=0xC,
                 opflags=0b000, salt="d1a")           # r3 = junk * 0.0
        pg.falu2(4, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=0, mod_hi=0xC, opflags=0b000, salt="d1b")
        pg.falu2(5, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=1, mod_hi=0xC, opflags=0b000, salt="d1c")
    mk("d1_alu_chain_modC", d1)

    def d1b(pg):
        pg.falu2(3, "fmul", 13, srcB_class=2, mod_hi=0x0, opflags=0b000, salt="d2a")
        pg.falu2(4, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=0, mod_hi=0x0, opflags=0b000, salt="d2b")
        pg.falu2(5, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=1, mod_hi=0x0, opflags=0b000, salt="d2c")
    mk("d2_alu_chain_mod0", d1b)

    # D3: the SAME two instructions but with a LOADED srcA, as in arm A10
    def d3(pg):
        pg.load_f(3, 40)
        pg.falu2(4, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=0, mod_hi=0xC, opflags=0b000, salt="d3b")
        pg.falu2(5, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=1, mod_hi=0xC, opflags=0b000, salt="d3c")
    mk("d3_load_src_modC", d3)

    # D4: srcA from a load, consumed TWICE with a gap -- is the second use still
    #     a "live load result"?
    def d4(pg):
        pg.load_f(3, 40)
        pg.load_f(6, 77)
        pg.falu2(4, "fadd", 3, srcB_reg=6, mod_hi=0xC, opflags=0b000, salt="d4a")
        pg.falu2(5, "fadd", 3, srcB_reg=6, mod_hi=0x0, opflags=0b000, salt="d4b")
        pg.falu2(7, "fadd", 3, srcB_reg=6, mod_hi=0x2, opflags=0b000, salt="d4c")
    mk("d4_gap_after_load", d4)

    # D5: mod_hi as a PER-OPERAND control?  one loaded operand, one ALU operand.
    def d5(pg):
        pg.falu2(3, "fmul", 13, srcB_class=2, mod_hi=0x0, opflags=0b000, salt="d5z")
        pg.falu2(3, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=40,
                 srcB_neg=0, mod_hi=0x0, opflags=0b000, salt="d5v")
        pg.load_f(6, 77)
        for i, mh in enumerate((0x0, 0x4, 0x8, 0xC)):
            pg.falu2(4 + i, "fadd", 3, srcB_reg=6, mod_hi=mh, opflags=0b000,
                     salt="d5%d" % i)
    mk("d5_mixed_provenance", d5)

    # D6: does a plain mov_imm-seeded register work as a falu2 operand at all?
    def d6(pg):
        for i, mh in enumerate((0x0, 0x4, 0x8, 0xC)):
            pg.falu2(4 + i, "fadd", 13, srcB_class=S.SRCB_CLASS_NONGPR,
                     inline_k=40, srcB_neg=0, mod_hi=mh, opflags=0b000,
                     salt="d6%d" % i)
    mk("d6_movimm_src", d6)

    # D7: THE 2x2 -- (opflags bit1) x (srcB_neg) for an INLINE IMMEDIATE srcB,
    #     and the same 2x2 for a GPR srcB.  EXP-0167 measured the inline sign
    #     with bit1 ALWAYS SET; D1/D3/D6 measured it with bit1 CLEAR and got the
    #     opposite sign, so the question is whether bit1 is a srcB NEGATE in the
    #     non-GPR operand class while it is a RELEASE in the GPR class.
    def d7(pg):
        pg.load_f(3, 40)                       # 10.25
        i = 4
        for of in (0b000, 0b010):
            for neg in (0, 1):
                pg.falu2(i, "fadd", 3, srcB_class=S.SRCB_CLASS_NONGPR,
                         inline_k=40, srcB_neg=neg, mod_hi=0xC, opflags=of,
                         salt="d7i%d%d" % (of, neg))
                i += 1
        return
    mk("d7_inline_bit1_x_neg", d7)

    def d8(pg):
        pg.load_f(3, 40)                       # 10.25
        pg.load_f(9, 77)                       # 19.5
        i = 4
        for of in (0b000, 0b010):
            for neg in (0, 1):
                pg.falu2(i, "fadd", 3, srcB_reg=9, srcB_neg=neg, mod_hi=0xC,
                         opflags=of, salt="d8g%d%d" % (of, neg))
                i += 1
        return
    mk("d8_gpr_bit1_x_neg", d8)

    # D9: odd mod_hi values once the loads have landed (a gap of one ALU op)
    def d9(pg):
        pg.load_f(3, 40)
        pg.load_f(9, 77)
        pg.falu2(2, "fmul", 13, srcB_class=2, mod_hi=0xC, opflags=0b000, salt="d9g")
        for i, mh in enumerate((0x0, 0x1, 0x3, 0x5, 0x7, 0xD, 0xF)):
            pg.falu2(4 + i, "fadd", 3, srcB_reg=9, mod_hi=mh, opflags=0b000,
                     salt="d9%d" % i)
    mk("d9_modhi_after_gap", d9)

    # D10: does a device_store RELEASE its index register?  r3/r4/r5 are seeded
    #      by mov_imm; only r4 is then used as a store index.
    def d10(pg):
        pg.movi(3, 21)
        pg.movi(4, 22)
        pg.movi(5, 23)
        pg.store(1, 300, index_reg=4, tag="probe")
    mk("d10_store_releases_index", d10)

    # D11: the same, but with an intervening instruction after the store, and a
    #      second store reusing the same index register.
    def d11(pg):
        pg.movi(4, 22)
        pg.store(1, 300, index_reg=4, tag="p1")
        pg.store(1, 301, index_reg=4, tag="p2")
    mk("d11_two_stores_same_index", d11)

    # D12: an index register that is a LIVE device_load result -- does the store
    #      see the loaded value or the STALE one?  r6 is pre-seeded to 22 by
    #      mov_imm and then loaded with imem[33] = 33 immediately before use;
    #      the second store has one ALU instruction of separation.
    def d12(pg):
        pg.movi(6, 22)
        pg.movi(7, 22)
        pg.load_i(6, 33)
        pg.store(1, 300, index_reg=6, tag="live")
        pg.load_i(7, 34)
        pg.falu2(2, "fmul", 13, srcB_class=2, mod_hi=0xC, opflags=0b000, salt="d12g")
        pg.store(1, 400, index_reg=7, tag="gapped")
    mk("d12_live_index_register", d12)
    return out


def main():
    bindir, work, base, abs_off, clen = build()
    poison = work / "poison.bin"
    memf = work / "mem.bin"
    imemf = work / "imem.bin"
    poison.write_bytes(P.poison_bytes())
    memf.write_bytes(P.mem_bytes())
    imemf.write_bytes(P.imem_bytes())
    IN = [(0, str(poison)), (1, str(memf)), (2, str(imemf))]
    OUTS = [(0, P.OUT_BYTES), (1, P.MEM_BYTES), (2, P.IMEM_BYTES)]
    runner = RN.ComputeRunner(str(bindir / "agxrun_persist"),
                             str(EXP / "kernels" / "carrier220.metal"), "k")
    print("device", runner.device, "carrier_len", clen)
    for n, (name, fn) in enumerate(make_probes()):
        pg = P.Prog(SLOTS, name)
        pg.prologue()
        fn(pg)
        predicted = {R: pg.rbits(R) for R in P.DUMP_REGS}
        pg.dump()
        prog = pg.finish(clen)
        sp = bytearray(base)
        sp[abs_off:abs_off + clen] = prog
        arch = work / ("d_%02d.bin" % n)
        arch.write_bytes(bytes(sp))
        res = runner.run(str(arch), IN, OUTS, timeout=20.0)
        print("== %-24s %s" % (name, res.get("status")))
        ob = res.get("surf", {}).get(0)
        if ob is None:
            print("   no output:", res.get("error"))
            continue
        for R in P.DUMP_REGS[:12]:
            o = pg.dump_byte(R)
            got = struct.unpack("<I", ob[o:o + 4])[0]
            pr = predicted[R]
            gf = struct.unpack("<f", struct.pack("<I", got))[0]
            pf = None if pr is None else struct.unpack("<f", struct.pack("<I", pr))[0]
            flag = "" if pr == got else "   <<<"
            print("   r%-2d got=%#010x (%-14s)  pred=%s%s"
                  % (R, got, "%g" % gf, ("%#010x (%g)" % (pr, pf)) if pr is not None
                     else "none", flag))
    runner.close()


if __name__ == "__main__":
    main()
