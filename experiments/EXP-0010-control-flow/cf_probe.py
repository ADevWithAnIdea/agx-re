#!/usr/bin/env python3
# cf_probe.py -- EXP-0010 control-flow splice-and-observe harness. Runs ON DEVICE.
# Reuses IntProbe (EXP-0007) for _agc.main splicing + persistent runner, and adds
# helpers to splice ANY region (e.g. _agc.main.constant_program) at absolute file
# offsets. CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, struct, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
def load_mod(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = load_mod("intprobe", os.path.join(HERE, "intprobe.py"))
agxparse = load_mod("agxparse", os.path.join(HERE, "agxparse.py"))
IntProbe = intprobe.IntProbe

def i32(v): return b"".join(struct.pack("<i", int(x)) for x in v)
def ints_from(raw, signed=True):
    f = "<i" if signed else "<I"
    return [struct.unpack_from(f, raw, i)[0] for i in range(0, len(raw)-3, 4)]

def run_abs(probe, abs_over, ins, outs, grid, tg, timeout=8.0, signed=True):
    """Splice at ABSOLUTE file offsets (not _agc.main-relative) and run."""
    spliced = bytearray(probe.basebuf)
    for off, val in abs_over.items():
        spliced[off] = val & 0xff
    arch = os.path.join(probe.workdir, "spa.bin")
    with open(arch, "wb") as f: f.write(spliced)
    inpaths = {}
    for idx, v in ins.items():
        p = os.path.join(probe.workdir, f"ina_{idx}.bin")
        with open(p, "wb") as f: f.write(i32(v) if not isinstance(v, bytes) else v)
        inpaths[idx] = p
    outspec = {idx: nel*4 for idx, nel in outs.items()}
    resp = probe.runner.request(archive=arch, grid=grid, tg=tg, ins=inpaths, outs=outspec, timeout=timeout)
    res = {"_status": resp["status"], "_error": resp.get("error")}
    for idx, nel in outs.items():
        raw = resp["outs"].get(idx, b"")
        res[idx] = ints_from(raw, signed) if raw else []
    return res

def region(probe, sym):
    """(abs_off, length) of a symbol region in the archive file."""
    return agxparse.locate_region(probe.basebuf, sym)

def main_region(probe):
    return probe.region_off, probe.region_len

def hexdump_region(probe, sym):
    loc = region(probe, sym)
    if not loc: return None
    off, ln = loc
    return probe.basebuf[off:off+ln]
