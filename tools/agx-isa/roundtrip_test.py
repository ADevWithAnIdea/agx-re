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
    "fsub  (09 01 1c 05 00 c8)": "09011c0500c8",   # d = a + (-b)
    "faddi (09 b1 14 01 80 c0)": "09b1140180c0",   # d = a + imm
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
}

# Synthesized field combos for the asm->disasm->fields direction.
SYNTH = [
    # falu2 op-select decomposed: opsel 0b100=fadd / 0b101=fmul (HW-validated)
    ("falu2",   {"dst": 0x05, "opsel": 0b100, "opmod": 3, "srcmode": 0,
                 "srcA": 0x01, "srcB": 0x00, "mods": 0xc0}),   # -> 09051c0100c0 fadd
    ("falu2",   {"dst": 0x05, "opsel": 0b101, "opmod": 3, "srcmode": 0,
                 "srcA": 0x01, "srcB": 0x00, "mods": 0xc0}),   # -> 09051d0100c0 fmul
    ("falu2",   {"dst": 0x42, "opsel": 0b100, "opmod": 0, "srcmode": 0,
                 "srcA": 0x11, "srcB": 0x22, "mods": 0x00}),
    ("falu3",   {"dst": 0x01, "op": 0x1e, "srcA": 0x05, "srcB": 0x81, "srcC": 0x08, "ext": 0xc002}),
    ("fminmax", {"dst": 0x03, "op": 0x1e, "srcA": 0x05, "sel": 0x01, "mods": 0xc0}),
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


def main():
    f = 0
    f += test_real_roundtrip()
    f += test_synth_roundtrip()
    f += test_tokenize_programs()
    print(f"\n{'ALL PASS' if f == 0 else str(f) + ' FAILURES'}")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
