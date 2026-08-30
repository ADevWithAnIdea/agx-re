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
    # ---- SIMD-group MATRIX multiply-accumulate (0xcf, 12B, EXP-0022 HW) ----
    "matmad_f32 (cf 02 56 ... acc=1)":      "cf02560200040809d4432401",  # r=a*b+c float  HW
    "matmul_f32 (cf 02 56 ... acc=0)":      "cf02560200040800d4412400",  # r=a*b   float  HW
    "matmad_f16 (cf 00 56 ... half)":       "cf005604020c080410628c00",  # r=a*b+c half   HW
    "matmac_mpp (cf 02 54 ... tiled)":      "cf02540501b46f004a422401",  # MPP tiled MAC  HW-obs
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
    # ---- SFU rcp/rsqrt/sqrt single ops + 0x29 estimate seeds (EXP-0026) ----
    "fspecial rcp  (af 00 fast 1/x)":       "af005600020010482000",   # SFU reciprocal HW
    "fspecial rsqrt(af 01 fast)":           "af0156000200b0400000",   # SFU rsqrt HW
    "fspecial sqrt (2f 01 fast)":           "2f015604030092400000",   # SFU sqrt HW
    "fspecial_est rcp  (29 81 25 09)":      "2981250900c2",           # rcp estimate seed HW
    "fspecial_est rsqrt(29 81 25 0b)":      "2981250b00c2",           # rsqrt estimate seed HW
    "fspecial_est sqrt (29 81 25 0d)":      "2981250d00c2",           # sqrt estimate seed HW
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
    # EXP-M4-13 R7: two own-MSL get_sr with a high destination register, exercising the
    # dst_hi (byte+3 bits5-7) + dp_width fields split. 24aa1046 = SR 0xaa -> r34;
    # 0c9d5086 = SR 0x9d -> r64 (dp_width flips 0x10->0x50 at the top dst bank).
    "get_sr r34 (24 aa 10 46)":            "24aa1046",                # threadgroups.z -> r34
    "get_sr r64 (0c 9d 50 86)":            "0c9d5086",                # tg_pos.y -> r64 (top bank)
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
    # ---- RAY TRACING (EXP-0023): dedicated intersect op + AS-data load ----
    "rt_intersect const-origin (d4 ea 90 ..)": "d4ea90a68b000000",  # isect_dist op#1 HW-dedicated
    "rt_intersect dyn-origin  (a4 ea 10 ..)":  "a4ea1046cb000000",  # isect_dynray op#1 (dynamic ray)
    "rt_intersect +fntable    (24 ea d0 ..)":  "24ead0a6ab008000",  # trace_custom op#1 (fn-table, byte+6 bit7)
    "rt_intersect result-read (34 ea 10 ..)":  "34ea10266386269f",  # isect_dist op#2 (result read)
    "rt_as_load (df 02 54 ..)":                "df025432000000005c02044c0000",  # BVH/ray-data load
    # ---- SCOREBOARD / BARRIER (EXP-0025): the only explicit ordering op in compute ----
    "barrier tgmem (07 04 54 61 09 00)": "070454610900",  # threadgroup_barrier(mem_threadgroup) HW/splice
    "barrier device (07 04 54 85 08 00)":"070454850800",  # threadgroup_barrier(mem_device) HW
    "falu_acc (09 01 38 11)":            "09013811",       # compact 4-byte float accumulate HW (NOT a wait)
    # ---- RT-1a-FIX: memory index, iadd polarity, uniform source, undecoded groups ----
    "falu2_uni a+uniform (09 0d 14 01 80 c0)": "090d140180c0",  # GPR + UNIFORM src (NOT a minifloat imm) RT-1a-FIX HW
    "falu_acc 0x18 form (19 0b 18 09)":  "190b1809",       # compact float accumulate, byte+2=0x18 variant RT-1a-FIX HW
    "spill_frame_marker (60 00 00 00)":  "60000000",       # spill/frame-setup marker after entry get_sr RT-1a-FIX HW len
    "device_load a[i0] (67 00 46 0a ..)":"6700460a02802000510100404600",  # index_reg=+5, +6 inert, idx_off RT-1a-FIX HW
    "iadd2 add (9f 01 56 .. a8 17 05)":  "9f015600020800a81705",  # byte0 0x9f = ADD (RT-1a-FIX polarity) HW
    "iadd2 sub (1f 01 56 .. a8 17 05)":  "1f015600020010a81705",  # byte0 0x1f = SUBTRACT (RT-1a-FIX polarity) HW
    # ---- FRAGMENT STAGE (EXP-0029), carved from our own compiled render pipelines ----
    "iter center (2f 0d 54 .. m0)":      "2f0d5400030000021000",   # varying interpolate, center  HW
    "iter perspW (2f 0d 54 .. m4)":      "2f0d5400030004021000",   # perspective-denominator iter HW
    "iter_at centroid (af 14 54 .. 01)": "af14540403000a01",       # interpolate-at setup, centroid HW
    "iter_at sample   (af 04 54 .. 03)": "af04540403000a03",       # interpolate-at setup, sample   HW
    "iter_flat (1f 0b 54 0b 00 05)":     "1f0b540b0005",           # flat varying load HW
    "frag_color_store (e7 06 54 ..)":    "e70654000000014e00000000",  # colour store RT0 HW
    "tile_read (67 0e 54 ..)":           "670e5404000001ce02000000",  # programmable-blend tile read HW
    "frag_tile_setup (87 02 54 0c 08)":  "8702540c0800",           # tile/RT access setup HW
    "frag_color_pack (97 0c 54 ..)":     "970c54000250805004c8",   # colour-register pack HW
    "pixel_order acquire (07 14 54 50 06)":"071454500600",         # raster-order-group wait HW-diff
    "pixel_order release (07 04 54 d0 06)":"070454d00600",         # raster-order-group signal HW-diff
    # ---- EXP-0036 consolidation: merged EXP-0030/0031/0033/0034/0035 descriptors ----
    # get_special_register (EXP-0031): SR# = byte1, dst = byte0-hi (0xN4 & 0xNc forms).
    "get_sr tgpg (24 a8 10 06)":          "24a81006",   # dst r2, SR 0xa8 threadgroups_per_grid.x
    "get_sr lane (54 82 14 66)":          "54821466",   # dst r5, SR 0x82 simd_lane_id (0xN4 form)
    "mov_imm 32 (0c 20)":                 "0c20",       # threads_per_simdgroup=32 (constant-fold)
    "half_alu hadd (10 85 24 84 00 c0)":  "1085248400c0",  # native fp16 add (EXP-0033)
    "ibitcount popcount (27 05 56 ..)":   "2705560002005c04",   # popcount (EXP-0033/0007)
    "ibitcount find_msb (a7 05 56 ..)":   "a7055604030c4e04",   # find-MSB / bit-scan (EXP-0033, from k_int_bitcount)
    "irotate imm (27 01 56 .. 12B)":      "2701560002006c00f0150900",  # rotate-by-immediate funnel (EXP-0033)
    "pack_convert (97 04 56 ..)":         "9704560c03102a544482",  # pack_float_to_unorm2x16 (EXP-0033, from k_cvt_pack)
    "unpack_convert (17 04 56 ..)":       "1704560000001cca",  # unpack_unorm2x16, 8B (EXP-M4-12 fresh isolated compile; byte+1!=07 vs simd_ballot). EXP-0033's 10B was a 2-byte over-read.
    "iminmax_chain (22 01 1e 05 07 c0)":  "22011e0507c0",   # min3/clamp first op (EXP-0033)
    "frame_marker (43 00 00 01)":         "43000001",   # call/frame-setup marker (EXP-0035; re-scoped EXP-0030)
    "call (0f 05 54 1a 8f 10 54 54 ..)":  "0f05541a8f105454ffffffffff00",  # direct CALL (EXP-0035, from k_cf_call)
    "ret leaf (8f 02 54 00)":             "8f025400",   # function RETURN, leaf (EXP-0035)
    "call_indirect (0f 80 85 02 07 02)":  "0f8085020702",  # visible_function_table indirect call (EXP-0035, from k_fptr)
    # ---- EXP-0037: vertex varying store + texture coordinate math (from our own render stages) ----
    "vary_store pos (57 26 54 00 00 40 49 00)": "5726540000404900",  # VS [[position]] store, from r_basic_vertex
    "vary_store varying (57 06 56 0a a0 40 48 00)": "5706560aa0404800",  # VS user-varying store, from r_basic_vertex
    "tex_coord_setup (5b 03 2f 00 42 00 00 14 00 00)": "5b032f00420000140000",  # coord/interp setup, from r_basic_vertex
    "coord_madf (2e 87 23 a0 42 00 00 06 02 00)": "2e8723a0420000060200",  # coord fused mul-add leader, from k_tex_array_cube
    # ---- EXP-0038: u64 carry / non-leaf frame / half pack / cache bit (our own compiled kernels) ----
    "carry_gen (32 01 35 03 22 81)":       "320135032281",   # u64 carry-generate (from k_u64add)
    "frame_prologue (6f 03 04 00 00 20)":  "6f0304000020",   # non-leaf frame prologue (from k_chain mid())
    "link_save (07 00 54 00 81 00 00 00)": "0700540081000000",  # link-register save before a nested call
    "link_restore (07 00 54 00 81 ff 1f 00)": "0700540081ff1f00",  # link-register restore after a nested call
    "half_pack (18 05 18 03)":             "18051803",       # half2 pack (from k_h2add)
    "simd_reduce max 0x54 cache (bf 03 54 04 03 08 14 03)": "bf03540403081403",  # later-consumer reduce (0x54 cache bit)
    "unpack_convert 0x54 cache (17 04 54 ..)": "1704540000001cca",  # unpack, 0x54 cache-bit variant, 8B (EXP-M4-12: dropped trailing `e7 00` = next device_store head)
    # ---- RT-ISA-FIX: ballot 0x17 mis-decode, shuffle 0x54 decode-gap, 0x0f exec-mask family, 0x07 fence ----
    "simd_ballot(pred) (17 17 54 ..)":     "1717540002001448220c",   # simd_ballot(lane<5)=0x1F HW; byte+1=0x17 (was mis-decoded as unpack)
    "simd_active_mask (17 07 54 ..)":      "17075400020200080218",   # simd_active_threads_mask HW; byte+1=0x07
    "simd_shuffle bcast3 0x54 (47 04 54 ..)": "470454000200062c0400", # simd_broadcast(v,3)=35 HW; byte+2=0x54 (was undecodable)
    "simd_shuffle xor3  0x54 (c7 04 54 ..)":  "c70454000200062c0400", # simd_shuffle_xor(v,3) HW; byte+2=0x54
    "jump back-edge (0f 00 54 ..)":        "0f0054c6ffffffffff00",   # loop back-edge, off=-58, from cf_for HW
    "jump_cond guard (0f 01 54 5c ..)":    "0f01545c000000000000",   # loop-exit guard, off=+0x5c, from cf_for HW
    "if_push (0f 05 54 01)":               "0f055401",               # exec-mask push (4B), from cf_for HW
    "pop_reconverge (0f 06 04 02 00 00)":  "0f0604020000",           # reconverge/pop, from cf_for HW
    "cf_merge (8f 04 54 22)":              "8f045422",               # loop-body CF merge marker, from cf_for HW
    "scoreboard_fence pre-call (07 22 02 00)": "07220200",           # 4B fence before a call (RT-1b census)
    "scoreboard_fence CF (07 02 00 00)":   "07020000",               # 4B fence around divergence, from cf_nested HW
    # ---- EXP-O2C: matrix operand decode + new RT ops (our own RT/tensor kernels) ----
    "matrix_mac mad_f32 (cf 02 56 .. dst=byte+8)": "cf02560200040809d4432401",  # A*B+C f32, full operand decode
    "matrix_mac mul_f32 (cf 02 56 .. acc=0)":      "cf02560200040800d4412400",  # A*B   f32
    "matrix_mac mad_f16 (cf 00 56 .. half)":       "cf005604020c080410628c00",  # A*B+C half
    "matrix_mac mpp_tiled (cf 02 54 ..)":          "cf02540501b46f004a422401",  # MPP tiled MAC (mode 0x54)
    "rt_intersect motion (a4 ea 10 46 bb ..)":     "a4ea1046bb000000",  # motion AS trace (byte+2=0x10, byte+4=0xbb)
    "rt_ray_mem (5f 02 54 ..)":                    "5f02542200000000400a06300200",  # ray-data / traversal-stack mem op
    "rt_transform_test (e2 95 27 81 22 ..)":       "e2952781227a0382207c",  # ray-vs-node transform/box-test
    "ray_move copy (eb 50 81 08)":                 "eb508108",  # ray reg-marshalling MOVE, copy form (byte+2=0x81)
    # ---- EXP-O2D: bfloat ALU + imageblock + device fence + helper-thread SR (our own kernels) ----
    "bf_alu bf_add (11 02 1c 02 09 00 c0 81)":     "11021c020900c081",  # native bfloat add (byte+1=0x02, opsel 0x1c)
    "bf_alu bf_mul (11 02 1d 02 09 00 c0 81)":     "11021d020900c081",  # native bfloat mul (opsel 0x1d) HW-splice
    "imageblock_store (e7 16 54 04 05 00 01 0e ..)": "e71654040500010e00000004",  # tile imageblock write (byte+1=0x16)
    "imageblock_load (67 16 54 04 05 00 01 8e ..)":  "671654040500018e02000010",  # tile imageblock read (byte+1=0x16)
    "mem_fence device (07 04 54 84 0a 00)":        "070454840a00",  # atomic_thread_fence(mem_device, seq_cst)
    "get_sr helper (04 84 11 06)":                 "04841106",  # simd_is_helper_thread (SR 0x84, FS)
    # ---- EXP-M4-01 round-3 census ops (length HW-anchored, own-shader) ----
    "frame_marker_compact (60 00)":                "6000",          # 2B compact frame/scope marker (tg-atomic)
    "cubearray_coord_const (f0 c0 04 00)":         "f0c00400",      # cube/cube-array normalized-coord const load
    "tg_addr_compute (1c 02 00 00 00 00)":         "1c0200000000",  # threadgroup-buffer base/offset compute
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
    # ---- TRANSCENDENTAL fast-math lowerings (EXP-0026): single SFU ops / compositions ----
    "fast_rcp":   "1ca010066710440000012000510100404600af005600020010482000e7005400010121001100009011000e000000",
    "fast_rsqrt": "1ca010066710440000012000510100404600af0156000200b0400000e7005400010121001100009011000e000000",
    "fdiv_fast":  "1ca0100667105404010120005101004046006700440000012000110000404600af00560403081048200009011d050020e7005400020121001100009011000e000000",
    "expe_fast":  "1ca01006671044000001200051010040460009012d0900c2af0254000200b0400000e7005400010121001100009011000e000000",
    "loge_fast":  "1ca0100667104400000120005101004046002f0256000300b040000009010d090002e7005400010121001100009011000e000000",
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
    # ---- SCOREBOARD (EXP-0025): a 10-way reduction that mixes 6-byte 0x3c fadds and
    # the 4-byte 0x38 compact accumulates -- tokenizes cleanly (no wait ops anywhere).
    "manyload10": "1ca0100667105400000120005101004046006700541c010120005101004046006700541a020120001100004046006700541603012000510000404600670054140401200091000040460067005410050120009100004046006700540e060120009100004046006700540a0701200011010040460067005408080120001101004046006700440409012000d1000040460009013c1d00c009013c1b002009013c17004009013c150060090138110901380f09013c0b00a00901380909011c050080e70054000a0121001100009011000e000000",
    # ---- FRAGMENT whole _agc.main programs (EXP-0029), from our own render pipelines.
    # out_const: colour packs (0x97) + tile setup (0x87) + colour store (0xe7 06) + frag end (0x07) + stop.
    "frag_out_const":     "970c54000250805004c8970454010220c05004c88702540006008702540c0800e70654000000014e000000000702540c02000e000000",
    # interp_noperspective: four 10-byte varying interpolates (0x2f iter) + colour packs + store epilog.
    "frag_interp_nopersp":"2f0d54000300000210002f055402030400021000 2f055408030200021000 2f05540403060002100097045400020020d045c297045401020410d045c2870254000600 8702540c0800e70654000000014e000000000702540c02000e000000".replace(' ',''),
    # interp_flat: four 6-byte flat loads (0x1f iter_flat) + colour packs + store epilog.
    "frag_interp_flat":   "1f0b540b00051f03548700051f03540401001f03548001009704560602 3448d045c297145407021810d045c2870254000600 8702540c0800e70654060000014e000000000702540c02000e000000".replace(' ',''),
    # out_mrt: three per-RT colour stores (frag_color_store byte+5 = RT index) — tokenizes clean.
    "frag_out_mrt":       "970c5404021838d005c8970454050220c0d004c897045402020c20d005c8970454030214c0d004c897045400020008d005c8970454010208c0d004c8870254000600870254c00800e70654040004014e00000000070254c00000870254300800e70654020002014e000000000702543000008702540c0800e70654000000014e000000000702540c02000e000000",
    # ---- EXP-0036: whole programs exercising the merged EXP-0030/31/33/35 descriptors
    # (each instruction has a matching descriptor -> tokenizes to 0 leftover). ----
    "merged_alu":  "1ca010061085248400c0270556000200"
                   "5c0422011e0507c0a7055604030c4e040e000000",  # get_sr+half_alu+popcount+min3+find_msb+stop
    "merged_call": "1ca010060c20430000010f05541a8f1054"
                   "54ffffffffff008f0254000f80850207020e000000", # get_sr+mov_imm+frame_marker+call+ret+call_indirect+stop
    # ---- EXP-0038: whole _agc.main / regions exercising the merged W2 descriptors ----
    # h2add: get_sr + loads + half_alu (0x10, 6B) + half_pack (0x18, 4B) + store + stop.
    "h2add":   "0ca010066710540200002000490100404600670044040100200049010040460010041c0200c018051803"
               "e7005402020021000900009011000e000000",
    # u64add carry chain: get_sr + loads + iadd_lo + carry_gen(0x32) + psel + iadd_hi + iadd_carry + store + stop.
    "u64add":  "5ca01006671054060005200059010040480067004402010520005901004048009f01560003041aa81505"
               "3201350322810500""20809f015402030820a817059f015402020c08881705e7005400020521001900001012000e000000",
    # non-leaf frame region: frame_prologue(0x6f) + link_save(0x07 8B) + link_restore(0x07 8B) + non-leaf ret(8f12).
    "nonleaf_frame": "6f03040000200700540081000000""0700540081ff1f00""8f125400",
    # ---- EXP-O2D: native bfloat kernels (get_sr + 2 loads + bf ALU + mov_zext16 + store + stop) ----
    "bfaddu": "0ca010066710540201002000410100404600670044030200200041010040460011021c020900c08113000001e7005402000021001100009011000e000000",
    "bfmulu": "0ca010066710540201002000410100404600670044030200200041010040460011021d020900c08113000001e7005402000021001100009011000e000000",
    # ---- EXP-O2D: tile-shader imageblock region (get_sr helper + imageblock write/read + device fence + stop) ----
    "ib_tile":  "04841106""e71654040500010e00000004""671654040500018e02000010""070454840a00""0e000000",
    # ---- EXP-O2C: ray-tracing op region (intersect + ray-data mem + transform-test + ray move + AS load + matrix MAC + stop) ----
    "rt_ops":   "d4ea90a68b000000""5f02542200000000400a06300200""e2952781227a0382207c""eb508108""df025432000000005c02044c0000""cf02560200040809d4432401""0e000000",
}

