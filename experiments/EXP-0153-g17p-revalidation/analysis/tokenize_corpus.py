#!/usr/bin/env python3
"""EXP-0153 arm G, step 2: tokenize a hex corpus with the committed ISA DB and
report the EXACT metrics EXP-0148 used, so the G17P number and the M4 number
are produced by ONE tokenizer from ONE `db.json`.

Metrics reproduced verbatim from `EXP-0148/analysis/tokenize_corpus.py`:
  files, clean_files, gap_bytes (strict-walk leftover), total_bytes,
  total_instrs, per-mnemonic counts.
`--resync` continues past an undecodable byte by advancing one 2-byte parcel;
that is a census aid, and the gaps are counted honestly.

Usage:
  python3 tokenize_corpus.py <isadb_dir> <hexdir> <out.jsonl> <summary.json> [--resync]
  python3 tokenize_corpus.py --compare <hexdirA> <hexdirB> <out.json>

CLEAN-ROOM: the input is the hex of `_agc.main` bytes compiled from OUR OWN
MSL. No Apple binary is read.
"""
import collections
import importlib.util
import json
import os
import sys


def load_isadb(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location(
        "isadb_%d" % abs(hash(d)), os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def walk(isadb, buf, resync):
    seq, off, n = [], 0, len(buf)
    while off < n:
        try:
            rec, length = isadb.decode_one(buf, off)
        except Exception as e:
            seq.append({"off": off, "mnem": "<gap>", "len": 2,
                        "hex": buf[off:off + 2].hex(), "err": str(e)[:80]})
            if not resync:
                return seq, n - off
            off += 2
            continue
        seq.append({"off": off, "mnem": rec["mnemonic"], "len": length,
                    "hex": rec["hex"]})
        off += length
    return seq, 0


def tokenize_dir(isadb, hexdir, outp, resync):
    files = sorted(f for f in os.listdir(hexdir) if f.endswith(".hex"))
    counts = collections.Counter()
    gap_files, gap_bytes, total_bytes, total_instrs = [], 0, 0, 0
    per_file = {}
    fh = open(outp, "w") if outp else None
    for fn in files:
        buf = bytes.fromhex(open(os.path.join(hexdir, fn)).read().strip())
        total_bytes += len(buf)
        seq, tail = walk(isadb, buf, resync)
        ngap = sum(1 for s in seq if s["mnem"] == "<gap>")
        gb = ngap * 2 + tail
        per_file[fn] = {"bytes": len(buf), "gap_bytes": gb,
                        "clean": (gb == 0)}
        if ngap or tail:
            gap_files.append(fn)
            gap_bytes += gb
        for i, s in enumerate(seq):
            counts[s["mnem"]] += 1
            if s["mnem"] == "<gap>":
                continue
            total_instrs += 1
            if fh:
                fh.write(json.dumps({
                    "file": fn, "idx": i, "off": s["off"], "mnem": s["mnem"],
                    "len": s["len"], "hex": s["hex"]}) + "\n")
    if fh:
        fh.close()
    return {"resync": resync, "hexdir": os.path.abspath(hexdir),
            "files": len(files), "clean_files": len(files) - len(gap_files),
            "gap_files": gap_files, "gap_bytes": gap_bytes,
            "total_bytes": total_bytes, "total_instrs": total_instrs,
            "counts": dict(counts.most_common()), "per_file": per_file}


def compare(dirA, dirB, outp):
    """Byte-identity between two hex trees (H-G2). `dirA` is the reference."""
    A = dict((f, open(os.path.join(dirA, f)).read().strip())
             for f in os.listdir(dirA) if f.endswith(".hex"))
    B = dict((f, open(os.path.join(dirB, f)).read().strip())
             for f in os.listdir(dirB) if f.endswith(".hex"))
    both = sorted(set(A) & set(B))
    same = [f for f in both if A[f] == B[f]]
    diff = [f for f in both if A[f] != B[f]]
    lendiff = [f for f in diff if len(A[f]) != len(B[f])]
    detail = {}
    for f in diff[:200]:
        a, b = A[f], B[f]
        n = min(len(a), len(b))
        first = next((i // 2 for i in range(0, n, 2) if a[i:i + 2] != b[i:i + 2]), None)
        nbyte = sum(1 for i in range(0, n, 2) if a[i:i + 2] != b[i:i + 2])
        detail[f] = {"len_a": len(a) // 2, "len_b": len(b) // 2,
                     "first_diff_byte": first, "n_differing_bytes": nbyte}
    rep = {"dir_a": os.path.abspath(dirA), "dir_b": os.path.abspath(dirB),
           "n_a": len(A), "n_b": len(B), "n_both": len(both),
           "only_a": sorted(set(A) - set(B)), "only_b": sorted(set(B) - set(A)),
           "n_byte_identical": len(same), "n_differing": len(diff),
           "n_length_differing": len(lendiff),
           "pct_byte_identical": (round(100.0 * len(same) / len(both), 2)
                                  if both else None),
           "differing_files": diff, "detail_first_200": detail}
    json.dump(rep, open(outp, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: rep[k] for k in
                      ("n_both", "n_byte_identical", "n_differing",
                       "n_length_differing", "pct_byte_identical")}))
    return rep


def main():
    if sys.argv[1] == "--compare":
        compare(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    isadir, hexdir, outp, summp = sys.argv[1:5]
    resync = "--resync" in sys.argv
    isadb = load_isadb(isadir)
    summ = tokenize_dir(isadb, hexdir, outp if outp != "-" else None, resync)
    json.dump(summ, open(summp, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: summ[k] for k in
                      ("resync", "files", "clean_files", "gap_bytes",
                       "total_bytes", "total_instrs")}))


if __name__ == "__main__":
    main()
