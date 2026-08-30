#!/usr/bin/env python3
"""EXP-0154 anchor extraction.

Compiles each authored probe kernel in `kernels/probes.metal` with
`tools/shdump`, tokenizes the resulting `_agc.main` with `tools/agx-isa`, and
reports where each instruction family we need actually lands.

An "anchor block" is a contiguous run of instructions lifted VERBATIM from the
compiled form of our own MSL. Only pure-ALU instructions may be lifted: a
device_load/device_store/branch inside the block would reference the carrier's
own buffer bindings and would not survive being moved into a synthesized
program.

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

# Instructions that may NOT appear inside a lifted anchor block: they touch
# memory, control flow, or the carrier's binding table.
NON_LIFTABLE = {"device_load", "device_store", "stop", "jmp_exec_any",
                "jmp_exec_none", "if_push", "if_pop", "else_pop", "while_push",
                "pop_exec", "get_sr", "uniform_store", "threadgroup_load",
                "threadgroup_store", "wait", "spill_frame_marker",
                "frame_prologue", "link_save_restore", "device_atomic"}


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
    the DB cannot resolve); that is a RESULT about the DB, not a crash, so it is
    recorded and tokenization stops there."""
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
    """Return (start_off, end_off, [record...]) for the `occurrence`-th
    `mnemonic`, widened by `before`/`after` instructions. Raises if any
    instruction in the widened window is not liftable."""
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
    # offset of the instruction under test INSIDE the block
    target_off = recs[i]["off"] - start
    return start, end, target_off, window


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
            report[fn] = {"error": str(e)[:400]}
            print("%-14s COMPILE FAIL %s" % (fn, str(e)[:120]))
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
        print("%-14s len=%-4d leftover=%d  %s" % (
            fn, len(main_bytes), len(leftover),
            " ".join("%s@%d%s" % (r["mnemonic"], r["off"],
                                  "!LENNONE" if r.get("length") is None else "")
                     for r in recs)))
    outp = workdir / "anchor_report.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", outp)


if __name__ == "__main__":
    main()
