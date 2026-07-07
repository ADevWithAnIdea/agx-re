#!/usr/bin/env python3
# roundtrip_test.py -- proves the table-driven codec is lossless in both
# directions for the seeded instruction set:
#
#   (A)  asm(disasm(bytes)) == bytes     for every real instruction we extracted
#        from our own compiled shaders (fadd/fmul + the structural set).
#   (B)  disasm(asm(fields)) == fields    for synthesized field combinations.
#
# Plus (C): the length rule tokenizes whole real _agc.main programs from our own
# shaders with ZERO leftover / misaligned bytes.
#
# CLEAN-ROOM: every byte here is from the compiled form of MSL we wrote.

import sys
import isadb

# Real instructions carved out of our own compiled shaders (EXP-0001/EXP-0005).
# (mnemonic-agnostic: we decode, re-encode, and require byte-identity.)
REAL_INSTRS = {
    "fadd  (09 05 1c 01 00 c0)": "09051c0100c0",   # d = a + b     HW-VALIDATED
    "fmul  (09 05 1d 01 00 c0)": "09051d0100c0",   # d = a * b     HW-VALIDATED
    "fadd-nofast (09 01 1c 05 00 c0)": "09011c0500c0",  # d=a+b (no-fast reg alloc) EXP-0006
    "fsub  (09 01 1c 05 00 c8)": "09011c0500c8",   # d = a + (-b)  srcB negate HW-VALIDATED
    "fadd-dst3 (39 05 04 01 00 c0)": "3905040100c0",  # dst=reg3 (b0[4:8]) HW-VALIDATED EXP-0006
    "fadd-map5 (59 09 1c 0b 00 c0)": "59091c0b00c0",  # dst=reg5,srcA=reg4,srcB=reg5 EXP-0006
    "faddi 1.0 (09 b1 14 01 80 c0)": "09b1140180c0",   # d = a + 1.0   imm HW-VALIDATED
    "faddi 2.0 (09 c1 14 01 80 c0)": "09c1140180c0",   # d = a + 2.0   imm HW-VALIDATED
    "fsubi 1.0 (09 b1 1c 01 80 c0)": "09b11c0180c0",   # d = a + (-1.0) imm sign HW-VALIDATED
    "fma   (09 01 1e 05 81 08 02 c0)": "09011e05810802c0",
    "fmax  (12 03 1e 05 00 c0)": "12031e0500c0",
    "fmin  (12 03 1e 05 01 c0)": "12031e0501c0",
    "fneg  (0b 01 0e 09 02 0a 00 80 00 00)": "0b010e09020a00800000",
    "fabs  (0b 01 0e 09 02 02 00 80 00 00)": "0b010e09020200800000",
    "load  (67 10 54 00 ...)": "6710540000012000510100404600",
    "store (e7 00 54 00 ...)": "e700540002012100110000901100",
    "preamble (1c a0 10 06)": "1ca01006",
    "preamble (0c a0 10 06)": "0ca01006",
    "stop  (0e 00 00 00)": "0e000000",
    # ---- INTEGER ALU (EXP-0007), carved from our own compiled int shaders ----
    "iadd  (9f 01 56 00 02 08 00 a8 17 05)": "9f015600020800a81705",  # a+b (10B) HW
    "isub  (1f 01 56 00 02 00 10 a8 17 05)": "1f015600020010a81705",  # a-b (srcA-neg) HW
    "imul  (9f 00 56 ... 12B)":            "9f00560002080000d0260a00",# a*b (12B mad,c=0) HW
    "imad  (9f 00 56 ... 12B)":            "9f00560002080040d02f2a00",# a*b+c (12B) HW
    "iaddi5 (9f 01 56 00 02 0a 00 88 15 04)":"9f015600020a00881504", # a+5 imm=(5<<1) HW
    "iaddi255 (... fe 01 ...)":            "9f01560002fe01881504",    # a+255 imm HW
    "imin  (02 01 1e 05 07 c0)":           "02011e0507c0",           # signed min HW
    "imax  (02 01 1e 05 06 c0)":           "02011e0506c0",           # signed max HW
    "umin  (02 01 1e 05 05 c0)":           "02011e0505c0",           # unsigned min HW
    "umax  (02 01 1e 05 04 c0)":           "02011e0504c0",           # unsigned max HW
    "iand  (0b 05 1f 01 00 00 00 80 00 00)":"0b051f01000000800000",  # a&b (0x0b logic)
    "ixor  (0b 05 1e 01 02 08 00 80 00 00)":"0b051e01020800800000",  # a^b
    "popcnt(27 05 56 00 02 00 5c 04)":      "2705560002005c04",       # popcount (8B)
    "ishr  (a7 01 56 00 02 00 08 78 62 00)":"a7015600020008786200",  # a>>2 (10B)
    "ibfe  (a7 00 56 ... 12B)":            "a700560002001000f0118100",# extract_bits (12B)
    "icmp  (12 03 1d 05 ... 14B)":         "12031d05228107c0208013000001",# (a<b)?1:0 (14B)
}

