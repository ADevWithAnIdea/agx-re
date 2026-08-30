#!/usr/bin/env python3
"""CLOSURE-SHADOWING SCAN -- an offline, no-device gate for a defect class that
cost this experiment a gated run.

    python3 harness/closure_scan.py <file.py> [<function> ...]
    exit 0 = clean, 1 = findings

================================ UPSTREAM NOTES ================================

Written to be lifted into `experiments/` as a shared check (alongside
`harness/saferunner.py` and `harness/verify_remote.py`). It is a single
dependency-free file, it takes a path and an optional function name, and it
exits non-zero on a finding, so it drops into any experiment's selftest.

**The defect.** A long capture driver typically builds per-arm closures --
`raw_case`, `record`, `classify` -- inside one big `main()` loop, and those
closures read configuration bound earlier in the SAME enclosing scope. Python
resolves a closure's free variable at CALL time, not at definition time. If any
later statement in that scope rebinds the name, every subsequent call silently
sees the new object.

**What it cost here.** `harness/run.py` bound the compute arm's read-back SIZE as
`nb` and `raw_case` passed it as `outs={0: nb, 4: nb}`. Two hundred lines later
the pre-registered falsifier did `nb = bytearray(blk0)`. From the falsifier
onward every request asked the runner for a read-back of *a bytearray* bytes and
raised inside the request builder. `raw/g17p_20260830_run01` was lost.

**Why it is worth a mechanical check rather than care.** The failure presented as
a HANG CASCADE -- one clean case, then everything unrecoverable including the
unspliced health check -- which is byte-for-byte the signature of a *different*
defect (the shared runner's abandoned reader thread) that had been fixed twenty
minutes earlier. Four pilots did not separate them. The general hazard is not a
Python one: **having just fixed a cascade-shaped defect makes the next
cascade-shaped defect harder to see**, because the first explanation is
available and fits. What resolved it was instrumentation -- a traceback naming
the call site -- not reasoning, and what prevents it recurring is this scan.

**What it flags.** Any name that a nested function READS as a free variable and
that the enclosing function ASSIGNS more than once. Mutually exclusive branches
of one `if`/`else` are safe and are the expected false positive, so callers pass
an explicit allow-list WITH A REASON rather than weakening the rule; three names
in this experiment's `run.py` are allow-listed on exactly that ground.
"""
import ast
import collections
import sys


def scan(path, funcname="main", ignore=(), allow=()):
    """-> {name: [nested functions that read it]} for names the enclosing
    function assigns more than once."""
    tree = ast.parse(open(path).read())
    fns = [n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == funcname]
    if not fns:
        raise KeyError("no function %r in %s" % (funcname, path))
    fn = fns[0]

    assigned = collections.Counter()

    def walk(node):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue                      # a nested function is its own scope
            if isinstance(ch, ast.Name) and isinstance(ch.ctx, ast.Store):
                assigned[ch.id] += 1
            walk(ch)
    walk(fn)

    reads = collections.defaultdict(set)
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn:
            local = {n.id for n in ast.walk(node)
                     if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            local |= {n.arg for n in ast.walk(node) if isinstance(n, ast.arg)}
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) \
                        and n.id not in local:
                    reads[n.id].add(node.name)
    return {k: sorted(v) for k, v in reads.items()
            if assigned.get(k, 0) > 1 and k not in ignore and k not in allow}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bad = scan(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "main")
    for k, v in sorted(bad.items()):
        print("%s: read by %s, and the enclosing scope assigns it more than once" % (k, v))
    print("closure_scan: %d finding(s)" % len(bad))
    sys.exit(1 if bad else 0)
