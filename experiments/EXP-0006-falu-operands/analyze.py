#!/usr/bin/env python3
# analyze.py -- structural tokenizer + ALU locator for EXP-0006. Runs on device.
# Locates the ALU instruction as the byte gap between the load block and the
# store block (loads=0x67/14B, stores=0xe7/14B, stop=0x0e/4B, preamble low-nib
# 0xC /4B). Does NOT assume the ALU byte0 or length. Prints per-kernel: the load
# destination-register bytes and the exact ALU bytes.
# CLEAN-ROOM: operates only on OUR OWN compiled shader bytes.
import os, sys, subprocess, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load_mod(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
agxparse=load_mod("agxparse",os.path.join(HERE,"agxparse.py"))

def structural_tokens(main):
    """Return list of (kind, off, length, bytes). kind in preamble/load/store/stop/ALU."""
    toks=[]; off=0; n=len(main)
    # front: preamble
    if (main[0]&0x0f)==0x0c:
        toks.append(("preamble",0,4,bytes(main[0:4]))); off=4
    # walk loads
    while off<n and main[off]==0x67:
        toks.append(("load",off,14,bytes(main[off:off+14]))); off+=14
    # ALU = bytes until the first store/stop
    alu_start=off
    while off<n and main[off] not in (0xe7,0x0e):
        off+=1
    if off>alu_start:
        toks.append(("ALU",alu_start,off-alu_start,bytes(main[alu_start:off])))
    # stores
    while off<n and main[off]==0xe7:
        toks.append(("store",off,14,bytes(main[off:off+14]))); off+=14
    # stop
    if off<n and main[off]==0x0e:
        toks.append(("stop",off,4,bytes(main[off:off+4]))); off+=4
    if off<n:
        toks.append(("REST",off,n-off,bytes(main[off:])))
    return toks

def main_of(source, func="k", fast_math=False, workdir="work"):
    os.makedirs(workdir,exist_ok=True)
    base=os.path.join(workdir,"a.bin")
    cmd=["./shdump","-o",base,"-f",func]
    if not fast_math: cmd.append("--no-fast-math")
    cmd.append(source)
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise RuntimeError("shdump: "+r.stderr)
    with open(base,"rb") as f: buf=f.read()
    _,pieces=agxparse.extract_agx(buf)
    return pieces["_agc.main"]

if __name__=="__main__":
    fast = "--fast" in sys.argv
    kernels=[a for a in sys.argv[1:] if not a.startswith("--")]
    for k in kernels:
        src=f"kernels/{k}.metal"
        try:
            m=main_of(src, fast_math=fast)
        except Exception as e:
            print(f"{k}: ERROR {e}"); continue
        toks=structural_tokens(m)
        print(f"\n=== {k} ({'fast' if fast else 'nofast'})  mainlen={len(m)} ===")
        for (kind,off,L,b) in toks:
            note=""
            if kind=="load":
                # dest-reg bytes are around load byte +3..+4 (empirically); show +2..+5
                note=f" destregZone={b[2:6].hex()}"
            print(f"  +{off:#04x} {kind:8s} {b.hex()}{note}")
        alu=[t for t in toks if t[0]=="ALU"]
        if alu:
            b=alu[0][3]
            print(f"  ALU bytes = {b.hex()}  ({len(b)}B)  bits: "+
                  " ".join(f"b{i}={x:08b}" for i,x in enumerate(b)))