# Whole real _agc.main programs (from our own kernels) for the tokenization test.
REAL_PROGRAMS = {
    "empty":   "0e000000",
    "fadd":    "1ca010066710540000012000510100404600670044040101200051010040460009051c0100c0e7005400020121001100009011000e000000",
    "fmul":    "1ca010066710540000012000510100404600670044040101200051010040460009051d0100c0e7005400020121001100009011000e000000",
    "fsub_ab": "1ca010066710540000012000510100404600670044040100200051010040460009011c0500c8e7005400020121001100009011000e000000",
    "fadd_imm":"1ca01006671044000001200051010040460009b1140180c0e7005400010121001100009011000e000000",
    "fma":     "1ca0100667105400000120005101004046006700540401012000510100404600670044080201200051010040460009011e05810802c0e7005400030121001100009011000e000000",
    "copy":    "1ca010066710440000012000510100404600e7005600010121001100009011000e000000",
    "neg":     "1ca0100667104400000120005101004046000b010e09020a00800000e7005400010121001100009011000e000000",
    "absf":    "1ca0100667104400000120005101004046000b010e09020200800000e7005400010121001100009011000e000000",
    "maxf":    "0ca010066710540200002000510100404600670044040100200051010040460012031e0500c0e7005402020021001100009011000e000000",
    "minf":    "0ca010066710540200002000510100404600670044040100200051010040460012031e0501c0e7005402020021001100009011000e000000",
    # ---- INTEGER _agc.main programs (EXP-0007), our own compiled int kernels ----
    "iadd":    "1ca01006671054000001200051010040460067004404010120005101004046009f015600020800a81705e7005400020121001100009011000e000000",
    "isub":    "1ca01006671054000001200051010040460067004404010120005101004046001f015600020010a81705e7005400020121001100009011000e000000",
    "imul":    "1ca01006671054000001200051010040460067004404010120005101004046009f00560002080000d0260a00e7005400020121001100009011000e000000",
    "imad":    "1ca010066710540000012000510100404600670054040101200051010040460067004408020120005101004046009f00560002080040d02f2a00e7005400030121001100009011000e000000",
    "iaddimm": "1ca0100667104400000120005101004046009f015600020a00881504e7005400010121001100009011000e000000",
    "imin":    "1ca010066710540000012000510100404600670044040101200051010040460002011e0507c0e7005400020121001100009011000e000000",
    "umax":    "1ca010066710540000012000510100404600670044040101200051010040460002011e0504c0e7005400020121001100009011000e000000",
    "iand":    "1ca01006671054000001200051010040460067004404010120005101004046000b051f01000000800000e7005400020121001100009011000e000000",
    "ixor":    "1ca01006671054000001200051010040460067004404010120005101004046000b051e01020800800000e7005400020121001100009011000e000000",
    "popcnt":  "1ca0100667104400000120005101004046002705560002005c04e7005400010121001100009011000e000000",
    "ishr":    "1ca010066710440000012000510100404600a7015600020008786200e7005400010121001100009011000e000000",
    "ibfe":    "1ca010066710440000012000510100404600a700560002001000f0118100e7005400010121001100009011000e000000",
    "icmp_lt": "0ca010066710540200002000510100404600670044040100200051010040460012031d05228107c0208013000001e7005402020021001100009011000e000000",
    "idstc":   "1ca01006671054040001200051010040460067004400010120005101004046009f015606020010a81105e700540602012000110000901100e700540403012000110000901100e7005400040121001100009011000e000000",
}

