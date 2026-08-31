#!/usr/bin/env python3
"""Verify the deliverable's INSTRUCTION-LENGTH claims against the live tokenizer.

The doc-number guard catches stale COUNTS. Nothing caught stale PROSE, and three
drifts were found by hand on 2026-08-30, all of which would have misled an
emitter: the docs told a reader `frame_marker_compact` is 4 bytes when applying
that to the tokenizer was refused as a measured corpus regression; the length
table still listed byte+2 `0x2d` at 14 bytes after it was corrected to 10; and a
bfloat widening was not documented at all.

DESIGN RULE, learned the hard way in this corpus: a checker that guesses
manufactures false alarms. The doc's length claims are heterogeneous prose --
"6, or 8 if byte[+2] & 0x02", "10/12 -- not yet solved", "6/8/10/14". This tool
therefore checks ONLY rows whose claim is a single unambiguous integer, and
reports everything else as UNCHECKED with its text. An unchecked row is an
honest gap, not a pass.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import isadb  # noqa: E402

DOC = os.path.join(ROOT, "docs", "isa", "README.md")
ROW = re.compile(r"^\|\s*`(0x[0-9a-fA-F]{2})`\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|")
INT = re.compile(r"^\*{0,2}(\d+)\*{0,2}$")


def claims(text):
    """(byte0, claimed_length_or_None, raw_text, line_no) for each simple row."""
    out = []
    for ln, line in enumerate(text.split("\n"), 1):
        m = ROW.match(line)
        if not m:
            continue
        b0, c2, c3 = m.group(1), m.group(2).strip(), m.group(3).strip()
        # Not every leading `0xNN` in this table is a BYTE0 key. Rows added
        # 2026-08-30 key on byte+2 (the icmpsel discriminator, the bfloat
        # op-select mask), and probing those as byte0 produced a false alarm on a
        # row I had just written correctly. If the row names a non-zero byte
        # offset, it is not a byte0 claim and this tool must not judge it.
        if re.search(r"byte\s*\+\s*[1-9]|`b[1-9]`|\bb2\b", line):
            out.append((int(b0, 16), None, line.strip() + "   [keys on a non-byte0 "
                        "offset -- not a byte0 length claim]", ln))
            continue
        # the length column is whichever of the two is a bare integer
        for cand in (c2, c3):
            im = INT.match(cand)
            if im:
                out.append((int(b0, 16), int(im.group(1)), line.strip(), ln))
                break
        else:
            out.append((int(b0, 16), None, line.strip(), ln))
    return out


def probe(b0):
    """Length the tokenizer gives a minimal buffer starting with b0.

    Zero-filled: many rules key on later bytes, so a mismatch here is a REPORT,
    not proof the doc is wrong -- the doc row may describe a different context.
    """
    buf = bytes([b0]) + b"\x00" * 23
    try:
        return isadb.instr_length(buf, 0)
    except Exception as e:
        return "error: %s" % e


def selftest():
    """Must be able to say both yes and no."""
    ok = True
    good = "| `0x0e` | stop | 4 |"
    bad = "| `0x0e` | stop | 999 |"
    amb = "| `0x09` | float ALU | 6, or **8 if `byte[+2] & 0x02`** |"
    g = claims(good)
    b = claims(bad)
    a = claims(amb)
    if not (g and g[0][1] == 4):
        print("SELFTEST FAIL: did not parse a simple claim"); ok = False
    if not (b and b[0][1] == 999):
        print("SELFTEST FAIL: did not parse a wrong claim"); ok = False
    if not (a and a[0][1] is None):
        print("SELFTEST FAIL: an AMBIGUOUS claim was parsed as a number -- that is "
              "how a checker manufactures false alarms"); ok = False
    # A row keyed on byte+2 must NOT be judged as a byte0 claim.
    nb0 = claims("| `0x2d` | **10** | icmpsel, byte+2 is the discriminator |")
    if not (nb0 and nb0[0][1] is None):
        print("SELFTEST FAIL: a non-byte0 row was judged as a byte0 length claim")
        ok = False
    # ...but a genuine byte0 row must still be judged.
    if not (claims("| `0x0e` | stop | 4 |")[0][1] == 4):
        print("SELFTEST FAIL: the non-byte0 guard swallowed a real claim"); ok = False
    return ok


def main():
    if not selftest():
        return 2
    text = open(DOC, encoding="utf-8", errors="replace").read()
    rows = claims(text)
    agree = differ = unchecked = 0
    notes = []
    for b0, claimed, raw, ln in rows:
        if claimed is None:
            unchecked += 1
            notes.append("  UNCHECKED  docs/isa/README.md:%d  %s" % (ln, raw[:110]))
            continue
        got = probe(b0)
        if got == claimed:
            agree += 1
        else:
            differ += 1
            notes.append("  DIFFERS    docs/isa/README.md:%d  byte0 %#04x: doc says %s, "
                         "tokenizer says %s  (zero-filled probe; the row may describe a "
                         "different context -- verify before editing either)"
                         % (ln, b0, claimed, got))
    for n in notes:
        print(n)
    print("length claims: %d agree, %d differ, %d unchecked (ambiguous prose)"
          % (agree, differ, unchecked))
    # Differences are REPORTED, never gated: a zero-filled probe cannot know the
    # context a doc row describes. Unchecked rows are the honest gap.
    return 0


if __name__ == "__main__":
    sys.exit(main())
