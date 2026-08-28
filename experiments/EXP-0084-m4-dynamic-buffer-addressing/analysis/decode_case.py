#!/usr/bin/env python3
"""EXP-0084 decode-kind case executable (run once per capture, one process).

Compiles `kernels/probes.metal`'s `splice_target` with tools/shdump, extracts
+ tokenizes `_agc.main` and `_agc.main.constant_program` with tools/agx-isa,
and applies the frozen identification algorithm (analysis/decode_lib.py).
Prints ONE JSON line to stdout; no GPU dispatch occurs (compile-only, static
analysis -- OWN-SHADER / STRUCTURAL evidence, not HW-PROBE).

Usage:
  python3 decode_case.py --shdump BIN --source SRC.metal --function NAME \
      --work-archive PATH
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode_lib  # noqa: E402

TIMEOUTS = {"build": 60, "extract": 20}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shdump", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--function", required=True)
    ap.add_argument("--work-archive", required=True)
    a = ap.parse_args()

    d = decode_lib.full_decode(a.shdump, a.source, a.function, a.work_archive, TIMEOUTS)
    out = {
        "schema": 1,
        "function": a.function,
        "build_ok": d["build"]["exit"] == 0 and not d["build"]["timed_out"] and d["build"]["exception"] is None,
        "main_len": len(d["main_hex"]) // 2 if d["main_hex"] else 0,
        "preamble_len": len(d["preamble_hex"]) // 2 if d["preamble_hex"] else 0,
        "main_leftover_len": len(d.get("main_leftover", "")) // 2,
        "preamble_leftover_len": len(d.get("preamble_leftover", "")) // 2,
        "n_device_load_main": d["ident"]["n_device_load_main"] if d["ident"] else -1,
        "n_device_load_preamble": d["ident"]["n_device_load_preamble"] if d["ident"] else -1,
        "l1": d["ident"]["l1"] if d["ident"] else None,
        "l2": d["ident"]["l2"] if d["ident"] else None,
        "confirmation_ok": d["ident"]["confirmation_ok"] if d["ident"] else False,
    }
    print(json.dumps(out, sort_keys=True))
    try:
        sys.stdout.flush()
    except OSError:
        sys.stderr.write("STDOUT_FLUSH_FAIL\n")
        sys.exit(5)
    sys.exit(0)


if __name__ == "__main__":
    main()
