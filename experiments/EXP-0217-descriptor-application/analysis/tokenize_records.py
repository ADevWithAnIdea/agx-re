#!/usr/bin/env python3
"""EXP-0217 -- second tokenization metric, on the COMMITTED RECORD SETS.

The 1080-file own-MSL corpus is M4 compiler output and contains no native
bfloat at all, so a bfloat descriptor change is invisible to it. This script
supplies the missing denominator: it tokenizes every committed dispatched
encoding of the two record sets EXP-0216 analysed, with whichever tools/agx-isa
tree is named, and reports the mnemonic histogram.

Usage: tokenize_records.py <isadb_dir> <out.json>

CLEAN-ROOM: reads only this repository's own committed raw records (our own
MSL, compiled at runtime and dispatched on our own hardware). No Apple binary.
"""
import collections
import importlib.util
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

CASES = [
    ("EXP-0171-g17p-ilogic-srca", "bf_alu"),
    ("EXP-0144-m4-emit-pack", "cvt_f2h"),
]


def load_isadb(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location("isadb_%d" % abs(hash(d)),
                                                  os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def iter_bytes(expdir, want_instr):
    root = os.path.join(REPO, "experiments", expdir, "raw")
    for dirpath, _dn, filenames in os.walk(root):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            with open(os.path.join(dirpath, fn)) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line[0] != "{":
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if r.get("instr") != want_instr or not r.get("bytes"):
                        continue
                    yield r["bytes"]


def main():
    isadir, outp = sys.argv[1], sys.argv[2]
    isadb = load_isadb(isadir)
    out = {}
    for expdir, keyed in CASES:
        counts = collections.Counter()
        n = 0
        for hexs in iter_bytes(expdir, keyed):
            n += 1
            try:
                rec, _L = isadb.decode_one(bytes.fromhex(hexs), 0)
                counts[rec["mnemonic"]] += 1
            except Exception as e:
                counts["ERR:" + str(e).split(" at offset")[0]] += 1
        out[keyed] = {"exp": expdir, "n_records": n,
                      "tokenized_as": dict(counts.most_common())}
    json.dump(out, open(outp, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: {"n": v["n_records"], "top": list(v["tokenized_as"].items())[:6]}
                      for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
