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
    # ---- MEMORY family (EXP-0012), carved from our own compiled load/store shaders ----
    "load32 (copy1 device i32)":   "6710440001012000510100404600",  # 32-bit scalar HW
    "load8  (ld_char device i8)":  "6710440001012000610100404200",  # 8-bit  (+8=61,+12=42) HW
    "load64 (ld_long device i64)": "6710440001022000590100404800",  # 64-bit (+5=02,+12=48) HW
    "load4x (vec4i device .4)":    "6710440001042000570100404000",  # 4-word vector (+5=04) HW
    "store4x(vec4i device .4)":    "e700560000042100170000101000",  # 4-word store  (+5=04) HW
    "tg_store (threadgroup +1=02)":"e702560008080000440200300200",  # threadgroup store HW
    "tg_load  (threadgroup +1=02)":"6702540008088000440d00c00800",  # threadgroup load  HW
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
    # ---- SCALAR ALU (EXP-0013): conversions / special funcs / bitwise-LUT / cmp CC ----
    "cvt_f2i (27 07 56 .. 10B)":            "270756000200b4480300",   # float->int (trunc) HW
    "cvt_f2u (27 07 56 .. 10B)":            "270756000200b4080200",   # float->uint HW
    "cvt_i2f (a7 07 56 .. 8B)":             "a70756000200ac60",       # int->float HW
    "cvt_u2f (a7 07 56 .. 8B)":             "a70756000200ac20",       # uint->float HW
    "cvt_f2h (11 03 1c 81 00 c2)":          "11031c8100c2",           # fp32->fp16 HW
    "cvt_h2f (09 00 1c 81 00 c2)":          "09001c8100c2",           # fp16->fp32 (falu2, 16b srcA) HW
    "fspecial exp2 (af 02 56 ..)":          "af0256000200b0400000",   # exp2 (0xaf) HW
    "fspecial log2 (2f 02 56 ..)":          "2f0256000200b0400000",   # log2 (0x2f) HW
    "fspecial floor (2f 00 56 .. b8=02)":   "2f0056000200b0400200",   # floor HW
    "fspecial ceil  (2f 00 56 .. b8=04)":   "2f0056000200b0400400",   # ceil HW
    "ilogic AND (0b 05 1f 01 ..)":          "0b051f01000000800000",   # a&b HW (LUT)
    "ilogic OR  (0b 05 1f 01 0208 ..)":     "0b051f01020800800000",   # a|b HW
    "ilogic XOR (0b 05 1e 01 0208 ..)":     "0b051e01020800800000",   # a^b HW
    "ilogic NAND(0b 05 1e 01 0308 ..)":     "0b051e01030800800000",   # ~(a&b) HW
    "ashr_i (a7 01 56 .. >>2 signed 10B)":  "a7015600020008786200",   # arith shr imm HW
    "lshr_i (a7 00 56 .. >>2 unsigned 12B)":"a700560002000800f0110100",# logical shr = bfe HW
    "icmp_lt  (12 03 1d .. s< b6=07)":      "12031d05228107c0208013000001", # signed <  HW
    "ucmp_lt  (12 03 1d .. u< b6=05)":      "12031d05228105c0208013000001", # unsigned < HW
    "fcmp_lt  (12 03 1d .. f< b6=03)":      "12031d05228103c0208013000001", # float <   HW
    "icmp_eq  (12 03 1d .. == b4=26)":      "12031d05268107c0208013000001", # signed == HW
    # ---- CONTROL FLOW (EXP-0010), carved from our own compiled CF shaders -----
    "icmp_pred (0a 01 22 82 14 22)":       "0a0122821422",            # gid>=4 predicate HW
    "sel   (16 c2 a0 c8)":                 "16c2a0c8",                # data select HW
    "psel  (05 22 a0 de)":                 "0522a0de",                # grid select HW
    "jump  (0f 00 54 d4 ff ff ff ff ff 00)":"0f0054d4ffffffffff00",   # -44 back-edge HW
    "get_sr(1c a0 10 06)":                 "1ca01006",                # get thread id HW
    # ---- SUBGROUP / QUAD / ATOMICS (EXP-0018), carved from our own compiled kernels ----
    "simd_reduce sum  (bf 01 56..14 03)":  "bf01560002001403",       # simd_sum HW
    "simd_reduce or   (bf 00 56..14 03)":  "bf00560002001403",       # simd_or  HW
    "simd_reduce and  (3f 00 56..14 03)":  "3f00560002001403",       # simd_and HW (byte0 bit7=0)
    "simd_reduce max  (bf 02 56..14 07)":  "bf02560002001407",       # simd_max HW
    "simd_reduce fadd (3f 06 56..14 12)":  "3f06560002001412",       # simd_sum(float) HW
    "simd_reduce excl (bf 01 56..14 0b)":  "bf0156000200140b",       # exclusive prefix-sum HW
    "quad_reduce sum  (b7 01 56..14 03)":  "b701560002001403",       # quad_sum HW (bit3=0)
    "quad_reduce min  (37 02 56..14 07)":  "3702560002001407",       # quad_min HW
    "simd_shuffle bcast0 (47 04 56..)":    "470456000200002c0400",   # simd_broadcast(v,0) HW
    "simd_shuffle bcast5 (47 04 56..0a)":  "4704560002000a2c0400",   # simd_broadcast(v,5) lane<<1 HW
    "simd_shuffle xor1  (c7 04 56..02)":   "c70456000200022c0400",   # simd_shuffle_xor(v,1) HW
    "quad_shuffle bcast0 (47 00 56..)":    "470056000200002c0400",   # quad_broadcast(v,0) HW
    "simd_ballot (17 07 56..)":            "17075600020000582204",   # simd_ballot mask source HW
    "atomic_rmw add  (67 11 54..20)":      "6711540000800100004200002000",  # device fetch_add HW
    "atomic_rmw smax (67 11 54..28)":      "6711540000800100004200002800",  # device fetch_max HW
    "atomic_mem xchg (67 01 56..3c)":      "6701560000000000000200003c00",  # atomic_exchange HW
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
    # ---- MEMORY _agc.main programs (EXP-0012): get_sr + [iadd] + load + store + stop ----
    "mcopy32": "1ca010066710440001012000510100404600e7005600000121001100009011000e000000",
    "mload64": "2ca010066710440001022000590100404800e7005600000221001900001012000e000000",
    "mvec4":   "4ca010066710440001042000570100404000e7005600000421001700001010000e000000",
    "moff1":   "1ca010069f1154000202088811046700440001802000510100404600e7005600000121001100009011000e000000",
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
    # ---- SCALAR ALU whole programs (EXP-0013): single-op convert/special/logic/cmp ----
    "cv_f2h":  "0ca01006671044020000200051010040460011031c8100c2e7005402010021000100001011000e000000",
    "cv_h2f":  "1ca01006671044000001200041010040440009001c8100c2e7005400010121001100009011000e000000",
    "cv_f2i":  "1ca010066710440000012000510100404600270756000200b4480300e7005400010121001100009011000e000000",
    "cv_i2f":  "1ca010066710440000012000510100404600a70756000200ac60e7005400010121001100009011000e000000",
    "cv_f2u":  "1ca010066710440000012000510100404600270756000200b4080200e7005400010121001100009011000e000000",
    "cv_u2f":  "1ca010066710440000012000510100404600a70756000200ac20e7005400010121001100009011000e000000",
    "cv_u2us": "0ca01006671044020000200041010040460013000001e7005602010021001100009011000e000000",
    "exp2":    "1ca010066710440000012000510100404600af0256000200b0400000e7005400010121001100009011000e000000",
    "log2":    "1ca0100667104400000120005101004046002f0256000200b0400000e7005400010121001100009011000e000000",
    "floor":   "1ca0100667104400000120005101004046002f0056000200b0400200e7005400010121001100009011000e000000",
    "iand":    "1ca01006671054000001200051010040460067004404010120005101004046000b051f01000000800000e7005400020121001100009011000e000000",
    "ior":     "1ca01006671054000001200051010040460067004404010120005101004046000b051f01020800800000e7005400020121001100009011000e000000",
    "ashr_i":  "1ca010066710440000012000510100404600a7015600020008786200e7005400010121001100009011000e000000",
    "lshr_i":  "1ca010066710440000012000510100404600a700560002000800f0110100e7005400010121001100009011000e000000",
    "fcmp_lt": "0ca010066710540200002000510100404600670044040100200051010040460012031d05228103c0208013000001e7005402020021001100009011000e000000",
    "ucmp_lt": "0ca010066710540200002000510100404600670044040100200051010040460012031d05228105c0208013000001e7005402020021001100009011000e000000",
    # ---- CONTROL FLOW whole programs (EXP-0010): branchless select forms that
    # tokenize cleanly as get_sr + [load] + compare(0x02) + select + store + stop.
    "gsel4":   "1ca010060203078422ef0522a0dee7005400000121001100009011000e000000",
    "dsel5":   "1ca01006671044000101200051010040460002010f8422e416c2a0c8e7005400000121001100009011000e000000",
    # ---- SUBGROUP / QUAD whole programs (EXP-0018): get_sr + load + reduce/shuffle/ballot + store + stop
    "s_sum":   "1ca010066710440000012000510100404600bf01560002001403e7005400010121001100009011000e000000",
    "s_max":   "1ca010066710440000012000510100404600bf02560002001407e7005400010121001100009011000e000000",
    "s_and":   "1ca0100667104400000120005101004046003f00560002001403e7005400010121001100009011000e000000",
    "s_pfx_ex":"1ca010066710440000012000510100404600bf0156000200140be7005400010121001100009011000e000000",
    "q_sum":   "1ca010066710440000012000510100404600b701560002001403e7005400010121001100009011000e000000",
    "q_min":   "1ca0100667104400000120005101004046003702560002001407e7005400010121001100009011000e000000",
    "s_bcast0":"1ca010066710440000012000510100404600470456000200002c0400e7005400010121001100009011000e000000",
    "s_shufx": "1ca010066710440000012000510100404600c70456000200022c0400e7005400010121001100009011000e000000",
    "s_ballot":"1ca01006671044000001200051010040460017075600020000582204e7005400010121001100009011000e000000",
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
    # ---- scalar ALU (EXP-0013) ----
    # cvt_f2i (float->int, byte+7 0x48 = signed): reproduces 27 07 56 00 02 00 b4 48 03 00
    ("cvt_f2i", {"b2": 0x56, "src": 0x0200, "b5": 0x00, "cvtop": 0xb4, "signflag": 0x48, "tail": 0x0003}),
    # cvt_i2f (int->float, byte+7 0x60 = signed): a7 07 56 00 02 00 ac 60
    ("cvt_i2f", {"b2": 0x56, "src": 0x0200, "b5": 0x00, "cvtop": 0xac, "signflag": 0x60}),
    # cvt_f2h (fp32->fp16): 11 03 1c 81 00 c2
    ("cvt_f2h", {"b1": 0x03, "op": 0x1c, "src": 0x81, "b4": 0x00, "tail": 0xc2}),
    # fspecial floor (round-mode byte+8 = 0x02): 2f 00 56 00 02 00 b0 40 02 00
    ("fspecial", {"fn_hi": 0, "fnclass": 0x00, "b2": 0x56, "src": 0x0200, "b5": 0x00,
                  "b6": 0xb0, "b7": 0x40, "roundmode": 0x02, "b9": 0x00}),
    # ilogic AND (op_base=1 and/or, no invert): 0b 05 1f 01 00 00 00 80 00 00
    ("ilogic", {"b1": 0x05, "op_base": 1, "srcB": 0x01, "lut_a": 0x00, "lut_b": 0x00, "ext": 0x8000}),
    # ilogic XOR (op_base=0 xor, invert bits): 0b 05 1e 01 02 08 00 80 00 00
    ("ilogic", {"b1": 0x05, "op_base": 0, "srcB": 0x01, "lut_a": 0x02, "lut_b": 0x08, "ext": 0x8000}),
    # ---- subgroup / quad / atomics (EXP-0018) ----
    # simd_sum: scope=1(simd), opcls=1, op=0x01(add/xor), dtype=0x03 -> bf 01 56 00 02 00 14 03
    ("simd_reduce", {"scope": 1, "b0hi": 0, "opcls": 1, "op": 0x01, "b3": 0x00,
                     "src": 0x02, "b5": 0x00, "shape": 0x14, "dtype": 0x03}),
    # quad_min: scope=0(quad), opcls=0, op=0x02(max/min), dtype=0x07 -> 37 02 56 00 02 00 14 07
    ("simd_reduce", {"scope": 0, "b0hi": 0, "opcls": 0, "op": 0x02, "b3": 0x00,
                     "src": 0x02, "b5": 0x00, "shape": 0x14, "dtype": 0x07}),
    # simd_broadcast(v,5): dir=0, mode=0x04(simd), lane=0x0a(5<<1) -> 47 04 56 00 02 00 0a 2c 04 00
    ("simd_shuffle", {"dir": 0, "mode": 0x04, "b3": 0x00, "src": 0x02, "b5": 0x00,
                      "lane": 0x0a, "tail": 0x00042c}),
    # atomic_rmw add (byte+12 = 0x20) -> 67 11 54 00 00 80 01 00 00 42 00 00 20 00
    ("atomic_rmw", {"b2": 0x54, "b3": 0x00, "base_slot": 0x00,
                    "mid": 0x4200000180, "op": 0x20, "b13": 0x00}),
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
