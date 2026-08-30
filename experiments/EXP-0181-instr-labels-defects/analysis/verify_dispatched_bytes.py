#!/usr/bin/env python3
"""EXP-0181 -- prove the DESCRIPTOR itself was executed, not a sibling.

Many of the 30 weak `_instruction` labels sit on dst-GENERALISED siblings of a
HW-validated form (`bf_add_dst` generalises `bf_alu`, `cvt_f2h_dst` generalises
`cvt_f2h`, ...).  A raw record tagged `"instr": "bf_add_dst"` is the sweeping
harness's own attribution; it is not proof that the bytes it dispatched belong to
that descriptor.  This script checks the attribution against the live decoder:
for every distinct `bytes` string in the committed raw that a harness tagged with
one of the 30 mnemonics, it asks `isadb.decode_one` which descriptor claims it.

Reported per (mnemonic, experiment):
  * n_distinct_byte_strings seen;
  * how many decode BACK to the same mnemonic (self-attributed);
  * the mnemonics they decode to instead, with counts;
  * up to 5 example byte strings that DO decode to the mnemonic (these are the
    encodings for which "this descriptor executed on hardware" is literally true).

CLEAN-ROOM: pure re-analysis of our own committed raw + our own db.json.
"""
import json, os, sys, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import isadb  # noqa: E402

EXPROOT = os.path.join(ROOT, "experiments")


def decode_mnem(hexs):
    try:
        buf = bytes.fromhex(hexs)
    except ValueError:
        return "<not-hex>"
    if not buf:
        return "<empty>"
    try:
        d = isadb.decode_one(buf, 0)
    except Exception as e:
        return "<error:%s>" % type(e).__name__
    if isinstance(d, tuple):          # decode_one returns (record, length)
        d = d[0] if d else None
    if d is None:
        return "<no-match>"
    if isinstance(d, dict):
        return d.get("mnemonic") or d.get("instr") or "<dict>"
    return str(d)


def main(argv):
    want = set(argv[1:])
    seen = collections.defaultdict(collections.Counter)   # (m,exp) -> byte-string counter
    for path in glob.iglob(os.path.join(EXPROOT, "EXP-*", "raw", "**", "*.jsonl"),
                           recursive=True):
        rel = os.path.relpath(path, ROOT)
        exp = rel.split(os.sep)[1]
        with open(path, "r", errors="replace") as fh:
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
                b = r.get("bytes")
                if isinstance(b, str) and b:
                    seen[(m, exp)][b] += 1
    out = {}
    cache = {}
    for (m, exp), ctr in sorted(seen.items()):
        self_ok, others, examples = 0, collections.Counter(), []
        for b in ctr:
            if b not in cache:
                cache[b] = decode_mnem(b)
            d = cache[b]
            if d == m:
                self_ok += 1
                if len(examples) < 5:
                    examples.append(b)
            else:
                others[d] += 1
        out.setdefault(m, {})[exp] = {
            "distinct_byte_strings": len(ctr),
            "decode_back_to_self": self_ok,
            "decode_to_other": dict(others.most_common(8)),
            "self_examples": examples,
        }
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
