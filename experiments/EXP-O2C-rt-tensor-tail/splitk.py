#!/usr/bin/env python3
# EXP-O2C: split a multi-kernel .metal into one temp file per top-level function
# (prelude + that function only), so an invalid kernel does not poison the whole
# library compile. A top-level function block runs from a line beginning with a
# return-type + name up to the next line that is exactly "}" at column 0.
# Emits: for each function, writes work/<tag>_<fn>.metal and prints "fn".
# CLEAN-ROOM: operates only on our own MSL source.
import sys, re, os
src = open(sys.argv[1]).read()
tag = sys.argv[2]
outdir = sys.argv[3] if len(sys.argv) > 3 else "work"
os.makedirs(outdir, exist_ok=True)
lines = src.split("\n")
# prelude = everything before the first top-level function definition
defre = re.compile(r'^(kernel|vertex|fragment)\s+\S+\s+(\w+)\s*\(')
# also catch [[intersection(...)]] functions (span multiple lines)
starts = []
i = 0
while i < len(lines):
    m = defre.match(lines[i])
    if m:
        starts.append((i, m.group(2)))
    i += 1
prelude_end = starts[0][0] if starts else len(lines)
# But an [[intersection(...)]] attribute line precedes some kernels; include any
# attribute/comment lines immediately above each start with the block.
prelude = "\n".join(lines[:prelude_end])

def block_end(s):
    j = s
    while j < len(lines):
        if lines[j].rstrip() == "}":
            return j
        j += 1
    return len(lines) - 1

for (s, name) in starts:
    e = block_end(s)
    body = "\n".join(lines[s:e+1])
    out = prelude + "\n\n" + body + "\n"
    p = os.path.join(outdir, f"{tag}_{name}.metal")
    open(p, "w").write(out)
    print(name)
