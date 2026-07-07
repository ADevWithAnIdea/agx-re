#!/usr/bin/env python3
# EXP-0018 hardware validation harness (runs ON THE DEVICE under exp0018/).
# Compiles OUR OWN MSL (shdump), optionally splices _agc.main bytes, dispatches
# on the real A18 Pro GPU (persistrun), reads back per-lane outputs. Proves:
#  - subgroup/quad op SEMANTICS by feeding each lane a distinct value,
#  - atomic aggregate correctness (many lanes -> one location),
#  - the atomic operation field (byte+12) by splice-and-observe.
# CLEAN-ROOM: only OUR OWN compiled (and spliced) bytes run.
import os, struct, subprocess, importlib.util, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
agxparse = load_mod("agxparse", os.path.join(HERE, "agxparse.py"))
PersistRunner = load_mod("persistrun", os.path.join(HERE, "persistrun.py")).PersistRunner

def pack(dt, vals):
    f = {'i':'<i','u':'<I','f':'<f'}[dt]
    return b"".join(struct.pack(f, (int(x)&0xffffffff) if dt=='u' else (int(x) if dt=='i' else float(x))) for x in vals)
def unpack(dt, raw, n):
    sz=4; f={'i':'<i','u':'<I','f':'<f'}[dt]
    return [struct.unpack_from(f, raw, k*sz)[0] for k in range(n)]

class H:
    def __init__(self, source):
        self.source=source; self.work=os.path.join(HERE,"work"); os.makedirs(self.work,exist_ok=True)
    def build(self, fn):
        base=os.path.join(self.work,f"{fn}.bin")
        r=subprocess.run(["./shdump","-o",base,"-f",fn,"--no-fast-math",self.source],capture_output=True,text=True)
        if r.returncode!=0: raise RuntimeError(f"shdump {fn}: {r.stderr[-200:]}")
        buf=open(base,"rb").read()
        off,length=agxparse.locate_region(buf,"_agc.main")
        return base,buf,off,length
    def run(self, fn, grid, tg, ins, outs, splices=None, timeout=8.0):
        # ins: {idx:(dt,[vals])}; outs:{idx:(dt,nelem)}; splices:{main_off:byte}
        base,buf,off,length=self.build(fn)
        if splices:
            b=bytearray(buf)
            for mo,val in splices.items(): b[off+mo]=val&0xff
            arch=os.path.join(self.work,f"{fn}_sp.bin"); open(arch,"wb").write(b)
        else:
            arch=base
        inpaths={}
        for idx,(dt,v) in ins.items():
            p=os.path.join(self.work,f"in_{fn}_{idx}.bin"); open(p,"wb").write(pack(dt,v)); inpaths[idx]=p
        outspec={idx:nel*4 for idx,(dt,nel) in outs.items()}
        runner=PersistRunner(source=self.source,function=fn,fast_math=False,agxrun_persist="./agxrun_persist")
        try:
            resp=runner.request(archive=arch,grid=grid,tg=tg,ins=inpaths,outs=outspec,timeout=timeout)
        finally:
            runner.close()
        res={"_status":resp["status"],"_err":resp.get("error")}
        for idx,(dt,nel) in outs.items():
            raw=resp["outs"].get(idx,b"")
            res[idx]=unpack(dt,raw,nel) if raw else []
        return res
    def main_hex(self, fn):
        base,buf,off,length=self.build(fn)
        return buf[off:off+length].hex(), off, length

def find(hexs, pat):
    i=hexs.find(pat); return None if i<0 else i//2
