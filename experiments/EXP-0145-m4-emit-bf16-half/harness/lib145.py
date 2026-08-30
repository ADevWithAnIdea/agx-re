#!/usr/bin/env python3
"""EXP-0145 shared runner library.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Only bytes produced by compiling OUR OWN
MSL (kernels/*.metal) are inspected, spliced and executed.  No Apple binary is
disassembled, dumped or introspected.

Design points that are BINDING (protocol 7 of experiments/FIELD-SWEEP-PROTOCOL.md):
  * unique splice-archive path per request (the file is deleted after the
    response, so a 60k-case sweep does not need 800 GB of disk, but no path is
    ever reused -> Metal cannot serve a cached library);
  * the read-back buffers are POISONED with 0xDEADBEEF by binding the same
    buffer index as BOTH an input (a poison file) and an output;
  * an INTEGRITY SENTINEL on an independent path (buffer 4, stored 0xA5A5A5A5
    by every carrier) gives a three-way ran / did-not-run / corrupted verdict;
  * every fault is re-run before it is believed, and the OS fault-classification
    string is recorded verbatim;
  * the unmutated baseline is re-validated periodically; an all-attempts
    baseline failure stops the run (cascade, not data).
"""
import os, sys, json, struct, hashlib, importlib.util, time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP  = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(EXP, '..', '..'))

