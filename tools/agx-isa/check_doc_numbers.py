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
# A clause about a DIFFERENT measure that happens to share the 166/1040 denominator
# is not a stale headline. "the only committed recipe registry covers 35 of 166
# mnemonics" is recipe-dashboard coverage, not emittability. Keep this list narrow:
# each word names a distinct dashboard or registry, never the emittability figure.
OTHER = re.compile(r"\b(registry|recipe|dashboard|liveness|geometry|semantic|"
                   r"resource|overflow|blocks?|rejects?)\b", re.I)
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


def clause_of(line, pos, back=0):
    """The clause around pos. `back` extends leftward by that many clauses.

    An em-dash splits "Recipe is unmoved -- at 2 of 166" into two clauses and
    strands the word that identifies the measure, so the OTHER check reads one
    clause further left than the STALE check does. One clause, not the whole
    line: the whole line is what produced the earlier false negative on a
    status-board row.
    """
    ms = [m for m in CLAUSE.finditer(line) if m.end() <= pos]
    bounds = [0] + [m.end() for m in ms]
    start = bounds[-1]
    if back and ms:
        # Extend leftward ONLY across a dash. A dash continues a statement
        # ("Recipe is unmoved -- at 2 of 166"); a period or semicolon starts a new
        # one, and reaching across it would excuse a genuinely stale figure sitting
        # after an unrelated mention. The selftest asserts both halves.
        if "-" in ms[-1].group(0) or "\u2014" in ms[-1].group(0):
            start = bounds[max(0, len(bounds) - 2)]
    ends = [m.start() for m in CLAUSE.finditer(line) if m.start() > pos] + [len(line)]
    return line[start:min(ends)]


def scan(text, cur, path, out):
    bad = 0
    for ln, line in enumerate(text.split("\n"), 1):
        for m in FIG.finditer(line):
            got, denom = int(m.group(1)), m.group(2)
            if got == cur[denom]:
                continue
            cl = clause_of(line, m.start())
            if OTHER.search(clause_of(line, m.start(), back=1)):
                out.append("    ok(other measure) %s:%d  %s" % (path, ln, m.group(0)))
                continue
            if HIST.search(cl):
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
    other = "the only committed recipe registry covers %d of 166 mnemonics" % (cur["166"] + 7)
    # The em-dash case that motivated back=1: the identifying word is one clause left.
    other_dash = "Recipe is unmoved - at %d of 166 nothing gained one" % (cur["166"] + 7)
    # ...and back=1 must NOT reach so far that a real stale headline is excused.
    stale_after_other = ("The recipe dashboard reads 2 of 166. Emittable is %d of 166."
                         % (cur["166"] + 7))
    stale_near_other = ("%d of 166 instructions are emittable. Separately the recipe "
                        "registry covers 35 of 166." % (cur["166"] + 7))
    o = []
    a, b, c = scan(stale, cur, "T", o), scan(fresh, cur, "T", o), scan(hist, cur, "T", o)
    d = scan(row, cur, "T", o)
    e = scan(other, cur, "T", o)          # different measure -> exempt
    f = scan(stale_near_other, cur, "T", o)  # a real stale headline in the SAME line
    g = scan(other_dash, cur, "T", o)        # identifier one clause left -> exempt
    h = scan(stale_after_other, cur, "T", o)  # back=1 must not excuse this
    if not (a == 1 and b == 0 and c == 0 and d == 1 and e == 0 and f == 1
            and g == 0 and h == 1):
        print("SELFTEST FAIL: stale=%d(1) fresh=%d(0) historical=%d(0) long-row=%d(1) "
              "other-measure=%d(0) stale-beside-other=%d(1) other-across-dash=%d(0) "
              "stale-after-other=%d(1)" % (a, b, c, d, e, f, g, h))
        return False
    return True


def main():
    cur, nrel = current()
    if not selftest(cur):
        return 2
    print("legacy label figure: %d of 166 instructions, %d of 1040 fields"
          % (cur["166"], cur["1040"]))
    print("NOTE: RE_EXPERIMENT_PROCESS_CORRECTIONS.md §8 RETIRES this as the completeness\n"
          "      measure -- a checker 'must not derive a single N of 166 emittable headline\n"
          "      from field labels'. The seven §9 dashboards are the accounting; run\n"
          "      `python3 tools/agx-isa/dashboards.py`. This tool now only stops a STALE\n"
          "      legacy figure from sitting in a normative doc as if it were current, and\n"
          "      requires every doc that states one to carry the retirement notice.")
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

    # §8: a normative doc may still MENTION the legacy figure, but never as the
    # completeness measure. If it states one, it must carry the retirement notice.
    RET = "THE SINGLE EMITTABILITY HEADLINE IS RETIRED"
    missing = []
    for dp, _, fns in os.walk(os.path.join(ROOT, "docs")):
        for fn in sorted(fns):
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), ROOT)
            if rel == "docs/isa/emit-worklist.md":
                continue
            txt = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
            if FIG.search(txt) and RET not in txt:
                missing.append(rel)
    for m in missing:
        print("  §8 VIOLATION %s states a legacy emittability figure without the "
              "retirement notice" % m)
    print("DOCS STATING THE LEGACY FIGURE WITHOUT THE §8 NOTICE: %d" % len(missing))
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
