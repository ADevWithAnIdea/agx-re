#!/usr/bin/env python3
"""EXP-0219 PRE-FREEZE CALIBRATION for part A.  Compile-only + one dispatch.

Runs on the neo.  Compiles our own `kernels/probes_imad.metal` with tools/shdump,
tokenizes `_agc.main` with the PINNED tools/agx-isa, and reports the 12-byte
`imad` anchor and its offset.  Then compiles both carriers and reports the
`_agc.main` region length and whether the synthesized program fits.

Nothing here is a hardware result.  Its outputs (anchor hex, region lengths) are
folded into CAPTURE_CONTRACT.json and frozen BEFORE the first gated dispatch.
"""
from __future__ import print_function
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import imad_helpers as H          # noqa: E402
import imad_carrier as C          # noqa: E402
isadb = H.isadb

out = {"isa_dir": str(H.ISA_DIR)}

wd = EXP / "work" / "calib"
wd.mkdir(parents=True, exist_ok=True)
p = wd / "probe_imad.bin"
r = subprocess.run([str(C.SHDUMP), "-o", str(p), "-f", "k_imad",
                    "--no-fast-math", str(EXP / "kernels" / "probes_imad.metal")],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
if r.returncode != 0:
    sys.exit("shdump failed: " + r.stderr.decode()[-600:])
_, pieces = C.agxparse.extract_agx(p.read_bytes())
main = pieces["_agc.main"]
recs, leftover = isadb.disassemble(main)
toks, off = [], 0
for rec in recs:
    toks.append({"off": off, "len": rec["length"], "mn": rec["mnemonic"],
                 "bytes": main[off:off + rec["length"]].hex()})
    off += rec["length"]
out["probe_main_hex"] = main.hex()
out["probe_main_len"] = len(main)
out["probe_leftover"] = leftover.hex() if leftover else ""
out["probe_tokens"] = toks
imads = [t for t in toks if t["mn"] == "imad"]
out["imad_tokens"] = imads
out["anchor"] = imads[0]["bytes"] if imads else None

for name, src in (("dag", "kernels/carrier_dag.metal"),
                  ("const", "kernels/carrier_const.metal")):
    q = wd / ("carrier_%s.bin" % name)
    r = subprocess.run([str(C.SHDUMP), "-o", str(q), "-f", "k",
                        "--no-fast-math", str(EXP / src)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if r.returncode != 0:
        out[name] = {"error": r.stderr.decode()[-600:]}
        continue
    buf = q.read_bytes()
    loc = C.agxparse.locate_region(buf, "_agc.main")
    _, pc = C.agxparse.extract_agx(buf)
    ent = {"region_off": loc[0], "region_len": loc[1],
           "main_len": len(pc["_agc.main"])}
    if out["anchor"]:
        for sset in (1, 2):
            try:
                prog = H.synth_program("int", bytes.fromhex(out["anchor"]),
                                       loc[1], sset)
                n = sum(len(x) for x in H.seed_instrs("int", sset))
                n += sum(len(x) for x in H.pre_sentinel_instrs("int", sset))
                ent["synth_ok_sset%d" % sset] = True
                ent["block_off_sset%d" % sset] = n
                ent["block_check_sset%d" % sset] = prog[n:n + 12].hex()
            except Exception as e:                              # noqa: BLE001
                ent["synth_ok_sset%d" % sset] = str(e)[:200]
    out[name] = ent

print(json.dumps(out, indent=1))