def _lm(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

agxparse      = _lm('agxparse', os.path.join(REPO, 'tools', 'shdump', 'agxparse.py'))
PersistRunner = _lm('persistrun', os.path.join(REPO, 'tools', 'agxtest', 'persistrun.py')).PersistRunner

POISON = 0xDEADBEEF
SENT   = 0xA5A5A5A5
# The sentinel + tail anchor every carrier ends with, used to bound the
# instruction region WITHOUT a hard-coded offset (a compiler change moves the
# anchor and is caught as a baseline mismatch, not silently swept).
ANCHORS = [bytes.fromhex('0ca502a416002d0d'), bytes.fromhex('1ca502a416002d0d'),
           bytes.fromhex('4ca502a416002d0d')]

# ---------------------------------------------------------------- numbers
def bf16_rne(x):
    """f32 -> bf16 bits, round-to-nearest-EVEN (pre-registered assumption R1)."""
    x = float(x)
    try:
        u = struct.unpack('<I', struct.pack('<f', x))[0]
    except OverflowError:                 # beyond f32 range -> signed infinity
        return 0xFF80 if x < 0 else 0x7F80
    if (u & 0x7F800000) == 0x7F800000 and (u & 0x7FFFFF):
        return ((u >> 16) | 0x0040) & 0xFFFF
    lsb = (u >> 16) & 1
    return ((u + 0x7FFF + lsb) >> 16) & 0xFFFF

def bf16_to_f(b):  return struct.unpack('<f', struct.pack('<I', (b & 0xFFFF) << 16))[0]
def f32_bits(x):   return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def bits_f32(u):   return struct.unpack('<f', struct.pack('<I', u & 0xFFFFFFFF))[0]

def fp16_rne(x):
    """f64/f32 -> fp16 bits, exact integer round-to-nearest-EVEN, INF on
    overflow.  Written out rather than using struct.pack('<e') because that
    raises OverflowError on the fp16 overflow boundary (the bug that cost
    EXP-0147 its run01)."""
    x = float(x)
    u = struct.unpack('<Q', struct.pack('<d', x))[0]
    s = (u >> 63) & 1
    e = (u >> 52) & 0x7FF
    m = u & ((1 << 52) - 1)
    if e == 0x7FF:
        if m: return (s << 15) | 0x7E00              # quiet NaN
        return (s << 15) | 0x7C00                    # inf
    if e == 0 and m == 0: return (s << 15)           # +-0
    E = e - 1023
    sig = (1 << 52) | m if e else m                  # 53-bit significand
    if e == 0: E = -1022
    # target: value = sig * 2^(E-52); fp16 has 11-bit significand, emin -14
    #   normal:   exponent field 1..30, significand 1.f * 2^(E)
    if E < -30:                                       # far below the last subnormal
        return (s << 15)
    if E < -14:                                       # subnormal: ulp is 2^-24
        shift = 28 - E                                # == 52 - 10 - (E + 14)
    else:
        shift = 52 - 10
    if E > 15:
        return (s << 15) | 0x7C00                    # overflow -> inf
    q = sig >> shift
    rem = sig & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    if rem > half or (rem == half and (q & 1)): q += 1
    if E < -14:
        # q may carry to 0x400, which IS the smallest normal bit pattern.
        return (s << 15) | q
    # q is 11 bits (1.f); may carry to 12
    ee = E + 15
    if q >> 11:
        q >>= 1; ee += 1
    if ee >= 31: return (s << 15) | 0x7C00
    return (s << 15) | (ee << 10) | (q & 0x3FF)

def fp16_to_f(b):
    b &= 0xFFFF
    s = (b >> 15) & 1; e = (b >> 10) & 0x1F; m = b & 0x3FF
    if e == 0x1F:
        return float('nan') if m else (float('-inf') if s else float('inf'))
    if e == 0:
        v = m * 2.0 ** -24
    else:
        v = (1024 + m) * 2.0 ** (e - 25)
    return -v if s else v

# ---------------------------------------------------------------- shader io
def load_main(binpath):
    buf = open(binpath, 'rb').read()
    off, ln = agxparse.locate_region(buf, '_agc.main')
    _, pieces = agxparse.extract_agx(buf)
    return buf, off, pieces['_agc.main']

def find_anchor(main):
    for a in ANCHORS:
        i = main.find(a)
        if i >= 0: return i, a
    raise RuntimeError('sentinel anchor not found -- compiler output changed')

def sha(b): return hashlib.sha256(b).hexdigest()

def write_buf(path, data):
    open(path, 'wb').write(data); return path

def poison_file(path, nbytes):
    return write_buf(path, struct.pack('<I', POISON) * (nbytes // 4))

# ---------------------------------------------------------------- runner
class Arm:
    """One carrier under test: owns a PersistRunner, the poisoned buffers,
    the baseline bytes, and the unique-archive-path counter."""
    def __init__(self, name, src, binpath, ins_sets, out_bytes, grid=1, tg=1,
                 spdir=None, timeout=8.0):
        self.name, self.src, self.binpath = name, src, binpath
        self.ins_sets = ins_sets           # {'S1': {idx: path}, ...}
        self.out_bytes = out_bytes
        self.grid, self.tg, self.timeout = grid, tg, timeout
        self.buf, self.off, self.main = load_main(binpath)
        self.anchor_at, _ = find_anchor(self.main)
        self.spdir = spdir or os.path.join(EXP, 'work', 'sp')
        os.makedirs(self.spdir, exist_ok=True)
        self.seq = 0
        self.hangs = 0
        self.poison_out  = poison_file(os.path.join(self.spdir, name + '_p0.bin'), out_bytes)
        self.poison_sent = poison_file(os.path.join(self.spdir, name + '_p4.bin'), 8)
        self.r = PersistRunner(source=src, function='k', fast_math=False,
                               agxrun_persist=os.path.join(EXP, 'work', 'bin', 'agxrun_persist'))

    def run(self, spliced, setname):
        self.seq += 1
        path = os.path.join(self.spdir, '%s_%08d.bin' % (self.name, self.seq))
        open(path, 'wb').write(spliced)
        ins = dict(self.ins_sets[setname])
        ins[0] = self.poison_out
        ins[4] = self.poison_sent
        try:
            resp = self.r.request(archive=path, grid=self.grid, tg=self.tg, ins=ins,
                                  outs={0: self.out_bytes, 4: 8}, timeout=self.timeout)
        finally:
            try: os.unlink(path)
            except OSError: pass
        out = resp['outs'].get(0)
        sent = resp['outs'].get(4)
        st = resp['status']
        if st == 'HANG': self.hangs += 1
        # three-way sentinel verdict
        sv = 'absent'
        if sent and len(sent) >= 8:
            s0, s1 = struct.unpack('<II', sent[:8])
            if s0 == SENT and s1 == POISON: sv = 'clean'
            elif s0 == SENT:                sv = 'ran_perturbed'
            elif s0 == POISON:              sv = 'not_run'
            else:                           sv = 'corrupt'
        return {'status': st, 'out': out.hex() if out else '', 'sent': sv,
                'error': resp.get('error'), 'restarted': resp.get('restarted', False)}

    def splice(self, pos, value):
        b = bytearray(self.buf); b[self.off + pos] = value; return bytes(b)

    def splice_bytes(self, pos, newbytes):
        b = bytearray(self.buf); b[self.off + pos:self.off + pos + len(newbytes)] = newbytes
        return bytes(b)

    def close(self):
        try: self.r.close()
        except Exception: pass