# Synthesized field combos for the asm->disasm->fields direction.
SYNTH = [
    # falu2 (reg-reg), EXP-0006 HW-validated field layout. fadd d=srcA+srcB:
    #   dst reg0, srcA=reg0/32b, srcB=reg2/32b -> 09051c0100c0 (== fast-math fadd)
    ("falu2",  {"dst": 0, "srcA_size": 1, "srcA_reg": 2, "opsel": 0b100,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 0, "ctrl": 0,
                "srcB_imm": 0, "mod_lo": 0, "srcB_neg": 0, "mod_hi": 0xc}),
    # fmul, same operands:
    ("falu2",  {"dst": 0, "srcA_size": 1, "srcA_reg": 2, "opsel": 0b101,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 0, "ctrl": 0,
                "srcB_imm": 0, "mod_lo": 0, "srcB_neg": 0, "mod_hi": 0xc}),
    # fsub d = srcA + (-srcB): srcB_neg=1 (HW-validated a+b -> a-b):
    ("falu2",  {"dst": 0, "srcA_size": 1, "srcA_reg": 0, "opsel": 0b100,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 2, "ctrl": 0,
                "srcB_imm": 0, "mod_lo": 0, "srcB_neg": 1, "mod_hi": 0xc}),  # -> 09011c0500c8
    # dst = reg5 exercises the b0[4:8] dst field (HW-validated):
    ("falu2",  {"dst": 5, "srcA_size": 1, "srcA_reg": 4, "opsel": 0b100,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 5, "ctrl": 0,
                "srcB_imm": 0, "mod_lo": 0, "srcB_neg": 0, "mod_hi": 0xc}),  # -> 59091c0b00c0
    # falu2i packed immediate: a + 1.0 (exp=0xb bias11, mant=0, sign=0) HW-validated:
    ("falu2i", {"dst": 0, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xb, "opsel": 0b100,
                "imm_sign": 0, "opflags": 1, "srcA_size": 1, "srcA_reg": 0,
                "ctrl_lo": 0, "mods": 0xc0}),                                # -> 09b1140180c0
    # a + (-2.0): exp=0xc, sign=1:
    ("falu2i", {"dst": 0, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xc, "opsel": 0b100,
                "imm_sign": 1, "opflags": 1, "srcA_size": 1, "srcA_reg": 0,
                "ctrl_lo": 0, "mods": 0xc0}),                                # -> 09c11c0180c0
    ("falu3",   {"dst": 0x01, "op": 0x1e, "srcA": 0x05, "srcB": 0x81, "srcC": 0x08, "ext": 0xc002}),
    ("fminmax", {"dst": 0x03, "op": 0x1e, "srcA": 0x05, "sel": 0x01, "mods": 0xc0}),
    # ---- integer (EXP-0007) ----
    # iadd a+b: dst=reg0, srcA_neg=0 (add), lenbit=1 (10B), arith_en=1. Reproduces
    # the compiler's iadd bytes 9f 01 56 00 02 08 00 a8 17 05.
    ("iadd2",   {"srcA_neg": 1, "lenbit": 1, "b1hi": 0, "b2lo": 0, "arith_en": 1,
                 "b2hi": 0x15, "dst": 0x00, "opmode": 0x02, "srcB_imm": 0x08,
                 "b6": 0x00, "tail": 0x0517a8}),
    # iminmax: signed min (sel=0x7), srcA=reg descriptor 0x05, srcB=0xc0.
    ("iminmax", {"b1": 0x01, "op": 0x1e, "srcA": 0x05, "sel": 0x7, "selhi": 0, "srcB": 0xc0}),
    # iminmax: unsigned max (sel=0x4).
    ("iminmax", {"b1": 0x01, "op": 0x1e, "srcA": 0x05, "sel": 0x4, "selhi": 0, "srcB": 0xc0}),
]


