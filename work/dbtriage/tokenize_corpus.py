#!/usr/bin/env python3
"""DB-defect triage -- corpus tokenization metric, identical in shape to
EXP-0148/analysis/tokenize_corpus.py so the numbers are directly comparable
(clean-file count + strict leftover bytes).

Usage: python3 work/dbtriage/tokenize_corpus.py <isadb_dir> <summary.json> [--resync]

CLEAN-ROOM: input is the hex of _agc.main bytes compiled from OUR OWN MSL
(experiments/EXP-M4-13-full-corpus/hex). No Apple binary is read.
"""
import json, os, sys, importlib.util, collections

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")


def load_isadb(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location("isadb_%d" % abs(hash(d)), os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def walk(isadb, buf, resync):
    seq = []
    off = 0
    n = len(buf)
    while off < n:
        try:
            rec, length = isadb.decode_one(buf, off)
        except Exception as e:
            seq.append({"off": off, "mnem": "<gap>", "len": 2})
            if not resync:
                return seq, n - off
            off += 2
            continue
        seq.append({"off": off, "mnem": rec["mnemonic"], "len": length})
        off += length
    return seq, 0


def main():
    isadir, summp = sys.argv[1], sys.argv[2]
    resync = "--resync" in sys.argv
    isadb = load_isadb(isadir)
    files = sorted(f for f in os.listdir(HEXDIR) if f.endswith(".hex"))
    counts = collections.Counter()
    gap_files, gap_bytes, total_bytes, total_instrs = [], 0, 0, 0
    for fn in files:
        buf = bytes.fromhex(open(os.path.join(HEXDIR, fn)).read().strip())
        total_bytes += len(buf)
        seq, tail = walk(isadb, buf, resync)
        ngap = sum(1 for s in seq if s["mnem"] == "<gap>")
        if ngap or tail:
            gap_files.append(fn)
            gap_bytes += ngap * 2 + tail
        for s in seq:
            counts[s["mnem"]] += 1
            if s["mnem"] != "<gap>":
                total_instrs += 1
    summ = {"resync": resync, "files": len(files), "clean_files": len(files) - len(gap_files),
            "gap_files": gap_files, "gap_bytes": gap_bytes, "total_bytes": total_bytes,
            "total_instrs": total_instrs, "counts": dict(counts.most_common())}
    json.dump(summ, open(summp, "w"), indent=1)
    print(json.dumps({k: summ[k] for k in ("resync", "files", "clean_files", "gap_bytes",
                                           "total_bytes", "total_instrs")}))


if __name__ == "__main__":
    main()
