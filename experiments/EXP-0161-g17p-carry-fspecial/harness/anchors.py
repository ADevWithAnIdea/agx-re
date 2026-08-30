#!/usr/bin/env python3
"""EXP-0161 anchor extraction.

Compiles every authored probe kernel in `kernels/probes.metal` with
`tools/shdump`, tokenizes the resulting `_agc.main` with `tools/agx-isa`, and
reports where each instruction family we need actually lands.

An "anchor block" is a contiguous run of instructions lifted VERBATIM from the
compiled form of our own MSL. Only pure-ALU instructions may be lifted: a
device_load/device_store/branch inside the block would reference the carrier's
own bindings and would not survive being moved into a synthesized program.

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
import sweeprun as S     # noqa: E402
isadb = H.isadb

SHDUMP = S.SHDUMP
agxparse = S.agxparse

NON_LIFTABLE = {"device_load", "device_store", "stop", "jmp_exec_any",
                "jmp_exec_none", "if_push", "if_pop", "else_pop", "while_push",
                "pop_exec", "get_sr", "uniform_store", "threadgroup_load",
                "threadgroup_store", "wait", "spill_frame_marker",
                "frame_prologue", "link_save_restore", "device_atomic"}


def compile_main(source, function, workdir, fast_math=False):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / ("anchor_%s%s.bin" % (function, "_fm" if fast_math else ""))
    cmd = [str(SHDUMP), "-o", str(out), "-f", function]
    if not fast_math:
        cmd.append("--no-fast-math")
    cmd.append(str(source))
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=300)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("shdump failed for %s: %s"
                           % (function, r.stderr.decode()[-700:]))
    _, pieces = agxparse.extract_agx(out.read_bytes())
    return pieces["_agc.main"]


def tokenize(main):
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


def find_block(recs, mnemonic, before=0, after=0, occurrence=0):
    """(start_off, end_off, target_off_in_block, window) for the
    `occurrence`-th `mnemonic`, widened by `before`/`after` instructions."""
    idxs = [i for i, r in enumerate(recs) if r["mnemonic"] == mnemonic]
    if len(idxs) <= occurrence:
        raise KeyError("%s occurrence %d not found" % (mnemonic, occurrence))
    i = idxs[occurrence]
    lo = max(0, i - before)
    hi = min(len(recs) - 1, i + after)
    window = recs[lo:hi + 1]
    bad = [r["mnemonic"] for r in window if r["mnemonic"] in NON_LIFTABLE]
    if bad:
        raise ValueError("block around %s contains non-liftable %s"
                         % (mnemonic, bad))
    start = window[0]["off"]
    end = window[-1]["off"] + window[-1]["length"]
    return start, end, recs[i]["off"] - start, window


FUNCS_FASTMATH = set()          # `fast::` in the source, so no TU-wide flag


def main():
    workdir = EXP / "work" / "anchors"
    src = EXP / "kernels" / "probes.metal"
    funcs = [ln.split("void ", 1)[1].split("(", 1)[0].strip()
             for ln in src.read_text().splitlines()
             if ln.startswith("kernel void ")]
    report = {}
    for fn in funcs:
        for fm in (False, True):
            key = fn if not fm else fn + "@fm"
            try:
                main_bytes = compile_main(src, fn, workdir, fast_math=fm)
            except Exception as e:
                report[key] = {"error": str(e)[:400]}
                print("%-18s COMPILE FAIL %s" % (key, str(e)[:110]))
                continue
            recs, leftover = tokenize(main_bytes)
            report[key] = {
                "func": fn, "fast_math": fm,
                "main_len": len(main_bytes),
                "main_hex": main_bytes.hex(),
                "leftover": leftover.hex(),
                "tokens": [{"off": r["off"], "len": r["length"],
                            "mn": r["mnemonic"],
                            "bytes": (main_bytes[r["off"]:r["off"] + r["length"]].hex()
                                      if r.get("length") is not None else None)}
                           for r in recs],
            }
            print("%-18s len=%-4d leftover=%d  %s" % (
                key, len(main_bytes), len(leftover),
                " ".join("%s@%d%s" % (r["mnemonic"], r["off"],
                                      "!LENNONE" if r.get("length") is None else "")
                         for r in recs)))
    outp = workdir / "anchor_report.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", outp)


if __name__ == "__main__":
    main()
