#!/usr/bin/env python3
"""EXP-0180 anchor resolution: compile OUR OWN MSL (kernels/probes.metal) with
tools/shdump, extract `_agc.main`, tokenize it with the PINNED tools/agx-isa, and record
where each lift-control anchor lives. Writes work/anchors/anchor_report.json.

A miss is REPORTED, never patched around: adding a kernel to chase an anchor after the
freeze is exactly the post-hoc fitting the freeze exists to prevent.

CLEAN-ROOM: the only machine code inspected is the compiled form of our own MSL.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def find_tools():
    for cand in (EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


FUNCS = ["k_hadd", "k_hmul", "k_hsat", "k_hfma", "k_hfma_abs", "k_hfma_satabs"]


def main():
    tools = find_tools()
    agxparse = _load("agxparse", tools / "shdump" / "agxparse.py")
    shdump = tools / "shdump" / "shdump"
    src = EXP / "kernels" / "probes.metal"
    outdir = EXP / "work" / "anchors"
    outdir.mkdir(parents=True, exist_ok=True)
    rep = {}
    for fn in FUNCS:
        binp = outdir / ("%s.bin" % fn)
        r = subprocess.run([str(shdump), "-o", str(binp), "-f", fn, "--no-fast-math", str(src)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if r.returncode != 0 or not binp.exists():
            rep[fn] = {"error": r.stderr.decode()[-600:]}
            continue
        _, pieces = agxparse.extract_agx(binp.read_bytes())
        main_bytes = pieces.get("_agc.main")
        if main_bytes is None:
            rep[fn] = {"error": "no _agc.main"}
            continue
        toks, off, leftover = [], 0, 0
        while off < len(main_bytes):
            ln = None
            try:
                import isadb
                ln = isadb.instr_length(main_bytes, off)
            except Exception:
                ln = None
            if not ln:
                toks.append({"off": off, "len": None, "mn": "<unknown>", "bytes": None})
                leftover = len(main_bytes) - off
                break
            mn, _ = H.tokenize_first(main_bytes[off:off + ln])
            toks.append({"off": off, "len": ln, "mn": mn or "<unknown>",
                         "bytes": main_bytes[off:off + ln].hex()})
            off += ln
        rep[fn] = {"main_hex": main_bytes.hex(), "main_len": len(main_bytes),
                   "tokens": toks, "leftover": leftover}
    (outdir / "anchor_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True))
    for fn, r in sorted(rep.items()):
        if "error" in r:
            print("%-16s ERROR %s" % (fn, r["error"][:120]))
        else:
            print("%-16s len=%-4d leftover=%-3d  %s" % (
                fn, r["main_len"], r["leftover"],
                " ".join("%s@%s" % (t["mn"], t["off"]) for t in r["tokens"])))


if __name__ == "__main__":
    main()
