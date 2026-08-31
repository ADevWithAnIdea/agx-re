#!/usr/bin/env python3
"""EXP-0220 mnemonic + provenance census.

REBUILDS every case's program from the frozen authored inputs and ASSERTS its
sha256 equals the one recorded in raw -- so the census below is a census of the
bytes that actually executed, not of a re-derivation that might have drifted.
Then counts, per mnemonic, how many field values were emitted in each provenance
class.  `COPIED` and `CARRIER` must both be zero: that is Gate D's donor test.

No device is contacted.
"""
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import cases220 as C     # noqa: E402
import synth220 as S     # noqa: E402

RUN = "g17p-20260831-run01"
CLEN = 3228              # measured on the neo, recorded in raw/*/00_inputs.json
SLOTS = {"out": 0, "mem": 1, "imem": 2}


def main():
    meta = json.load(open(os.path.join(EXP, "raw", RUN, "00_inputs.json")))
    clen = meta["carrier_agc_main_len"]
    raw = {}
    for ln in open(os.path.join(EXP, "raw", RUN, "sweep.jsonl")):
        ln = ln.strip()
        if ln:
            r = json.loads(ln)
            raw[r["name"]] = r
    cs = C.build_cases(include_hazard=True)
    mism = []
    mnem = collections.Counter()
    prov = collections.defaultdict(lambda: collections.Counter())
    cites = collections.defaultdict(set)
    for c in cs:
        pg, prog = C.build_program_for(c, SLOTS, clen)
        h = hashlib.sha256(prog).hexdigest()
        r = raw.get(c["name"])
        if r is None:
            mism.append((c["name"], "absent from raw"))
            continue
        if r["prog_sha256"] != h:
            mism.append((c["name"], "hash %s != %s" % (h[:12], r["prog_sha256"][:12])))
        for (off, m, req, b) in pg.E.parts:
            mnem[m] += 1
        for row in pg.E.led.rows:
            prov[row["instr"]][row["prov"]] += 1
            if row["prov"] in (S.RULE, S.FREE):
                cites["%s.%s" % (row["instr"], row["field"])].add(row["cite"])
    doc = {"run": RUN, "carrier_agc_main_len": clen,
           "cases": len(cs), "hash_mismatches": mism,
           "assemble_calls_per_mnemonic": dict(mnem),
           "field_emissions_by_provenance":
               {k: dict(v) for k, v in sorted(prov.items())},
           "total_copied": sum(v.get("COPIED", 0) for v in prov.values()),
           "total_carrier": sum(v.get("CARRIER", 0) for v in prov.values()),
           "citations_per_field": {k: sorted(v) for k, v in sorted(cites.items())}}
    json.dump(doc, open(os.path.join(HERE, "census.json"), "w"), indent=1,
              sort_keys=True)
    print("cases rebuilt          :", len(cs))
    print("program-hash mismatches:", len(mism), mism[:3])
    print("assemble calls         :", dict(mnem))
    for k, v in sorted(prov.items()):
        print("  %-14s %s" % (k, dict(v)))
    print("TOTAL COPIED  :", doc["total_copied"])
    print("TOTAL CARRIER :", doc["total_carrier"])
    return 1 if (mism or doc["total_copied"] or doc["total_carrier"]) else 0


if __name__ == "__main__":
    sys.exit(main())