# Synthesized field combos for the asm->disasm->fields direction.
SYNTH = [
    # falu2 (reg-reg), EXP-0006 HW-validated field layout. fadd d=srcA+srcB:
    #   dst reg0, srcA=reg0/32b, srcB=reg2/32b -> 09051c0100c0 (== fast-math fadd)
    ("falu2",  {"dst": 0, "srcA_size": 1, "srcA_reg": 2, "opsel": 0b100,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 0, "ctrl": 0,
                "srcB_imm": 0, "srcA_class": 0, "srcB_class": 0, "srcB_neg": 0, "mod_hi": 0xc,
                "srcA_reg_top": 0, "srcB_reg_top": 0}),
    # fmul, same operands:
    ("falu2",  {"dst": 0, "srcA_size": 1, "srcA_reg": 2, "opsel": 0b101,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 0, "ctrl": 0,
                "srcB_imm": 0, "srcA_class": 0, "srcB_class": 0, "srcB_neg": 0, "mod_hi": 0xc,
                "srcA_reg_top": 0, "srcB_reg_top": 0}),
    # fsub d = srcA + (-srcB): srcB_neg=1 (HW-validated a+b -> a-b):
    ("falu2",  {"dst": 0, "srcA_size": 1, "srcA_reg": 0, "opsel": 0b100,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 2, "ctrl": 0,
                "srcB_imm": 0, "srcA_class": 0, "srcB_class": 0, "srcB_neg": 1, "mod_hi": 0xc,
                "srcA_reg_top": 0, "srcB_reg_top": 0}),  # -> 09011c0500c8
    # dst = reg5 exercises the b0[4:8] dst field (HW-validated):
    ("falu2",  {"dst": 5, "srcA_size": 1, "srcA_reg": 4, "opsel": 0b100,
                "opflags": 3, "srcB_size": 1, "srcB_reg": 5, "ctrl": 0,
                "srcB_imm": 0, "srcA_class": 0, "srcB_class": 0, "srcB_neg": 0, "mod_hi": 0xc,
                "srcA_reg_top": 0, "srcB_reg_top": 0}),  # -> 59091c0b00c0
    # falu2i packed immediate: a + 1.0 (exp=0xb bias11, mant=0, sign=0) HW-validated:
    ("falu2i", {"dst": 0, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xb, "opsel": 0b100,
                "imm_sign": 0, "opflags": 1, "srcA_size": 1, "srcA_reg": 0,
                "ctrl_lo": 0, "mods": 0xc0, "srcA_reg_top": 0}),             # -> 09b1140180c0
    # a + (-2.0): exp=0xc, sign=1:
    ("falu2i", {"dst": 0, "imm_flag": 1, "imm_mant": 0, "imm_exp": 0xc, "opsel": 0b100,
                "imm_sign": 1, "opflags": 1, "srcA_size": 1, "srcA_reg": 0,
                "ctrl_lo": 0, "mods": 0xc0, "srcA_reg_top": 0}),             # -> 09c11c0180c0
    # EXP-M4-13 R10 (falu_int_frag retype): the old raw 16-bit 'ext' field split into
    # ctrl (byte+6) + srcmods (byte+7); same bytes (ext=0xc002 -> ctrl=0x02, srcmods=0xc0).
    ("falu3",   {"dst": 0x0, "srcA": 0x01, "op": 0x1e, "srcB": 0x05, "ctrl_len": 0x81, "srcC": 0x08, "ctrl": 0x02, "srcmods": 0xc0}),
    # dst=r3 exercises the byte0 high-nibble destination field (EXP-M4-13 R2 fix_falu3_ishift;
    # renamed dst_lo -> dst by EXP-0138, which proved byte+1 is the FIRST SOURCE, not the dst high bits):
    ("falu3",   {"dst": 0x3, "srcA": 0x07, "op": 0x1e, "srcB": 0x0b, "ctrl_len": 0x81, "srcC": 0x0e, "ctrl": 0x02, "srcmods": 0x60}),
    # EXP-M4-13 R2 (n2_intalu): float min/max UNIFIED into low-nibble-2 iminmax.
    # fmin at dst r1 (byte0 0x12) -> reproduces the old fminmax bytes 12031e0501c0:
    ("iminmax", {"dst": 0x1, "dst_full": 0x03, "fmt": 0x3, "srcA": 0x05, "sel": 0x1, "selhi": 0, "srcB": 0xc0}),
    # ---- integer (EXP-0007) ----
    # iadd a+b: dst=reg0, addsub=1 (ADD opcode, byte0 0x9f -- RT-1a-FIX polarity),
    # lenbit=1 (10B), store_en=1. Reproduces the compiler's iadd bytes
    # 9f 01 56 00 02 08 00 a8 17 05. (EXP-M4-13 R6 refined field schema.)
    ("iadd2",   {"addsub": 0x1, "lenbit": 0x1, "srcB_reg_hi": 0x0, "b2_bit0": 0x0,
                 "store_en": 0x1, "b2_fmt": 0x15, "dst": 0x0, "opmode": 0x2,
                 "srcB_imm": 0x8, "srcB_imm_hi": 0x0, "srcB_ext": 0x0, "srcA": 0xa8,
                 "opc_tail": 0x17, "opc_tail2": 0x5}),
    # isub a-b (RT-1a-FIX): addsub=0 (SUBTRACT opcode, byte0 0x1f). 1f 01 56 00 02 00 10 a8 17 05.
    ("iadd2",   {"addsub": 0x0, "lenbit": 0x1, "srcB_reg_hi": 0x0, "b2_bit0": 0x0,
                 "store_en": 0x1, "b2_fmt": 0x15, "dst": 0x0, "opmode": 0x2,
                 "srcB_imm": 0x0, "srcB_imm_hi": 0x0, "srcB_ext": 0x8, "srcA": 0xa8,
                 "opc_tail": 0x17, "opc_tail2": 0x5}),
    # iminmax (n2_intalu unified schema): signed min (sel=0x7) at dst r0 -> 02011e0507c0.
    ("iminmax", {"dst": 0x0, "dst_full": 0x01, "fmt": 0x3, "srcA": 0x05, "sel": 0x7, "selhi": 0, "srcB": 0xc0}),
    # iminmax: unsigned max (sel=0x4) at dst r0 -> 02011e0504c0.
    ("iminmax", {"dst": 0x0, "dst_full": 0x01, "fmt": 0x3, "srcA": 0x05, "sel": 0x4, "selhi": 0, "srcB": 0xc0}),
    # ---- scalar ALU (EXP-0013) ----
    # cvt_f2i (float->int, byte+7 0x48 = signed): reproduces 27 07 56 00 02 00 b4 48 03 00
    ("cvt_f2i", {"mode": 0x56, "dst": 0x0, "src_class": 0x2, "src": 0x0, "cvtop": 0xb4, "signflag": 0x48, "dst_class": 0x3, "b9": 0x0}),
    # cvt_i2f (int->float, byte+7 0x60 = signed): a7 07 56 00 02 00 ac 60
    ("cvt_i2f", {"mode": 0x56, "dst": 0x0, "src_class": 0x2, "src": 0x0, "cvtop": 0xac, "signflag": 0x60}),
    # cvt_f2h (fp32->fp16): 11 03 1c 81 00 c2
    ("cvt_f2h", {"b1": 0x03, "op": 0x1c, "src": 0x81, "b4": 0x00, "tail": 0xc2}),
    # fspecial floor (round-mode byte+8 = 0x02): 2f 00 56 00 02 00 b0 40 02 00
    # EXP-M4-13 R7 refined field names (fn_hi/fnclass/dst/src_cache/src/src_class/
    # src_ext/fnsel/precsel/roundmode/sched_flag); SAME bytes as the old b2/b6/b7 form.
    ("fspecial", {"fn_hi": 0, "fnclass": 0x0, "dst": 0x0, "src_cache": 0x56, "src": 0x00,
                  "src_class": 0x02, "src_ext": 0x00, "fnsel": 0xb0, "precsel": 0x40,
                  "roundmode": 0x02, "sched_flag": 0x00}),
    # fspecial rcp (SFU 1/x, fn_hi=1 byte0->0xaf, fnclass=0): af 00 56 00 02 00 10 48 20 00
    ("fspecial", {"fn_hi": 1, "fnclass": 0x0, "dst": 0x0, "src_cache": 0x56, "src": 0x00,
                  "src_class": 0x02, "src_ext": 0x00, "fnsel": 0x10, "precsel": 0x48,
                  "roundmode": 0x20, "sched_flag": 0x00}),
    # fspecial rsqrt at dst r2 (EXP-M4-13 R7): byte+1 = fnclass(1) | dst(2)<<4 = 0x21;
    # exercises the dst field split -> af 21 56 00 02 00 b0 40 00 00.
    ("fspecial", {"fn_hi": 1, "fnclass": 0x1, "dst": 0x2, "src_cache": 0x56, "src": 0x00,
                  "src_class": 0x02, "src_ext": 0x00, "fnsel": 0xb0, "precsel": 0x40,
                  "roundmode": 0x00, "sched_flag": 0x00}),
    # fspecial_est reciprocal seed (byte0 0x29, byte+2 0x25, subop 0x09): 29 81 25 09 00 c2
    ("fspecial_est", {"dst": 0x2, "srcA": 0x81, "subop": 0x09, "b4": 0x00, "b5": 0xc2}),
    # fspecial_est rsqrt seed (subop 0x0b): 29 81 25 0b 00 c2
    ("fspecial_est", {"dst": 0x2, "srcA": 0x81, "subop": 0x0b, "b4": 0x00, "b5": 0xc2}),
    # ilogic AND (op_base=1 and/or, no invert): 0b 05 1f 01 00 00 00 80 00 00
    # (EXP-M4-13 R6 refined schema: srcA=byte1, outmod=byte7 store bit.)
    ("ilogic", {"dst": 0x0, "srcA": 0x5, "op_base": 0x1, "srcB": 0x1, "lut_a_sel": 0x0, "lut_a_free": 0x0, "lut_a_z": 0x0, "lut_b": 0x0,
                "z6": 0x0, "outmod": 0x80, "z8": 0x0, "z9": 0x0}),
    # ilogic XOR (op_base=0 xor, invert bits): 0b 05 1e 01 02 08 00 80 00 00
    ("ilogic", {"dst": 0x0, "srcA": 0x5, "op_base": 0x0, "srcB": 0x1, "lut_a_sel": 0x2, "lut_a_free": 0x0, "lut_a_z": 0x0, "lut_b": 0x8,
                "z6": 0x0, "outmod": 0x80, "z8": 0x0, "z9": 0x0}),
    # ---- subgroup / quad / atomics (EXP-0018) ----
    # simd_sum: scope=1(simd), opcls=1, op=0x01(add/xor), dtype=0x03, cache=1(0x56) -> bf 01 56 00 02 00 14 03
    # EXP-M4-13 R10 (falu_int_frag retype): register CORRECTION b3->dst(byte+3),
    # src->opmarker(byte+4 const marker), b5->src(byte+5 true source); identical bytes.
    ("simd_reduce", {"scope": 1, "b0hi": 0, "opcls": 1, "cache": 1, "op": 0x01, "dst": 0x00,
                     "opmarker": 0x02, "src": 0x00, "shape": 0x14, "dtype": 0x03}),
    # quad_min: scope=0(quad), opcls=0, op=0x02(max/min), dtype=0x07, cache=1(0x56) -> 37 02 56 00 02 00 14 07
    ("simd_reduce", {"scope": 0, "b0hi": 0, "opcls": 0, "cache": 1, "op": 0x02, "dst": 0x00,
                     "opmarker": 0x02, "src": 0x00, "shape": 0x14, "dtype": 0x07}),
    # simd_max as a LATER consumer of a shared source: cache=0 -> byte+2 0x54 (EXP-0038 cache-bit).
    ("simd_reduce", {"scope": 1, "b0hi": 0, "opcls": 1, "cache": 0, "op": 0x02, "dst": 0x00,
                     "opmarker": 0x02, "src": 0x00, "shape": 0x14, "dtype": 0x07}),
    # simd_broadcast(v,5): dir=0, mode=0x04(simd), lane=0x0a(5<<1), cache=1 -> 47 04 56 00 02 00 0a 2c 04 00
    ("simd_shuffle", {"dir": 0x0, "mode": 0x4, "cache": 0x1, "dst": 0x0, "src": 0x2, "srctype": 0x0, "lane": 0xa, "rtype": 0x2c, "dsthi": 0x4, "rsv9": 0x0}),
    # atomic_rmw add (op=16 'add' at byte+12 bits[1:6]) -> 6711540000800100004200002000
    # EXP-M4-13 R10 (atomics_tex retype): the old raw b2/b3/mid/b13 fields were split
    # into the typed amode/index_reg/oper_reg_*/idx_off/op(5b)/per_lane layout; same bytes.
    # (EXP-0141 split byte+5/+6: index_reg=0x80 -> index_reg=0 + oper_reg_lo=1;
    #  addr_desc=0x01 -> oper_reg_hi=1 + addr_desc_hi=0. Byte image unchanged.)
    ("atomic_rmw", {"amode": 0x54, "rsv3": 0x00, "base_slot": 0x00, "index_reg": 0x00, "oper_reg_lo": 0x1,
                    "oper_reg_hi": 0x01, "addr_desc_hi": 0x0, "ret_flag": 0x00, "ret_desc": 0x00, "idx_off": 0x42,
                    "rsv10": 0x00, "rsv11": 0x00, "op_lsb": 0x00, "op": 0x10,
                    "per_lane": 0x00, "op_msb": 0x00, "amode_hi": 0x00}),
    # ---- ray tracing (EXP-0023) ----
    # NOTE (EXP-0175): `rt_intersect.subop`, `rt_transform_test.{marker,subop,cmpmode}`
    # and `ray_move.form` were FOLDED INTO `match` -- they had zero free bits, i.e.
    # exactly one legal value, so they were never fields an emitter chooses. The
    # assembled bytes are unchanged; the pinned values now come from `match`.
    # rt_intersect const-origin: dst=reg13, subop=0xea, mode=0x90, as_type=0x8b primitive_AS -> d4 ea 90 a6 8b 00 00 00
    ("rt_intersect", {"dst": 0xd, "mode": 0x90, "ray_param": 0xa6,
                      "as_type": 0x8b, "b5": 0x00, "flags": 0x00, "b7": 0x00}),
    # rt_intersect +fn-table: mode=0xd0, flags byte+6 bit7 set (0x80) -> 24 ea d0 a6 ab 00 80 00
    ("rt_intersect", {"dst": 0x2, "mode": 0xd0, "ray_param": 0xa6,
                      "as_type": 0xab, "b5": 0x00, "flags": 0x80, "b7": 0x00}),
    # rt_intersect motion: mode=0x10 (dyn/motion), as_type=0xbb primitive_motion_AS -> a4 ea 10 46 bb 00 00 00
    ("rt_intersect", {"dst": 0xa, "mode": 0x10, "ray_param": 0x46,
                      "as_type": 0xbb, "b5": 0x00, "flags": 0x00, "b7": 0x00}),
    # ---- EXP-O2C new RT ops + matrix operand decode ----
    # rt_transform_test: dst=reg14, src=0x95, byte+2=0x27 -> e2 95 27 81 22 7a 03 82 20 7c
    ("rt_transform_test", {"dst": 0xe, "src": 0x95, "opA": 0x7a, "opAmod": 0x3, "opAflags": 0x82, "mark2": 0x20, "opB": 0x7c}),
    # ray_move copy form (byte+2=0x81): dst=reg14, src=0x50 -> eb 50 81 08
    ("ray_move", {"dst": 0xe, "src": 0x50, "b3": 0x08}),
    # ---- EXP-O2D bfloat ALU ----
    # bf_add scalar (opsel byte+2=0x1c): -> 11 02 1c 02 09 00 c0 81
    ("bf_alu", {"opsel": 0x1c, "srcA": 0x02, "srcB": 0x09, "tail": 0x81c000}),
    # bf_mul scalar (opsel byte+2=0x1d): -> 11 02 1d 02 09 00 c0 81
    ("bf_alu", {"opsel": 0x1d, "srcA": 0x02, "srcB": 0x09, "tail": 0x81c000}),
    # ---- EXP-M4-13 R7: b_alu14_c83 full-coverage schema (2 real own-corpus instances).
    # Exercises the byte+5/+8/+9 slots that the R4 schema left UNCOVERED, plus the
    # byte+7 GPR source and byte+12/+13 uniform/state operand. -> 3f1383120300800e0000030092cb
    ("b_alu14_c83", {"form": 3, "reg_a": 0x13, "reg_b": 0x12, "fmt4": 0x03, "src_lo": 0x00,
                     "fmt6": 0x80, "srcB_reg": 0x0e, "rsv8": 0x00, "rsv9": 0x00, "fmt10": 0x03,
                     "rsv11": 0x00, "srcU_reg": 0x92, "srcU_desc": 0xcb}),
    # -> 3f0f830e0300800a000003009c01
    ("b_alu14_c83", {"form": 3, "reg_a": 0x0f, "reg_b": 0x0e, "fmt4": 0x03, "src_lo": 0x00,
                     "fmt6": 0x80, "srcB_reg": 0x0a, "rsv8": 0x00, "rsv9": 0x00, "fmt10": 0x03,
                     "rsv11": 0x00, "srcU_reg": 0x9c, "srcU_desc": 0x01}),
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
