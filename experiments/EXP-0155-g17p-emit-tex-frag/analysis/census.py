#!/usr/bin/env python3
"""census.py -- EXP-0155 PRE-FREEZE calibration: compile every carrier from OUR
OWN MSL, tokenize both stages with tools/agx-isa, and report which target
instructions actually occur, how many times, and their decoded fields.

This is CALIBRATION, not evidence: it is what the frozen contract is written
FROM.  Its transcript is retained in raw/prefreeze/.

CLEAN-ROOM: OWN-SHADER.  Only bytes compiled from kernels/*.metal are inspected.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.environ.get("AGXRE_REPO", os.path.abspath(os.path.join(EXP, "..", "..")))
sys.path.insert(0, os.path.join(EXP, "harness"))
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb                       # noqa: E402
import casematrix as CM            # noqa: E402

WORK = os.path.join(EXP, "work")
GFRUN = os.path.join(WORK, "gfrun")
SHDUMP = os.path.join(WORK, "shdump")
AGXPARSE = os.path.join(REPO, "tools", "shdump", "agxparse.py")

TARGETS = ["vary_slot", "vary_store", "tex_sample", "tex_coord_setup", "tex_deriv",
           "tex_write", "imageblock_load", "imageblock_store", "iter", "iter_at",
           "iter_flat", "frag_color_store", "frag_color_pack", "frag_tile_setup",
           "frag_depth_store", "simd_ballot", "simd_shuffle", "simd_reduce"]


def sh(cmd, timeout=180):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def tokenize(buf):
    recs, off, leftover = [], 0, None
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError as e:
            leftover = (off, str(e))
            break
        rec["off"] = off
        recs.append(rec)
        off += L
    return recs, leftover


def scan(buf, mnemonic):
    """The anchored-decode fallback run.py uses when a program contains ops the
    DB cannot length-resolve: keep only offsets that also decode cleanly for the
    two following instructions."""
    hits = []
    for o in range(len(buf) - 1):
        try:
            rec, L = isadb.decode_one(buf, o)
        except ValueError:
            continue
        if rec["mnemonic"] != mnemonic:
            continue
        ok, p2 = True, o + L
        for _ in range(2):
            if p2 >= len(buf):
                break
            try:
                _r, _l = isadb.decode_one(buf, p2)
            except ValueError:
                ok = False
                break
            p2 += _l
        if ok:
            hits.append((o, rec["hex"], rec["fields"]))
    return hits


def main():
    out = {}
    for name, cfg in CM.CARRIERS.items():
        src = os.path.join(EXP, cfg["src"])
        arch = os.path.join(WORK, f"{name}.bin")
        if cfg["kind"] == "compute":
            rc, so, se = sh([SHDUMP, "-o", arch, "-f", cfg["function"], src])
            stages = ["compute"]
        else:
            cmd = [GFRUN, "--source", src, "--vertex", CM.RENDER_VERTEX,
                   "--fragment", CM.RENDER_FRAGMENT,
                   "--color-format", str(cfg["color_format"]),
                   "--samples", str(cfg.get("samples", 1)),
                   "--width", str(cfg["width"]), "--height", str(cfg["height"]),
                   "--build-archive", arch]
            if cfg.get("depth"):
                cmd.append("--depth")
            if cfg.get("resolve"):
                cmd.append("--resolve")
            if cfg.get("tex_sample"):
                cmd += ["--tex-sample", "%d,%d" % cfg["tex_sample"]]
            if cfg.get("tex_write"):
                cmd += ["--tex-write", "%d,%d" % cfg["tex_write"]]
            if cfg.get("tex_depth"):
                cmd += ["--tex-depth", "%d,%d" % cfg["tex_depth"]]
            if cfg.get("tex_extra"):
                cmd.append("--tex-extra")
            if cfg.get("clear"):
                cmd += ["--clear", ",".join(str(v) for v in cfg["clear"])]
            rc, so, se = sh(cmd)
            stages = ["vertex", "fragment"]
        if rc != 0:
            out[name] = {"build": "FAIL", "stdout": so[-2000:], "stderr": se[-2000:]}
            print(f"### {name}: BUILD FAILED\n{so[-1500:]}\n{se[-1500:]}")
            continue
        entry = {"build": "OK", "stages": {}}
        for st in stages:
            a = [sys.executable, AGXPARSE, arch] + ([] if st == "compute"
                                                    else ["--stage", st])
            rc2, loc, _ = sh(a + ["--locate", "_agc.main"])
            rc3, hx, _ = sh(a + ["--extract-hex"])
            if rc2 or rc3:
                entry["stages"][st] = {"locate": "FAIL"}
                continue
            off, ln = (int(x) for x in loc.split())
            buf = bytes.fromhex(hx.strip())
            recs, leftover = tokenize(buf)
            hits = {}
            for t in TARGETS:
                h = [r for r in recs if r["mnemonic"] == t]
                if h:
                    hits[t] = [{"occ": i, "off": r["off"], "hex": r["hex"],
                                "fields": r["fields"]} for i, r in enumerate(h)]
            scanned = {}
            if leftover is not None:
                for t in TARGETS:
                    h = scan(buf, t)
                    if h:
                        scanned[t] = [{"occ": i, "off": o, "hex": hx2, "fields": fl}
                                      for i, (o, hx2, fl) in enumerate(h)]
            entry["stages"][st] = {"abs_off": off, "len": len(buf), "scanned": scanned,
                                   "n_instr": len(recs), "leftover": leftover,
                                   "targets": hits,
                                   "mnemonics": sorted({r["mnemonic"] for r in recs})}
            print(f"### {name}/{st}: {len(buf)}B, {len(recs)} instrs, "
                  f"leftover={leftover}")
            for t, h in hits.items():
                print(f"     {t}: {len(h)}  offs={[x['off'] for x in h]}")
            for t, h in scanned.items():
                print(f"   ~ SCAN {t}: {len(h)}  offs={[x['off'] for x in h]}")
        out[name] = entry
    with open(os.path.join(EXP, "work", "census.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("\nwrote work/census.json")


if __name__ == "__main__":
    main()
