#!/usr/bin/env python3
"""EXP-0216 Q1 — the sub-span sufficiency test.

Five of the 22 suspects are NARROWINGS: the current span is a strict sub-span of
the span the record declares (`mov_zext16.extend` (24,8) -> (27,5),
`reg_move_cb.form` and `shift_amt_move.kind` (16,8) -> (20,4), `iter_at.grp`
(0,8) -> (7,1)).  A dense sweep of the wider span necessarily dispatches every
value of the narrower one, so the evidence is not lost -- but the narrowing
makes a testable claim:

    PREDICTION IF THE NARROWING IS RIGHT
      the observation is constant across every case that shares the SUB-SPAN
      value, i.e. the bits the repair dropped are inert in this carrier.

    PREDICTION IF THE NARROWING IS WRONG
      observations differ within at least one sub-span group: a dropped bit is
      live, and the repair moved a live bit out of the field.

The test also reports the reverse direction: whether the sub-span alone already
partitions the outcomes (if not, the wider field carries information the narrow
one cannot express).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import (BY_MNEM, bits, dump, fields_covering, iter_records,  # noqa
                     match_ok, outcome_of, span_of)

CASES = [
    ("EXP-0154-g17p-emit-alu", "mov_zext16", "extend"),
    ("EXP-0161-g17p-carry-fspecial", "mov_zext16", "extend"),
    ("EXP-0169-g17p-rerecord", "reg_move_cb", "form"),
    ("EXP-0154-g17p-emit-alu", "shift_amt_move", "kind"),
    ("EXP-0168-g17p-dst-resweep", "iter_at", "grp"),
]


def observable(r):
    o = r.get("observed")
    if isinstance(o, dict):
        for k in ("regs", "post", "digest", "out", "words", "hh"):
            if k in o:
                return json.dumps(o[k], sort_keys=True)
    return json.dumps(o, sort_keys=True)


def run(expdir, instr, field):
    cur = span_of(instr, field)
    rows = defaultdict(lambda: defaultdict(Counter))
    decl = Counter()
    n = 0
    nonmatch = [0]
    ex = None
    for rel, ln, r in iter_records(expdir, instr, field):
        fs, fw = r.get("fstart"), r.get("fwidth")
        v = r.get("value")
        if fs is None or fw is None or not isinstance(v, int):
            continue
        if not (fs <= cur[0] and cur[0] + cur[1] <= fs + fw):
            continue                     # not a narrowing for this record
        decl[(fs, fw)] += 1
        if not match_ok(instr, r["bytes"]):
            nonmatch[0] += 1
            continue                     # no longer this instruction: excluded
        sub = bits(r["bytes"], cur[0], cur[1])
        # context = the encoding with the DECLARED span masked out, so two
        # encodings are only ever compared when everything else is identical
        raw = bytearray.fromhex(r["bytes"])
        for bit in range(fs, fs + fw):
            raw[bit >> 3] &= 0xFF ^ (1 << (bit & 7))
        ctx = (r.get("carrier"), r.get("arm"), bytes(raw).hex())
        rows[ctx][sub][(r["bytes"], outcome_of(r), observable(r))] += 1
        n += 1
        if ex is None:
            ex = {"file": rel, "line": ln, "bytes": r["bytes"]}
    other = [f for f in fields_covering(instr, decl and list(decl)[0][0] or 0,
                                       decl and list(decl)[0][1] or 8)]
    mb = [(s0, w0, v0) for (s0, w0, v0) in BY_MNEM[instr]["match"]]
    out = {"exp": expdir, "row": instr + "." + field,
           "declared": {str(k): v for k, v in decl.items()},
           "current_subspan": cur,
           "n_records_match_preserving": n,
           "n_records_match_destroying_excluded": nonmatch[0],
           "current_match_bits": mb,
           "fields_now_covering_the_declared_span": other,
           "example": ex, "per_carrier": {}}
    for car, groups in rows.items():
        # per group: how many DISTINCT encodings share this sub-span value, and
        # do two distinct encodings disagree?  (Repetitions of one encoding that
        # disagree are run-to-run variance, never a live dropped bit.)
        maxenc = 0
        cross, nondet = {}, {}
        for g, c in groups.items():
            per_enc = defaultdict(set)
            for (bh, oc, ob), _n in c.items():
                per_enc[bh].add((oc, ob))
            maxenc = max(maxenc, len(per_enc))
            obs_sets = {frozenset(v) for v in per_enc.values()}
            if len(per_enc) > 1 and len(obs_sets) > 1:
                cross[str(g)] = len(per_enc)
            nd = [e for e, v in per_enc.items() if len(v) > 1]
            if nd:
                nondet[str(g)] = nd[:3]
        distinct_across = len({frozenset((oc, ob) for (bh, oc, ob) in c)
                               for c in groups.values()})
        if maxenc < 2:
            verdict = ("NO-POWER: the match bits and this field TILE the swept "
                       "span, so exactly one encoding exists per sub-span value; "
                       "a byte sweep cannot separate them")
        elif cross:
            verdict = "NARROWING-REFUTED (two encodings sharing the sub-span value disagree)"
        elif distinct_across > 1:
            verdict = "NARROWING-CONSISTENT (dropped bits inert here)"
        else:
            verdict = "NO-DETECTION-POWER (sub-span does not separate anything)"
        out["per_carrier"][str(car)] = {
            "n_subspan_groups_seen": len(groups),
            "n_subspan_values_possible": 1 << cur[1],
            "max_distinct_encodings_per_group": maxenc,
            "groups_where_two_encodings_disagree": cross,
            "groups_where_one_encoding_disagreed_across_runs": nondet,
            "distinct_observation_sets_across_groups": distinct_across,
            "verdict": verdict}
    return out


if __name__ == "__main__":
    out = [run(*c) for c in CASES]
    dump(out, "q1_subspan.json")
    for o in out:
        print(f"{o['row']:22s} {o['exp'][:26]:26s} decl={list(o['declared'])} "
              f"cur={o['current_subspan']} n_match={o['n_records_match_preserving']} "
              f"n_excl={o['n_records_match_destroying_excluded']} "
              f"now_covering={[f[0] for f in o['fields_now_covering_the_declared_span']]}")
        for car, d in o["per_carrier"].items():
            print(f"    carrier={str(car)[:28]:28s} groups={d['n_subspan_groups_seen']}"
                  f"/{d['n_subspan_values_possible']} xdisagree={len(d['groups_where_two_encodings_disagree'])} "
                  f"maxenc={d['max_distinct_encodings_per_group']} "
                  f"distinct_obs_sets={d['distinct_observation_sets_across_groups']} "
                  f"{d['verdict']}")
