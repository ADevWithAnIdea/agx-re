#!/usr/bin/env python3
"""EXP-0157 resync tokenizer.

`isadb.disassemble` stops at the first undecodable byte. Our ray-query
carriers are ~25 kB of `_agc.main` and desynchronise early, so a strict walk
sees only the first few hundred bytes. This walker continues past a bad byte
by one 2-byte parcel (the technique EXP-0148 used for its corpus census) and
records, for every token, whether its immediate predecessor was a gap.

A token whose predecessor is `<gap>` is MANUFACTURED, not observed: the walk
could have re-entered the stream mid-instruction. Every consumer here treats
`after_gap` tokens as candidates to be confirmed by an independent method
(differential compilation), never as located instructions.

CLEAN-ROOM: operates only on bytes compiled from our own MSL.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402


def walk(b):
    """Yield dicts: offset, mnemonic, length, fields, after_gap."""
    out = []
    off = 0
    after_gap = False
    n = len(b)
    while off < n:
        ln = isadb.instr_length(b[off:])
        if not ln or off + ln > n:
            off += 2
            after_gap = True
            continue
        recs, left = isadb.disassemble(b[off:off + ln])
        if not recs or left or recs[0].get("length") != ln:
            off += 2
            after_gap = True
            continue
        out.append({"offset": off, "mnemonic": recs[0]["mnemonic"], "length": ln,
                    "fields": recs[0].get("fields") or {},
                    "bytes": b[off:off + ln].hex(), "after_gap": after_gap})
        after_gap = False
        off += ln
    return out


if __name__ == "__main__":
    import collections
    import json
    for path in sys.argv[1:]:
        b = bytes.fromhex(Path(path).read_text().strip())
        toks = walk(b)
        c = collections.Counter(t["mnemonic"] for t in toks)
        cg = collections.Counter(t["mnemonic"] for t in toks if not t["after_gap"])
        print("== %s  %d bytes  %d tokens (%d clean-predecessor)"
              % (path, len(b), len(toks), sum(1 for t in toks if not t["after_gap"])))
        print(json.dumps({"all": dict(c.most_common()),
                          "clean_predecessor": dict(cg.most_common())}, indent=1))
