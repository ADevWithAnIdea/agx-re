#!/usr/bin/env python3
"""rules.py -- EXP-0163: exact, machine-checked bit rules for the fields that MOVED.

For every (arm, field) that moved at least one value, describe the moving set
EXACTLY -- as a bit predicate where one fits, otherwise as the literal set --
and group the observations into equivalence classes by their surface-hash set,
so "which values behave alike" is stated from the data rather than guessed.

CLEAN-ROOM: analysis of our own captured observations only.
"""
import argparse, collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import carriers as CA   # noqa: E402


def bit_rule(moved, n=256):
    """Smallest exact description of `moved` as a predicate over the value bits."""
    S = set(moved)
    if not S:
        return "none"
    if len(S) == n:
        return "ALL values"
    for b in range(8):
        if S == {v for v in range(n) if v & (1 << b)}:
            return f"exactly the values with bit{b} set"
        if S == {v for v in range(n) if not (v & (1 << b))}:
            return f"exactly the values with bit{b} clear"
    # constant mask/equality over a subset of bits
    on = (1 << 8) - 1
    off = (1 << 8) - 1
    for v in S:
        on &= v
        off &= ~v & 0xFF
    if on or off:
        cand = {v for v in range(n) if (v & on) == on and (v & off) == 0}
        if cand == S:
            bits_on = [i for i in range(8) if on >> i & 1]
            bits_off = [i for i in range(8) if off >> i & 1]
            return ("exactly the values with "
                    + " and ".join([f"bit{i} set" for i in bits_on]
                                   + [f"bit{i} clear" for i in bits_off]))
    return f"{len(S)} values, set = " + ",".join(hex(v) for v in sorted(S)[:32]) + \
           ("..." if len(S) > 32 else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("-o", default=os.path.join(HERE, "bit_rules.json"))
    args = ap.parse_args()
    targets = {(m, f) for m, fs in CA.TARGETS.items() for f in fs}

    per = collections.defaultdict(dict)     # (arm, field) -> run -> data
    for path in args.runs:
        run = os.path.basename(os.path.dirname(path))
        acc = collections.defaultdict(lambda: {"out": {}, "hh": {}})
        base = {}
        for line in open(path):
            d = json.loads(line)
            if d["field"] == "_baseline":
                base[d["carrier"]] = d["observed"].get("hh")
                continue
            if d["field"].startswith("_"):
                continue
            if (d["instr"], d["field"]) not in targets:
                continue
            e = acc[(d["carrier"], d["field"])]
            e["out"][d["value"]] = d["outcome"]
            if d["observed"].get("status") == "OK":
                e["hh"][d["value"]] = json.dumps(d["observed"]["hh"], sort_keys=True)
        for k, e in acc.items():
            moved = sorted(v for v, o in e["out"].items() if o in ("wrong_value", "silent_zero"))
            faults = sorted(v for v, o in e["out"].items() if o in ("fault", "hang"))
            classes = collections.defaultdict(list)
            for v, h in e["hh"].items():
                classes[h].append(v)
            cl = sorted(([sorted(vs) for vs in classes.values()]), key=lambda x: -len(x))
            # PER-BIT liveness, computed exactly: bit b is LIVE on this arm iff
            # flipping ONLY b changes the observation class for at least one
            # value.  This turns a 256-value sweep into a statement an emitter
            # can use ("bit1 selects X"), and it is derived, not guessed.
            cls = {}
            for h, vs in classes.items():
                for v in vs:
                    cls[v] = h
            live_bits, bit_flips = [], {}
            width = 8 if len(e["out"]) > 2 else 1
            for b in range(width):
                n_diff = sum(1 for v in cls
                             if (v ^ (1 << b)) in cls and cls[v] != cls[v ^ (1 << b)])
                bit_flips[b] = n_diff
                if n_diff:
                    live_bits.append(b)
            per[k][run] = {
                "live_bits": live_bits,
                "bit_flip_counts": bit_flips,
                "n": len(e["out"]), "n_moved": len(moved), "moved": moved,
                "n_faults": len(faults), "faults": faults,
                "rule": bit_rule(moved, 256 if len(e["out"]) > 2 else len(e["out"])),
                "n_equiv_classes": len(cl),
                "equiv_class_sizes": [len(c) for c in cl][:12],
                "equiv_classes": [c[:24] for c in cl][:8],
                "baseline_class_is_largest": (cl and base.get(k[0]) is not None
                                              and json.dumps(base[k[0]], sort_keys=True)
                                              == max(classes, key=lambda h: len(classes[h]))),
            }
    out = {}
    for (arm, fld), runs in sorted(per.items()):
        if all(r["n_moved"] == 0 and r["n_faults"] == 0 for r in runs.values()):
            continue
        out[f"{arm}|{fld}"] = runs
    json.dump(out, open(args.o, "w"), indent=1, sort_keys=True)
    print(f"{'arm | field':58s} {'moved/n':>10s}  classes / live bits / rule")
    for k, runs in sorted(out.items()):
        r0 = list(runs.values())[0]
        agree = len({(tuple(r["moved"]), tuple(r["faults"])) for r in runs.values()}) == 1
        print("%-58s %5d/%-4d  classes=%-3d live_bits=%-16s %s%s" % (
            k, r0["n_moved"], r0["n"], r0["n_equiv_classes"],
            ",".join(str(b) for b in r0["live_bits"]) or "-", r0["rule"][:52],
            "" if agree else "   [CROSS-RUN DISAGREEMENT]"))
    print("\nwrote", args.o)


if __name__ == "__main__":
    main()
