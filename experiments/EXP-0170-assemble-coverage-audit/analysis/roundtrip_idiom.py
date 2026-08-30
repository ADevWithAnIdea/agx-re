#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm C -- census of the *disassemble -> re-assemble -> compare* self-check
idiom across committed experiments and tools.

Why: such a check is blind to any defect that is SYMMETRIC across encode and decode.
DEF-0166-1 is exactly that -- a `match` bit stuck at 1 by the old OR-only
`assemble()` is also read back as 1 by `disassemble()`, so `assemble(disassemble(b))
== b` passes while proving nothing about whether the encoder can put the value the
CALLER asked for into the field.  A round trip verifies that the codec is
self-consistent; it never verifies that it is correct.

Method: AST scan for any function/module scope that calls BOTH a decoder
(`disassemble` / `decode_one` / `decode`) AND an encoder (`assemble` /
`assemble_op`) and contains a comparison or an assert.  Every hit is then read by
hand and classified in RESULTS.md.

READ-ONLY.  Writes only analysis/roundtrip_idiom.json.
Usage: python3 analysis/roundtrip_idiom.py
"""
import ast, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))

DEC = {"disassemble", "decode_one", "decode", "disasm"}
ENC = {"assemble", "assemble_op"}
SCAN = ["experiments", "tools", "work"]
SKIPDIRS = {"__pycache__", ".git"}


def callname(n):
    f = n.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def scan_scope(node, src):
    calls, cmps, asserts = set(), 0, 0
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            c = callname(n)
            if c:
                calls.add(c)
        elif isinstance(n, ast.Compare):
            cmps += 1
        elif isinstance(n, ast.Assert):
            asserts += 1
    return calls, cmps, asserts


def main():
    hits = []
    nfiles = 0
    for base in SCAN:
        for root, dirs, files in os.walk(os.path.join(ROOT, base)):
            dirs[:] = [d for d in dirs if d not in SKIPDIRS]
            for fn in sorted(files):
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, ROOT)
                nfiles += 1
                try:
                    src = open(p, errors="replace").read()
                    tree = ast.parse(src)
                except Exception:
                    continue
                scopes = [("<module>", tree, getattr(tree, "lineno", 1))]
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        scopes.append((n.name, n, n.lineno))
                for name, node, lineno in scopes:
                    calls, cmps, asserts = scan_scope(node, src)
                    d, e = calls & DEC, calls & ENC
                    if d and e and (cmps or asserts):
                        hits.append({
                            "file": rel, "scope": name, "lineno": lineno,
                            "decoders": sorted(d), "encoders": sorted(e),
                            "comparisons": cmps, "asserts": asserts,
                        })
    # drop the enclosing <module> scope when a function in the same file already hit
    byfile = {}
    for h in hits:
        byfile.setdefault(h["file"], []).append(h)
    kept = []
    for f, hs in byfile.items():
        fns = [h for h in hs if h["scope"] != "<module>"]
        kept.extend(fns if fns else hs)

    out = {"_meta": {"generated_by": "EXP-0170/analysis/roundtrip_idiom.py",
                     "decoder_names": sorted(DEC), "encoder_names": sorted(ENC),
                     "python_files_scanned": nfiles,
                     "why": "a disassemble->re-assemble->compare check is blind to any "
                            "defect symmetric across encode and decode; DEF-0166-1 is "
                            "exactly such a defect"},
           "n_hits": len(kept),
           "hits": sorted(kept, key=lambda h: (h["file"], h["lineno"]))}
    json.dump(out, open(os.path.join(HERE, "roundtrip_idiom.json"), "w"), indent=1)
    print("python files scanned: %d" % nfiles)
    print("scopes that decode AND re-encode AND compare/assert: %d" % len(kept))
    for h in out["hits"]:
        print("  %-72s %-26s L%-5d dec=%s enc=%s cmp=%d assert=%d"
              % (h["file"], h["scope"], h["lineno"], ",".join(h["decoders"]),
                 ",".join(h["encoders"]), h["comparisons"], h["asserts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
