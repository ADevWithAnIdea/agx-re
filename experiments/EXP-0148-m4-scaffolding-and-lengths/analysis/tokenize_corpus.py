#!/usr/bin/env python3
"""EXP-0148 analysis step 1 -- tokenize the whole own-MSL corpus with a chosen
copy of the ISA DB and emit a per-instance record for every descriptor firing.

Usage:  python3 tokenize_corpus.py <isadb_dir> <out.jsonl> <summary.json> [--resync]

`--resync` continues past an undecodable byte by advancing one 2-byte parcel and
retrying.  That is a CENSUS aid, not a clean tokenization: gaps are recorded as
`<gap>` pseudo-records so the resulting statistics stay honest.

The isadb_dir must contain isadb.py + db.json.  We import the copy in that
directory so the live tools/agx-isa/ tree is never mutated by this experiment.

CLEAN-ROOM: input is the hex of _agc.main bytes compiled from OUR OWN MSL
(experiments/EXP-M4-13-full-corpus/{hex,corpus}).  No Apple binary is read.
"""
import json, os, sys, importlib.util, collections

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")


def load_isadb(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location("isadb_%d" % abs(hash(d)), os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def walk(isadb, buf, resync):
    """Return a list of {off,mnem,len,hex} plus gap markers."""
    seq = []
    off = 0
    n = len(buf)
    while off < n:
        try:
            rec, length = isadb.decode_one(buf, off)
        except Exception as e:
            seq.append({"off": off, "mnem": "<gap>", "len": 2, "hex": buf[off:off+2].hex(),
                        "err": str(e)[:80]})
            if not resync:
                return seq, n - off
            off += 2
            continue
        seq.append({"off": off, "mnem": rec["mnemonic"], "len": length, "hex": rec["hex"]})
        off += length
    return seq, 0


def main():
    isadir, outp, summp = sys.argv[1], sys.argv[2], sys.argv[3]
    resync = "--resync" in sys.argv
    isadb = load_isadb(isadir)

    files = sorted(f for f in os.listdir(HEXDIR) if f.endswith(".hex"))
    counts = collections.Counter()
    gap_files, gap_bytes, total_bytes, total_instrs = [], 0, 0, 0
    with open(outp, "w") as fh:
        for fn in files:
            buf = bytes.fromhex(open(os.path.join(HEXDIR, fn)).read().strip())
            total_bytes += len(buf)
            seq, tail = walk(isadb, buf, resync)
            ngap = sum(1 for s in seq if s["mnem"] == "<gap>")
            if ngap or tail:
                gap_files.append(fn)
                gap_bytes += ngap * 2 + tail
            for i, s in enumerate(seq):
                counts[s["mnem"]] += 1
                if s["mnem"] == "<gap>":
                    continue
                total_instrs += 1
                fh.write(json.dumps({
                    "file": fn, "idx": i, "off": s["off"], "mnem": s["mnem"],
                    "len": s["len"], "hex": s["hex"],
                    "prev": seq[i-1]["mnem"] if i > 0 else "<BOF>",
                    "prev_hex": seq[i-1]["hex"] if i > 0 else "",
                    "next": seq[i+1]["mnem"] if i + 1 < len(seq) else "<EOF>",
                    "next_hex": seq[i+1]["hex"] if i + 1 < len(seq) else "",
                }) + "\n")
            fh.flush()
    summ = {"resync": resync, "files": len(files), "clean_files": len(files) - len(gap_files),
            "gap_files": gap_files, "gap_bytes": gap_bytes, "total_bytes": total_bytes,
            "total_instrs": total_instrs, "counts": dict(counts.most_common())}
    json.dump(summ, open(summp, "w"), indent=1)
    print(json.dumps({k: summ[k] for k in ("resync", "files", "clean_files", "gap_bytes",
                                           "total_bytes", "total_instrs")}))


if __name__ == "__main__":
    main()
