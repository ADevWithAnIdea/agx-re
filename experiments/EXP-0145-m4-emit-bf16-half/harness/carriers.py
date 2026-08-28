#!/usr/bin/env python3
"""EXP-0145 carrier table + baseline derivation.

Every carrier is a .metal file in ../kernels/ that WE authored. For each one
this module compiles it with tools/shdump, locates `_agc.main`, disassembles
it with tools/agx-isa (READ-ONLY), and LOCATES the target instruction BY
MNEMONIC -- never by a hard-coded byte offset -- so a compiler change is
detected as a baseline mismatch rather than silently sweeping the wrong bytes.

CLEAN-ROOM: OWN-SHADER. Only our own compiled shader bytes are inspected.
"""
import os, struct, subprocess, sys, importlib.util

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
EXP  = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

def _lm(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

agxparse = _lm('agxparse', os.path.join(REPO, 'tools', 'shdump', 'agxparse.py'))
PersistRunner = _lm('persistrun', os.path.join(REPO, 'tools', 'agxtest', 'persistrun.py')).PersistRunner
sys.path.insert(0, os.path.join(REPO, 'tools', 'agx-isa'))
import isadb  # noqa: E402  (read-only: disassemble/assemble)

# ---------------------------------------------------------------- number fmt
def bf16_rne(x):
    """f32 -> bf16 bits, round-to-nearest-EVEN. This is the pre-registered
    rounding assumption for every bfloat oracle in this experiment; the
    ROUNDING family tests it directly with exact-tie inputs."""
    u = struct.unpack('<I', struct.pack('<f', float(x)))[0]
    if (u & 0x7F800000) == 0x7F800000 and (u & 0x7FFFFF):   # NaN -> quiet NaN
        return ((u >> 16) | 0x0040) & 0xFFFF
    lsb = (u >> 16) & 1
    return ((u + 0x7FFF + lsb) >> 16) & 0xFFFF

def bf16_to_f(bits):
    return struct.unpack('<f', struct.pack('<I', (bits & 0xFFFF) << 16))[0]

def fp16_bits(x):
    return struct.unpack('<H', struct.pack('<e', float(x)))[0]

def fp16_to_f(bits):
    return struct.unpack('<e', struct.pack('<H', bits & 0xFFFF))[0]

def f32_bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]

# ---------------------------------------------------------------- carriers
# name -> (source, target mnemonic, occurrence index, buffer writer id, out bytes)
CARRIERS = {
  'C1_bf_f32':      dict(src='c_bf_f32.metal',       instr='bf_add_dst',  occ=0, io='f32x2',  outb=4,  op='add'),
  'C2_bfmul_f32':   dict(src='c_bfmul_f32.metal',    instr='bf_mul_dst',  occ=0, io='f32x2',  outb=4,  op='mul'),
  'C3_bf_native':   dict(src='c_bf_native.metal',    instr='bf_alu',      occ=0, io='bf16x2', outb=2,  op='add'),
  'C4_bfmul_native':dict(src='c_bfmul_native.metal', instr='bf_alu',      occ=0, io='bf16x2', outb=2,  op='mul'),
  'C5_bffma_native':dict(src='c_bffma_native.metal', instr='bf_fma_dst',  occ=0, io='bf16x3', outb=2,  op='fma'),
  'C6_hmin':        dict(src='c_hmin.metal',         instr='hminmax',     occ=0, io='fp16x2', outb=2,  op='min'),
  'C7_hmax':        dict(src='c_hmax.metal',         instr='hminmax',     occ=0, io='fp16x2', outb=2,  op='max'),
  'C8_h2fma':       dict(src='c_h2fma.metal',        instr='h_alu_hi',    occ=0, io='fp16x3v2',outb=4, op='fma2'),
  'C9_fabs':        dict(src='c_fabs.metal',         instr='funary',      occ=0, io='f32x1',  outb=4,  op='abs'),
  'C10_orimm':      dict(src='c_orimm.metal',        instr='funary_imm',  occ=0, io='u32x1',  outb=4,  op='orimm'),
}

def compile_carrier(src_path, out_path):
    r = subprocess.run([os.path.join(EXP, 'work', 'bin', 'shdump'), '-o', out_path,
                        '-f', 'k', '--no-fast-math', src_path],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError('shdump failed: ' + r.stderr + r.stdout)
    return out_path

def load(binpath):
    buf = open(binpath, 'rb').read()
    off, ln = agxparse.locate_region(buf, '_agc.main')
    _, pieces = agxparse.extract_agx(buf)
    return buf, off, pieces['_agc.main']

def locate_instr(main, mnemonic, occ=0):
    """Return (byte offset, length) of the occ-th `mnemonic` in main, by
    disassembling with tools/agx-isa. Raises if absent."""
    recs, left = isadb.disassemble(main)
    o = 0; seen = 0
    for r in recs:
        if r['mnemonic'] == mnemonic:
            if seen == occ:
                return o, r['length']
            seen += 1
        o += r['length']
    raise RuntimeError('mnemonic %s occurrence %d not found (leftover=%d)' % (mnemonic, occ, len(left)))
