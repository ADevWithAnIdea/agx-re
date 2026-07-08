#!/usr/bin/env python3
# patches.py — accumulating, anchor-confirmed length-rule fixes, applied as an
# override layer over isadb.instr_length. Import apply() to activate.
# CLEAN-ROOM: our own shader bytes only. Each fix cites an anchored gap.
import isadb
_orig = isadb.instr_length
def _b(buf,off,k): return buf[off+k] if off+k<len(buf) else -1

# --- integer compare/minmax/select/carry group: byte0 low-nibble 2 ------------
# high nibble of byte0 = destination register (r0..r15). Length is keyed on the
# byte+2 op-select (all op-selects are <= 0x3f; larger byte+2 is an operand tail).
# Confirmed by anchored gaps (cvt/iadd/imad/store brackets) in i_max, i_cmp,
# mm3, l_add, l_cmp, i_selreg, u_div, s_div, s_mod.
_L6  = {0x1e,0x2e,0x3e, 0x26,0x36, 0x35}                  # iminmax / carry_gen -> 6
_L14 = {0x1d,0x2d}                                        # icmpsel const-select-> 14

def low2_len(buf, off):
    b0=buf[off]; b1=_b(buf,off,1); b2=_b(buf,off,2); b3=_b(buf,off,3); b4=_b(buf,off,4)
    # transcendental range-reduction select: byte+1==0xc2, tail `.. 80 08`, 8 bytes.
    # (t_sin@24 `02 c2 49 0b 24 85 80 08`, k_transcend@24 `02 c2 39 0f 24 81 80 08`.)
    if b1==0xc2 and _b(buf,off,6)==0x80 and _b(buf,off,7)==0x08:
        return 8
    if 0 <= b2 <= 0x3f:
        ln = b2 & 0x0f
        if b2 in _L6:  return 6
        if b2 in _L14: return 14
        # byte0 0x22 (dst r2): no confirmed real op uses the 0x27/reg-select forms;
        # keep its baseline behavior there to avoid reshuffling garbage in already-
        # desynced kernels (k_tex_atomic). The minmax/icmpsel fixes above still apply.
        if b0==0x22:
            pass
        elif b2==0x27:
            # 0x27 split: coord/madd (register operand byte+3==0x80) or
            # rt_transform_test (byte+3==0x81 & byte+4==0x22) -> 10; else the
            # 8-byte quotient/wide-select (u_div@98 b3=0f, k_cf_if@38 b3=08/@46 b3=8a).
            if b3==0x80 or (b3==0x81 and b4==0x22): return 10
            return 8
        # register-select cmpsel/fcmpsel: ln in {7,f} (or 64-bit 0x25). Length 10
        # ONLY when byte+3 is a register descriptor (high nibble 0 or 8); a large
        # byte+3 (e.g. 0xe4) is a branch/immediate compare -> shorter, fall through.
        if b0!=0x22 and (ln in (0x07,0x0f) or b2==0x25) and (b3 & 0xf0) in (0x00,0x80):
            return 10
    # unrecognized/short form: preserve ORIGINAL per-byte behavior so a tail byte
    # or an unhandled form never gets a wrong length (never worse than baseline).
    if b0==0x02: return 6
    if b0==0x12: return 14 if (b2 & 0x0f)==0x0d else 6
    if b0==0x22: return 6 if (b2 & 0x0f)==0x0e or b2==0x35 else 10
    if b0==0x32: return 6
    return None                       # new high-nibble, unknown op -> undecoded

def patched(buf, off=0):
    b0=buf[off]; lo=b0 & 0x0f
    if lo==0x02:
        # keep the rt_transform_test / carry_gen precedence that _orig has, but the
        # low2 handler already covers those signatures.
        r=low2_len(buf,off)
        return r if r is not None else _orig(buf,off)
    if lo==0x09:
        b2=_b(buf,off,2)
        if b2 in (0x19,0x21,0x31):    # compact 4-byte float (s_div@136/@244, t_sqrt@28)
            return 4
        return _orig(buf,off)
    # --- 0x27 convert/prep: byte+1==0x02 is a 12-byte matrix-load prep form -----
    # k_matrix@58 `27 02 54 02 03 04 08 00 f0 11 01 00` (anchored iadd2..iadd2, =12).
    # DB's 0x27 rule handles b1 in {0x00,0x01,0x10}->12 but drops 0x02 to the else->8,
    # which desyncs and exposes the tail `f0 11 01 00` (the spurious 0xf0 group).
    if b0==0x27 and _b(buf,off,1)==0x02:
        return 12
    # --- compact low-nibble-c move (byte0 0x2c), 4 bytes ------------------------
    # s_div@178 `2c 0c 00 02` (anchored between falu3 and falu2, =4). A compact
    # move/immediate form; high nibble = dst reg. Gate on byte+1==0x0c so it never
    # swallows the get_sr (byte+3 lo-nibble 6) or a real longer 0xNc op.
    if b0==0x2c and _b(buf,off,1)==0x0c:
        return 4
    # --- transcend range-reduction op (byte0 low-nibble 3, byte+2==0x27), 10 B ---
    # k_tex_atomic@226 `33 8a 27 bf 10 02 00 00 00 00` (two anchored 10B ops), also
    # in k_transcend. Low nibble 3 = the 0x13 move family; the byte+2==0x27 form is a
    # distinct 10-byte op. 0x13 zero-extend (byte+2 != 0x27) keeps its 4-byte length.
    if (b0 & 0x0f)==0x03 and _b(buf,off,2)==0x27:
        return 10
    # --- half2 packed ALU (byte0 low-nibble 0/8, byte+2==0x24), 6 bytes ----------
    # k_half2_pack@32 `38 82 24 84 00 c8` / `30 83 24 85 00 08` (anchored 6B each);
    # k_half_arith@38 `18 84 24 85 00 08`. The packed-half2 arithmetic op (distinct
    # from the 0x10 scalar native-half ALU and the 0x18 b1==0x05 half_pack).
    if (b0 & 0x0f) in (0x00,0x08) and _b(buf,off,2)==0x24 and b0 not in (0x00,):
        return 6
    return _orig(buf,off)

def apply():   isadb.instr_length = patched
def restore(): isadb.instr_length = _orig
