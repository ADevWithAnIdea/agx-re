#!/usr/bin/env python3
"""DB-defect triage -- functional (not corpus) check that each class-(c) variant
actually changes what it claims to change. The corpus A/B answers "does this break
existing tokenization"; this answers "does it decode the encoding the hardware accepts".
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(d):
    p = os.path.join(HERE, "cvar", d, "isadb.py")
    spec = importlib.util.spec_from_file_location("m_" + d, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def try_decode(m, h):
    try:
        rec, ln = m.decode_one(bytes.fromhex(h), 0)
        return "%s(len %d)" % (rec["mnemonic"], ln)
    except Exception as e:
        return "UNDECODABLE (%s)" % str(e)[:50]


CASES = [
    # (variant, label, hex, what the hardware does)
    ("c1_pixel_order", "pixel_order acquire, byte+4 = 0x06 (compiler's value)",
     "071454500600", "runs correctly"),
    ("c1_pixel_order", "pixel_order acquire, byte+4 = 0x0a (1 of the 112 legal acquire values)",
     "071454500a00", "runs BYTE-EXACTLY correct on HW (EXP-0147)"),
    ("c1_pixel_order", "pixel_order release, byte+4 = 0xff (1 of the 224 legal release values)",
     "070454d0ff00", "runs BYTE-EXACTLY correct on HW (EXP-0147)"),
    ("c2_carry_gen", "carry_gen byte+2 = 0x35 (compiler's value)",
     "320135032281", "runs correctly"),
    ("c2_carry_gen", "carry_gen byte+2 = 0x07 (1 of the 8 legal values)",
     "320107032281", "runs correctly on HW (EXP-0146)"),
    ("c2_carry_gen", "carry_gen byte+2 = 0x27 (1 of the 8 legal values)",
     "320127032281", "runs correctly on HW (EXP-0146)"),
    ("c3_cvt_bf16", "cvt_bf16 byte+4 = 0x01 (the pinned value)",
     "0102148105024000", "decodes today"),
    ("c3_cvt_bf16", "cvt_bf16 byte+4 = 0x05 (what OUR OWN compiler emits)",
     "0102148105054000", "emitted by our own compiler (EXP-0144)"),
    ("c7_sfu_marker", "sfu_marker 06 02 (compiler's value)", "0602", "runs correctly"),
    ("c7_sfu_marker", "sfu_marker 0e 02 (byte0 bit3 free)", "0e02", "runs correctly on HW (EXP-0146)"),
    ("c7_sfu_marker", "sfu_marker 06 ee (byte+1 bits 2,3,5,6,7 free)", "06ee",
     "runs correctly on HW (EXP-0146)"),
    ("c8_reg_move", "reg_move form 0x01", "0b010100", "moves a value (EXP-0140)"),
    ("c8_reg_move", "reg_move form 0x25 (a moving form with no descriptor today)",
     "0b012500", "moves a value (EXP-0140 byte+2 sweep)"),
]

base = load("baseline")
for var, label, h, hw in CASES:
    m = load(var)
    b, a = try_decode(base, h), try_decode(m, h)
    flag = "  <-- CHANGED" if b != a else ""
    print("%-14s %-62s %s" % (var, label, h))
    print("      HW: %-52s" % hw)
    print("      baseline: %-28s variant: %-28s%s" % (b, a, flag))
