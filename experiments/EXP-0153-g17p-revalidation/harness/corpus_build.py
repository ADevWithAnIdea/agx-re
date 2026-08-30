#!/usr/bin/env python3
"""EXP-0153 arm G, step 1: rebuild the own-MSL corpus ON G17P.

For every program in the committed M4 corpus
(`experiments/EXP-M4-13-full-corpus/hex/<cat>__<name>__<stage>.hex`, 1080
programs from 871 authored `.metal` sources) this compiles the SAME source on
the A18 Pro with our own `shdump` and extracts the same stage's `_agc.main`
bytes with our own `agxparse.py`, writing `<out>/<cat>__<name>__<stage>.hex`.

The stage is taken from the M4 filename, so the two hex trees are directly
comparable file-for-file:

  *__compute.hex           -> shdump (compute pipeline)
  *__vertex.hex / *__fragment.hex -> shdump --render, then agxparse --stage

Compile failures are FIRST-CLASS results and are recorded in `failures.json`
with the compiler's own message, never silently skipped.

CLEAN-ROOM: the only sources compiled and the only bytes inspected are our own
MSL and its compiled output. No Apple binary is introspected.

Usage (on the neo):
  python3 harness/corpus_build.py --corpus <corpus dir> --names <names.txt> \
      --bin-dir bin --out work/hex_g17p --report raw/<run>/corpus_build.json
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402  (only for H.TOOLS)

AGXPARSE = str(H.TOOLS / "shdump" / "agxparse.py")


def build_one(args):
    name, corpus, bin_dir, out_dir, tmp = args
    cat, base, stage = name.rsplit("__", 2)
    src = Path(corpus) / cat / (base + ".metal")
    if not src.exists():
        return name, None, "source-missing:%s" % src
    arch = Path(tmp) / (name + ".bin")
    cmd = [str(Path(bin_dir) / "shdump"), "-o", str(arch), "--no-fast-math"]
    if stage in ("vertex", "fragment"):
        cmd.append("--render")
    cmd.append(str(src))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return name, None, "shdump-timeout"
    if r.returncode != 0 or not arch.exists():
        return name, None, ("shdump-fail:" + (r.stderr or r.stdout or "")[-300:])
    pcmd = [sys.executable, "-B", AGXPARSE, str(arch), "--extract-hex"]
    if stage in ("vertex", "fragment"):
        pcmd[3:3] = ["--stage", stage]
    try:
        p = subprocess.run(pcmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return name, None, "agxparse-timeout"
    finally:
        try:
            os.unlink(str(arch))
        except OSError:
            pass
    if p.returncode != 0:
        return name, None, ("agxparse-fail:" + (p.stderr or "")[-300:])
    hexs = p.stdout.strip()
    if not hexs:
        return name, None, "agxparse-empty"
    (Path(out_dir) / (name + ".hex")).write_text(hexs + "\n")
    return name, len(hexs) // 2, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--names", required=True,
                    help="text file, one <cat>__<name>__<stage> per line")
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / "corpus_tmp"; tmp.mkdir(parents=True, exist_ok=True)
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    names = [l.strip() for l in open(a.names) if l.strip()]
    todo = [(n, a.corpus, a.bin_dir, str(out), str(tmp)) for n in names
            if not (out / (n + ".hex")).exists()]
    print("corpus: %d programs, %d to build" % (len(names), len(todo)), flush=True)
    ok, fail, t0 = {}, {}, time.time()
    for n in names:
        p = out / (n + ".hex")
        if p.exists():
            ok[n] = len(p.read_text().strip()) // 2
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for i, (name, nbytes, err) in enumerate(ex.map(build_one, todo)):
            if err:
                fail[name] = err
            else:
                ok[name] = nbytes
            if (i + 1) % 100 == 0:
                print("  %d/%d  ok=%d fail=%d  %.0fs"
                      % (i + 1, len(todo), len(ok), len(fail), time.time() - t0),
                      flush=True)
                json.dump({"ok": ok, "fail": fail, "partial": True},
                          open(a.report, "w"), indent=1, sort_keys=True)
    rep = {"corpus": a.corpus, "n_requested": len(names), "n_ok": len(ok),
           "n_fail": len(fail), "total_bytes": sum(ok.values()),
           "seconds": round(time.time() - t0, 1), "ok": ok, "fail": fail,
           "target": "G17P", "flags": "shdump --no-fast-math (+ --render for "
                                      "vertex/fragment stages)"}
    json.dump(rep, open(a.report, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: rep[k] for k in ("n_requested", "n_ok", "n_fail",
                                          "total_bytes", "seconds")}))


if __name__ == "__main__":
    main()
