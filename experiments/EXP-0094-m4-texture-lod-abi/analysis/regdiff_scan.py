#!/usr/bin/env python3
"""EXP-0094 register-pressure regdiff scan (own-shader-diff, compile-only, no
GPU dispatch). Compiles each generated regpress_{bias,grad}_nNN.metal via
shdump, extracts the fragment/compute AGX bytes via agxparse.py, locates the
14-byte texture-sample bundle (4-byte companion `X5 80 0c XX` + 10-byte
sampler op, per EXP-0016/EXP-0034's already-published field map), and reports
how each op+N byte varies with register pressure N.

Every case is its own subprocess (shdump is a fresh process per compile);
single-threaded, sequential. This script performs NO GPU dispatch -- shdump's
--render/plain compute compile targets the AGXAccelerator compiler only, no
command buffer is submitted here (that happens only in run.py's regsplice
backend, which forces the ACTUAL splice to run on the real M4).

Output: analysis/regdiff_report.json (also printed).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SHDUMP = EXP / "harness" / "bin" / "shdump"
AGXPARSE = EXP.parents[1] / "tools" / "shdump" / "agxparse.py"
KGEN = EXP / "kernels" / "generated"
WORK = EXP / "work" / "regdiff"
WORK.mkdir(parents=True, exist_ok=True)

N_VALUES = [0, 1, 2, 4, 8, 12, 16, 24, 32]

# companion signature: byte0 low nibble 5, byte1=0x80, byte2=0x0c (EXP-0016/34)
COMPANION_RE = re.compile(rb"[0-9a-f](5)80 0c", re.IGNORECASE)  # placeholder, unused


def run(cmd, timeout=30):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def find_bundle(hexstr):
    """Locate the 14-byte sample bundle: companion byte0 low-nibble=5, byte1=80,
    byte2=0c, followed 4 bytes later by a sampler-op byte0 whose low nibble is 0.
    Returns (offset_bytes, companion_hex, op_hex) for the FIRST match, or None."""
    b = bytes.fromhex(hexstr)
    n = len(b)
    for i in range(n - 14):
        b0 = b[i]
        if (b0 & 0x0F) != 0x5:
            continue
        if b[i + 1] != 0x80 or b[i + 2] != 0x0C:
            continue
        op0 = b[i + 4]
        if (op0 & 0x0F) != 0x0:
            continue
        comp = b[i:i + 4]
        op = b[i + 4:i + 14]
        return i, comp.hex(), op.hex()
    return None


def compile_extract(src_path, render, stage):
    tag = src_path.stem
    out = WORK / f"{tag}.bin"
    if render:
        cmd = [str(SHDUMP), "-o", str(out), "--render", "--vertex", "vmain",
               "--fragment", "fmain", str(src_path)]
    else:
        cmd = [str(SHDUMP), "-o", str(out), str(src_path)]
    rc, so, se = run(cmd, timeout=30)
    if rc != 0:
        return {"compile_ok": False, "stderr": se, "stdout": so}
    cmd2 = [sys.executable, str(AGXPARSE), str(out), "--stage", stage, "--extract-hex"]
    rc2, so2, se2 = run(cmd2, timeout=30)
    if rc2 != 0:
        return {"compile_ok": True, "extract_ok": False, "stderr": se2}
    hexstr = so2.strip()
    bundle = find_bundle(hexstr)
    return {
        "compile_ok": True, "extract_ok": True,
        "hex_len": len(hexstr) // 2,
        "hex_sha256_prefix": hexstr[:32],
        "bundle_offset": bundle[0] if bundle else None,
        "companion": bundle[1] if bundle else None,
        "sampler_op": bundle[2] if bundle else None,
    }


def main():
    report = {"bias": [], "grad": []}
    for n in N_VALUES:
        bp = KGEN / f"regpress_bias_n{n:02d}.metal"
        r = compile_extract(bp, render=True, stage="fragment")
        r["n"] = n
        report["bias"].append(r)
        print(f"bias n={n:2d} op={r.get('sampler_op')} comp={r.get('companion')} "
              f"len={r.get('hex_len')} ok={r.get('compile_ok')}/{r.get('extract_ok')}")
        gp = KGEN / f"regpress_grad_n{n:02d}.metal"
        r2 = compile_extract(gp, render=False, stage="compute")
        r2["n"] = n
        report["grad"].append(r2)
        print(f"grad n={n:2d} op={r2.get('sampler_op')} comp={r2.get('companion')} "
              f"len={r2.get('hex_len')} ok={r2.get('compile_ok')}/{r2.get('extract_ok')}")

    out_path = HERE / "regdiff_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
