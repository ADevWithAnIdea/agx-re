#!/usr/bin/env python3
"""EXP-0181 -- for each of the 30 instructions, find the UNMUTATED (baseline/anchor)
byte string each sweeping experiment actually dispatched, and ask the live decoder
whether the committed descriptor claims it.

Two different facts get separated here, and the label decision turns on which one
an experiment established:
  * the HARDWARE FORM executed and produced its documented result (an oracle-scored
    baseline case with outcome `ok`), and
  * the committed DESCRIPTOR claims those bytes (`decode_one` returns the mnemonic
    at the descriptor's own length).
A descriptor can have the first without the second -- e.g. the bfloat cluster, whose
G17P anchors are DEF-0171-2's untokenizable byte+1 == 0x00 forms.

CLEAN-ROOM: pure re-analysis of our own committed raw + our own db.json.
"""
import json, os, sys, glob, collections, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import isadb  # noqa: E402
EXPROOT = os.path.join(ROOT, "experiments")

BASELINE = re.compile(r"baseline|anchor|unmutated|_semantic|SEM", re.I)


def dec(h):
    try:
        r = isadb.decode_one(bytes.fromhex(h), 0)
    except Exception as e:
        return "ERR:%s" % e
    if isinstance(r, tuple):
        r = r[0]
    return (r or {}).get("mnemonic", "?") if isinstance(r, dict) else str(r)


def main(argv):
    want = set(argv[1:])
    rows = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    notes = collections.defaultdict(set)
    for path in glob.iglob(os.path.join(EXPROOT, "EXP-*", "raw", "**", "*.jsonl"),
                           recursive=True):
        exp = os.path.relpath(path, ROOT).split(os.sep)[1]
        with open(path, errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                m = r.get("instr") or r.get("mnemonic")
                if not isinstance(m, str) or (want and m not in want):
                    continue
                tag = " ".join(str(r.get(k, "")) for k in ("kind", "arm", "group", "field"))
                if not BASELINE.search(tag):
                    continue
                b = r.get("bytes")
                if not isinstance(b, str) or not b:
                    continue
                rows[m][exp][(b, r.get("outcome"))] += 1
                n = r.get("note")
                if isinstance(n, str) and n:
                    notes[m].add(n[:200])
    out = {}
    for m in sorted(rows):
        per = {}
        for exp in sorted(rows[m]):
            recs = []
            for (b, oc), n in sorted(rows[m][exp].items(), key=lambda kv: -kv[1])[:12]:
                recs.append({"bytes": b, "outcome": oc, "n": n, "decodes_to": dec(b)})
            per[exp] = recs
        out[m] = {"baselines": per, "baseline_notes": sorted(notes[m])[:8]}
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
