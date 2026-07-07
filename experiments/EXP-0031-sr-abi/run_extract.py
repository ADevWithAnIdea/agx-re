#!/usr/bin/env python3
# EXP-0031 device-side extractor. Runs ON THE DEVICE.
# For each kernel in manifest.json: compile with shdump (compute or --render),
# extract _agc.main + _agc.main.constant_program hex for each relevant stage.
# Writes raw/extract.json  (all OWN-SHADER bytes).
import os, json, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHDUMP = os.path.join(HERE, "shdump")
AGXPARSE = os.path.join(HERE, "agxparse.py")
KDIR = os.path.join(HERE, "kernels")
OUTDIR = os.path.join(HERE, "out")
os.makedirs(OUTDIR, exist_ok=True)

manifest = json.load(open(os.path.join(HERE, "manifest.json")))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def extract(binpath, stage, symbol):
    cmd = ["python3", AGXPARSE, binpath, "--stage", stage,
           "--extract-hex", "--symbol", symbol]
    rc, out, err = run(cmd)
    if rc != 0:
        return None
    return out.strip().replace(" ", "").replace("\n", "")

results = []
for m in manifest:
    src = os.path.join(KDIR, m["file"])
    binp = os.path.join(OUTDIR, m["file"] + ".bin")
    rec = dict(m)
    if m["kind"] == "compute":
        rc, o, e = run([SHDUMP, "-o", binp, src])
        rec["compile_rc"] = rc
        rec["compile_err"] = e.strip()[-300:] if rc != 0 else ""
        if rc == 0:
            rec["compute_main"] = extract(binp, "compute", "_agc.main")
            rec["compute_cprog"] = extract(binp, "compute", "_agc.main.constant_program")
    else:
        rc, o, e = run([SHDUMP, "-o", binp, "--render",
                        "--vertex", m["vfunc"], "--fragment", m["ffunc"], src])
        rec["compile_rc"] = rc
        rec["compile_err"] = e.strip()[-300:] if rc != 0 else ""
        if rc == 0:
            rec["vertex_main"] = extract(binp, "vertex", "_agc.main")
            rec["vertex_cprog"] = extract(binp, "vertex", "_agc.main.constant_program")
            rec["fragment_main"] = extract(binp, "fragment", "_agc.main")
            rec["fragment_cprog"] = extract(binp, "fragment", "_agc.main.constant_program")
    results.append(rec)
    print(f"{m['file']:20s} rc={rec['compile_rc']}"
          + ("" if rec['compile_rc'] == 0 else f" ERR {rec['compile_err'][:80]}"))

os.makedirs(os.path.join(HERE, "raw"), exist_ok=True)
with open(os.path.join(HERE, "raw", "extract.json"), "w") as f:
    json.dump(results, f, indent=1)
print("wrote raw/extract.json")
