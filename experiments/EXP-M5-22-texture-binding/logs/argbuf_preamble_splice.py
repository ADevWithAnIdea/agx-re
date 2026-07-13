#!/usr/bin/env python3
# EXP-M5-22 argument-buffer index splice: prove the arg-buffer texture index is the
# single PREAMBLE byte 0xa0+index (main sample op is index-agnostic). Bind 4 distinct-
# colored textures via a Tier-2 argument buffer, splice the preamble index byte, observe
# the sampled pixel. Run on device in ~/cleanroom_work/EXP-M5-22 after building f_ab0.bin
# (shdump --render --vertex v_main --fragment f_ab0 kernels/tex_bind.metal) and agxrender3.
import subprocess, re, os
arch="f_ab0.bin"; raw=bytearray(open(arch,"rb").read())
pat=bytes.fromhex("0f000300a04c00")            # preamble descriptor-setup op; IDX byte follows
idx=[m.start() for m in re.finditer(re.escape(pat),raw)][0]+len(pat)
REND=os.path.expanduser("~/cleanroom_work/EXP-M5-22/agxrender3")
def run(v,label):
    d=bytearray(raw); d[idx]=v; open(arch+".spliced","wb").write(d)
    r=subprocess.run([REND,"--archive",arch+".spliced","--source","kernels/tex_bind.metal",
        "--vertex","v_main","--fragment","f_ab0","--argtex","255,0,0,255","--argtex","0,255,0,255",
        "--argtex","0,0,255,255","--argtex","255,255,0,255"],capture_output=True,text=True,timeout=20)
    print(label, [l for l in r.stdout.splitlines() if l.startswith(("PIXEL","STATUS"))])
for k,c in enumerate(["RED","GREEN","BLUE","YELLOW"]): run(0xa0+k, f"idx{k}(0x{0xa0+k:02x}) expect {c}:")
