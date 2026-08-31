#!/usr/bin/env python3
"""EXP-0216 Q2/Q3 — the two experiments whose `instr` key their own bytes do not
decode to.

Three things are computed, in this order, and NONE of them consults the key:

  1. MATCH ARITHMETIC.  For every committed encoding, which of the rival
     descriptors' match bits hold?  A descriptor no committed encoding satisfies
     did not run, whatever the key says.  For `cvt_f2h` the single 8-bit
     constraint byte0 == 0x11 is decomposed into its low nibble (the opcode
     group) and its high nibble (which every dst-parameterised sibling in this
     database spends on a `dst` register).

  2. SPAN OVERLAY, PER SWEPT BYTE.  For each byte the experiment actually swept,
     which field of the KEYED descriptor covers it, and which field of the
     TOKENIZED sibling?  This is the operand-hazard test named in the dispatch:
     if the two names sit on the SAME (start,width), a re-pointing cannot move a
     verdict onto a different operand.  If they differ, it can, and nothing may
     be said until behaviour decides.

  3. TOKENIZER vs DESCRIPTOR.  The committed anchor bytes are run through
     isadb.decode_one so the failure can be attributed to the LENGTH RULE or to
     a descriptor `match`, which are different defects in different files.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import (BY_MNEM, REPO, dump, fields_covering, iter_records,  # noqa
                     match_ok, outcome_of)

sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (our own tool, read-only)

CASES = [
    ("EXP-0171-g17p-ilogic-srca", "bf_alu", ["bf_add_dst", "bf_mul_dst"]),
    ("EXP-0144-m4-emit-pack", "cvt_f2h", ["cvt_f2h_dst"]),
]


def match_detail(mnem, hexstr):
    d = BY_MNEM[mnem]
    raw = bytes.fromhex(hexstr)
    if len(raw) < d["length"]:
        return ["SHORT(%d<%d)" % (len(raw), d["length"])]
    v = int.from_bytes(raw[: d["length"]], "little")
    bad = []
    for (s, w, val) in d["match"]:
        got = (v >> s) & ((1 << w) - 1)
        if got != val:
            bad.append("bits[%d:+%d] want %d got %d" % (s, w, val, got))
    return bad


def tokenize(hexstr):
    try:
        rec, ln = isadb.decode_one(bytes.fromhex(hexstr), 0)
        return rec["mnemonic"], ln, None
    except ValueError as e:
        return None, None, str(e)


def run(expdir, keyed, siblings):
    per_byte = defaultdict(Counter)
    tok = Counter()
    matchfail = Counter()
    byte0 = Counter()
    nibbles = Counter()
    n = 0
    keyed_ok = 0
    sib_ok = Counter()
    examples = []
    lens = Counter()
    for rel, ln, r in iter_records(expdir, keyed, None):
        bh = r["bytes"]
        n += 1
        raw = bytes.fromhex(bh)
        lens[len(raw)] += 1
        byte0[raw[0]] += 1
        nibbles[(raw[0] & 0xF, raw[0] >> 4)] += 1
        bi = r.get("byte_index")
        if bi is not None:
            per_byte["swept"][bi] += 1
        m, L, err = tokenize(bh)
        tok[m or ("ERR:" + err.split("(")[0].strip())] += 1
        if match_ok(keyed, bh):
            keyed_ok += 1
        else:
            for b in match_detail(keyed, bh):
                matchfail[b] += 1
        for s in siblings:
            if match_ok(s, bh):
                sib_ok[s] += 1
        if len(examples) < 4:
            examples.append({"file": rel, "line": ln, "bytes": bh,
                             "field_key": r.get("field"),
                             "byte_index": bi, "value": r.get("value"),
                             "tokenized_as": m, "outcome": outcome_of(r)})
    # span overlay per swept byte
    overlay = {}
    for bi in sorted(per_byte["swept"]):
        row = {"n_records": per_byte["swept"][bi],
               keyed: fields_covering(keyed, bi * 8, 8)}
        for s in siblings:
            row[s] = fields_covering(s, bi * 8, 8)
        row["same_span_for_the_operand"] = all(
            sorted((f[1], f[2]) for f in row[keyed]) ==
            sorted((f[1], f[2]) for f in row[s]) for s in siblings
            if row[s] and row[keyed])
        overlay[str(bi)] = row
    return {"exp": expdir, "keyed_instr": keyed, "siblings": siblings,
            "n_records_with_bytes": n,
            "instruction_lengths_seen": dict(lens),
            "records_satisfying_the_keyed_descriptor_match": keyed_ok,
            "records_satisfying_each_sibling_match": dict(sib_ok),
            "which_match_bit_fails_and_how_often": dict(matchfail),
            "byte0_histogram": dict(sorted(byte0.items())),
            "byte0_low_nibble_x_high_nibble": {str(k): v for k, v in sorted(nibbles.items())},
            "tokenizer_says": dict(tok),
            "span_overlay_per_swept_byte": overlay,
            "examples": examples}


if __name__ == "__main__":
    out = [run(*c) for c in CASES]
    dump(out, "q2_sibling.json")
    for o in out:
        print("=" * 78)
        print(o["exp"], "keyed", o["keyed_instr"], "n", o["n_records_with_bytes"])
        print("  lengths          ", o["instruction_lengths_seen"])
        print("  keyed match ok   ", o["records_satisfying_the_keyed_descriptor_match"])
        print("  sibling match ok ", o["records_satisfying_each_sibling_match"])
        print("  match failures   ", o["which_match_bit_fails_and_how_often"])
        print("  tokenizer        ", o["tokenizer_says"])
        for bi, row in o["span_overlay_per_swept_byte"].items():
            print("  byte", bi, "n=%d" % row["n_records"], "same_span=",
                  row["same_span_for_the_operand"])
            for k, v in row.items():
                if k in ("n_records", "same_span_for_the_operand"):
                    continue
                print("      %-14s %s" % (k, v))
