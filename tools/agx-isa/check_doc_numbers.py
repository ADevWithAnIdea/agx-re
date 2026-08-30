#!/usr/bin/env python3
"""Fail if a normative doc states an emittability figure that is not current.

The headline moved eight times on 2026-08-30 (79 -> 41 -> 55 -> 38 -> 37 -> 34
-> 33 -> 32). docs/compiler-readiness.md was left telling the reader the figure
had been withdrawn "to 41/166" -- true when written, stale by six subsequent
withdrawals, and a reader who has never seen the hardware would take it as
current. This is the guard against that.

A stale figure is allowed ONLY on a line that marks itself historical (an arc, a
"was", a "withdrawn from"). Everything else is an error.

PROVENANCE.md and experiments/ are append-only evidence: a row records what was
true when written and MUST NOT be rewritten, so they are never scanned.
"""
import json, os, re, sys

D = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(D))
EMIT = {"hardware-run", "isolated-byte-diff"}
DATA_WORD_ROLE = "data-word"
HIST = re.compile(r"\b(was|were|withdrew|withdrawn|arc|historical|superseded|"
                  r"previously|used to|before|down from|→|->)\b", re.I)
FIG = re.compile(r"\b(\d{1,4})\s*(?:of|/)\s*(166|1040)\b")


def current():
    db = json.load(open(os.path.join(D, "db.json")))
    val = json.load(open(os.path.join(D, "validation.json")))["instructions"]
    rel = [i for i in db["instructions"] if i.get("emitter_role") != DATA_WORD_ROLE]
    inst = 0
    for i in rel:
        m = i["mnemonic"]
        names = [f["name"] for f in i.get("fields", [])]
        e = val.get(m, {})
        if not names:
            continue
        if any(e.get(n, {}).get("label") not in EMIT for n in names):
            continue
        if (e.get("_instruction") or {}).get("label") not in EMIT:
            continue
        if "EMITTABLE VETO" in ((e.get("_instruction") or {}).get("note", "") or ""):
            continue
        inst += 1
    fields = sum(1 for m, e in val.items() for n, v in e.items()
                 if n != "_instruction" and v.get("label") in EMIT)
    return {"166": inst, "1040": fields}, len(rel)


# A whole LINE is too coarse: a status-board row is one line and can run to
# thousands of characters, so a historical clause at its end ("...from 79 to
# 41") exempted a CURRENT claim at its start. That false negative let
# docs/P0-P1-CLOSURE.md keep asserting 41 of 166 as live status. The exemption
# is now scoped to the clause around the match.
CLAUSE = re.compile(r"[.;:]\s|\s[—-]{1,2}\s|\|")


def clause_of(line, pos):
    starts = [0] + [m.end() for m in CLAUSE.finditer(line) if m.end() <= pos]
    ends = [m.start() for m in CLAUSE.finditer(line) if m.start() > pos] + [len(line)]
    return line[max(starts):min(ends)]


def scan(text, cur, path, out):
    bad = 0
    for ln, line in enumerate(text.split("\n"), 1):
        for m in FIG.finditer(line):
            got, denom = int(m.group(1)), m.group(2)
            if got == cur[denom]:
                continue
            if HIST.search(clause_of(line, m.start())):
                out.append("    ok(historical) %s:%d  %s" % (path, ln, m.group(0)))
                continue
            out.append("  STALE %s:%d  states %s, current is %d of %s"
                       % (path, ln, m.group(0), cur[denom], denom))
            bad += 1
    return bad


def selftest(cur):
    """The check must be able to come out BOTH ways. Twelve gates in this corpus
    could not, so this one proves itself on every run."""
    stale = "The emitter can do %d of 166 instructions today." % (cur["166"] + 7)
    fresh = "The emitter can do %d of 166 instructions today." % cur["166"]
    hist = "It was %d of 166 before the audit." % (cur["166"] + 7)
    # The regression that motivated clause scoping: a live claim in a long table
    # row whose LATER text is historical. This must still be caught.
    row = ("| P0.6 | status | **OPEN** (%d of 166 emitter-relevant instructions "
           "emittable) | the number went down, from 79 to %d |"
           % (cur["166"] + 7, cur["166"] + 7))
    o = []
    a, b, c = scan(stale, cur, "T", o), scan(fresh, cur, "T", o), scan(hist, cur, "T", o)
    d = scan(row, cur, "T", o)
    if not (a == 1 and b == 0 and c == 0 and d == 1):
        print("SELFTEST FAIL: stale=%d (want 1) fresh=%d (want 0) historical=%d "
              "(want 0) long-row=%d (want 1)" % (a, b, c, d))
        return False
    return True


def main():
    cur, nrel = current()
    if not selftest(cur):
        return 2
    print("current figure: %d of 166 instructions, %d of 1040 fields"
          % (cur["166"], cur["1040"]))
    if nrel != 166:
        print("NOTE: emitter-relevant count is %d, not 166 — the denominators in "
              "docs/ are hard-coded and now wrong." % nrel)
    bad, notes = 0, []
    for sub in ("docs",):
        for dp, _, fns in os.walk(os.path.join(ROOT, sub)):
            for fn in sorted(fns):
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, ROOT)
                if rel == "docs/isa/emit-worklist.md":
                    continue  # generated from the corpus; cannot go stale
                bad += scan(open(p, encoding="utf-8", errors="replace").read(),
                            cur, rel, notes)
    for n in notes:
        print(n)
    print("STALE FIGURES: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
