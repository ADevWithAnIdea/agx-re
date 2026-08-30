#!/usr/bin/env python3
"""EXP-0210 -- Gate E pair comparison: identical actual-byte ledgers + (arm, value) agreement.

    python3 analysis/pairwise.py <runA.jsonl> <runB.jsonl> [--label X]

Gate E asks for "two clean runs in reversed or shuffled case order, identical actual-byte
ledgers, and no victim/cascade evidence".  This computes exactly those three things and
nothing else.  It does not promote, label, or judge semantics; each source experiment's own
`analysis/verdicts*.py` does that, unedited.

Agreement is keyed by **(arm, field, value, byte_index, carrier)** -- whichever of those the
record carries -- and compares the `observed` payload with volatile timing excluded.  The
pooled-across-arms, `gputime_ns`-inclusive key is a known checker defect (EXP-0202 section
3.1) and is not used here.

Hard outcomes (`fault`, `hang`, `cmdbuf_error`, `measurement_failure`, `invalid_run`,
`undecodable`) are counted SEPARATELY from payload agreement and reported both ways, so a
fault/clean flip cannot be silently folded into or out of the agreement number.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict

KEYFIELDS = ("arm", "field", "value", "byte_index", "carrier", "case", "case_id",
             "idx", "seq", "instr", "kind", "offset", "name", "sub", "variant")
# `idx`/`seq` are dispatch-order counters in some harnesses and identity in others; they are
# used only when the remaining key fields do not already make the key unique.
ORDER_ONLY = ("idx", "seq")
HARD = {"fault", "hang", "cmdbuf_error", "measurement_failure", "invalid_run",
        "undecodable", "timeout", "victim", "not_written"}
VOLATILE = {"gputime_ns", "gputime", "t", "ts", "elapsed", "duration_ns", "wall",
            "time_ns", "cpu_ns"}


def load(path):
    out = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    return out


def strip_volatile(o):
    if isinstance(o, dict):
        return {k: strip_volatile(v) for k, v in sorted(o.items())
                if k.lower() not in VOLATILE}
    if isinstance(o, list):
        return [strip_volatile(x) for x in o]
    return o


def mkkey(r, fields):
    return tuple(json.dumps(r.get(f), sort_keys=True, default=str) for f in fields)


def ledger_of(r):
    l = r.get("ledger")
    if isinstance(l, dict):
        return l
    return {k: r.get(k) for k in
            ("actual_bytes", "actual_instr", "requested_value", "decoded_value",
             "bytes_match", "ledger_ok", "requested_instr", "instr_offset")
            if k in r}


def actual_bytes(r):
    l = ledger_of(r)
    for k in ("actual_instr", "actual_bytes", "actual", "bytes"):
        if l.get(k):
            return l[k]
    return r.get("bytes")


def payload(r):
    for k in ("observed", "obs", "out", "readback"):
        if k in r:
            return json.dumps(strip_volatile(r[k]), sort_keys=True, default=str)
    return json.dumps(strip_volatile({k: v for k, v in r.items()
                                      if k in ("post", "regs", "outs", "values")}),
                      sort_keys=True, default=str)


def outcome(r):
    for k in ("outcome", "result", "status_class", "classification"):
        v = r.get(k)
        if isinstance(v, str):
            return v
    return "?"


def pick_keyfields(A, B):
    """Smallest prefix of KEYFIELDS (order counters last) that is unique in both runs."""
    present = [f for f in KEYFIELDS if f not in ORDER_ONLY
               and any(f in r for r in A[:200])]
    for n in range(1, len(present) + 1):
        fs = present[:n]
        if (len({mkkey(r, fs) for r in A}) == len(A)
                and len({mkkey(r, fs) for r in B}) == len(B)):
            return fs, True
    for extra in ORDER_ONLY:
        fs = present + [extra]
        if (len({mkkey(r, fs) for r in A}) == len(A)
                and len({mkkey(r, fs) for r in B}) == len(B)):
            return fs, True
    return present, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runA")
    ap.add_argument("runB")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    A, B = load(a.runA), load(a.runB)
    fs, unique = pick_keyfields(A, B)
    ka = defaultdict(list)
    kb = defaultdict(list)
    for r in A:
        ka[mkkey(r, fs)].append(r)
    for r in B:
        kb[mkkey(r, fs)].append(r)
    shared = sorted(set(ka) & set(kb))

    # --- ledger -----------------------------------------------------------------
    led = Counter()
    ledger_diff = []
    for k in shared:
        ra, rb = ka[k][0], kb[k][0]
        xa, xb = actual_bytes(ra), actual_bytes(rb)
        if xa == xb:
            led["actual_bytes_identical"] += 1
        else:
            led["actual_bytes_DIFFER"] += 1
            if len(ledger_diff) < 8:
                ledger_diff.append({"key": k, "A": xa, "B": xb})
    for tag, R in (("A", A), ("B", B)):
        for r in R:
            l = ledger_of(r)
            if l.get("bytes_match") is True:
                led["bytes_match_true_" + tag] += 1
            elif l.get("bytes_match") is False:
                led["bytes_match_FALSE_" + tag] += 1
            rv, dv = l.get("requested_value"), l.get("decoded_value")
            if rv is not None and dv is not None:
                led["req_eq_dec_" + tag if rv == dv
                    else "req_NE_dec_" + tag] += 1
    enc = {}
    for tag, R in (("A", A), ("B", B)):
        per = defaultdict(set)
        for r in R:
            per[r.get("arm", "?")].add(actual_bytes(r))
        enc[tag] = {k: len(v) for k, v in sorted(per.items())}

    # --- agreement --------------------------------------------------------------
    agree = dis = 0
    hard_flip = soft_dis = 0
    both_hard = 0
    examples = []
    per_arm = defaultdict(lambda: [0, 0])
    for k in shared:
        ra, rb = ka[k][0], kb[k][0]
        oa, ob = outcome(ra), outcome(rb)
        ha, hb = oa in HARD, ob in HARD
        if ha and hb:
            both_hard += 1
            continue
        if ha != hb:
            hard_flip += 1
            dis += 1
            per_arm[ra.get("arm", "?")][1] += 1
            if len(examples) < 8:
                examples.append({"key": k, "A_outcome": oa, "B_outcome": ob,
                                 "class": "hard_flip"})
            continue
        if payload(ra) == payload(rb):
            agree += 1
            per_arm[ra.get("arm", "?")][0] += 1
        else:
            dis += 1
            soft_dis += 1
            per_arm[ra.get("arm", "?")][1] += 1
            if len(examples) < 8:
                examples.append({"key": k, "A_outcome": oa, "B_outcome": ob,
                                 "class": "soft"})

    hardcount = {tag: Counter(outcome(r) for r in R if outcome(r) in HARD)
                 for tag, R in (("A", A), ("B", B))}
    victims = {tag: sum(1 for r in R if r.get("victim") is True
                        or "InnocentVictim" in json.dumps(r.get("fault_class") or ""))
               for tag, R in (("A", A), ("B", B))}
    comparable = agree + dis
    out = {
        "label": a.label,
        "runA": a.runA, "runB": a.runB,
        "n_A": len(A), "n_B": len(B),
        "key_fields": fs, "key_unique": unique,
        "shared_keys": len(shared),
        "A_only": len(set(ka) - set(kb)), "B_only": len(set(kb) - set(ka)),
        "ledger": dict(led),
        "ledger_diff_examples": ledger_diff,
        "distinct_actual_encodings_per_arm": enc,
        "agreement": {"comparable": comparable, "agree": agree, "disagree": dis,
                      "pct": (round(100.0 * agree / comparable, 4)
                              if comparable else None),
                      "hard_flip": hard_flip, "soft_disagree": soft_dis,
                      "both_hard_excluded": both_hard},
        "disagreement_examples": examples,
        "hard_outcomes": {t: dict(c) for t, c in hardcount.items()},
        "victim_records": victims,
        "worst_arms": sorted(({"arm": k, "agree": v[0], "disagree": v[1]}
                              for k, v in per_arm.items() if v[1]),
                             key=lambda d: -d["disagree"])[:10],
    }
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
