#!/usr/bin/env python3
"""EXP-0145 NUMERIC-family host oracles. Every candidate is computed on the
host from exact rational arithmetic; nothing is read from the GPU.

For each case we emit a SET of candidate results (RNE / RNA / truncate /
FTZ / DAZ / fused / unfused ...) and record which candidates the hardware
matched. That is what turns "we got a number" into "we measured the rounding
rule", and it is why an assumption cannot silently absorb an error.
"""
import os, sys, struct
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib145 as L

# ---------------------------------------------------------------- bf16 core
def bf_parts(b):
    b &= 0xFFFF
    return (b >> 15) & 1, (b >> 7) & 0xFF, b & 0x7F

def bf_is_nan(b): return ((b >> 7) & 0xFF) == 0xFF and (b & 0x7F) != 0
def bf_is_inf(b): return ((b >> 7) & 0xFF) == 0xFF and (b & 0x7F) == 0
def bf_is_sub(b): return ((b >> 7) & 0xFF) == 0 and (b & 0x7F) != 0

def bf_to_frac(b):
    s, e, m = bf_parts(b)
    if e == 0xFF: return None                       # inf/NaN handled by caller
    v = Fraction(m, 128) * Fraction(2) ** -126 if e == 0 else \
        (1 + Fraction(m, 128)) * Fraction(2) ** (e - 127)
    return -v if s else v

def frac_to_bf(v, mode='rne', ftz=False):
    """Round an exact Fraction to bf16 bits. mode: rne|rna|trunc."""
    if v == 0: return 0x0000
    s = 1 if v < 0 else 0
    a = -v if v < 0 else v
    # find exponent E with 2^E <= a < 2^(E+1)
    E = 0
    if a >= 1:
        while a >= Fraction(2) ** (E + 1): E += 1
    else:
        while a < Fraction(2) ** E: E -= 1
    if E < -126:                                    # subnormal range
        if ftz: return s << 15
        q = a / (Fraction(2) ** -133)               # ulp of bf16 subnormal
        e_field = 0
    else:
        q = a / (Fraction(2) ** (E - 7))            # 8-bit significand
        e_field = E + 127
    i = int(q); r = q - i
    if mode == 'trunc':      pass
    elif mode == 'rna':      i += 1 if r >= Fraction(1, 2) else 0
    else:                    i += 1 if (r > Fraction(1, 2) or (r == Fraction(1, 2) and i & 1)) else 0
    if E < -126:
        if i >= 128: return (s << 15) | i           # carried into the smallest normal
        if i == 0 and ftz: return s << 15
        return (s << 15) | i
    if i >= 256: i >>= 1; e_field += 1
    if e_field >= 255: return (s << 15) | 0x7F80    # overflow -> inf
    return (s << 15) | (e_field << 7) | (i & 0x7F)

# ---------------------------------------------------------------- fp16 core
def fp_is_nan(b): return ((b >> 10) & 0x1F) == 0x1F and (b & 0x3FF) != 0
def fp_is_inf(b): return ((b >> 10) & 0x1F) == 0x1F and (b & 0x3FF) == 0
def fp_is_sub(b): return ((b >> 10) & 0x1F) == 0 and (b & 0x3FF) != 0

def fp_to_frac(b):
    b &= 0xFFFF; s = (b >> 15) & 1; e = (b >> 10) & 0x1F; m = b & 0x3FF
    if e == 0x1F: return None
    v = Fraction(m, 1024) * Fraction(2) ** -14 if e == 0 else \
        (1 + Fraction(m, 1024)) * Fraction(2) ** (e - 15)
    return -v if s else v

def frac_to_fp(v, mode='rne', ftz=False):
    if v == 0: return 0x0000
    s = 1 if v < 0 else 0
    a = -v if v < 0 else v
    E = 0
    if a >= 1:
        while a >= Fraction(2) ** (E + 1): E += 1
    else:
        while a < Fraction(2) ** E: E -= 1
    if E < -14:
        if ftz: return s << 15
        q = a / (Fraction(2) ** -24); e_field = 0
    else:
        q = a / (Fraction(2) ** (E - 10)); e_field = E + 15
    i = int(q); r = q - i
    if mode == 'trunc':  pass
    elif mode == 'rna':  i += 1 if r >= Fraction(1, 2) else 0
    else:                i += 1 if (r > Fraction(1, 2) or (r == Fraction(1, 2) and i & 1)) else 0
    if E < -14: return (s << 15) | i
    if i >= 2048: i >>= 1; e_field += 1
    if e_field >= 31: return (s << 15) | 0x7C00
    return (s << 15) | (e_field << 10) | (i & 0x3FF)

# ---------------------------------------------------------------- candidates
def _bf_binop(op, ab, bb, daz=False, ftz=False, mode='rne'):
    """Exact bf16 binary op -> candidate bits, or a special-value verdict."""
    a, b = ab, bb
    if daz:
        if bf_is_sub(a): a = a & 0x8000
        if bf_is_sub(b): b = b & 0x8000
    if bf_is_nan(a): return (a | 0x0040) & 0xFFFF
    if bf_is_nan(b): return (b | 0x0040) & 0xFFFF
    ia, ib = bf_is_inf(a), bf_is_inf(b)
    fa, fb = bf_to_frac(a), bf_to_frac(b)
    sa, sb = (a >> 15) & 1, (b >> 15) & 1
    if op == 'add':
        if ia and ib: return 0x7FC0 if sa != sb else a
        if ia: return a
        if ib: return b
        r = fa + fb
        if r == 0: return 0x0000 if not (sa and sb) else 0x8000
        return frac_to_bf(r, mode, ftz)
    if op == 'mul':
        if (ia and fb == 0) or (ib and fa == 0): return 0x7FC0
        if ia or ib: return ((sa ^ sb) << 15) | 0x7F80
        r = fa * fb
        if r == 0: return ((sa ^ sb) << 15)
        return frac_to_bf(r, mode, ftz)
    raise ValueError(op)

