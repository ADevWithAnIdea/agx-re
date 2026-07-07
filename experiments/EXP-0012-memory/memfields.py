#!/usr/bin/env python3
# memfields.py -- EXP-0012: align device/threadgroup load & store instructions
# across a kernel family and print a per-byte field table. Runs ON DEVICE
# (compiles our own MSL). CLEAN-ROOM: our own bytes only.
import os, sys, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))
SHDUMP = os.path.join(HERE, "shdump"); KDIR = os.path.join(HERE, "kernels")

def compile_main(name):
    base = os.path.join(HERE, "work", f"{name}.bin")
    r = subprocess.run([SHDUMP,"-o",base,"-f","k","--no-fast-math",os.path.join(KDIR,name+".metal")],
                       capture_output=True, text=True)
    if r.returncode != 0: return None
    with open(base,"rb") as f: buf=f.read()
    _, pieces = agxparse.extract_agx(buf)
    return pieces.get("_agc.main", b"") if pieces else None

def find_mem(main):
    """Return list of (kind, off, 14-byte) for every plausible 0x67/0xe7 mem op.
    Plausible = byte0 in {67,e7} and byte+13 == 0x00 and off+14<=len."""
    out=[]; n=len(main)
    for i in range(n-13):
        if main[i] in (0x67,0xe7) and main[i+13]==0x00:
            out.append(("LD" if main[i]==0x67 else "ST", i, bytes(main[i:i+14])))
    return out

def table(names, want):
    # want: 'LD' or 'ST' -- print first matching mem op per kernel, aligned
    print(f"\n===== {want} field table (byte +0..+13) =====")
    print("kernel        " + " ".join(f"+{i:<2d}" for i in range(14)))
    rows=[]
    for nm in names:
        m = compile_main(nm)
        if m is None: print(f"{nm:13s} <compile failed>"); continue
        mem = [x for x in find_mem(m) if x[0]==want]
        if not mem: print(f"{nm:13s} <no {want}>"); continue
        b = mem[0][2]
        print(f"{nm:13s} " + " ".join(f"{x:02x} " for x in b))
        rows.append((nm,b))
    # highlight which byte-positions vary
    if rows:
        varying=[i for i in range(14) if len(set(r[1][i] for r in rows))>1]
        print("varying bytes:", ["+%d"%i for i in varying])
    return rows

if __name__=="__main__":
    LD = ["copy1","copyf","const_copy","ld_char","ld_uchar","ld_short","ld_ushort",
          "ld_long","vec2i","vec3","vec4i","off1","str2"]
    ST = ["copy1","st_char","st_short","ld_long","vec2i","vec3","vec4i"]
    table(LD,"LD")
    table(ST,"ST")
    # threadgroup: print ALL mem ops (device + threadgroup) for tg kernels
    for nm in ["tg_copy","tg_rot8"]:
        m = compile_main(nm)
        if m is None: print(f"\n{nm}: compile failed"); continue
        print(f"\n===== {nm} : all mem ops (byte+1 flags address space) =====")
        print("  main:", m.hex())
        for kind,off,b in find_mem(m):
            asf = "THREADGROUP" if b[1]==0x02 else ("device" if b[1] in (0x00,0x10) else f"?b1={b[1]:02x}")
            print(f"  [{off:3d}] {kind}  b1={b[1]:#04x} base_slot(+4)={b[4]:#04x} [{asf}]  {b.hex()}")