def test_real_roundtrip():
    fails = 0
    print("== (A) asm(disasm(bytes)) == bytes  [real own-shader instructions] ==")
    for label, h in REAL_INSTRS.items():
        raw = bytes.fromhex(h)
        rec, length = isadb.decode_one(raw, 0)
        reasm = isadb.assemble(rec["mnemonic"], rec["fields"])
        ok = reasm == raw
        fails += not ok
        print(f"  [{'OK' if ok else 'FAIL'}] {label:38s} {h}  ->  {reasm.hex()}")
    return fails


def test_synth_roundtrip():
    fails = 0
    print("\n== (B) disasm(asm(fields)) == fields  [synthesized] ==")
    for mnem, fields in SYNTH:
        raw = isadb.assemble(mnem, fields)
        rec, length = isadb.decode_one(raw, 0)
        ok = (rec["mnemonic"] == mnem and rec["fields"] == fields)
        fails += not ok
        opn = rec.get("op_mnemonic") or "?"
        print(f"  [{'OK' if ok else 'FAIL'}] {mnem}({fields}) -> {raw.hex()} "
              f"-> {rec['mnemonic']}[{opn}] {rec['fields']}")
    return fails


def test_tokenize_programs():
    fails = 0
    print("\n== (C) tokenize whole real _agc.main programs (0 leftover) ==")
    for name, h in REAL_PROGRAMS.items():
        buf = bytes.fromhex(h)
        recs, leftover = isadb.disassemble(buf)
        clean = (leftover == b"" and all("error" not in r for r in recs))
        # also verify concatenating instruction hex reproduces the program
        rebuilt = b"".join(bytes.fromhex(r["hex"]) for r in recs if "hex" in r and "error" not in r)
        exact = rebuilt == buf
        ok = clean and exact
        fails += not ok
        seq = " ".join((r["op_mnemonic"] or r["mnemonic"]) for r in recs if "error" not in r)
        print(f"  [{'OK' if ok else 'FAIL'}] {name:9s} {len(recs)} instrs: {seq}")
        if not ok:
            print(f"        leftover={leftover.hex()} exact={exact}")
    return fails


def test_imm_codec():
    """Packed-float immediate codec matches the HW-validated K<->bytes table
    (EXP-0006 raw/validate_imm_dst.log)."""
    print("\n== (D) packed float immediate codec (K -> b1/sign -> K) ==")
    # (K, expected b1 byte, expected sign)  -- all HW-validated on the A18 Pro.
    TABLE = [(0.0,0x81,0),(0.0625,0x85,0),(0.125,0x89,0),(0.25,0x91,0),(0.5,0xa1,0),
             (0.75,0xa9,0),(1.0,0xb1,0),(1.5,0xb9,0),(2.0,0xc1,0),(3.0,0xc9,0),
             (3.5,0xcd,0),(4.0,0xd1,0),(8.0,0xe1,0),(16.0,0xf1,0),(30.0,0xff,0),
             (-1.0,0xb1,1),(-0.5,0xa1,1),(-2.0,0xc1,1)]
    fails = 0
    for K, eb1, esign in TABLE:
        b1, sign = isadb.imm_encode(K)
        back = isadb.imm_decode(b1, sign)
        ok = (b1 == eb1 and sign == esign and abs(back - K) < 1e-6)
        fails += not ok
        print(f"  [{'OK' if ok else 'FAIL'}] K={K:>8}  b1={b1:#04x} sign={sign}  decode={back:+g}")
    return fails


def main():
    f = 0
    f += test_real_roundtrip()
    f += test_synth_roundtrip()
    f += test_tokenize_programs()
    f += test_imm_codec()
    print(f"\n{'ALL PASS' if f == 0 else str(f) + ' FAILURES'}")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
