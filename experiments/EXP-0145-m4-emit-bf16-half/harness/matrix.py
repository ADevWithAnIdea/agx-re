#!/usr/bin/env python3
"""EXP-0145 FROZEN case matrix. Deterministic: importing this module and
hashing `matrix_json()` must reproduce the sha256 recorded in
CAPTURE_CONTRACT.json. Nothing here touches the GPU.

CLEAN-ROOM: OWN-SHADER. Inputs and oracles are host-computed from our own MSL
carriers; no Apple binary is introspected.
"""
import os, sys, json, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib145 as L

BF, FP = L.bf16_rne, L.fp16_rne
OUTB = 16                      # bytes read back from buffer 0 (element 0 + poison tail)

def u16(v): return b''.join(struct.pack('<H', x & 0xFFFF) for x in v)
def u32(v): return b''.join(struct.pack('<I', x & 0xFFFFFFFF) for x in v)
def f32(v): return b''.join(struct.pack('<f', float(x)) for x in v)
N = 8

# --------------------------------------------------------------- carriers
# id -> dict(src, region=(lo,hi) or [windows], io, targets, grid, tg)
CARRIERS = {
 'C1_bf_f32':      dict(src='c_bf_f32',       win=[(32, 60)], io='f32x2',
                        targets='cvt_bf16 cvt_f2h_dst pad_operand bf_add_dst n3_mov'),
 'C2_bfmul_f32':   dict(src='c_bfmul_f32',    win=[(32, 60)], io='f32x2',
                        targets='cvt_bf16 cvt_f2h_dst pad_operand bf_mul_dst n3_mov'),
 'C3_bf_native':   dict(src='c_bf_native',    win=[(32, 40)], io='bf2x1',
                        targets='bf_add_dst(native)'),
 'C4_bfmul_native':dict(src='c_bfmul_native', win=[(32, 40)], io='bf2x1',
                        targets='bf_mul_dst(native)'),
 'C5_bffma_native':dict(src='c_bffma_native', win=[(46, 56)], io='bf3x1',
                        targets='bf_fma_dst'),
 'C6_hmin':        dict(src='c_hmin',         win=[(32, 38)], io='h2x1',
                        targets='hminmax(min)'),
 'C7_hmax':        dict(src='c_hmax',         win=[(32, 38)], io='h2x1',
                        targets='hminmax(max)'),
 'C8_h2fma':       dict(src='c_h2fma',        win=[(46, 58)], io='h3x2',
                        targets='h_alu_hi_ext(0x20 8B) half_pack(0x28 4B)'),
 'C9_fabs':        dict(src='c_fabs',         win=[(18, 28)], io='f32x1',
                        targets='funary/b_alu10_loe'),
 'C10_orimm':      dict(src='c_orimm',        win=[(18, 28)], io='u32x1',
                        targets='funary_imm'),
 'C11_bf2':        dict(src='c_bf2',          win=[(32, 48)], io='bf2x2',
                        targets='bf_mul_dst x2 (bfloat2 lanes)'),
 'C12_hcoord':     dict(src='c_hcoord',       win=[(32, 44)], io='h2x2',
                        targets='h_alu_hi_ext(0x20 8B) half_pack(0x28 4B)'),
 'C14_sfutan':     dict(src='c_sfutan',       win=[(44, 54), (280, 286)], io='f32x1p',
                        targets='n2_op10 n2_op6'),
}

# --------------------------------------------------------------- input sets
INPUTS = {
 'f32x2':  {'S1': dict(a=3.0, b=5.0),  'S2': dict(a=17.0, b=9.0)},
 'bf2x1':  {'S1': dict(a=3.0, b=5.0),  'S2': dict(a=17.0, b=9.0)},
 'bf3x1':  {'S1': dict(a=3.0, b=5.0, c=2.0), 'S2': dict(a=17.0, b=9.0, c=4.0)},
 'h2x1':   {'S1': dict(a=3.0, b=5.0),  'S2': dict(a=17.0, b=9.0)},
 'h3x2':   {'S1': dict(a=(3.0, 7.0), b=(5.0, 2.0), c=(1.0, 4.0)),
            'S2': dict(a=(17.0, 6.0), b=(9.0, 3.0), c=(4.0, 5.0))},
 'bf2x2':  {'S1': dict(a=(3.0, 7.0), b=(5.0, 2.0)), 'S2': dict(a=(17.0, 6.0), b=(9.0, 3.0))},
 'h2x2':   {'S1': dict(a=(3.0, 7.0), b=(5.0, 2.0)), 'S2': dict(a=(17.0, 6.0), b=(9.0, 3.0))},
 'f32x1':  {'S1': dict(a=-2.5),        'S2': dict(a=6.75)},
 'f32x1p': {'S1': dict(a=0.5),         'S2': dict(a=1.25)},
 'u32x1':  {'S1': dict(a=0x12345678),  'S2': dict(a=0x000000FF)},
}

