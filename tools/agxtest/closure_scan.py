#!/usr/bin/env python3
"""CLOSURE-SHADOWING SCAN -- an offline, no-device gate for a defect class that cost a
gated run and then hid inside the symptoms of a different defect.

    python3 tools/agxtest/closure_scan.py <file.py> [<function> ...]
        [--allow NAME[:reason] ...] [--ignore NAME ...]
    exit 0 = clean, 1 = findings

    from closure_scan import scan
    bad = scan("harness/run.py", "main", ignore=IGNORE, allow=ALLOW)   # {} == clean

UPSTREAMED 2026-08-30 by EXP-0185 from `EXP-0178-g17p-sysval-tileread/harness/closure_scan.py`
(gate G10 of that experiment's `selftest.py`). Dependency-free, stdlib `ast` only, so it
drops into any experiment's selftest.

WHY THIS EXISTS
===============

**The defect.** A long capture driver typically builds per-arm closures -- `raw_case`,
`record`, `classify` -- inside one big `main()` loop, and those closures read configuration
bound earlier in the SAME enclosing scope. Python resolves a closure's free variable at
CALL time, not at definition time. If any later statement in that scope rebinds the name,
every subsequent call silently sees the new object.

**What it cost.** EXP-0178's `harness/run.py` bound the compute arm's read-back SIZE as
`nb` and `raw_case` passed it as `outs={0: nb, 4: nb}`. Two hundred lines later the
pre-registered falsifier did `nb = bytearray(blk0)`. From the falsifier onward every
request asked the runner for a read-back of *a bytearray* bytes and raised inside the
request builder. The run `raw/g17p_20260830_run01` was lost.

**Why it is worth a mechanical check rather than care.** The failure presented as a HANG
CASCADE -- one clean case, then everything unrecoverable including the unspliced health
check -- which is **byte-for-byte the signature of a different defect** (DEF-0178-1, the
shared runner's abandoned reader thread) that the same agent had fixed twenty minutes
earlier. Four pilots did not separate them. The general hazard is not a Python one:
**having just fixed a cascade-shaped defect makes the next cascade-shaped defect harder to
see**, because the first explanation is available and it fits. What resolved it was
instrumentation -- a traceback naming the call site -- not reasoning, and what prevents it
recurring is this scan.

**What it flags.** Any name that a nested function READS as a free variable and that the
enclosing function ASSIGNS more than once. Mutually exclusive branches of one `if`/`else`
are safe and are the expected false positive, so callers pass an explicit allow-list WITH A
REASON rather than weakening the rule (EXP-0178 allow-listed exactly three names, each an
if/else anchor-resolution branch).

Clean-room: static analysis of OUR OWN harness source. No Apple binary involved.
"""
import ast
import collections
import sys


def scan(path, funcname="main", ignore=(), allow=()):
    """-> {name: [nested functions that read it]} for names the enclosing function
    assigns more than once.

    `ignore` and `allow` are any containers of names (a dict `{name: reason}` is the
    intended shape for `allow`, so the reason is committed next to the exemption)."""
    with open(path) as fh:
        tree = ast.parse(fh.read())
    fns = [n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and n.name == funcname]
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


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    fns, allow, ignore = [], {}, set()
    it = iter(argv[1:])
    for a in it:
        if a == "--allow":
            nxt = next(it)
            name, _, reason = nxt.partition(":")
            allow[name] = reason or "(no reason given)"
        elif a == "--ignore":
            ignore.add(next(it))
        else:
            fns.append(a)
    findings = 0
    for fname in (fns or ["main"]):
        bad = scan(path, fname, ignore=ignore, allow=allow)
        for k, v in sorted(bad.items()):
            print("%s(): %s: read by %s, and the enclosing scope assigns it more than once"
                  % (fname, k, v))
        findings += len(bad)
    print("closure_scan: %d finding(s) in %s" % (findings, path))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