def bf_candidates(op, ab, bb, cb=None):
    """Return {name: 2-byte little-endian expected output}."""
    out = {}
    def put(n, bits): out[n] = struct.pack('<H', bits & 0xFFFF)
    if op in ('add', 'mul'):
        put('rne',       _bf_binop(op, ab, bb))
        put('rna',       _bf_binop(op, ab, bb, mode='rna'))
        put('trunc',     _bf_binop(op, ab, bb, mode='trunc'))
        put('rne_ftz',   _bf_binop(op, ab, bb, ftz=True))
        put('rne_daz',   _bf_binop(op, ab, bb, daz=True))
        put('rne_dazftz',_bf_binop(op, ab, bb, daz=True, ftz=True))
        put('src_a', ab); put('src_b', bb); put('zero', 0)
    else:                                              # fma
        if bf_is_nan(ab) or bf_is_nan(bb) or bf_is_nan(cb):
            for n in ('fused_rne', 'unfused_rne'):
                put(n, (next(x for x in (ab, bb, cb) if bf_is_nan(x)) | 0x0040))
        elif bf_is_inf(ab) or bf_is_inf(bb) or bf_is_inf(cb):
            m = _bf_binop('mul', ab, bb)
            put('fused_rne', _bf_binop('add', m, cb))
            put('unfused_rne', _bf_binop('add', m, cb))
        else:
            fa, fb, fc = bf_to_frac(ab), bf_to_frac(bb), bf_to_frac(cb)
            exact = fa * fb + fc
            put('fused_rne',   frac_to_bf(exact) if exact != 0 else 0x0000)
            put('fused_rna',   frac_to_bf(exact, 'rna') if exact != 0 else 0x0000)
            put('fused_trunc', frac_to_bf(exact, 'trunc') if exact != 0 else 0x0000)
            put('fused_ftz',   frac_to_bf(exact, 'rne', True) if exact != 0 else 0x0000)
            m = _bf_binop('mul', ab, bb)
            put('unfused_rne', _bf_binop('add', m, cb))
        put('src_a', ab); put('src_b', bb); put('src_c', cb or 0); put('zero', 0)
    return out

def fp_minmax_candidates(which, ab, bb):
    out = {}
    def put(n, bits): out[n] = struct.pack('<H', bits & 0xFFFF)
    na, nb = fp_is_nan(ab), fp_is_nan(bb)
    fa, fb = fp_to_frac(ab), fp_to_frac(bb)
    if na and nb:
        put('ieee_minnum', ab); put('nan_prop', ab)
    elif na:
        put('ieee_minnum', bb); put('nan_prop', ab)
    elif nb:
        put('ieee_minnum', ab); put('nan_prop', bb)
    else:
        ia, ib = fp_is_inf(ab), fp_is_inf(bb)
        va = (float('-inf') if (ab >> 15) else float('inf')) if ia else float(fa)
        vb = (float('-inf') if (bb >> 15) else float('inf')) if ib else float(fb)
        pick_min = ab if va < vb else (bb if vb < va else ab)
        pick_max = ab if va > vb else (bb if vb > va else ab)
        alt_min  = ab if va < vb else (bb if vb < va else bb)
        alt_max  = ab if va > vb else (bb if vb > va else bb)
        put('ieee_minnum', pick_min if which == 'min' else pick_max)
        put('nan_prop',    pick_min if which == 'min' else pick_max)
        put('tie_second',  alt_min if which == 'min' else alt_max)
    put('src_a', ab); put('src_b', bb); put('zero', 0)
    return out

def fp_fma_candidates(ab, bb, cb):
    out = {}
    def put(n, bits): out[n] = struct.pack('<H', bits & 0xFFFF)
    if fp_is_nan(ab) or fp_is_nan(bb) or fp_is_nan(cb):
        q = next(x for x in (ab, bb, cb) if fp_is_nan(x))
        put('fused_rne', q | 0x0200); put('unfused_rne', q | 0x0200)
    elif fp_is_inf(ab) or fp_is_inf(bb) or fp_is_inf(cb):
        put('inf_case', 0x7C00); put('ninf_case', 0xFC00); put('nan_case', 0x7E00)
    else:
        fa, fb, fc = fp_to_frac(ab), fp_to_frac(bb), fp_to_frac(cb)
        exact = fa * fb + fc
        put('fused_rne',   frac_to_fp(exact) if exact != 0 else 0x0000)
        put('fused_rna',   frac_to_fp(exact, 'rna') if exact != 0 else 0x0000)
        put('fused_trunc', frac_to_fp(exact, 'trunc') if exact != 0 else 0x0000)
        put('fused_ftz',   frac_to_fp(exact, 'rne', True) if exact != 0 else 0x0000)
        p = fa * fb
        pr = fp_to_frac(frac_to_fp(p)) if p != 0 else Fraction(0)
        u = pr + fc
        put('unfused_rne', frac_to_fp(u) if u != 0 else 0x0000)
    put('src_a', ab); put('src_b', bb); put('src_c', cb); put('zero', 0)
    return out
