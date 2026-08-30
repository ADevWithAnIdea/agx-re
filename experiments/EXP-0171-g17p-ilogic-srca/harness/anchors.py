#!/usr/bin/env python3
"""EXP-0171 anchor extraction.

Compiles every authored probe kernel in `kernels/probes.metal` with
`tools/shdump`, tokenizes the resulting `_agc.main` with `tools/agx-isa`, and
records where each instruction family we need actually lands, plus the exact
anchor bytes of every token.

The report is the ONLY input to `harness/casematrix.py::build_cases`, so the
frozen matrix hash is a function of (our MSL, the compiler on this host, our
db.json) and nothing else.

Two uses per token:
  * NAT   -- `off` is the byte offset inside `_agc.main` at which one byte is
             spliced IN PLACE in the probe kernel's own archive.
  * SYNTH -- `bytes` is the instruction lifted BYTE-FOR-BYTE into a program we
             assembled ourselves.

ADAPTED, with citation, from `experiments/EXP-0154-g17p-emit-alu/harness/
anchors.py` -- same project, same rules.

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


def compile_archive(source, function, workdir):
    """Compile ONE kernel to its own binary archive. Returns (path, bytes)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / ("arch_%s.bin" % function)
    r = subprocess.run([str(SHDUMP), "-o", str(out), "-f", function,
                        "--no-fast-math", str(source)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=300)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("shdump failed for %s: %s"
                           % (function, r.stderr.decode()[-700:]))
    return out, out.read_bytes()


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


def kernel_names(src):
    return [ln.split("void ", 1)[1].split("(", 1)[0].strip()
            for ln in Path(src).read_text().splitlines()
            if ln.startswith("kernel void ")]


def main():
    workdir = EXP / "work" / "anchors"
    src = EXP / "kernels" / "probes.metal"
    report = {}
    for fn in kernel_names(src):
        try:
            arch_path, archbuf = compile_archive(src, fn, workdir)
        except Exception as e:
            report[fn] = {"error": str(e)[:400]}
            print("%-14s COMPILE FAIL %s" % (fn, str(e)[:120]))
            continue
        loc = agxparse.locate_region(archbuf, "_agc.main")
        _, pieces = agxparse.extract_agx(archbuf)
        main_bytes = pieces["_agc.main"]
        recs, leftover = tokenize(main_bytes)
        report[fn] = {
            "archive": str(arch_path),
            "region_off": loc[0] if loc else None,
            "region_len": loc[1] if loc else None,
            "main_len": len(main_bytes),
            "main_hex": main_bytes.hex(),
            "leftover": leftover.hex(),
            "tokens": [{"off": r["off"], "len": r["length"], "mn": r["mnemonic"],
                        "bytes": (main_bytes[r["off"]:r["off"] + r["length"]].hex()
                                  if r.get("length") is not None else None)}
                       for r in recs],
        }
        print("%-14s main=%-4d region=%s leftover=%d  %s" % (
            fn, len(main_bytes),
            ("%d+%d" % loc) if loc else "NONE", len(leftover),
            " ".join("%s@%d" % (r["mnemonic"], r["off"]) for r in recs)))
    outp = workdir / "anchor_report.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", outp)


if __name__ == "__main__":
    main()
