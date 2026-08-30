#!/usr/bin/env python3
"""Adversarial self-test for work/merge_verdicts.py: prove each gate FIRES.

This corpus produced thirteen "checks that could not come out the other way" in
one week -- a gate that counted a GPU fault as movement, one that counted our own
disassembler failing to decode as movement, a promotion gate with no `moved >= 1`
conjunct, and an audit that could only ever LOSE evidence. merge_verdicts.py is
the single chokepoint through which every label enters the corpus, and its eight
refusal paths had never been shown to fire.

Every case below is a verdict that MUST be refused. A case that merges is a
gate that does not work. Runs with --dry-run against the real db.json and
validation.json; writes nothing.
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MERGE = os.path.join(ROOT, "work", "merge_verdicts.py")
DB = os.path.join(ROOT, "tools", "agx-isa", "db.json")


def a_real_field():
    db = json.load(open(DB))
    for i in db["instructions"]:
        for f in i.get("fields", []):
            return i["mnemonic"], f["name"], f["start"], f["width"]
    raise SystemExit("db.json has no fields")


M, F, START, WIDTH = a_real_field()
# The base fixture NAMES its bits. DEF-0212-1's guard refuses a verdict that does
# not, and it fires before the label/evidence/range rules -- so without this the
# later cases never reach the rule they are testing. The selftest caught that
# reordering itself, which is the point of asserting each rule independently.
OK = {"label": "hardware-run", "range": "0..1 dense", "target": "M4",
      "evidence": ["EXP-0138"], "note": "selftest",
      "start": START, "width": WIDTH}



def variant(**kw):
    d = dict(OK)
    d.update(kw)
    return {k: v for k, v in d.items() if v is not None}


CASES = [
    ("key is not mnemonic.field",      {"notadotkey": variant()},              "not <mnemonic>.<field>"),
    ("unknown mnemonic",               {"no_such_insn.x": variant()},          "unknown mnemonic"),
    ("field not in db.json",           {"%s.no_such_field" % M: variant()},    "is not a field of"),
    ("descriptor moved under verdict", {"%s.%s" % (M, F): variant(start=START + 3, width=WIDTH)},
                                                                                "the descriptor moved"),
    ("invalid label",                  {"%s.%s" % (M, F): variant(label="probably-fine")},
                                                                                "invalid label"),
    ("emitter-grade, empty evidence",  {"%s.%s" % (M, F): variant(evidence=[])},
                                                                                "empty evidence"),
    ("hardware-run, no real range",    {"%s.%s" % (M, F): variant(range="tested")},
                                                                                "without a real range"),
    # DEF-0212-1: a verdict that names no bits must be refused when db.json knows
    # them. This one skipped the span guard entirely until EXP-0212 found it.
    ("verdict states no start/width",  {"%s.%s" % (M, F): variant(start=None, width=None)},
                                                                                "states no start/width"),
]


def run(doc):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "analysis"), exist_ok=True)
    p = os.path.join(d, "analysis", "verdicts.json")
    json.dump(doc, open(p, "w"))
    r = subprocess.run([sys.executable, MERGE, p, "--dry-run"],
                       capture_output=True, text=True, cwd=ROOT)
    return (r.stdout or "") + (r.stderr or "")


def main():
    fails = []
    for name, doc, expect in CASES:
        out = run(doc)
        refused = expect in out
        print("%-4s %s" % ("PASS" if refused else "FAIL", name))
        if not refused:
            fails.append(name)
            print("     expected %r in output; got:\n%s" % (expect, out[:600]))

    # The other direction. A gate that refuses EVERYTHING is as broken as one
    # that refuses nothing, so a well-formed verdict must still be accepted.
    out = run({"%s.%s" % (M, F): variant(start=START, width=WIDTH)})
    accepted = "problem" not in out.lower() or "0 problem" in out.lower()
    print("%-4s a well-formed verdict is still ACCEPTED (gate is not refuse-all)"
          % ("PASS" if accepted else "FAIL"))
    if not accepted:
        fails.append("well-formed verdict refused")
        print(out[:600])

    print("\nMERGE-GATE SELFTEST %s (%d failure(s))"
          % ("PASS" if not fails else "FAIL", len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
