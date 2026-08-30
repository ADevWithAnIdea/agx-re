#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 step 2 -- for every `note` in validation.json, find the committed
experiment artifact that carries the same note text for the same
<mnemonic>.<field> key.

Rationale: a note whose numbers were transcribed from an experiment's own
committed verdict file is at worst wrong at the source; a note whose numbers
appear nowhere in the corpus was authored at merge time and has no committed
observation behind it at all. The two need different follow-up, so they are
separated before any recomputation.

Evidence-path resolution reuses tools/agx-isa/validate_labels.py's rule --
`glob(experiments/<slug>*)` -- so this audit resolves citations exactly the
way the project's own validator does.

Read-only.  Writes analysis/note_provenance.json.
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
EMIT = ("hardware-run", "isolated-byte-diff")


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def resolve(slug):
    """validate_labels.py's rule, verbatim in behaviour."""
    return sorted(glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*")))


def harvest(expdir):
    """{key: [(relpath, note_text)]} over every dict-of-dicts JSON in analysis/."""
    out = {}
    for pat in ("analysis/*.json", "work/*.json", "*.json"):
        for p in glob.glob(os.path.join(expdir, pat)):
            try:
                d = json.load(open(p))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            rel = os.path.relpath(p, ROOT)
            stack = [("", d)]
            seen = 0
            while stack and seen < 20000:
                pre, node = stack.pop()
                for k, v in (node.items() if isinstance(node, dict) else []):
                    seen += 1
                    if isinstance(v, dict):
                        key = k if not pre else pre + "/" + k
                        for nk in ("note", "semantics", "notes", "why", "reason", "merge_note", "verdict_note", "range"):
                            if isinstance(v.get(nk), str):
                                out.setdefault(k, []).append((rel, nk, v[nk]))
                        if seen < 20000:
                            stack.append((key, v))
    return out


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    cache = {}
    res = {}
    for m, e in sorted(val["instructions"].items()):
        for f, r in sorted(e.items()):
            if not isinstance(r, dict):
                continue
            nt = norm(r.get("note"))
            if not nt:
                continue
            key = "%s.%s" % (m, f)
            grade = "EMIT" if (r.get("label") in EMIT and f != "_instruction") else "OTHER"
            hits = []
            searchset = list(r.get("evidence") or [])
            # ALSO search every experiment the NOTE ITSELF names. EXP-0194 6 shows a
            # citation-scoped audit cannot see evidence the label forgot to cite; the
            # same blind spot would make a faithfully-transcribed note look invented.
            searchset += re.findall(r"\b(EXP-[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*)", nt)
            for ev in dict.fromkeys(searchset):
                for d in resolve(ev):
                    if d not in cache:
                        cache[d] = harvest(d)
                    idx = cache[d]
                    for cand_key in (key, f, m):
                        for rel, nk, txt in idx.get(cand_key, []):
                            t = norm(txt)
                            if not t:
                                continue
                            if t == nt:
                                hits.append({"file": rel, "field": nk, "kind": "exact", "key": cand_key})
                            elif t and (t in nt or nt in t):
                                hits.append({"file": rel, "field": nk, "kind": "substring", "key": cand_key})
            kinds = {h["kind"] for h in hits}
            res[key] = {
                "grade": grade, "label": r.get("label"), "evidence": r.get("evidence") or [],
                "note": nt,
                "provenance": ("exact" if "exact" in kinds else
                               ("substring" if "substring" in kinds else "none")),
                "hits": hits[:6],
            }
    json.dump(res, open(os.path.join(HERE, "note_provenance.json"), "w"), indent=1, sort_keys=True)
    import collections
    c = collections.Counter((v["grade"], v["provenance"]) for v in res.values())
    for k in sorted(c):
        print(k, c[k])


if __name__ == "__main__":
    main()
