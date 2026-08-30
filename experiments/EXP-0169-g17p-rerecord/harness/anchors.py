#!/usr/bin/env python3
"""EXP-0169 anchor extraction.

Compiles each authored probe kernel in `kernels/probes.metal` with
`tools/shdump` (the PUBLIC runtime API), tokenizes the resulting `_agc.main`
with `tools/agx-isa`, and writes `work/anchors/anchor_report.json`, which is
what `harness/casematrix.py` resolves arms against.

An "anchor block" is a contiguous run of instructions lifted VERBATIM from the
compiled form of our own MSL. Only pure-ALU instructions may be lifted: a
device_load/device_store/branch inside the block would reference the carrier's
own buffer bindings and would not survive being moved into a synthesized
program (`casematrix.NON_LIFTABLE`).

Structure reused from EXP-0154 `harness/anchors.py`, same project, same rules.

CLEAN-ROOM: OWN-SHADER. The only machine code inspected is the compiled form of
kernels/probes.metal, which we authored.
"""
from __future__ import print_function

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
isadb = H.isadb


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _find_tools():
    for cand in (EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


TOOLS = _find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
SHDUMP = TOOLS / "shdump" / "shdump"


def compile_main(source, function, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / ("anchor_%s.bin" % function)
    r = subprocess.run([str(SHDUMP), "-o", str(out), "-f", function,
                        "--no-fast-math", str(source)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=300)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("shdump failed for %s: %s"
                           % (function, r.stderr.decode()[-700:]))
    _, pieces = agxparse.extract_agx(out.read_bytes())
    return pieces["_agc.main"]


def tokenize(main):
    """Annotate each record with its absolute offset. `isadb.disassemble` can
    return a record whose `length` is None (an instruction whose length rule
    the DB cannot resolve); that is a RESULT about the DB, not a crash, so it
    is recorded and tokenization stops there."""
    recs, leftover = isadb.disassemble(main)
    off = 0
    good = []
    for r in recs:
        r["off"] = off
        if r.get("length") is None:
            r["length_none"] = True
            good.append(r)
            break
        good.append(r)
        off += r["length"]
    return good, leftover


def main():
    workdir = EXP / "work" / "anchors"
    src = EXP / "kernels" / "probes.metal"
    funcs = [ln.split("void ", 1)[1].split("(", 1)[0].strip()
             for ln in src.read_text().splitlines()
             if ln.startswith("kernel void ")]
    report = {}
    for fn in funcs:
        try:
            main_bytes = compile_main(src, fn, workdir)
        except Exception as e:
            report[fn] = {"error": str(e)[:600]}
            print("%-16s COMPILE FAIL %s" % (fn, str(e)[:110]))
            continue
        recs, leftover = tokenize(main_bytes)
        report[fn] = {
            "main_len": len(main_bytes),
            "main_hex": main_bytes.hex(),
            "leftover": leftover.hex(),
            "tokens": [{"off": r["off"], "len": r["length"],
                        "mn": r["mnemonic"],
                        "bytes": (main_bytes[r["off"]:r["off"] + r["length"]].hex()
                                  if r.get("length") is not None else None)}
                       for r in recs],
        }
        print("%-16s len=%-4d leftover=%d  %s" % (
            fn, len(main_bytes), len(leftover),
            " ".join("%s@%d%s" % (r["mnemonic"], r["off"],
                                  "!LENNONE" if r.get("length") is None else "")
                     for r in recs)))
    outp = workdir / "anchor_report.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", outp)

    # which arms resolve, and which do not -- reported, never patched around
    sys.path.insert(0, str(HERE))
    import casematrix as CM  # noqa: E402
    resolved, misses = CM.resolve_arms(report)
    print("\nresolved anchors:")
    for k in sorted(resolved):
        r = resolved[k]
        print("   %-30s %-16s block[%d:%d] tgt=+%d len=%d"
              % ("%s/%s" % (k[0], k[1]), r["probe"], r["block_lo"],
                 r["block_hi"], r["tgt"], r["ilen"]))
    if misses:
        print("\nUNRESOLVED (arm dropped, reported as a miss):")
        for m in misses:
            print("   " + json.dumps(m, sort_keys=True))
    (workdir / "arm_resolution.json").write_text(
        json.dumps({"resolved": {"%s/%s/%s" % k: v for k, v in resolved.items()},
                    "misses": misses}, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
