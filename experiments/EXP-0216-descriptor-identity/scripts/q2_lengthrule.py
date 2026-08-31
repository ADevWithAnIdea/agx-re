#!/usr/bin/env python3
"""EXP-0216 Q2 — is the bfloat failure a DESCRIPTOR defect or a LENGTH-RULE one?

The dispatch asks explicitly whether a finding is a defect in `isadb.py`'s
tokenizer rather than in `db.json`'s descriptors.  For the bfloat group it is
both, in different places, and they are separable:

  * DESCRIPTOR: `bf_alu`'s match pins byte0 == 0x11 (a full byte, of which the
    high nibble is a destination register everywhere else in this group) and
    byte1 == 0x02.  Zero committed encodings satisfy it.
  * LENGTH RULE: `isadb._n1_len` gates the bfloat branch on
    `byte2 in (0x1c, 0x1d, 0x1e)`.  This script dispatches the byte-2 values the
    HARDWARE accepted in EXP-0171's NAT carrier through `instr_length` and shows
    how many of them the length rule can still not size.

Everything below is our own tool run against our own committed bytes.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import REPO, dump, iter_records, outcome_of  # noqa

sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402


def run():
    cases = {}
    for rel, ln, r in iter_records("EXP-0171-g17p-ilogic-srca", "bf_alu", None):
        if r.get("byte_index") != 2 or r.get("carrier") != "NAT":
            continue
        b2 = bytes.fromhex(r["bytes"])[2]
        cases.setdefault(b2, (r["bytes"], outcome_of(r),
                              tuple((r.get("observed") or {}).get("words") or ())[:4],
                              rel, ln))
    accepted, rows = [], {}
    for b2, (bh, oc, w, rel, ln) in sorted(cases.items()):
        try:
            rec, L = isadb.decode_one(bytes.fromhex(bh), 0)
            tok, err = rec["mnemonic"], None
        except ValueError as e:
            tok, L, err = None, None, str(e)
        rows["0x%02x" % b2] = {"bytes": bh, "hw_outcome": oc,
                               "first4_words": list(w), "tokenized_as": tok,
                               "length": L, "tokenizer_error": err,
                               "file": rel, "line": ln}
        if oc == "ok":
            accepted.append(b2)
    base = rows["0x1c"]["first4_words"]
    ident = [hex(b) for b in accepted if rows["0x%02x" % b]["first4_words"] == base]
    sized = [hex(b) for b in accepted if rows["0x%02x" % b]["length"] is not None]
    return {
        "carrier": "EXP-0171 NAT (own-MSL bfloat add lifted from G17P), byte 2 swept 0..255",
        "n_byte2_values": len(cases),
        "hardware_accepted_byte2_values": [hex(b) for b in accepted],
        "of_those_bit_identical_to_the_0x1c_baseline": ident,
        "of_those_the_length_rule_can_size": sized,
        "length_rule_gate": "isadb._n1_len: bfloat branch requires byte2 in "
                            "(0x1c, 0x1d, 0x1e)",
        "consequence": "%d of %d hardware-accepted byte-2 encodings have NO length "
                       "under today's isadb; decode_one raises "
                       "'unknown instruction length (byte0=0x31)' on them."
                       % (len(accepted) - len(sized), len(accepted)),
        "per_byte2": rows,
    }


if __name__ == "__main__":
    o = run()
    dump([o], "q2_lengthrule.json")
    print(o["hardware_accepted_byte2_values"])
    print("bit-identical to 0x1c:", o["of_those_bit_identical_to_the_0x1c_baseline"])
    print("length rule can size :", o["of_those_the_length_rule_can_size"])
    print(o["consequence"])
