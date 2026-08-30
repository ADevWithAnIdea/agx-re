#!/usr/bin/env python3
"""EXP-0182 -- collect every HW-VALIDATED *anchor* committed in experiments' raw/.

An ANCHOR is the exact byte string an experiment dispatched on real hardware as the
UNMUTATED instance of a descriptor, and which the hardware executed correctly.  It is
the strongest thing a tokenizer can be asked to decode: our own tools must be able to
read back an encoding our own hardware already accepted.

Frozen selection rule (PRE_REGISTRATION.md, R-A1..R-A5) -- a raw record qualifies iff:
  R-A1  it lives under experiments/EXP-*/raw/**/*.jsonl (committed append-only evidence);
  R-A2  its `instr`/`mnemonic` names a descriptor in db.json;
  R-A3  its `bytes` is hex of EXACTLY that descriptor's declared length
        (so the record's bytes are the instruction, not a whole carrier);
  R-A4  `outcome == "ok"` AND `match == true` (the hardware produced the oracle value);
  R-A5  the record is a BASELINE, not a mutation: `field` in {"-", "_baseline"} OR the
        note matches unmutated | baseline | POS-CTRL | compiler-natural | semantic vector.
        (`field: null` alone is NOT enough -- EXP-0171 emits field-less sweep records
        whose bytes are mutated; admitting them put a b2=0x04 "bf_alu" in the set.)

Usage:  python3 analysis/collect_anchors.py > analysis/anchors.json
CLEAN-ROOM: pure re-analysis of our own committed raw + our own db.json.
"""
import collections, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb  # noqa: E402

BASELINE_NOTE = re.compile(r"unmutated|baseline|POS-CTRL|compiler-natural|semantic vector", re.I)
BASELINE_FIELD = {"-", "_baseline"}


def main():
    declared = {d["mnemonic"]: d["length"] for d in isadb.DB}
    found = collections.OrderedDict()
    for path in sorted(glob.glob(os.path.join(REPO, "experiments", "EXP-*", "raw", "**", "*.jsonl"),
                                 recursive=True)):
        rel = os.path.relpath(path, REPO)
        exp = rel.split(os.sep)[1]
        run = rel.split(os.sep)[3] if len(rel.split(os.sep)) > 3 else ""
        for line in open(path, errors="replace"):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            mn = r.get("instr") or r.get("mnemonic")
            b = r.get("bytes")
            if not isinstance(mn, str) or not isinstance(b, str) or mn not in declared:
                continue                                              # R-A2
            if len(b) != 2 * declared[mn]:
                continue                                              # R-A3
            if r.get("outcome") != "ok" or r.get("match") is not True:
                continue                                              # R-A4
            note = r.get("note") or ""
            if not (r.get("field") in BASELINE_FIELD or BASELINE_NOTE.search(note)):
                continue                                              # R-A5
            key = (mn, b)
            if key in found:
                found[key]["n_records"] += 1
                found[key]["runs"].add(run)
                continue
            found[key] = {"mnemonic": mn, "bytes": b, "declared_length": declared[mn],
                          "experiment": exp, "raw": rel, "runs": {run},
                          "carrier": r.get("carrier"), "note": note[:200], "n_records": 1}
    out = []
    for v in found.values():
        v["runs"] = sorted(x for x in v["runs"] if x)
        out.append(v)
    out.sort(key=lambda v: (v["mnemonic"], v["bytes"]))
    json.dump({"_meta": {"rule": "PRE_REGISTRATION R-A1..R-A5",
                         "n_anchors": len(out),
                         "n_mnemonics": len({v["mnemonic"] for v in out})},
               "anchors": out}, sys.stdout, indent=1)
    print()


main()
