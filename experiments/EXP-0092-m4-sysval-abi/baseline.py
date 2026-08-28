#!/usr/bin/env python3
"""EXP-0092 baseline: recompile kernels/srprobe.metal and kernels/dstprobe.metal
FRESH (via a throwaway shdump build) and confirm the frozen anchors pinned in
casematrix.py (SRPROBE_MAIN_HEX / DSTPROBE_MAIN_HEX) still exactly match this
toolchain's output. A frozen contract that has drifted is a clean pre-capture
stop (EXP-0081/EXP-0086 pattern), never a silent re-pin.

Writes {"schema":1, "frozen_anchor_diffs": [...], "srprobe_hex":..., "dstprobe_hex":...}
to --out. A NON-EMPTY frozen_anchor_diffs list means run.py must stop (sys.exit(3))
before any raw/ capture proceeds.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402


def extract_main_hex(shdump, agxparse, source, workdir):
    archive = workdir / "pilot.bin"
    r = subprocess.run([str(shdump), "-o", str(archive), str(source)],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not archive.exists():
        raise RuntimeError("shdump failed: %s" % r.stderr)
    mod = _load_agxparse(agxparse)
    with open(archive, "rb") as f:
        buf = f.read()
    _, pieces = mod.extract_agx(buf)
    main_bytes = pieces.get("_agc.main") if pieces else None
    if main_bytes is None:
        raise RuntimeError("could not extract _agc.main")
    return main_bytes.hex()


def _load_agxparse(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("agxparse", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        shdump_bin = workdir / "shdump"
        r = subprocess.run(["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations",
                            "-o", str(shdump_bin), str(REPO / "tools" / "shdump" / "shdump.m"),
                            "-framework", "Metal", "-framework", "Foundation"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise SystemExit("baseline shdump build failed: %s" % r.stderr)
        agxparse = REPO / "tools" / "shdump" / "agxparse.py"

        srprobe_hex = extract_main_hex(shdump_bin, agxparse, HERE / "kernels" / "srprobe.metal", workdir)
        dstprobe_hex = extract_main_hex(shdump_bin, agxparse, HERE / "kernels" / "dstprobe.metal", workdir)

    diffs = []
    if srprobe_hex != CM.SRPROBE_MAIN_HEX:
        diffs.append({"kernel": "srprobe", "frozen": CM.SRPROBE_MAIN_HEX, "fresh": srprobe_hex})
    if dstprobe_hex != CM.DSTPROBE_MAIN_HEX:
        diffs.append({"kernel": "dstprobe", "frozen": CM.DSTPROBE_MAIN_HEX, "fresh": dstprobe_hex})

    out = {"schema": 1, "srprobe_hex": srprobe_hex, "dstprobe_hex": dstprobe_hex,
          "frozen_anchor_diffs": diffs}
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    if diffs:
        print("BASELINE DRIFT: %d anchor mismatch(es)" % len(diffs))
        sys.exit(3)
    print("BASELINE OK: frozen anchors reproduced exactly")


if __name__ == "__main__":
    main()
