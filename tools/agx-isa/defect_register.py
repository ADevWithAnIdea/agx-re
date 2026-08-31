#!/usr/bin/env python3
"""Generate docs/defect-register.md — every DEF-NNNN-N known to this corpus.

93 defect identifiers were scattered across db.json notes, validation.json notes,
experiment RESULTS files and tool comments with **no index**. A defect register is
the "what is wrong with our own model" list: an implementer needs it before
trusting a descriptor, and we need it before repeating a repair.

This scrapes rather than curates, deliberately. A hand-written register goes stale
the moment the next defect lands; a generated one cannot. Where a defect's text is
ambiguous the register says so and points at the source, because a wrong one-line
summary of a defect is worse than a pointer to the real one.
"""
import collections, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ID = re.compile(r"\bDEF-(\d{4}|[A-Z0-9]+)-(\d+)\b")


def scan():
    """Every DEF- mention, with its file and the sentence around it."""
    out = collections.defaultdict(list)
    cmd = ["git", "grep", "-n", "-I", "-E", r"DEF-[0-9A-Z]+-[0-9]+", "--", "."]
    try:
        txt = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout
    except Exception as e:
        print("git grep failed: %s" % e, file=sys.stderr)
        return out
    for line in txt.split("\n"):
        if not line or ":" not in line:
            continue
        try:
            path, ln, body = line.split(":", 2)
        except ValueError:
            continue
        # Never read the generated register itself: it lives in the tree, so a
        # plain `git grep` finds its own rows and the file starts feeding on its
        # own summaries. The count rose 93 -> 94 on the first run that did this,
        # and several "primary sources" pointed at the register rather than at
        # the evidence.
        if os.path.normpath(path) == os.path.join("docs", "defect-register.md"):
            continue
        for m in ID.finditer(body):
            out[m.group(0)].append((path, int(ln), body.strip()))
    _extend_multiline(out)
    return out


def _extend_multiline(found):
    """Pull in following lines when a definition CONTINUES past the ID's line.

    The first version was line-based, so it reported 6 defects as having "no
    prose definition anywhere". They all had one -- it just continued onto the
    next line, or the id sat at the end of its own line ("Recorded as
    db_defects -> DEF-0153-1."). Scraping a line at a time and then calling the
    result a gap in the RECORD blamed the corpus for a limitation of the tool.
    """
    want = collections.defaultdict(set)
    for did, ms in found.items():
        for path, ln, body in ms:
            i = body.find(did)
            if i >= 0 and len(body[i + len(did):].split()) < 8:
                want[path].add((ln, did))
    for path, entries in want.items():
        full = os.path.join(ROOT, path)
        try:
            lines = open(full, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for ln, did in entries:
            tail = []
            for k in range(ln, min(ln + 3, len(lines))):
                nxt = lines[k].strip().lstrip("#").strip()
                if not nxt or ID.search(nxt):
                    break
                tail.append(nxt)
            if tail:
                found[did].append((path, ln, did + " " + " ".join(tail)))


def summarise(did, mentions):
    """Best available one-line summary FOR THIS defect id.

    Never invents. If nothing looks like a definition, returns None and the row
    says 'no prose definition found' rather than guessing at one.

    The first version sliced from the first `DEF-` in the line, so a line
    mentioning several ids attributed ANOTHER defect's text to this one --
    DEF-0139-3 was summarised with DEF-0171-1's finding. A wrong one-line summary
    of a defect is worse than a pointer to the real one, which is what this
    docstring already said and the code did not do. Now: slice from THIS id, and
    stop at the next id so no other defect's text is absorbed.
    """
    best = None
    for path, ln, body in mentions:
        if path.endswith(".py") and body.strip().startswith("#"):
            body = body.lstrip("# ").strip()
        i = body.find(did)
        if i < 0:
            continue
        tail = body[i + len(did):]
        nxt = ID.search(tail)
        if nxt:
            tail = tail[:nxt.start()]
        tail = tail.lstrip(" :,)-–—").strip()
        if len(tail.split()) < 8:
            continue
        # Prefer a DEFINITION over a passing mention. An id appearing early in
        # the line is usually the subject of that line; one appearing 400 chars
        # in is usually a cross-reference. Rank on that first, length second.
        score = (0 if i < 120 else 1, -len(tail.split()))
        if best is None or score < best[0]:
            best = (score, tail)
    return best[1][:400] if best else None


def main():
    found = scan()
    if not found:
        print("no defects found (is this a git checkout?)", file=sys.stderr)
        return 1
    lines = ["# Defect register — every `DEF-` known to this corpus", "",
             "**Generated by `tools/agx-isa/defect_register.py`; do not hand-edit.** "
             "Regenerate after any new defect.", "",
             "This is the *what is wrong with our own model* index. A descriptor, a "
             "tokenizer rule or a tool named here has a **known, recorded defect** — read "
             "the source before trusting it. Defects are kept, never deleted: "
             "`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §9 requires that a later correction "
             "not erase the earlier observation.", "",
             "| defect | mentions | primary source | summary |", "|---|---:|---|---|"]
    undefined = 0
    for did in sorted(found, key=lambda d: (d.split("-")[1], int(d.rsplit("-", 1)[1]))):
        ms = found[did]
        src = min(ms, key=lambda m: (0 if m[0].endswith(".md") else 1, len(m[0])))
        s = summarise(did, ms)
        if s is None:
            undefined += 1
            s = "*(no prose definition found — read the source)*"
        s = s.replace("|", "\\|")
        lines.append("| `%s` | %d | `%s:%d` | %s |" % (did, len(ms), src[0], src[1], s))
    lines += ["", "## Coverage", "",
              "- **%d** distinct defects; **%d** total mentions." %
              (len(found), sum(len(v) for v in found.values())),
              "- **%d** have no prose definition anywhere and are pointer-only — that is a "
              "real gap in the record, not a formatting artefact." % undefined]
    out = os.path.join(ROOT, "docs", "defect-register.md")
    open(out, "w").write("\n".join(lines) + "\n")
    print("wrote %s: %d defects, %d mentions, %d pointer-only"
          % (os.path.relpath(out, ROOT), len(found),
             sum(len(v) for v in found.values()), undefined))
    return 0


if __name__ == "__main__":
    sys.exit(main())
