#!/usr/bin/env python3
"""EXP-0179 arm Z -- the CALL CENSUS. Compile-only; no GPU dispatch.

Question: which of OUR OWN MSL constructs make the compiler emit an out-of-line
`call`, and which are inlined away?

DECLARED CLEAN-ROOM BOUNDARY (PRE_REGISTRATION section 0). This script reports,
per authored construct, whether the machine code compiled FROM OUR OWN SOURCE
contains a call. It does not model, threshold, or explain Apple's inlining
heuristic, and it inspects no Apple binary. Compiling our own MSL and analysing
the bytes produced from it is CLAUDE.md allowed technique 3 / CODEX.md
OWN-SHADER.

Detection is done TWO independent ways and both are recorded, because a
tokenizer that mis-lengths an instruction would otherwise silently hide it:

  1. RAW BYTE SCAN for the descriptor's own `match` bytes -- `call` is pinned at
     byte0 == 0x0f, byte+1 == 0x05, byte+2 == 0x54, byte+4 == 0x8f; `call_indirect`
     at byte0 == 0x0f, byte+1 == 0x80. The scan is position-independent and does
     not depend on the length rule being right.
  2. TOKENIZED census via the PINNED isadb.disassemble over `_agc.main` and over
     the whole __text section.

Usage (on the neo):
  python3 harness/census.py --out raw/prefreeze/census_<id>

CLEAN-ROOM: OWN-SHADER. No Apple binary is disassembled.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H          # noqa: E402  (pins db.json/isadb.py, fail-closed)
import isadb                     # noqa: E402  (the PINNED copy, via isa_helpers)

TOOLS = EXP / "tools"
SHDUMP = TOOLS / "shdump" / "shdump"
AGXPARSE = TOOLS / "shdump" / "agxparse.py"
FNDUMP = EXP / "harness" / "fndump"
KDIR = EXP / "kernels" / "census"

TIMEOUT = 300

# (id, file, function, mode, extra)
#   mode: "compute" | "render" | "linked"
CONSTRUCTS = [
    ("C01_plain_static",      "c_inline.metal",    "k_inline_ctl",      "compute", {}),
    ("C02_always_inline",     "c_inline.metal",    "k_always_inline",   "compute", {}),
    ("C03_noinline_gnu",      "c_noinline.metal",  "k_noinline_gnu",    "compute", {}),
    ("C04_noinline_cxx11",    "c_noinline.metal",  "k_noinline_cxx",    "compute", {}),
    ("C05_two_call_sites",    "c_noinline.metal",  "k_twocall",         "compute", {}),
    ("C06_noinline_void",     "c_noinline.metal",  "k_noinline_void",   "compute", {}),
    ("C07_noinline_float4",   "c_noinline.metal",  "k_noinline_vec4",   "compute", {}),
    ("C08_noinline_struct",   "c_noinline.metal",  "k_noinline_struct", "compute", {}),
    ("C09_twelve_args",       "c_noinline.metal",  "k_manyargs",        "compute", {}),
    ("C10_large_body_noattr", "c_size.metal",      "k_bigbody",         "compute", {}),
    ("C11_many_sites_noattr", "c_size.metal",      "k_manysites",       "compute", {}),
    ("C12_tail_recursion",    "c_recursion.metal", "k_rec_tail",        "compute", {}),
    ("C13_nontail_recursion", "c_recursion.metal", "k_rec_nontail",     "compute", {}),
    ("C14_mutual_recursion",  "c_mutualrec.metal", "k_mutual",          "compute", {}),
    ("C15_nonleaf_chain",     "c_frame.metal",     "k_chain",           "compute", {}),
    ("C16_leaf_only",         "c_frame.metal",     "k_leaf",            "compute", {}),
    ("C17_three_deep",        "c_frame.metal",     "k_deep",            "compute", {}),
    ("C18_spilling_nonleaf",  "c_frame.metal",     "k_bigframe",        "compute", {}),
    ("C19_visible_direct",    "c_visible.metal",   "k_visible_direct",  "compute", {}),
    ("C20_vft_runtime_idx",   "c_visible.metal",   "k_vft_dyn",         "linked",
     {"visible": "vadd,vmul"}),
    ("C21_vft_const_idx",     "c_visible.metal",   "k_vft_const",       "linked",
     {"visible": "vadd,vmul"}),
    ("C22_address_taken",     "c_addrtaken.metal", "k_addrtaken",       "compute", {}),
    ("C23_fragment_call",     "c_frag.metal",      "f_main",            "render",
     {"vertex": "v_main", "fragment": "f_main", "stage": "fragment"}),
    ("C24_vertex_call",       "c_frag.metal",      "v_main",            "render",
     {"vertex": "v_main", "fragment": "f_main", "stage": "vertex"}),
    # ---- EXTENSION, added after census_20260830a returned NO call from either
    # render stage. Not part of the 24 frozen in CAPTURE_CONTRACT.json; run under
    # a separate `*_ext` run id and reported as an extension.
    ("C25_fragment_big_call", "c_frag2.metal",     "f_big",             "render",
     {"vertex": "v_big", "fragment": "f_big", "stage": "fragment"}),
    ("C26_vertex_big_call",   "c_frag2.metal",     "v_big",             "render",
     {"vertex": "v_big", "fragment": "f_big", "stage": "vertex"}),
    ("C27_visible_linked",    "c_visible.metal",   "k_visible_direct",  "linked",
     {"visible": "vadd,vmul"}),
]

# The `match` constraints the PINNED db.json declares. Read from the DB rather
# than hard-coded, so the scan can never drift from the descriptor.
def match_constraints(mnemonic):
    for i in isadb.DB:   # isadb.DB IS the instruction list
        if i["mnemonic"] == mnemonic:
            out = []
            for (start, width, value) in i["match"]:
                if start % 8 or width != 8:
                    return None          # only byte-aligned 8-bit pins are scannable
                out.append((start // 8, value))
            return out, i["length"]
    return None


def raw_scan(buf, mnemonic):
    """Positions where every byte-aligned `match` byte of `mnemonic` holds."""
    mc = match_constraints(mnemonic)
    if mc is None:
        return []
    cons, length = mc
    span = max(off for off, _ in cons) + 1
    hits = []
    for p in range(0, len(buf) - span + 1):
        if all(buf[p + off] == val for off, val in cons):
            hits.append({"off": p, "bytes": buf[p:p + length].hex()})
    return hits


def tokenize(buf):
    try:
        recs, leftover = isadb.disassemble(buf)
    except Exception as e:
        return None, str(e)
    hist = {}
    for r in recs:
        hist[r["mnemonic"]] = hist.get(r["mnemonic"], 0) + 1
    return {"n": len(recs), "leftover": len(leftover), "hist": hist}, None


def sh(cmd, timeout=TIMEOUT):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace"), \
        r.stderr.decode("utf-8", "replace")


def extract(binpath, stage, symbol=None, whole=False):
    cmd = [sys.executable, str(AGXPARSE), str(binpath), "--extract-hex"]
    if stage:
        cmd += ["--stage", stage]
    if whole:
        cmd += ["--whole-text"]
    elif symbol:
        cmd += ["--symbol", symbol]
    rc, out, err = sh(cmd)
    if rc != 0:
        return None, err[-600:]
    hexs = "".join(out.split())
    try:
        return bytes.fromhex(hexs), None
    except ValueError:
        return None, "non-hex output: %r" % out[:200]


def build_one(cid, fname, func, mode, extra, workdir):
    binp = workdir / ("%s.bin" % cid)
    src = KDIR / fname
    if mode == "render":
        cmd = [str(SHDUMP), "-o", str(binp), "--render",
               "--vertex", extra["vertex"], "--fragment", extra["fragment"],
               "--no-fast-math", str(src)]
    elif mode == "linked":
        cmd = [str(FNDUMP), "-o", str(binp), "-f", func,
               "--visible", extra["visible"], "--no-fast-math", str(src)]
    else:
        cmd = [str(SHDUMP), "-o", str(binp), "-f", func,
               "--no-fast-math", str(src)]
    rc, out, err = sh(cmd)
    return binp, rc, out, err, cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    workdir = EXP / "work" / ("census_%d" % os.getpid())
    workdir.mkdir(parents=True, exist_ok=True)

    meta = {
        "experiment": "EXP-0179-g17p-call",
        "arm": "Z/census",
        "host": platform.node(),
        "platform": platform.platform(),
        "t_start": time.time(),
        "db_sha256": hashlib.sha256((H.ISA_DIR / "db.json").read_bytes()).hexdigest(),
        "isadb_sha256": hashlib.sha256((H.ISA_DIR / "isadb.py").read_bytes()).hexdigest(),
        "kernel_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(KDIR.glob("*.metal"))},
        "clean_room": "OWN-SHADER. Only our own MSL is compiled and only the bytes "
                      "produced from it are analysed. Apple's inlining heuristic is a "
                      "DECLARED BOUNDARY and is not characterised; per-construct "
                      "outcomes only, with no interpolation and no claim about why.",
    }
    (outdir / "00_meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True))

    log = open(str(outdir / "census.jsonl"), "a", buffering=1)
    want = set(x.strip() for x in args.only.split(",") if x.strip())
    rows = []
    for (cid, fname, func, mode, extra) in CONSTRUCTS:
        if want and cid not in want:
            continue
        rec = {"id": cid, "source": fname, "function": func, "mode": mode,
               "extra": extra, "t": round(time.time(), 3)}
        try:
            binp, rc, out, err, cmd = build_one(cid, fname, func, mode, extra, workdir)
        except subprocess.TimeoutExpired:
            rec.update({"compiled": False, "reason": "timeout"})
            log.write(json.dumps(rec, sort_keys=True) + "\n")
            os.fsync(log.fileno())
            rows.append(rec)
            continue
        rec["cmd"] = " ".join(str(c) for c in cmd)
        if rc != 0 or not binp.exists():
            rec.update({"compiled": False, "reason": "compile/pipeline rejected",
                        "stderr": err[-1500:]})
            log.write(json.dumps(rec, sort_keys=True) + "\n")
            os.fsync(log.fileno())
            rows.append(rec)
            continue
        rec["compiled"] = True
        stage = extra.get("stage") if mode == "render" else None
        main_b, e1 = extract(binp, stage, symbol="_agc.main")
        text_b, e2 = extract(binp, stage, whole=True)
        rec["extract_err"] = [e1, e2]
        for label, buf in (("main", main_b), ("text", text_b)):
            if buf is None:
                rec[label] = None
                continue
            tok, terr = tokenize(buf)
            rec[label] = {
                "len": len(buf),
                "sha256": hashlib.sha256(buf).hexdigest(),
                "tokenized": tok, "tokenize_error": terr,
                "raw_call": raw_scan(buf, "call"),
                "raw_call_indirect": raw_scan(buf, "call_indirect"),
                "raw_ret": raw_scan(buf, "ret"),
                "raw_frame_prologue": raw_scan(buf, "frame_prologue"),
                "raw_link_save_restore": raw_scan(buf, "link_save_restore"),
            }
        m = rec.get("main") or {}
        t = rec.get("text") or {}
        rec["verdict"] = {
            "call_in_main": len((m.get("raw_call") or [])),
            "call_in_text": len((t.get("raw_call") or [])),
            "call_indirect_in_main": len((m.get("raw_call_indirect") or [])),
            "ret_in_text": len((t.get("raw_ret") or [])),
            "nonleaf_frame_in_text": len((t.get("raw_frame_prologue") or [])),
            "emits_call": len((m.get("raw_call") or [])) > 0
                          or len((m.get("raw_call_indirect") or [])) > 0,
        }
        log.write(json.dumps(rec, sort_keys=True) + "\n")
        os.fsync(log.fileno())
        rows.append(rec)
        print("%-24s compiled=%s call_in_main=%d call_indirect=%d"
              % (cid, rec["compiled"], rec["verdict"]["call_in_main"],
                 rec["verdict"]["call_indirect_in_main"]))
    log.close()
    (outdir / "01_rows.json").write_text(json.dumps(rows, indent=1, sort_keys=True))
    print("CENSUS DONE", len(rows), "constructs ->", outdir)


if __name__ == "__main__":
    main()
