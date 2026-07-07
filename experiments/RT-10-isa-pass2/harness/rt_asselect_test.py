#!/usr/bin/env python3
# RT-10 Part4: is the rt_intersect byte+4 AS-select (prim 0x8b vs inst 0x6b) LOAD-BEARING?
# Build BOTH a primitive AS and an instance AS (rtrun2). Splice ONLY byte+4 of the first
# rt_intersect (@+0x054, so byte+4 @ _agc.main+0x058) in each kernel and observe whether
# the traversal result changes. Also re-test the OLD retracted 0x1b target on the prim path.
import subprocess, shutil

def locate(arch):
    o=subprocess.check_output(["python3","agxparse.py",arch,"--stage","compute","--locate","_agc.main"],text=True)
    return int(o.split()[0])

def run(arch, src, asmode, ray="0.2,0.2,0,0,0,1"):
    try:
        out=subprocess.check_output(["./rtrun2","--archive",arch,"--source",src,"--function","k",
            "--no-fast-math","--as",asmode,"--ray",ray,"--out","4"],text=True,stderr=subprocess.STDOUT,timeout=25)
    except subprocess.CalledProcessError as e:
        return "FAULT:"+(e.output.strip().splitlines()[-1] if e.output else "?")
    except subprocess.TimeoutExpired:
        return "HANG"
    for ln in out.splitlines():
        if ln.startswith("OUT "): return ln[4:].strip()
    for ln in out.splitlines():
        if ln.startswith("STATUS") and "OK" not in ln: return ln
    return "?"

def splice(base_arch, out_arch, abs_off, val):
    b=bytearray(open(base_arch,"rb").read())
    b[abs_off]=val
    open(out_arch,"wb").write(b)

OP_B4 = 0x054 + 4   # first rt_intersect byte+4

# --- primitive path ---
subprocess.check_call(["./shdump","-o","p4prim.bin","--no-fast-math","-f","k","k/p4_prim.metal"])
pm=locate("p4prim.bin")
print(f"# p4_prim _agc.main abs {pm}; byte+4 @ {pm+OP_B4} = 0x{open('p4prim.bin','rb').read()[pm+OP_B4]:02x}")
print("PRIM baseline (prim AS)             :", run("p4prim.bin","k/p4_prim.metal","prim"))
splice("p4prim.bin","pspl.bin",pm+OP_B4,0x6b)
print("PRIM byte+4 0x8b->0x6b (inst val)   :", run("pspl.bin","k/p4_prim.metal","prim"))
splice("p4prim.bin","pspl.bin",pm+OP_B4,0x1b)
print("PRIM byte+4 0x8b->0x1b (old claim)  :", run("pspl.bin","k/p4_prim.metal","prim"))
splice("p4prim.bin","pspl.bin",pm+OP_B4,0x00)
print("PRIM byte+4 0x8b->0x00              :", run("pspl.bin","k/p4_prim.metal","prim"))
splice("p4prim.bin","pspl.bin",pm+OP_B4,0xff)
print("PRIM byte+4 0x8b->0xff              :", run("pspl.bin","k/p4_prim.metal","prim"))

# --- instance path ---
subprocess.check_call(["./shdump","-o","p4inst.bin","--no-fast-math","-f","k","k/p4_inst.metal"])
im=locate("p4inst.bin")
print(f"\n# p4_inst _agc.main abs {im}; byte+4 @ {im+OP_B4} = 0x{open('p4inst.bin','rb').read()[im+OP_B4]:02x}")
print("INST baseline (inst AS)             :", run("p4inst.bin","k/p4_inst.metal","inst"))
splice("p4inst.bin","ispl.bin",im+OP_B4,0x8b)
print("INST byte+4 0x6b->0x8b (prim val)   :", run("ispl.bin","k/p4_inst.metal","inst"))
splice("p4inst.bin","ispl.bin",im+OP_B4,0x00)
print("INST byte+4 0x6b->0x00              :", run("ispl.bin","k/p4_inst.metal","inst"))
