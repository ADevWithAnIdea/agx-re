#!/usr/bin/env python3
"""EXP-0221 mnemonic + provenance census.

REBUILDS every case's program from the frozen authored inputs and ASSERTS its
sha256 equals the one recorded in raw -- so the census below describes the bytes
that actually executed, not a re-derivation that might have drifted.  Only then
does it count, per mnemonic, how many field values were emitted in each
provenance class.  `COPIED` and `CARRIER` must both be zero: that is Gate D's
donor test, and counting the tags without first proving the bytes would make it
a check on a string an author typed.

No device is contacted.
"""
import collections
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import cases221 as C     # noqa: E402
import synth221 as S     # noqa: E402

SLOTS = {"out": 0, "mem": 1, "imem": 2}


def runs():
    return sorted(os.path.basename(d) for d in
                  glob.glob(os.path.join(EXP, "raw", "*")) if os.path.isdir(d))


def main():
    doc = {"runs": {}}
    total_bad = 0
    for run in runs():
        meta = json.load(open(os.path.join(EXP, "raw", run, "00_inputs.json")))
        clen = meta["carrier_agc_main_len"]
        raw = {}
        for ln in open(os.path.join(EXP, "raw", run, "sweep.jsonl")):
            ln = ln.strip()
            if ln:
                r = json.loads(ln)
                raw[r["name"]] = r
        cs = C.build_cases(include_hazard=True)
        mism, mnem = [], collections.Counter()
        prov = collections.defaultdict(lambda: collections.Counter())
        cites = collections.defaultdict(set)
        rebuilt = 0
        for c in cs:
            if c["name"] not in raw:
                continue          # arm-filtered captures do not dispatch every case
            pg, prog = C.build_program_for(c, SLOTS, clen)
            rebuilt += 1
            h = hashlib.sha256(prog).hexdigest()
            if raw[c["name"]]["prog_sha256"] != h:
                mism.append((c["name"], "%s != %s"
                             % (h[:12], raw[c["name"]]["prog_sha256"][:12])))
            for (off, m, req, b) in pg.E.parts:
                mnem[m] += 1
            for row in pg.E.led.rows:
                prov[row["instr"]][row["prov"]] += 1
                if row["prov"] in (S.RULE, S.FREE):
                    cites["%s.%s" % (row["instr"], row["field"])].add(row["cite"])
        d = {"carrier": meta.get("carrier"), "carrier_agc_main_len": clen,
             "cases_in_raw": len(raw), "cases_rebuilt": rebuilt,
             "program_hash_mismatches": mism,
             "assemble_calls_per_mnemonic": dict(mnem),
             "field_emissions_by_provenance":
                 {k: dict(v) for k, v in sorted(prov.items())},
             "total_COPIED": sum(v.get("COPIED", 0) for v in prov.values()),
             "total_CARRIER": sum(v.get("CARRIER", 0) for v in prov.values()),
             "citations_per_field": {k: sorted(v) for k, v in sorted(cites.items())}}
        total_bad += len(mism) + d["total_COPIED"] + d["total_CARRIER"]
        doc["runs"][run] = d
        print("%-26s rebuilt %5d  hash-mismatch %3d  COPIED %d  CARRIER %d"
              % (run, rebuilt, len(mism), d["total_COPIED"], d["total_CARRIER"]))
        print("      assemble calls: %s" % dict(mnem))
    json.dump(doc, open(os.path.join(HERE, "census.json"), "w"), indent=1,
              sort_keys=True)
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
