#!/usr/bin/env python3
"""EXP-0086 pre-GPU baseline derivation: compile all 7 kernels (host-only,
no Metal device use), tokenize cleanly, and verify the FROZEN anchors
(casematrix.ANCHORS) match a FRESH compile on this toolchain byte-for-byte.
A mismatch is a clean pre-capture stop (toolchain drift), never silently
repaired -- mirrors EXP-0081's `frozen_anchor_diffs` gate.

Writes a JSON report to --out. Does not touch the GPU.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb          # noqa: E402
import casematrix as CM  # noqa: E402
import agxparse        # noqa: E402


def compile_kernel(shdump_bin, kernel, workdir):
    src = HERE / "kernels" / f"{kernel}.metal"
    out = workdir / f"{kernel}.bin"
    r = subprocess.run([str(shdump_bin), "-o", str(out), "--no-fast-math", str(src)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"shdump failed for {kernel}: {r.stderr}")
    _, pieces = agxparse.extract_agx(out.read_bytes())
    main_bytes = pieces.get("_agc.main") if pieces else None
    if main_bytes is None:
        raise RuntimeError(f"could not extract _agc.main for {kernel}")
    return main_bytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bin_dir = Path(a.bin_dir)
    workdir = Path(a.out).parent
    shdump_bin = bin_dir / "shdump"

    report = {"schema": 1, "kernels": {}, "frozen_anchor_diffs": []}
    for kernel in CM.KERNELS:
        main_bytes = compile_kernel(shdump_bin, kernel, workdir)
        recs, leftover = isadb.disassemble(main_bytes)
        clean = leftover == b""
        anc = CM.ANCHORS[kernel]
        diffs = []
        anchor_check = {}
        for site in ("c1", "c2"):
            off = anc[site]["offset"]
            length = len(bytes.fromhex(anc[site]["hex"])) // 1
            got_hex = main_bytes[off:off + len(bytes.fromhex(anc[site]["hex"]))].hex()
            want_hex = anc[site]["hex"]
            anchor_check[site] = {"offset": off, "got_hex": got_hex, "want_hex": want_hex}
            if got_hex != want_hex:
                diffs.append({"kernel": kernel, "site": site, "offset": off,
                              "got_hex": got_hex, "want_hex": want_hex})
        report["kernels"][kernel] = {
            "main_hex": main_bytes.hex(),
            "main_len": len(main_bytes),
            "clean_tokenize": clean,
            "n_instructions": len(recs),
            "leftover_hex": leftover.hex(),
            "anchor_check": anchor_check,
            "expected_out": CM.EXPECTED[kernel](CM.INPUTS[kernel]),
        }
        if not clean:
            diffs.append({"kernel": kernel, "site": "WHOLE", "error": "not clean tokenize"})
        report["frozen_anchor_diffs"].extend(diffs)

    Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"n_kernels": len(CM.KERNELS),
                      "frozen_anchor_diffs": len(report["frozen_anchor_diffs"])}))
    if report["frozen_anchor_diffs"]:
        sys.exit(3)


if __name__ == "__main__":
    main()
