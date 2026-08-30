#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0190 control -- prove that nothing load-bearing was changed while copying.

Compares, byte for byte, the frozen constants and the verdict-producing function bodies
of this experiment's analysis scripts against the committed originals:

  analysis/audit.py       vs  EXP-0164-inert-audit/analysis/audit.py
  analysis/collect_raw.py vs  EXP-0189-closing-audit/analysis/collect_raw.py
  analysis/recount.py     vs  EXP-0189-closing-audit/analysis/recount.py

Exit status 0 iff every checked body is identical.  Any difference is printed.

Usage: python3 analysis/verify_inheritance.py
"""
import ast, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.abspath(os.path.join(HERE, "..", ".."))

CHECKS = [
    ("analysis/audit.py", "EXP-0164-inert-audit/analysis/audit.py",
     ["cross_run", "stable_live", "classify", "build_record", "moved_of", "resolver"],
     ["MIN_COMMON", "MIN_AGREE_PCT", "MOVED_OVER_DISAGREE", "THIN_COMMON", "WITHHOLD",
      "EMIT_OK", "DATA_WORD_ROLE", "NONGATED", "NOTES"]),
    ("analysis/collect_raw.py", "EXP-0189-closing-audit/analysis/collect_raw.py",
     ["sig_of", "fit_offset", "identify", "resolve_label", "load_db"],
     ["HARD", "CONTAM", "HEXRE", "BYTELABEL", "STRIPEQ"]),
    ("analysis/recount.py", "EXP-0189-closing-audit/analysis/recount.py",
     ["emittable_current", "instr_dispatch_audit", "resolver"],
     ["EMIT_OK", "DATA_WORD_ROLE", "WITHHOLD", "NONGATED"]),
]


def bodies(path):
    src = open(path).read()
    tree = ast.parse(src)
    fn, const = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn[node.name] = ast.dump(node, include_attributes=False)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    const[t.id] = ast.dump(node.value, include_attributes=False)
    return fn, const


def main():
    bad = 0
    for mine, theirs, fns, consts in CHECKS:
        mp = os.path.join(HERE, "..", mine)
        tp = os.path.join(EXPDIR, theirs)
        if not os.path.exists(tp):
            print("MISSING original: %s" % tp)
            bad += 1
            continue
        mf, mc = bodies(mp)
        tf, tc = bodies(tp)
        for f in fns:
            if f not in tf:
                print("  %-24s %-14s ABSENT in original" % (mine, f)); bad += 1
            elif mf.get(f) != tf[f]:
                print("  %-24s %-14s DIFFERS" % (mine, f)); bad += 1
        for c in consts:
            if mc.get(c) != tc.get(c):
                print("  %-24s %-14s CONSTANT DIFFERS: %r vs %r"
                      % (mine, c, mc.get(c), tc.get(c))); bad += 1
        print("%-26s checked %d functions + %d constants against %s"
              % (mine, len(fns), len(consts), theirs))
    print("verify_inheritance: %s" % ("PASS (all bodies identical)" if not bad
                                      else "FAIL (%d differences)" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