def materialise(io, s, d, tag=''):
    """Write the input buffers for (io, set) into d; return {bufidx: path}."""
    v = INPUTS[io][s]; out = {}
    def w(i, data):
        p = os.path.join(d, 'in_%s_%s%s_%d.bin' % (io, s, tag, i))
        open(p, 'wb').write(data); out[i] = p
    if io == 'f32x2':   w(1, f32([v['a']]*N)); w(2, f32([v['b']]*N))
    elif io == 'bf2x1': w(1, u16([BF(v['a'])]*N)); w(2, u16([BF(v['b'])]*N))
    elif io == 'bf3x1': w(1, u16([BF(v['a'])]*N)); w(2, u16([BF(v['b'])]*N)); w(3, u16([BF(v['c'])]*N))
    elif io == 'h2x1':  w(1, u16([FP(v['a'])]*N)); w(2, u16([FP(v['b'])]*N))
    elif io == 'h3x2':
        for i, k in ((1,'a'), (2,'b'), (3,'c')):
            lo, hi = v[k]; w(i, u16([FP(lo), FP(hi)]*N))
    elif io == 'bf2x2':
        for i, k in ((1,'a'), (2,'b')):
            lo, hi = v[k]; w(i, u16([BF(lo), BF(hi)]*N))
    elif io == 'h2x2':
        for i, k in ((1,'a'), (2,'b')):
            lo, hi = v[k]; w(i, u16([FP(lo), FP(hi)]*N))
    elif io in ('f32x1', 'f32x1p'): w(1, f32([v['a']]*N))
    elif io == 'u32x1': w(1, u32([v['a']]*N))
    else: raise ValueError(io)
    return out

# --------------------------------------------------------------- oracles
# Host-computed expected first-element bytes for the UNMUTATED carrier, under
# the pre-registered rounding assumptions R1-R3 (see PRE_REGISTRATION.md).
def _bf(x): return L.bf16_to_f(BF(x))
def _h(x):  return L.fp16_to_f(FP(x))

def oracle(cid, s):
    io = CARRIERS[cid]['io']; v = INPUTS[io][s]
    if cid == 'C1_bf_f32':      return struct.pack('<f', _bf(_bf(v['a']) + _bf(v['b'])))
    if cid == 'C2_bfmul_f32':   return struct.pack('<f', _bf(_bf(v['a']) * _bf(v['b'])))
    if cid == 'C3_bf_native':   return struct.pack('<H', BF(_bf(v['a']) + _bf(v['b'])))
    if cid == 'C4_bfmul_native':return struct.pack('<H', BF(_bf(v['a']) * _bf(v['b'])))
    if cid == 'C5_bffma_native':return struct.pack('<H', BF(_bf(v['a'])*_bf(v['b']) + _bf(v['c'])))
    if cid == 'C6_hmin':        return struct.pack('<H', FP(min(_h(v['a']), _h(v['b']))))
    if cid == 'C7_hmax':        return struct.pack('<H', FP(max(_h(v['a']), _h(v['b']))))
    if cid == 'C8_h2fma':
        (al,ah),(bl,bh),(cl,ch) = v['a'], v['b'], v['c']
        return struct.pack('<HH', FP(_h(al)*_h(bl)+_h(cl)), FP(_h(ah)*_h(bh)+_h(ch)))
    if cid == 'C9_fabs':        return struct.pack('<f', abs(v['a']))
    if cid == 'C10_orimm':      return struct.pack('<I', v['a'] | 0x100)
    if cid == 'C11_bf2':
        (al,ah),(bl,bh) = v['a'], v['b']
        return struct.pack('<HH', BF(_bf(al)*_bf(bl)), BF(_bf(ah)*_bf(bh)))
    if cid == 'C12_hcoord':
        (al,ah),(bl,bh) = v['a'], v['b']
        al,ah,bl,bh = _h(al),_h(ah),_h(bl),_h(bh)
        return struct.pack('<HH', FP(al*bl+ah), FP(ah*bh+al))
    if cid == 'C14_sfutan':
        import math
        a = v['a']; return struct.pack('<f', math.tan(a)+2.0**a+math.log2(a))
    raise KeyError(cid)

ORACLE_TOL = {'C14_sfutan': 2e-3}      # transcendental arm: relative tolerance

# --------------------------------------------------------------- families
def family_bytewise():
    """F1: every byte of every window, all 256 values, both input sets."""
    for cid, c in sorted(CARRIERS.items()):
        for lo, hi in c['win']:
            for pos in range(lo, hi):
                for val in range(256):
                    yield dict(family='BYTEWISE', carrier=cid, pos=pos, value=val)

