#!/usr/bin/env python3
"""EXP-0195 step 5: re-derive every surviving claim straight from committed raw, with
exact file:line, both byte strings, db.json geometry, bit-span isolation proof, both
oracles, both observations, and the cross-run table.

Reads only experiments/**/raw/**/*.jsonl and tools/agx-isa/db.json.  Trusts no intermediate
produced by EXP-0194 or EXP-0195.
"""
import json, os, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

db = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "db.json")))
val = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "validation.json")))
GEOM = {(i["mnemonic"], f["name"]): (f["start"], f["width"])
        for i in db["instructions"] for f in i.get("fields", [])}

CANDIDATES = [(r["instr"], r["field"]) for r in json.load(open(os.path.join(HERE, "classification.json")))
              if r["verdict_uncited_only"] == "DESK-PROMOTABLE"]
UNCITED = {(r["instr"], r["field"]): r for r in json.load(open(os.path.join(HERE, "classification.json")))}

if not CANDIDATES:
    print("no DESK-PROMOTABLE row to verify")
    raise SystemExit

for mn, fld in CANDIDATES:
    start, width = GEOM[(mn, fld)]
    mask = ((1 << width) - 1) << start
    cur = val["instructions"][mn][fld]
    meta = UNCITED[(mn, fld)]
    print("=" * 100)
    print("%s.%s   db.json start=%d width=%d   (bit span %d..%d)"
          % (mn, fld, start, width, start, start + width - 1))
    print("current label : %s / target %s / evidence %s"
          % (cur["label"], cur.get("target"), cur.get("evidence")))
    print("current note  : %s" % (cur.get("note") or "-"))
    print("uncited exps holding raw : %s" % meta["uncited_exps"])
    print()
    hits = []
    for p in sorted(glob.glob(os.path.join(ROOT, "experiments", "*", "raw", "*", "*.jsonl"))):
        rel = os.path.relpath(p, ROOT)
        exp = rel.split(os.sep)[1]
        with open(p, errors="replace") as fh:
            for ln, line in enumerate(fh, 1):
                if ('"%s"' % fld) not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if str(r.get("instr")) != mn or str(r.get("field")) != fld:
                    continue
                hits.append((rel, ln, exp, r))
    print("%-56s %-6s %-18s %-5s %-6s %-6s %-5s %-6s %-22s %s"
          % ("raw file", "line", "bytes", "enc", "value", "outc", "match", "expect", "observed", "oracle"))
    for rel, ln, exp, r in hits:
        b = r.get("bytes")
        e = ((int.from_bytes(bytes.fromhex(b), "little") >> start) & ((1 << width) - 1)) if isinstance(b, str) else None
        print("%-56s %-6d %-18s %-5s %-6s %-6s %-5s %-6s %-22s %s"
              % (rel.replace("experiments/", ""), ln, b, e, r.get("value"), r.get("outcome"),
                 r.get("match"), r.get("expect_match"), json.dumps(r.get("observed"))[:22],
                 json.dumps(r.get("oracle"))[:40]))
    print()
    # isolation proof, per experiment
    for exp in sorted({h[2] for h in hits}):
        sub = [r for _, _, e, r in hits if e == exp and isinstance(r.get("bytes"), str)]
        outside = {(len(r["bytes"]), int.from_bytes(bytes.fromhex(r["bytes"]), "little") & ~mask) for r in sub}
        inside = {(int.from_bytes(bytes.fromhex(r["bytes"]), "little") >> start) & ((1 << width) - 1) for r in sub}
        print("  %-30s distinct-outside-span=%d (1 == isolated)  distinct-in-span=%s"
              % (exp, len(outside), sorted(inside)))
        # bytewise XOR of the two encodings
        bs = sorted({r["bytes"] for r in sub})
        if len(bs) == 2:
            x = int.from_bytes(bytes.fromhex(bs[0]), "little") ^ int.from_bytes(bytes.fromhex(bs[1]), "little")
            bits = [i for i in range(len(bs[0]) * 4) if x >> i & 1]
            print("     %s XOR %s -> differing bit indices %s   (field span = %s)"
                  % (bs[0], bs[1], bits, list(range(start, start + width))))
    print()
    # cross-run table
    runs = collections.defaultdict(lambda: collections.defaultdict(set))
    for rel, ln, exp, r in hits:
        if not isinstance(r.get("bytes"), str):
            continue
        run = "/".join(rel.split(os.sep)[:4])
        e = (int.from_bytes(bytes.fromhex(r["bytes"]), "little") >> start) & ((1 << width) - 1)
        runs[run][e].add((r.get("outcome"), json.dumps(r.get("observed")), json.dumps(r.get("oracle"))))
    print("  cross-run reproduction:")
    for run in sorted(runs):
        print("    %-58s %s" % (run, {k: sorted(v) for k, v in sorted(runs[run].items())}))
