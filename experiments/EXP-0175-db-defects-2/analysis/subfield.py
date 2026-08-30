#!/usr/bin/env python3
"""Shared helper: recover a SUB-BYTE field's behaviour from a dense byte sweep.

A dense 0..255 sweep of byte B contains, for a field F occupying bits
[lo, lo+w) of that byte, exactly 2**w encodings that differ from the anchor
ONLY in F: take the anchor's byte value A and substitute each candidate f:

    v(f) = (A & ~mask) | (f << lo)

Comparing outcomes across those 2**w cases isolates F while holding every other
bit of the byte at the value the compiler itself emitted. This is the EXP-0166
"A5 decomposition"; it is re-implemented here rather than imported so that the
re-derivation does not depend on EXP-0171's own analysis code.
"""
import json, os, collections

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
SRC = os.path.join(REPO, "experiments", "EXP-0171-g17p-ilogic-srca", "raw")
RUNS = ["g17p_20260830_run01", "g17p_20260830_run02"]


def load(run, arm=None):
    """All target/ladder cases of a run, indexed by (carrier_id, byte_index, value)."""
    recs = {}
    dropped = 0
    with open(os.path.join(SRC, run, "sweep.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            if arm and r["arm"] != arm:
                continue
            if r["byte_index"] is None:
                continue
            if r.get("invalid_run"):
                dropped += 1
                continue
            recs[(r["carrier_id"], r["byte_index"], r["value"])] = r
    return recs, dropped


def digest(rec):
    obs = rec.get("observed") or {}
    return obs.get("digest")


def subfield(recs, carrier_id, byte_index, lo, w):
    """-> (anchor_byte, {subvalue: rec}) for the 2**w cases isolating the field."""
    # the anchor byte value is recorded on every case of the group
    anchor = None
    for (cid, bi, v), r in recs.items():
        if cid == carrier_id and bi == byte_index:
            ab = bytes.fromhex(r["anchor_bytes"])
            anchor = ab[byte_index]
            break
    if anchor is None:
        return None, {}
    mask = ((1 << w) - 1) << lo
    out = {}
    for f in range(1 << w):
        v = (anchor & ~mask & 0xFF) | (f << lo)
        r = recs.get((carrier_id, byte_index, v))
        if r is not None:
            out[f] = r
    return anchor, out


def moved(recs, carrier_id, byte_index, lo, w):
    """How many sub-values change the observable vs the anchor sub-value."""
    anchor, cases = subfield(recs, carrier_id, byte_index, lo, w)
    if anchor is None or not cases:
        return None
    mask = ((1 << w) - 1) << lo
    anchor_f = (anchor & mask) >> lo
    base = digest(cases.get(anchor_f)) if anchor_f in cases else None
    n_moved = sum(1 for f, r in cases.items()
                  if f != anchor_f and digest(r) != base)
    return {"anchor_byte": anchor, "anchor_subvalue": anchor_f,
            "n_cases": len(cases), "moved": n_moved,
            "outcomes": dict(collections.Counter(r["outcome"] for r in cases.values())),
            "distinct_digests": len({digest(r) for r in cases.values()})}


def byte_liveness(recs, carrier_id, byte_index):
    """How many of the 256 whole-byte values change the observable."""
    group = {v: r for (cid, bi, v), r in recs.items()
             if cid == carrier_id and bi == byte_index}
    if not group:
        return None
    ab = bytes.fromhex(next(iter(group.values()))["anchor_bytes"])
    base = digest(group.get(ab[byte_index]))
    return {"n": len(group), "anchor_value": ab[byte_index],
            "moved": sum(1 for v, r in group.items()
                         if v != ab[byte_index] and digest(r) != base),
            "distinct_digests": len({digest(r) for r in group.values()})}
