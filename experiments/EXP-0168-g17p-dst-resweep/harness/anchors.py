#!/usr/bin/env python3
"""EXP-0168 anchor extraction (compute arm).

Compiles each authored probe kernel in `kernels/probes.metal` with
`tools/shdump`, tokenizes the resulting `_agc.main` with `tools/agx-isa`, and
reports where each instruction family we need actually lands.

Two anchor kinds:

  * LIFTABLE — a contiguous run of pure-ALU / register-file instructions that
    can be moved verbatim into a synthesized program (carrier STYLE-S). A
    device_load/device_store/branch inside the window would reference the probe
    kernel's own buffer bindings or branch displacements and would not survive
    the move.
  * IN-PLACE — control-flow and memory instructions, which are swept by mutating
    one field where it already sits inside the probe kernel's own compiled
    `_agc.main` and dispatching THAT kernel (carrier STYLE-P).

Structure reused, and cited, from EXP-0154 `harness/anchors.py` (same project,
same rules). Two deliberate differences:

  * `get_sr` is LIFTABLE here. EXP-0154 excluded it with the memory ops, but it
    reads a special register and touches no binding table; EXP-0031 spliced it
    on dispatched kernels. Its `dst` is one of this experiment's targets, so it
    has to be reachable.
  * the report additionally records, per kernel, the FULL byte string of every
    occurrence of every mnemonic, because several arms here need a
    cross-product over occurrences (dst x form) rather than a single anchor.

CLEAN-ROOM: OWN-SHADER. The only machine code inspected is the compiled form of
`kernels/probes.metal`, which we authored.
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


def find_tools():
    for cand in (EXP / "tools",                                # on the neo
                 EXP / "work" / "tools",
                 Path.home() / "agxre" / "EXP-0168" / "tools",
                 EXP.parents[1] / "tools",                      # on the repo host
                 Path.home() / "agxre" / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


TOOLS = find_tools()
agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
SHDUMP = TOOLS / "shdump" / "shdump"

# May NOT appear inside a LIFTED block: touches memory, control flow, or the
# probe kernel's binding table / branch displacements.
NON_LIFTABLE = {
    "device_load", "device_store", "device_atomic", "atomic_mem", "atomic_rmw",
    "atomic_tg", "stop", "jump", "jump_cond", "jmp_exec_any", "jmp_exec_none",
    "if_push", "if_push_pred", "if_pop", "pop_reconverge", "else_pop",
    "while_push", "pop_exec", "call", "ret", "uniform_store",
    "threadgroup_load", "threadgroup_store", "wait", "spill_frame_marker",
    "frame_prologue", "link_save_restore", "vary_store", "frag_color_store",
    "imageblock_store", "tile_read", "tile_read_mrt",
}


def compile_main(source, function, workdir, stage=None):
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
    buf = out.read_bytes()
    _, pieces = agxparse.extract_agx(buf)
    loc = agxparse.locate_region(buf, "_agc.main")
    return pieces["_agc.main"], loc, str(out)


def tokenize(main):
    """Annotate each record with its absolute offset. `isadb.disassemble` can
    return a record whose `length` is None (an instruction whose length rule the
    DB cannot resolve); that is a RESULT about the DB, not a crash, so it is
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


def liftable_window(recs, i, before=0, after=0):
    """(start, end, target_off_in_block, window) for record `i` widened by
    `before`/`after`. Raises if the widened window contains a non-liftable op."""
    lo = max(0, i - before)
    hi = min(len(recs) - 1, i + after)
    window = recs[lo:hi + 1]
    bad = [r["mnemonic"] for r in window if r["mnemonic"] in NON_LIFTABLE]
    if bad:
        raise ValueError("window around %s contains non-liftable %s"
                         % (recs[i]["mnemonic"], bad))
    if any(r.get("length") is None for r in window):
        raise ValueError("window contains an unlengthed instruction")
    start = window[0]["off"]
    end = window[-1]["off"] + window[-1]["length"]
    return start, end, recs[i]["off"] - start, window


def main():
    workdir = EXP / "work" / "anchors"
    src = EXP / "kernels" / "probes.metal"
    funcs = [ln.split("void ", 1)[1].split("(", 1)[0].strip()
             for ln in src.read_text().splitlines()
             if ln.startswith("kernel void ")]
    report = {}
    for fn in funcs:
        try:
            main_bytes, loc, binpath = compile_main(src, fn, workdir)
        except Exception as e:
            report[fn] = {"error": str(e)[:400]}
            print("%-18s COMPILE FAIL %s" % (fn, str(e)[:110]))
            continue
        recs, leftover = tokenize(main_bytes)
        occ = {}
        toks = []
        for i, r in enumerate(recs):
            mn = r["mnemonic"]
            n = occ.get(mn, 0)
            occ[mn] = n + 1
            ln = r.get("length")
            toks.append({
                "i": i, "off": r["off"], "len": ln, "mn": mn, "occ": n,
                "fields": r.get("fields"),
                "bytes": (main_bytes[r["off"]:r["off"] + ln].hex()
                          if ln is not None else None),
                "liftable": mn not in NON_LIFTABLE and ln is not None,
            })
        report[fn] = {
            "main_len": len(main_bytes),
            "main_hex": main_bytes.hex(),
            "region_off": (loc[0] if loc else None),
            "region_len": (loc[1] if loc else None),
            "archive": binpath,
            "leftover": leftover.hex(),
            "counts": occ,
            "tokens": toks,
        }
        print("%-18s len=%-4d leftover=%-3d  %s" % (
            fn, len(main_bytes), len(leftover),
            " ".join("%s@%d" % (t["mn"], t["off"]) for t in toks)))
    outp = workdir / "anchor_report.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", outp)

    # A compact index the case matrix consumes: mnemonic -> [(kernel, occ)...]
    idx = {}
    for fn, rep in report.items():
        for t in rep.get("tokens", []):
            idx.setdefault(t["mn"], []).append(
                {"kernel": fn, "occ": t["occ"], "off": t["off"],
                 "len": t["len"], "bytes": t["bytes"],
                 "liftable": t["liftable"]})
    (workdir / "anchor_index.json").write_text(
        json.dumps(idx, indent=1, sort_keys=True))
    want = ["uniform_mov", "reg_move_c0", "reg_move_c1", "reg_move_c2var",
            "reg_move_c9", "reg_move_cb", "falu2", "falu2i", "falu_acc",
            "get_sr", "copysign", "cvt_f2h", "cvt_f2i", "pack_convert",
            "unpack_convert", "shift_amt_move", "mov_imm", "stop",
            "if_push", "atomic_mem", "matrix_mac"]
    print("\nTARGET ANCHOR AVAILABILITY")
    for mn in want:
        hits = idx.get(mn, [])
        print("  %-16s %d occurrence(s)  %s" % (
            mn, len(hits),
            ", ".join("%s#%d" % (h["kernel"], h["occ"]) for h in hits[:6])))


if __name__ == "__main__":
    main()
