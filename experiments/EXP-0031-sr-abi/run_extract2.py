#!/usr/bin/env python3
# EXP-0031 device-side extractor #2: stage_in vertex-attribute fetch + bary.
# Runs ON THE DEVICE. Builds attrdump-based archives varying the vertex layout
# and extracts the VS/FS AGX bytes; also the fixed bary fragment. OWN-SHADER.
import os, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True); return p.returncode, p.stdout, p.stderr
def ext(binp, stage, sym="_agc.main"):
    rc,o,e = run(["python3", os.path.join(HERE,"agxparse.py"), binp, "--stage", stage,
                  "--extract-hex", "--symbol", sym])
    return o.strip().replace(" ","").replace("\n","") if rc==0 else None

ATTR = os.path.join(HERE,"attrdump"); SRC = os.path.join(HERE,"kernels","attr_stagein.metal")
OUT = os.path.join(HERE,"out"); os.makedirs(OUT, exist_ok=True)
variants = [
  ("base",   ["--fmt0","31","--off0","0","--fmt1","28","--off1","16","--stride","32"]),
  ("st64",   ["--fmt0","31","--off0","0","--fmt1","28","--off1","16","--stride","64"]),
  ("off1_12",["--fmt0","31","--off0","0","--fmt1","28","--off1","12","--stride","32"]),
  ("u8n",    ["--fmt0","45","--off0","0","--fmt1","28","--off1","16","--stride","32"]),
  ("half4",  ["--fmt0","31","--off0","0","--fmt1","25","--off1","16","--stride","32"]),
  ("perinst",["--fmt0","31","--off0","0","--fmt1","28","--off1","16","--stride","32","--step","1"]),
]
res = {}
for name,args in variants:
    binp = os.path.join(OUT, f"attr_{name}.bin")
    rc,o,e = run([ATTR,"-o",binp,"--source",SRC]+args)
    res[name] = {"ok": rc==0, "vs_main": ext(binp,"vertex"), "vs_cprog": ext(binp,"vertex","_agc.main.constant_program"),
                 "fs_main": ext(binp,"fragment"), "cfg": args}
# bary
rc,o,e = run([os.path.join(HERE,"shdump"),"-o",os.path.join(OUT,"f_bary.bin"),"--render",
              "--vertex","v_main","--fragment","f_main",os.path.join(HERE,"kernels","f_bary.metal")])
res["bary"] = {"ok": rc==0, "fs_main": ext(os.path.join(OUT,"f_bary.bin"),"fragment"),
               "fs_cprog": ext(os.path.join(OUT,"f_bary.bin"),"fragment","_agc.main.constant_program")}
with open(os.path.join(HERE,"raw","extract2.json"),"w") as f: json.dump(res,f,indent=1)
for k,v in res.items(): print(k, "OK" if v["ok"] else "FAIL", (v.get("vs_main") or v.get("fs_main") or "")[:48])
print("wrote raw/extract2.json")
