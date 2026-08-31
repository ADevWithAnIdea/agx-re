#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""sibling_check.py -- what the match-destroying refusals actually dispatched.

Twelve (experiment, row) candidates were refused because every committed encoding
fails the descriptor's own match bits. That is not noise: it means the experiment
keyed its records to one mnemonic while the bytes it committed tokenize -- with our
own disassembler, on today's db.json -- to a DIFFERENT one. This program names the
mnemonic the bytes actually are, and the field of THAT descriptor which owns the
swept byte, so the finding is reported rather than silently dropped.

It proposes nothing. Re-pointing a citation at a sibling descriptor is a descriptor
question, not a citation question, and it is left to the orchestrator.
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
W = os.path.join(EXP, "work")
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI
import isadb

SPEC = EI.load_db(os.path.join(W, "db_frozen.json"))
REF = json.load(open(os.path.join(W, "refusals.json")))

want = collections.defaultdict(set)     # exp -> {(mnem, field)}
for key, ents in REF.items():
    for a in ents:
        if "survive the descriptor's own match bits" in a["why"]:
            want[a["experiment"]].add(tuple(key.split(".", 1)))

out = {}
for exp, keys in sorted(want.items()):
    mnems = {m for m, _ in keys}
    found = collections.defaultdict(lambda: {"n": 0, "tokenizes_to": collections.Counter(),
                                             "byte_indices": collections.Counter(),
                                             "sibling_fields": collections.Counter(),
                                             "example": None})
    d = os.path.join(ROOT, "experiments", exp)
    for p, ext in EI.iter_files(d):
        if ext != ".jsonl" or (os.sep + "raw" + os.sep) not in p + os.sep:
            continue
        for ln, line in enumerate(open(p, errors="replace"), 1):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            m = r.get("instr")
            if m not in mnems:
                continue
            b = r.get("bytes")
            if not isinstance(b, str) or not b:
                continue
            try:
                recs, _ = isadb.disassemble(bytes.fromhex(b))
            except Exception:
                continue
            if not recs or recs[0].get("error"):
                continue
            tok = recs[0].get("mnemonic")
            bi = r.get("byte_index")
            for mm, f in keys:
                if mm != m:
                    continue
                c = found[(m, f)]
                c["n"] += 1
                c["tokenizes_to"][tok] += 1
                if isinstance(bi, int):
                    c["byte_indices"][bi] += 1
                    for sf, (st, w) in (SPEC.get(tok, {}).get("fields") or {}).items():
                        if st <= 8 * bi + 7 and st + w - 1 >= 8 * bi:
                            c["sibling_fields"]["%s.%s" % (tok, sf)] += 1
                if c["example"] is None:
                    c["example"] = {"file": os.path.relpath(p, ROOT), "line": ln,
                                    "bytes": b}
    for (m, f), c in found.items():
        out["%s|%s.%s" % (exp, m, f)] = {
            "records_with_bytes": c["n"],
            "our_disassembler_says": dict(c["tokenizes_to"]),
            "swept_byte_indices": {str(k): v for k, v in c["byte_indices"].items()},
            "fields_of_the_real_descriptor_covering_that_byte":
                dict(c["sibling_fields"].most_common(8)),
            "example": c["example"]}
json.dump(out, open(os.path.join(EXP, "analysis", "sibling_mnemonics.json"), "w"),
          indent=1, sort_keys=True)
for k, v in sorted(out.items()):
    print("%-58s n=%-6d tokenizes_to=%s -> %s" %
          (k, v["records_with_bytes"], v["our_disassembler_says"],
           list(v["fields_of_the_real_descriptor_covering_that_byte"])[:3]))
