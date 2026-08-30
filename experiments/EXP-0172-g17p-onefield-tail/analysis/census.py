#!/usr/bin/env python3
"""census.py -- EXP-0163 PRE-FREEZE calibration.

Builds every carrier in harness/carriers.py from OUR OWN MSL on the device,
extracts the compiled `_agc.main` bytes for each stage, tokenizes them with
tools/agx-isa, and reports every occurrence of every target mnemonic with its
decoded field values.

This is calibration, NOT evidence: its output lands in raw/prefreeze/ and no
verdict may cite it.  Its job is to answer, before the contract is frozen:
  * does each carrier compile at all, and with the exact pipeline descriptor
    the sweep will use?
  * does it actually emit the instruction the arm is meant to target?
  * does the occurrence carry a DIFFERENT field context from EXP-0155's arm --
    which is the whole premise of this experiment?

Usage (on the neo):  AGXRE_REPO=$HOME/agxre python3 analysis/census.py

CLEAN-ROOM: OWN-SHADER.  Only bytes compiled from kernels/*.metal are decoded.
"""
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.environ.get("AGXRE_REPO", os.path.abspath(os.path.join(EXP, "..", "..")))
sys.path.insert(0, os.path.join(EXP, "harness"))
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb                     # noqa: E402
import carriers as CA            # noqa: E402
from runner2 import render_cmd   # noqa: E402

WORK = os.path.join(EXP, "work")
AGXPARSE = os.path.join(REPO, "tools", "shdump", "agxparse.py")
GFRUN = os.path.join(WORK, "gfrun2")
SHDUMP = os.path.join(WORK, "shdump")


def sh(cmd, timeout=180):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def f32(vals):
    return [struct.unpack("<I", struct.pack("<f", v))[0] for v in vals]


def build(name, cfg):
    arch = os.path.join(WORK, f"{name}.bin")
    if cfg["kind"] == "compute":
        rc, out, err = sh([SHDUMP, "-o", arch, "-f", cfg["function"],
                           os.path.join(EXP, cfg["src"])])
    else:
        cmd = render_cmd(GFRUN, os.path.join(EXP, cfg["src"]), cfg, build=arch)
        rc, out, err = sh(cmd)
    return arch, rc, out, err


def stage_bytes(arch, stage):
    args = [sys.executable, AGXPARSE, arch]
    if stage != "compute":
        args += ["--stage", stage]
    rc, out, err = sh(args + ["--locate", "_agc.main"])
    if rc != 0:
        return None, None, err
    loc = out.split()
    off, ln = int(loc[0]), int(loc[1])
    rc, out, err = sh(args + ["--extract-hex"])
    if rc != 0:
        return None, None, err
    return off, bytes.fromhex(out.strip()), ""


def tokenize(buf):
    recs, left, off = [], None, 0
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError:
            left = off
            break
        rec["off"] = off
        recs.append(rec)
        off += L
    return recs, left


def scan(buf, mnem):
    """Anchored decode scan, used only where forward tokenization stops."""
    hits = []
    for o in range(len(buf) - 1):
        try:
            rec, L = isadb.decode_one(buf, o)
        except ValueError:
            continue
        if rec["mnemonic"] != mnem:
            continue
        ok, p = True, o + L
        for _ in range(2):
            if p >= len(buf):
                break
            try:
                _r, _l = isadb.decode_one(buf, p)
            except ValueError:
                ok = False
                break
            p += _l
        if ok:
            hits.append((o, rec))
    return hits


def main():
    os.makedirs(WORK, exist_ok=True)
    report = {}
    for name, cfg in CA.CARRIERS.items():
        entry = {"why": cfg["why"], "src": cfg["src"], "stages": {}}
        arch, rc, out, err = build(name, cfg)
        entry["build_rc"] = rc
        if rc != 0:
            entry["build_error"] = (out + err)[-3000:]
            report[name] = entry
            print(f"[{name}] BUILD FAILED rc={rc}\n{(out+err)[-1500:]}\n")
            continue
        stages = ["compute"] if cfg["kind"] == "compute" else ["vertex", "fragment"]
        for st in stages:
            off, buf, e = stage_bytes(arch, st)
            if buf is None:
                entry["stages"][st] = {"error": e[-1000:]}
                continue
            recs, left = tokenize(buf)
            occ = {}
            for m in list(CA.TARGETS) + ["op57", "tile_read", "device_store"]:
                found = [r for r in recs if r["mnemonic"] == m]
                if not found and left is not None:
                    found = [dict(r, off=o) for (o, r) in scan(buf, m)]
                if found:
                    occ[m] = [{"off": r["off"], "hex": r["hex"],
                               "fields": r["fields"]} for r in found]
            entry["stages"][st] = {
                "abs_off": off, "len": len(buf), "hex": buf.hex(),
                "tokenized": left is None, "stop_at": left,
                "n_instr": len(recs),
                "mnemonics": sorted({r["mnemonic"] for r in recs}),
                "targets": occ,
            }
            print(f"[{name}/{st}] len={len(buf)} tokenized={left is None} "
                  f"stop_at={left} instrs={len(recs)}")
            for m, lst in sorted(occ.items()):
                for i, r in enumerate(lst):
                    print(f"    {m}[{i}] @{r['off']} {r['hex']} {r['fields']}")
        report[name] = entry
    outp = os.path.join(EXP, "raw", "prefreeze", "census.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp, "w") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print("\nwrote", outp)


if __name__ == "__main__":
    main()
