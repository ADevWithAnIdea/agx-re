#!/usr/bin/env python3
# probe.py -- EXP-0006 reusable splice-and-observe harness for the float 2-source
# ALU (falu2) operand encoding. Runs ON THE DEVICE.
#
# Compiles OUR OWN MSL to a binary archive (shdump), locates _agc.main, walks it
# into instructions with the EXP-0005 length rule, finds the target falu2 (0x09)
# instruction, and lets a caller splice arbitrary bytes at absolute _agc.main
# offsets, dispatch on the real A18 Pro GPU (agxrun_persist via persistrun), and
# read back float32/float16 outputs.
#
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed; no Apple
# binary is disassembled or introspected.

import os, struct, subprocess, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

# ---- EXP-0005 instruction-length rule (copied; our own fact) ----------------
def instr_length(buf, off=0):
    b0 = buf[off]; lo = b0 & 0x0f
    if b0 == 0x0e: return 4
    if lo == 0x0c: return 4
    if lo == 0x07: return 14
    if b0 == 0x09: return 8 if (buf[off+2] & 0x02) else 6
    if b0 == 0x0b: return 10
    if b0 == 0x12: return 6
    return None

def tokenize(main):
    out = []; off = 0; n = len(main)
    while off < n:
        L = instr_length(main, off)
        if L is None:
            out.append((off, None, bytes(main[off:]))); break
        out.append((off, L, bytes(main[off:off+L]))); off += L
    return out

def f32(vals): return b"".join(struct.pack("<f", x) for x in vals)
def f16(vals):
    import numpy  # not always present; fall back
    return None
def floats_from(raw, half=False):
    if half:
        import struct as _s
        return [ _half_to_float(_s.unpack_from("<H", raw, i)[0]) for i in range(0, len(raw)-1, 2) ]
    return [struct.unpack_from("<f", raw, i)[0] for i in range(0, len(raw)-3, 4)]

def _half_to_float(h):
    s = (h >> 15) & 1; e = (h >> 10) & 0x1f; m = h & 0x3ff
    if e == 0:
        v = (m / 1024.0) * (2.0 ** -14)
    elif e == 31:
        v = float('inf') if m == 0 else float('nan')
    else:
        v = (1 + m/1024.0) * (2.0 ** (e - 15))
    return -v if s else v
def _float_to_half(f):
    import struct as _s
    # round-to-nearest via numpy-free path: pack float32, decompose
    b = _s.unpack("<I", _s.pack("<f", f))[0]
    s = (b >> 31) & 1; e = (b >> 23) & 0xff; m = b & 0x7fffff
    if e == 0: he = 0; hm = 0
    elif e == 0xff: he = 31; hm = (1 if m else 0)
    else:
        ne = e - 127 + 15
        if ne <= 0: he = 0; hm = 0
        elif ne >= 31: he = 31; hm = 0
        else: he = ne; hm = m >> 13
    return (s << 15) | (he << 10) | hm
def h16(vals):
    return b"".join(struct.pack("<H", _float_to_half(x)) for x in vals)


class Probe:
    def __init__(self, source, function="k", fast_math=False, workdir="work",
                 shdump="./shdump", agxparse="./agxparse.py",
                 agxrun_persist="./agxrun_persist", persistrun="./persistrun.py"):
        self.source = source; self.function = function; self.fast_math = fast_math
        self.workdir = workdir; os.makedirs(workdir, exist_ok=True)
        self.shdump = shdump
        self.agxparse = load_mod("agxparse", agxparse)
        self.PersistRunner = load_mod("persistrun", persistrun).PersistRunner
        self.agxrun_persist = agxrun_persist
        self._build()
        self.runner = self.PersistRunner(source=source, function=function,
                                         fast_math=fast_math,
                                         agxrun_persist=agxrun_persist)

    def _build(self):
        base = os.path.join(self.workdir, "base.bin")
        cmd = [self.shdump, "-o", base, "-f", self.function]
        if not self.fast_math: cmd.append("--no-fast-math")
        cmd.append(self.source)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(base):
            raise RuntimeError("shdump failed: " + r.stderr)
        with open(base, "rb") as f: self.basebuf = f.read()
        loc = self.agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None: raise RuntimeError("no _agc.main")
        self.region_off, self.region_len = loc
        _, pieces = self.agxparse.extract_agx(self.basebuf)
        self.main = pieces["_agc.main"]
        self.toks = tokenize(self.main)

    def find_falu2(self, which=0):
        """Return the _agc.main offset of the which-th 6-byte 0x09 instruction."""
        seen = 0
        for (off, L, b) in self.toks:
            if L == 6 and b[0] == 0x09:
                if seen == which: return off
                seen += 1
        raise RuntimeError("no falu2 (6-byte 0x09) instruction found")

    def find_falu(self, which=0):
        """Return offset of which-th 0x09 instruction (6 or 8 byte)."""
        seen = 0
        for (off, L, b) in self.toks:
            if b and b[0] == 0x09:
                if seen == which: return off
                seen += 1
        raise RuntimeError("no 0x09 instruction found")

    def run(self, overrides, ins, outs, grid=None, tg=None, timeout=6.0, half_out=False):
        """overrides: {abs_main_offset: byte_value}; ins: {idx: [floats] or ('h',[floats]) or bytes};
        outs: {idx: nelem}. Returns {idx: [floats]} plus '_status'."""
        spliced = bytearray(self.basebuf)
        for off, val in overrides.items():
            spliced[self.region_off + off] = val & 0xff
        arch = os.path.join(self.workdir, "sp.bin")
        with open(arch, "wb") as f: f.write(spliced)
        inpaths = {}
        for idx, v in ins.items():
            p = os.path.join(self.workdir, f"in_{idx}.bin")
            if isinstance(v, bytes): data = v
            elif isinstance(v, tuple) and v[0] == 'h': data = h16(v[1])
            else: data = f32(v)
            with open(p, "wb") as f: f.write(data)
            inpaths[idx] = p
        # element size: half outputs are 2 bytes, else 4
        esz = 2 if half_out else 4
        outspec = {idx: nel * esz for idx, nel in outs.items()}
        g = grid if grid is not None else 4
        t = tg if tg is not None else g
        resp = self.runner.request(archive=arch, grid=g, tg=t, ins=inpaths,
                                   outs=outspec, timeout=timeout)
        res = {"_status": resp["status"], "_error": resp.get("error")}
        for idx, nel in outs.items():
            raw = resp["outs"].get(idx, b"")
            res[idx] = floats_from(raw, half=half_out) if raw else []
            res[f"_raw{idx}"] = raw.hex()
        return res

    def close(self):
        try: self.runner.close()
        except Exception: pass
