#!/usr/bin/env python3
"""cube_decode.py -- EXP-0204: is `cubearray_coord_const` REACHABLE AT ALL?

A pure DECODE question, answered offline against the PINNED database, with no GPU
and no MSL provocation.  It complements the two provocation experiments that
already failed to reach the descriptor from source (EXP-0148: 0 firings in 1080
corpus files; EXP-0187: 31 authored cube constructs, 0 hits) by asking the
different question: if the four bytes are placed BY HAND, does the descriptor
fire?

Method: synthesise `f0 c0 04 <b3>` for every b3 in 0..255 and decode it
  (a) standalone, and
  (b) spliced at a PROVEN 4-byte instruction boundary in one of our own compiled
      carriers, so the length lookahead sees real following bytes,
and record which descriptor actually claims the bytes.
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import isadb                    # noqa: E402

CENSUS = os.path.join(HERE, "raw", "prefreeze", "census_run2.json")


def main():
    cen = json.load(open(CENSUS))
    buf = bytes.fromhex(cen["carriers"]["deriv"]["stages"]["fragment"]["hex"])
    # proven 4-byte boundaries from a complete forward tokenization
    recs, off = [], 0
    while off < len(buf):
        r, L = isadb.decode_one(buf, off)
        r["off"] = off
        r["len"] = L
        recs.append(r)
        off += L
    sites = [r for r in recs if r["len"] == 4]
    out = {"_question": "does cubearray_coord_const fire when its bytes are placed by hand?",
           "_carrier": "deriv (fragment stage tokenizes completely: %d tokens, no residue)"
                       % len(recs),
           "_sites": [{"off": r["off"], "mnemonic": r["mnemonic"], "hex": r["hex"]}
                      for r in sites],
           "standalone": {}, "in_context": {}}
    c1 = collections.Counter()
    for b3 in range(256):
        raw = bytes.fromhex("f0c004") + bytes([b3])
        try:
            d, L = isadb.decode_one(raw, 0)
            c1[f"{d['mnemonic']}/len{L}"] += 1
        except ValueError as e:
            c1["UNDECODABLE"] += 1
    out["standalone"] = dict(c1)
    for site in sites:
        c2 = collections.Counter()
        for b3 in range(256):
            tb = bytearray(buf)
            tb[site["off"]:site["off"] + 4] = bytes.fromhex("f0c004") + bytes([b3])
            try:
                d, L = isadb.decode_one(bytes(tb), site["off"])
                c2[f"{d['mnemonic']}/len{L}"] += 1
            except ValueError:
                c2["UNDECODABLE"] += 1
        out["in_context"][f"@{site['off']} (was {site['mnemonic']})"] = dict(c2)
    out["_verdict"] = (
        "cubearray_coord_const claims the bytes: "
        + ("YES" if any("cubearray_coord_const" in k
                        for k in list(c1) + [x for v in out["in_context"].values() for x in v])
           else "NO -- another descriptor matches first, so the descriptor is "
                "SHADOWED in the decode table and is unreachable even by direct "
                "synthesis, not merely unprovoked from MSL"))
    p = os.path.join(HERE, "analysis", "cube_decode.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    print("wrote", p)
    print("standalone:", out["standalone"])
    for k, v in out["in_context"].items():
        print("in context", k, v)
    print(out["_verdict"])


if __name__ == "__main__":
    main()
