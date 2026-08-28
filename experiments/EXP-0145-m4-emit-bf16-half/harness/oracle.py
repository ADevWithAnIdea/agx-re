#!/usr/bin/env python3
"""EXP-0145 HOST-COMPUTED oracles and input sets. Nothing here reads the GPU.

Pre-registered numeric assumptions (tested by the ROUNDING family, not assumed):
  R1  f32 -> bf16 conversion rounds to nearest, ties to EVEN.
  R2  a bfloat ALU op computes on bf16 operands and rounds the result to bf16
      once, RNE.  Every BYTEWISE/GENERATED input pair is chosen so the exact
      result is bf16-representable, so R2 cannot silently absorb an error.
  R3  a fp16 (half) ALU op computes on fp16 operands and rounds to fp16, RNE.
All oracle values are produced from these rules in Python, never from the GPU.
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from carriers import bf16_rne, bf16_to_f, fp16_bits, fp16_to_f, f32_bits  # noqa: E402

def u16(vals):  return b''.join(struct.pack('<H', v & 0xFFFF) for v in vals)
def u32(vals):  return b''.join(struct.pack('<I', v & 0xFFFFFFFF) for v in vals)
def f32b(vals): return b''.join(struct.pack('<f', float(v)) for v in vals)

N = 8   # elements per input buffer (only element 0 is read; grid = 1)

# ------------------------------------------------------------------ inputs
# Two input sets per carrier. Both operands change between sets, so a value
# that is CONSTANT across sets is distinguishable from one that tracks a or b.
INPUTS = {
 'f32x2':    {'S1': {'a': 3.0,  'b': 5.0}, 'S2': {'a': 17.0, 'b': 9.0}},
 'bf16x2':   {'S1': {'a': 3.0,  'b': 5.0}, 'S2': {'a': 17.0, 'b': 9.0}},
 'bf16x3':   {'S1': {'a': 3.0,  'b': 5.0, 'c': 2.0},  'S2': {'a': 17.0, 'b': 9.0, 'c': 4.0}},
 'fp16x2':   {'S1': {'a': 3.0,  'b': 5.0}, 'S2': {'a': 17.0, 'b': 9.0}},
 'fp16x3v2': {'S1': {'a': (3.0, 7.0), 'b': (5.0, 2.0), 'c': (1.0, 4.0)},
              'S2': {'a': (17.0, 6.0), 'b': (9.0, 3.0), 'c': (4.0, 5.0)}},
 'f32x1':    {'S1': {'a': -2.5}, 'S2': {'a': 6.75}},
 'u32x1':    {'S1': {'a': 0x12345678}, 'S2': {'a': 0x000000FF}},
}

def write_inputs(io, setname, dirpath, tag=''):
    """Materialise the input buffers for (io kind, input set) -> {slot: path}."""
    v = INPUTS[io][setname]; out = {}
    def w(slot, data):
        p = os.path.join(dirpath, 'in_%s_%s%s_%d.bin' % (io, setname, tag, slot))
        open(p, 'wb').write(data); out[slot] = p
    if io in ('f32x2',):
        w(1, f32b([v['a']] * N)); w(2, f32b([v['b']] * N))
    elif io == 'bf16x2':
        w(1, u16([bf16_rne(v['a'])] * N)); w(2, u16([bf16_rne(v['b'])] * N))
    elif io == 'bf16x3':
        w(1, u16([bf16_rne(v['a'])] * N)); w(2, u16([bf16_rne(v['b'])] * N)); w(3, u16([bf16_rne(v['c'])] * N))
    elif io == 'fp16x2':
        w(1, u16([fp16_bits(v['a'])] * N)); w(2, u16([fp16_bits(v['b'])] * N))
    elif io == 'fp16x3v2':
        for slot, key in ((1, 'a'), (2, 'b'), (3, 'c')):
            lo, hi = v[key]; w(slot, u16([fp16_bits(lo), fp16_bits(hi)] * N))
    elif io == 'f32x1':
        w(1, f32b([v['a']] * N))
    elif io == 'u32x1':
        w(1, u32([v['a']] * N))
    else:
        raise ValueError(io)
    return out

# ------------------------------------------------------- candidate library
# Per (carrier, input set), a dict {name: expected output bytes}. Used to
# CLASSIFY every swept value's observed output. Purely host-computed.
def _bf(x):   return bf16_to_f(bf16_rne(x))
def _bfb(x):  return bf16_rne(x)
def _h(x):    return fp16_to_f(fp16_bits(x))

def candidates(io, op, setname):
    v = INPUTS[io][setname]; c = {}
    if io in ('f32x2', 'bf16x2'):
        a, b = _bf(v['a']), _bf(v['b'])
        raw = {'a+b': a + b, 'a*b': a * b, 'a-b': a - b, 'b-a': b - a,
               'a': a, 'b': b, 'a+a': a + a, 'b+b': b + b, 'a*a': a * a, 'b*b': b * b,
               '-a': -a, '-b': -b, 'zero': 0.0,
               'fp16A+b': fp16_to_f(_bfb(v['a'])) + b, 'a+fp16B': a + fp16_to_f(_bfb(v['b'])),
               'fp16A+fp16B': fp16_to_f(_bfb(v['a'])) + fp16_to_f(_bfb(v['b'])),
               'fp16A*b': fp16_to_f(_bfb(v['a'])) * b, 'a*fp16B': a * fp16_to_f(_bfb(v['b'])),
               'fp16A': fp16_to_f(_bfb(v['a'])), 'fp16B': fp16_to_f(_bfb(v['b']))}
        for k, x in raw.items():
            c[k] = struct.pack('<f', x) if io == 'f32x2' else struct.pack('<H', bf16_rne(x))
    elif io == 'bf16x3':
        a, b, cc = _bf(v['a']), _bf(v['b']), _bf(v['c'])
        raw = {'a*b+c': a * b + cc, 'a*b': a * b, 'a+b': a + b, 'a+c': a + cc, 'b+c': b + cc,
               'a': a, 'b': b, 'c': cc, 'a*a+c': a * a + cc, 'b*b+c': b * b + cc,
               'a*b+a': a * b + a, 'a*b+b': a * b + b, 'a*b-c': a * b - cc, 'zero': 0.0}
        for k, x in raw.items():
            c[k] = struct.pack('<H', bf16_rne(x))
    elif io == 'fp16x2':
        a, b = _h(v['a']), _h(v['b'])
        raw = {'min': min(a, b), 'max': max(a, b), 'a': a, 'b': b, 'a+b': a + b,
               'a*b': a * b, 'a-b': a - b, 'zero': 0.0}
        for k, x in raw.items():
            c[k] = struct.pack('<e', x)
    elif io == 'fp16x3v2':
        (al, ah), (bl, bh), (cl, ch) = v['a'], v['b'], v['c']
        al, ah, bl, bh, cl, ch = map(_h, (al, ah, bl, bh, cl, ch))
        def pk(lo, hi): return struct.pack('<e', lo) + struct.pack('<e', hi)
        c['fma2']      = pk(al * bl + cl, ah * bh + ch)
        c['lo_only']   = pk(al * bl + cl, 0.0)
        c['hi_zero_lo_ok'] = pk(al * bl + cl, 0.0)
        c['hi_alt_ab'] = pk(al * bl + cl, ah * bh)
        c['hi_alt_lo'] = pk(al * bl + cl, al * bl + cl)
        c['hi_add']    = pk(al * bl + cl, ah + bh)
        c['hi_mul']    = pk(al * bl + cl, ah * bh)
        c['zero']      = b'\x00' * 4
    elif io == 'f32x1':
        a = v['a']
        for k, x in {'abs': abs(a), 'neg': -a, 'mov': a, 'zero': 0.0}.items():
            c[k] = struct.pack('<f', x)
    elif io == 'u32x1':
        a = v['a']
        for k, x in {'or100': a | 0x100, 'mov': a, 'and100': a & 0x100,
                     'xor100': a ^ 0x100, 'zero': 0}.items():
            c[k] = struct.pack('<I', x & 0xFFFFFFFF)
    return c

def classify(io, op, setname, out_bytes):
    if out_bytes is None:
        return None
    for name, exp in candidates(io, op, setname).items():
        if exp == out_bytes:
            return name
    return 'unknown'