# F2 GENERATED: instructions BUILT from the frozen rule model, never copied.
#   8-byte 0x11-group form (bf_add_dst / bf_mul_dst family)
def bf8(dst, sA, fA, sB, fB, opsel, selA=0, selB=0, dsthi=0, b5=0x00, b6=0xC0, b7=0x81):
    return bytes([((dst & 0xF) << 4) | 0x01,
                  ((sA & 0x7F) << 1) | (fA & 1),
                  opsel & 0xFF,
                  ((sB & 0x7F) << 1) | (fB & 1),
                  0x01 | ((dsthi & 1) << 2) | ((selA & 1) << 3) | ((selB & 1) << 4),
                  b5 & 0xFF, b6 & 0xFF, b7 & 0xFF])

GEN_OPS = {0x1c: 'add', 0x1d: 'mul'}

def family_generated():
    """F2: synthesised 0x11-group instructions spliced over C3's bf_add_dst.
    dst=2 is the register the carrier's store reads (any other dst must NOT
    reach the output -- that is the built-in falsifier)."""
    for opsel in (0x1c, 0x1d):
        for selA in (0, 1):
            for selB in (0, 1):
                for fA in (0, 1):
                    for fB in (0, 1):
                        yield dict(family='GENERATED', carrier='C3_bf_native', pos=32,
                                   gen=dict(dst=2, sA=0, fA=fA, sB=0, fB=fB, opsel=opsel,
                                            selA=selA, selB=selB, dsthi=0))
    for dst in range(16):                       # dst sweep: only dst==2 may reach out
        yield dict(family='GENERATED', carrier='C3_bf_native', pos=32,
                   gen=dict(dst=dst, sA=0, fA=0, sB=0, fB=0, opsel=0x1c, selA=0, selB=1, dsthi=0))
    for r in (0, 1, 2, 3, 4, 8, 16, 31, 32, 63, 64, 96, 126, 127):   # srcA register sweep
        yield dict(family='GENERATED', carrier='C3_bf_native', pos=32,
                   gen=dict(dst=2, sA=r, fA=0, sB=0, fB=0, opsel=0x1c, selA=0, selB=1, dsthi=0))
    for r in (0, 1, 2, 3, 4, 8, 16, 31, 32, 63, 64, 96, 126, 127):   # srcB register sweep
        yield dict(family='GENERATED', carrier='C3_bf_native', pos=32,
                   gen=dict(dst=2, sA=0, fA=0, sB=r, fB=0, opsel=0x1c, selA=0, selB=1, dsthi=0))
    yield dict(family='GENERATED', carrier='C3_bf_native', pos=32,          # dst-half select
               gen=dict(dst=2, sA=0, fA=0, sB=0, fB=0, opsel=0x1c, selA=0, selB=1, dsthi=1))
    # REFUTERS, pre-registered to FAIL the add oracle:
    yield dict(family='GENERATED', carrier='C3_bf_native', pos=32, refuter='opsel_fma_in_8B',
               gen=dict(dst=2, sA=0, fA=0, sB=0, fB=0, opsel=0x1e, selA=0, selB=1, dsthi=0))
    yield dict(family='GENERATED', carrier='C3_bf_native', pos=32, refuter='opsel_00',
               gen=dict(dst=2, sA=0, fA=0, sB=0, fB=0, opsel=0x00, selA=0, selB=1, dsthi=0))
    yield dict(family='GENERATED', carrier='C3_bf_native', pos=32, refuter='srcB_reg63',
               gen=dict(dst=2, sA=0, fA=0, sB=63, fB=0, opsel=0x1c, selA=0, selB=0, dsthi=0))

