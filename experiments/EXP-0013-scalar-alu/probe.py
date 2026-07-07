#!/usr/bin/env python3
# probe.py -- EXP-0013 splice-and-observe harness (runs ON THE DEVICE).
# Generalizes EXP-0007 intprobe with per-buffer dtypes: 'f'=float32, 'i'=int32,
# 'u'=uint32, 'h'=float16. Compiles OUR OWN MSL (shdump), locates _agc.main,
# structurally tokenizes it (preamble/load/ALU/store/stop), and lets a caller
# splice bytes at absolute _agc.main offsets and dispatch on the real A18 Pro GPU.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, struct, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def pack(dtype, vals):
    if isinstance(vals, bytes): return vals
    fmt = {'f':'<f','i':'<i','u':'<I','h':'<e'}[dtype]
    if dtype == 'u': return b"".join(struct.pack('<I', int(x) & 0xffffffff) for x in vals)
    if dtype == 'i': return b"".join(struct.pack('<i', int(x)) for x in vals)
    return b"".join(struct.pack(fmt, float(x) if dtype in 'fh' else int(x)) for x in vals)

def unpack(dtype, raw, n=None):
    sz = {'f':4,'i':4,'u':4,'h':2}[dtype]
    fmt = {'f':'<f','i':'<i','u':'<I','h':'<e'}[dtype]
    cnt = (len(raw)//sz) if n is None else n
    return [struct.unpack_from(fmt, raw, i*sz)[0] for i in range(cnt)]

# structural tokenizer (op-agnostic ALU locator). Makes NO assumption about the
# ALU length or byte0 -- the ALU is the byte gap between the load and store blocks.
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
    while off < n and main[off] == 0x67:
        toks.append(("load", off, 14, bytes(main[off:off+14]))); off += 14
    while off < n and main[off] == 0xe7:
        toks.append(("store", off, 14, bytes(main[off:off+14]))); off += 14
    if off < n and main[off] == 0x0e:
        toks.append(("stop", off, 4, bytes(main[off:off+4]))); off += 4
    if off < n:
        toks.append(("REST", off, n - off, bytes(main[off:])))
    return toks


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
        self.toks = structural_tokens(self.main)

    def alu(self, which=0):
        alus = [t for t in self.toks if t[0] == "ALU"]
        return alus[which][1], alus[which][3]

    def run(self, overrides, ins, outs, grid=None, tg=None, timeout=6.0):
        """overrides: {abs_main_offset: byte}; ins: {idx:(dtype,[vals])};
        outs: {idx:(dtype,nelem)}. Returns {idx:[vals]} + '_status'/'_rawIDX'."""
        spliced = bytearray(self.basebuf)
        for off, val in overrides.items():
            spliced[self.region_off + off] = val & 0xff
        arch = os.path.join(self.workdir, "sp.bin")
        with open(arch, "wb") as f: f.write(spliced)
        inpaths = {}
        for idx, (dt, v) in ins.items():
            p = os.path.join(self.workdir, f"in_{idx}.bin")
            with open(p, "wb") as f: f.write(pack(dt, v))
            inpaths[idx] = p
        outspec = {}
        for idx, (dt, nel) in outs.items():
            sz = {'f':4,'i':4,'u':4,'h':2}[dt]
            outspec[idx] = nel * sz
        g = grid if grid is not None else 4
        t = tg if tg is not None else g
        resp = self.runner.request(archive=arch, grid=g, tg=t, ins=inpaths,
                                   outs=outspec, timeout=timeout)
        res = {"_status": resp["status"], "_error": resp.get("error")}
        for idx, (dt, nel) in outs.items():
            raw = resp["outs"].get(idx, b"")
            res[idx] = unpack(dt, raw, nel) if raw else []
            res[f"_raw{idx}"] = raw.hex()
        return res

    def close(self):
        try: self.runner.close()
        except Exception: pass
