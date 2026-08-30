#!/usr/bin/env python3
"""EXP-0179 -> analysis/call_census.json.

Reduces `raw/prefreeze/census_*/census.jsonl` (arm Z) to the deliverable the
dispatch asks for: WHICH OF OUR OWN MSL CONSTRUCTS PRODUCE A `call`, and which
are inlined away or rejected.

DECLARED CLEAN-ROOM BOUNDARY. Per-construct outcomes only. No interpolation
between constructs, no threshold, no claim about why anything inlined, and no
inspection of any Apple binary. We author our own MSL until the instruction we
want appears (CLAUDE.md allowed technique 3); we do not characterise Apple's
inlining heuristic (a declared P0.8 boundary).
"""
from __future__ import print_function

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, nargs="+",
                    help="one or more raw/prefreeze/<run> directory names")
    ap.add_argument("--out", default=str(HERE / "call_census.json"))
    args = ap.parse_args()

    srcs = [EXP / "raw" / "prefreeze" / r / "census.jsonl" for r in args.run]
    rows = []
    for s_ in srcs:
        rows += [json.loads(ln) for ln in s_.read_text().splitlines() if ln.strip()]

    out = {
        "experiment": "EXP-0179-g17p-call",
        "arm": "Z/census",
        "target": "A18 Pro / G17P (identity recorded in the run's 00_meta.json)",
        "source_raw": [str(s_.relative_to(EXP)) for s_ in srcs],
        "clean_room": ("OWN-SHADER. Only our own MSL was compiled and only the "
                       "bytes produced from it were analysed. Apple's inlining "
                       "heuristic is a DECLARED BOUNDARY (docs/P0-P1-CLOSURE.md "
                       "P0.8) and is NOT characterised here: this table reports "
                       "per-construct outcomes with no interpolation and no claim "
                       "about why a construct inlined."),
        "detection": ("TWO independent methods per construct, both recorded: (1) a "
                      "position-independent RAW BYTE SCAN for the descriptor's own "
                      "byte-aligned `match` pins, which does not depend on the "
                      "length rule; (2) a TOKENIZED census via the pinned "
                      "isadb.disassemble. A disagreement between them is itself a "
                      "reportable defect."),
        "constructs": {},
        "summary": {},
    }
    n_call = n_ind = n_none = n_reject = 0
    for r in rows:
        cid = r["id"]
        e = {"source": r.get("source"), "function": r.get("function"),
             "mode": r.get("mode"), "compiled": r.get("compiled")}
        if not r.get("compiled"):
            e["outcome"] = "REJECTED"
            e["reason"] = r.get("reason")
            e["stderr_tail"] = (r.get("stderr") or "")[-600:]
            n_reject += 1
        else:
            v = r.get("verdict", {})
            m = r.get("main") or {}
            t = r.get("text") or {}
            e.update({
                "call_in_main": v.get("call_in_main"),
                "call_in_text": v.get("call_in_text"),
                "call_indirect_in_main": v.get("call_indirect_in_main"),
                "ret_in_text": v.get("ret_in_text"),
                "nonleaf_frame_in_text": v.get("nonleaf_frame_in_text"),
                "main_len": m.get("len"), "text_len": t.get("len"),
                "main_tokenized_hist": (m.get("tokenized") or {}).get("hist"),
                "main_tokenize_leftover": (m.get("tokenized") or {}).get("leftover"),
                "call_bytes_observed": [h["bytes"] for h in (m.get("raw_call") or [])],
            })
            if v.get("call_in_main"):
                e["outcome"] = "DIRECT_CALL"
                n_call += 1
            elif v.get("call_indirect_in_main"):
                e["outcome"] = "INDIRECT_CALL"
                n_ind += 1
            else:
                e["outcome"] = "NO_CALL (inlined or lowered)"
                n_none += 1
            tok = (m.get("tokenized") or {}).get("hist") or {}
            e["tokenizer_agrees"] = (bool(tok.get("call")) ==
                                     bool(v.get("call_in_main")))
        out["constructs"][cid] = e
    out["summary"] = {"n_constructs": len(rows), "direct_call": n_call,
                      "indirect_call": n_ind, "no_call": n_none,
                      "rejected": n_reject,
                      "HEADLINE": ("the compiler DOES emit an out-of-line call from "
                                   "our own MSL" if n_call else
                                   "NO construct tried produced a direct call")}
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", args.out)
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