# F3 NUMERIC: unmutated carriers, adversarial bf16/fp16 input batteries.
BF_PAIRS = [   # (name, a_bits, b_bits) fed straight into the native bfloat carriers
 ('tie_even_down',   0x3F80, 0x3B80),   # 1.0 + 2^-8 : EXACT tie; RNE->0x3F80 RNA->0x3F81
 ('tie_even_up',     0x3F81, 0x3B80),   # tie; RNE->0x3F82 RNA->0x3F82 trunc->0x3F81
 ('tie_neg_even',    0xBF80, 0xBB80),
 ('below_tie',       0x3F80, 0x3B7F),
 ('above_tie',       0x3F80, 0x3B81),
 ('mul_tie_even',    0x3F83, 0x3FC0),   # product tie; RNE->0x3FC4 RNA->0x3FC5
 ('mul_tie_odd',     0x3F81, 0x3FC0),   # product tie; RNE->0x3FC2 trunc->0x3FC1
 ('sub_plus_sub',    0x0001, 0x0001),   # smallest bf16 subnormals
 ('sub_plus_norm',   0x0001, 0x3F80),
 ('sub_min_x2',      0x0002, 0x0002),
 ('norm_min',        0x0080, 0x0080),   # smallest normal
 ('ovf',             0x7F7F, 0x7F7F),   # max + max -> inf?
 ('ovf_near',        0x7F7E, 0x0080),
 ('inf_plus_ninf',   0x7F80, 0xFF80),   # -> NaN
 ('nan_prop',        0x7FC1, 0x3F80),
 ('nan_payload',     0x7FA5, 0x0000),
 ('zero_plus_nzero', 0x0000, 0x8000),
 ('nzero_plus_nzero',0x8000, 0x8000),
 ('one_plus_none',   0x3F80, 0xBF80),
 ('big_plus_small',  0x4F00, 0x3F80),
 ('fma_fused_probe', 0x3F81, 0x3F81),   # with c = -0x3F82 : fused != unfused
]
# fp16 fma triples chosen so RNE / RNA / truncate / FTZ / fused-vs-unfused separate.
FP_FMA_TRIPLES = [
 ('h_tie_even',   0x3C00, 0x3C00, 0x1000),   # 1 + 2^-11 exact tie -> RNE 0x3C00 RNA 0x3C01
 ('h_tie_up',     0x3C01, 0x3C00, 0x1000),   # tie -> RNE 0x3C02, trunc 0x3C01
 ('h_ovf_bound',  0x7BFF, 0x3C00, 0x4C00),   # 65504 + 16 = 65520 -> RNE inf
 ('h_ovf_below',  0x7BFF, 0x3C00, 0x4BFF),   # just under the boundary -> 65504
 ('h_sub_out',    0x0001, 0x3C00, 0x0000),   # smallest subnormal passthrough (FTZ?)
 ('h_sub_prod',   0x2400, 0x2400, 0x0000),   # 2^-11 * 2^-11 = 2^-22 subnormal product
 ('h_sub_sum',    0x0001, 0x3C00, 0x0001),   # subnormal + subnormal
 ('h_fused',      0x3C01, 0x3C01, 0xBC02),   # fused != unfused
 ('h_nan_c',      0x3C00, 0x3C00, 0x7E00),
 ('h_inf_prod',   0x7C00, 0x0000, 0x3C00),   # inf * 0 -> NaN
]
FP_PAIRS = [
 ('nan_a',      0x7E00, 0x4500), ('nan_b', 0x4200, 0x7E00),
 ('pzero_nzero',0x0000, 0x8000), ('nzero_pzero', 0x8000, 0x0000),
 ('inf_num',    0x7C00, 0x4500), ('ninf_num', 0xFC00, 0x4500),
 ('sub_sub',    0x0001, 0x0002), ('sub_zero', 0x0001, 0x0000),
 ('max_ovf',    0x7BFF, 0x7BFF), ('near_ovf', 0x7BFF, 0x1400),
 ('equal',      0x4200, 0x4200), ('neg_pair', 0xC200, 0xC500),
]

def family_numeric():
    for cid in ('C3_bf_native', 'C4_bfmul_native'):
        for nm, ab, bb in BF_PAIRS:
            yield dict(family='NUMERIC', carrier=cid, case=nm, bits=dict(a=ab, b=bb))
    for nm, ab, bb in BF_PAIRS:
        for cb in (0x0000, 0xBF82, 0x3F80, 0x0001, 0x7F80):
            yield dict(family='NUMERIC', carrier='C5_bffma_native', case='%s_c%04x' % (nm, cb),
                       bits=dict(a=ab, b=bb, c=cb))
    for cid in ('C6_hmin', 'C7_hmax'):
        for nm, ab, bb in FP_PAIRS:
            yield dict(family='NUMERIC', carrier=cid, case=nm, bits=dict(a=ab, b=bb))
    for nm, ab, bb in FP_PAIRS:
        for cb in (0x0000, 0x3C00, 0x0001, 0x7C00):
            yield dict(family='NUMERIC', carrier='C8_h2fma', case='%s_c%04x' % (nm, cb),
                       bits=dict(a=ab, b=bb, c=cb))
    for nm, ab, bb, cb in FP_FMA_TRIPLES:
        yield dict(family='NUMERIC', carrier='C8_h2fma', case=nm, bits=dict(a=ab, b=bb, c=cb))

FAMILIES = {'BYTEWISE': family_bytewise, 'GENERATED': family_generated, 'NUMERIC': family_numeric}

def matrix_json():
    m = {}
    for k, f in sorted(FAMILIES.items()):
        m[k] = list(f())
    return json.dumps(m, sort_keys=True, separators=(',', ':'))

if __name__ == '__main__':
    j = matrix_json()
    counts = {k: len(v) for k, v in json.loads(j).items()}
    print(json.dumps(counts, indent=1))
    print('cases_total', sum(counts.values()))
    print('matrix_sha256', hashlib.sha256(j.encode()).hexdigest())
