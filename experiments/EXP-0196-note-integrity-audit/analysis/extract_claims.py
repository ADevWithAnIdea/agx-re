#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 step 1 -- extract every CHECKABLE claim out of every `note` in
tools/agx-isa/validation.json.

Read-only. Writes analysis/claims.jsonl.

A claim is checkable if it is numeric or existential: a count of dispatched
values, a count of carriers/runs/captures, an "N of M", a named raw file, a
named experiment, or an explicit assertion that something was executed /
reproduced / matched an oracle.
"""
import json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
VAL = os.path.join(ROOT, "tools", "agx-isa", "validation.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claims.jsonl")

EMIT = ("hardware-run", "isolated-byte-diff")

# (kind, regex, group-names)
PATTERNS = [
    ("values_dispatched",  re.compile(r"(\d+) values dispatched")),
    ("carriers_tested",    re.compile(r"(\d+) carrier\(s\) tested")),
    ("observations_moved", re.compile(r"(\d+) observations moved")),
    ("moved_on_of",        re.compile(r"moved on (\d+) of (\d+) ladder-passing carriers")),
    ("no_effect_on",       re.compile(r"no observable effect over the swept range on (\d+) structurally different ladder-passing carriers")),
    ("agreement",          re.compile(r"([\d.]+)% agreement over (\d+) shared values, (\d+) moved vs (\d+) disagreement")),
    ("agreeing_captures",  re.compile(r"(\d+) agreeing captures")),
    ("outcomes_kv",        re.compile(r"outcomes \{[^}]*\}")),
    ("outcomes_ok",        re.compile(r"outcomes ok=(\d+)")),
    ("silent_zero_n",      re.compile(r"(\d+) values return a silent zero")),
    ("raw_path",           re.compile(r"(?:^|[\s(])((?:experiments/)?EXP-[A-Za-z0-9-]+/)?(raw/[A-Za-z0-9_@./+-]+)")),
    ("exp_ref",            re.compile(r"\b(EXP-[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*)")),
    ("n_of_m",             re.compile(r"\b(\d+)\s*/\s*(\d+)\b")),
    ("runs_named",         re.compile(r"\b((?:m4_|g17p_)?(?:\d{8}_)?run\d+|rv\d+|pilot\d+)\b")),
    ("executed_claim",     re.compile(r"was executed|were executed|programs was executed|ran with the predicted|returned its own host-computed oracle", re.I)),
    ("reproduced_claim",   re.compile(r"reproduc\w+ (?:identically )?(?:across|in) (?:both|two|three|all |\d+)[^.;|]{0,40}", re.I)),
    ("oracle_claim",       re.compile(r"host[- ]computed oracle|host oracle|matched the oracle|oracle matched", re.I)),
]


def main():
    val = json.load(open(VAL))
    n = 0
    with open(OUT, "w") as fh:
        for m, entry in sorted(val["instructions"].items()):
            for f, r in sorted(entry.items()):
                if not isinstance(r, dict):
                    continue
                note = (r.get("note") or "").strip()
                grade = "EMIT" if (r.get("label") in EMIT and f != "_instruction") else \
                        ("EMIT_INSTR" if (r.get("label") in EMIT and f == "_instruction") else "OTHER")
                rec = {
                    "mnemonic": m, "field": f, "label": r.get("label"),
                    "target": r.get("target"), "evidence": r.get("evidence") or [],
                    "grade": grade, "note": note,
                    "values_dispatched_key": r.get("values_dispatched"),
                    "distinct_bytes_key": r.get("distinct_bytes"),
                    "encodable_range_key": r.get("encodable_range"),
                    "claims": [],
                }
                if note:
                    for kind, rx in PATTERNS:
                        for mo in rx.finditer(note):
                            rec["claims"].append({
                                "kind": kind,
                                "text": mo.group(0).strip(),
                                "groups": [g for g in mo.groups()] if mo.groups() else [],
                                "span": [mo.start(), mo.end()],
                            })
                if note or rec["values_dispatched_key"] is not None:
                    fh.write(json.dumps(rec) + "\n")
                    n += 1
    print("wrote %d records to %s" % (n, OUT))


if __name__ == "__main__":
    main()
