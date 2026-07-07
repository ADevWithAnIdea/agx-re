#!/usr/bin/env python3
# intprobe.py -- EXP-0007 splice-and-observe harness for the INTEGER 2-source
# ALU (byte0 0x9f). Runs ON THE DEVICE. Sibling of EXP-0006 probe.py but with
# int32/uint32 I/O instead of float.
#
# Compiles OUR OWN MSL to a binary archive (shdump), locates _agc.main, walks it
# into structural tokens (preamble / device-load(0x67) / ALU / device-store(0xe7)
# / stop(0x0e)), exposes the ALU-instruction region, and lets a caller splice
# arbitrary bytes at absolute _agc.main offsets, dispatch on the real A18 Pro GPU
# (agxrun_persist via persistrun), and read back int32/uint32 outputs.
#
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed; no Apple
# binary is disassembled or introspected.

import os, struct, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def i32(vals):
    return b"".join(struct.pack("<i", int(x)) for x in vals)
def u32(vals):
    return b"".join(struct.pack("<I", int(x) & 0xffffffff) for x in vals)
def ints_from(raw, signed=True):
    fmt = "<i" if signed else "<I"
    return [struct.unpack_from(fmt, raw, i)[0] for i in range(0, len(raw) - 3, 4)]

# ---- structural tokenizer (op-agnostic ALU locator; from EXP-0006 analyze.py).
# loads=0x67/14B, stores=0xe7/14B, stop=0x0e/4B, preamble low-nibble 0xC /4B.
# The ALU is the byte gap between the load block and the store block; this makes
# NO assumption about the integer ALU length or byte0 -- exactly what we need to
# discover the 0x9f length rule.
def structural_tokens(main):
    toks = []; off = 0; n = len(main)
    if (main[0] & 0x0f) == 0x0c:
        toks.append(("preamble", 0, 4, bytes(main[0:4]))); off = 4
    while off < n and main[off] == 0x67:
        toks.append(("load", off, 14, bytes(main[off:off+14]))); off += 14
    alu_start = off
    while off < n and main[off] not in (0xe7, 0x0e):
        off += 1
    if off > alu_start:
        toks.append(("ALU", alu_start, off - alu_start, bytes(main[alu_start:off])))
    while off < n and main[off] == 0x67:  # sometimes a load between ops
        toks.append(("load", off, 14, bytes(main[off:off+14]))); off += 14
    while off < n and main[off] == 0xe7:
        toks.append(("store", off, 14, bytes(main[off:off+14]))); off += 14
    if off < n and main[off] == 0x0e:
        toks.append(("stop", off, 4, bytes(main[off:off+4]))); off += 4
    if off < n:
        toks.append(("REST", off, n - off, bytes(main[off:])))
    return toks


class IntProbe:
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
        self.toks = structural_tokens(self.main)

    def alu(self, which=0):
        """Return (off, bytes) of the which-th ALU token (byte gap between load
        and store blocks)."""
        alus = [t for t in self.toks if t[0] == "ALU"]
        return alus[which][1], alus[which][3]

    def run(self, overrides, ins, outs, grid=None, tg=None, timeout=6.0,
            signed=True):
        """overrides: {abs_main_offset: byte_value}; ins: {idx: [ints] or ('u',[ints]) or bytes};
        outs: {idx: nelem}. Returns {idx: [ints]} plus '_status'/'_rawIDX'."""
        spliced = bytearray(self.basebuf)
        for off, val in overrides.items():
            spliced[self.region_off + off] = val & 0xff
        arch = os.path.join(self.workdir, "sp.bin")
        with open(arch, "wb") as f: f.write(spliced)
        inpaths = {}
        for idx, v in ins.items():
            p = os.path.join(self.workdir, f"in_{idx}.bin")
            if isinstance(v, bytes): data = v
            elif isinstance(v, tuple) and v[0] == 'u': data = u32(v[1])
            else: data = i32(v)
            with open(p, "wb") as f: f.write(data)
            inpaths[idx] = p
        outspec = {idx: nel * 4 for idx, nel in outs.items()}
        g = grid if grid is not None else 4
        t = tg if tg is not None else g
        resp = self.runner.request(archive=arch, grid=g, tg=t, ins=inpaths,
                                   outs=outspec, timeout=timeout)
        res = {"_status": resp["status"], "_error": resp.get("error")}
        for idx, nel in outs.items():
            raw = resp["outs"].get(idx, b"")
            res[idx] = ints_from(raw, signed=signed) if raw else []
            res[f"_raw{idx}"] = raw.hex()
        return res

    def close(self):
        try: self.runner.close()
        except Exception: pass
