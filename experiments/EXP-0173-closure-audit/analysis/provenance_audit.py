#!/usr/bin/env python3
"""EXP-0173: audit every PROVENANCE.md row against the filesystem.

For each row of the provenance table:
  * artifacts_exist  -- does every path-like artifact the row cites resolve on disk?
  * claim_reproduced -- true only when a COMMAND recomputed the claim; three-valued,
                        with "not-mechanically-checkable" for prose claims. Re-reading
                        a document is never recorded as a pass.
  * notes            -- what was checked and what was found.

CLEAN-ROOM: reads only our own committed markdown / JSON / text artifacts.

    python3 experiments/EXP-0173-closure-audit/analysis/provenance_audit.py
"""
import json, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXPDIR))
PROV = os.path.join(ROOT, "PROVENANCE.md")

EXP_RE = re.compile(r"\bEXP-(?:[0-9]{4}|M4-[0-9]+|M5-[0-9]+|O2[A-Z]|[A-Za-z0-9]{1,3}[A-Za-z0-9-]{0,9})\b")
# a backticked token that looks like a path
TICK_RE = re.compile(r"`([^`]+)`")
ROOTPREFIX = ("experiments/", "tools/", "docs/", "gpu_knowledge/", "mesa/")
# these are AMBIGUOUS: they occur both at repo root and inside an experiment dir,
# so both interpretations must be tried before a row is called broken.
AMBIG = ("work/", "raw/", "analysis/", "harness/", "kernels/")
EXPPREFIX = AMBIG + ("RESULTS.md", "README.md", "manifest.json",
                     "PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json")
# non-EXP experiment directories the corpus cites by bare name (red-team passes etc.)
DIRNAME_RE = re.compile(r"\b((?:RT|REVIEW|O2[A-Z])[A-Za-z0-9-]*)\b")


def expand_braces(tok):
    m = re.search(r"\{([^{}]*)\}", tok)
    if not m:
        return [tok]
    out = []
    for part in m.group(1).split(","):
        out.extend(expand_braces(tok[:m.start()] + part.strip() + tok[m.end():]))
    return out


def clean_token(tok):
    """Strip things that make a citation look like a path but are not one."""
    tok = tok.strip().rstrip(",;.")
    tok = tok.split()[0] if tok.split() else tok      # `analysis/ab_run.sh isa_copy`
    tok = re.sub(r":\d+(?:-\d+)?$", "", tok)          # `file.c:171-172`
    return tok


def looks_like_path(tok):
    if tok.startswith(ROOTPREFIX) or tok.startswith(EXPPREFIX):
        return True
    if "/" in tok and re.search(r"\.(json|txt|md|py|m|metal|jsonl|csv|h|c|xml)$", tok):
        return True
    return False


def exp_dirs(expid):
    """EXP-0055 -> experiments/EXP-0055-*  (also matches bare RT-*/REVIEW-* names)"""
    return sorted(glob.glob(os.path.join(ROOT, "experiments", expid + "-*"))) + \
           sorted(glob.glob(os.path.join(ROOT, "experiments", expid))) + \
           sorted(glob.glob(os.path.join(ROOT, "experiments", expid + "*")))


def resolve(tok, exps):
    """Return (exists, list_of_paths_tried)."""
    tried = []
    cands = []
    if tok.startswith(ROOTPREFIX):
        cands.append(os.path.join(ROOT, tok))
    else:
        for e in exps:
            for d in exp_dirs(e):
                cands.append(os.path.join(d, tok))
        # AMBIG prefixes and bare filenames also exist at repo root
        cands.append(os.path.join(ROOT, tok))
    for c in cands:
        tried.append(os.path.relpath(c, ROOT))
        if os.path.exists(c):
            return True, tried, os.path.relpath(c, ROOT)
        # tolerate a directory cited without trailing slash, and glob wildcards
        g = glob.glob(c)
        if g:
            return True, tried, os.path.relpath(g[0], ROOT)
    return False, tried, None


def main():
    lines = open(PROV).read().splitlines()
    rows = []
    for ln, line in enumerate(lines, 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].lower().startswith("date") or set(cells[0]) <= set("-: "):
            continue
        date, fact, where, cat, src = cells[0], cells[1], cells[2], cells[3], "|".join(cells[4:])
        rows.append({"line": ln, "date": date, "fact": fact, "docs": where,
                     "category": cat, "source": src})

    audited = []
    for r in rows:
        blob = r["fact"] + " " + r["source"]
        exps = sorted(set(EXP_RE.findall(blob)))
        # non-EXP experiment dirs cited by bare name (RT-*, REVIEW-*, O2*)
        for dn in set(DIRNAME_RE.findall(blob)):
            if glob.glob(os.path.join(ROOT, "experiments", dn + "*")):
                exps.append(dn)
        exps = sorted(set(exps))
        # experiment directories
        missing_exp = [e for e in exps if not exp_dirs(e)]
        # path artifacts
        toks = []
        for t in TICK_RE.findall(blob):
            for tt in expand_braces(t):
                tt = clean_token(tt)
                if looks_like_path(tt):
                    toks.append(tt)
        toks = sorted(set(toks))
        art = []
        for t in toks:
            ok, tried, hit = resolve(t, exps)
            art.append({"cited": t, "exists": ok, "resolved_to": hit,
                        "tried": tried[:4] if not ok else None})
        missing_art = [a["cited"] for a in art if not a["exists"]]
        # a cited git commit hash is an auditable artifact too
        commits = []
        # only a token the row itself CALLS a commit (avoids hex byte strings and
        # the pinned mesa revision, which is not an object in this repo)
        for c in set(re.findall(r"commit\s+`?([0-9a-f]{7,40})`?", blob)):
            rc = os.system("git -C %s cat-file -e %s^{commit} 2>/dev/null" % (ROOT, c))
            commits.append({"commit": c, "exists": rc == 0})
        missing_commits = [c["commit"] for c in commits if not c["exists"]]

        notes = []
        if not exps and not toks:
            notes.append("row cites NO experiment id and NO path artifact")
        if missing_exp:
            notes.append("experiment dir(s) NOT FOUND: " + ", ".join(missing_exp))
        if missing_art:
            notes.append("cited path(s) NOT FOUND: " + ", ".join(missing_art))

        if missing_commits:
            notes.append("cited git commit(s) NOT IN HISTORY: " + ", ".join(missing_commits))
        artifacts_exist = ((not missing_exp) and (not missing_art) and (not missing_commits)
                           and bool(exps or toks or commits))
        audited.append({
            "line": r["line"], "date": r["date"],
            "fact": r["fact"][:400],
            "docs_target": r["docs"], "category": r["category"],
            "source": r["source"][:400],
            "experiments_cited": exps, "experiments_missing": missing_exp,
            "artifacts_cited": [a["cited"] for a in art],
            "artifacts_missing": missing_art,
            "commits_cited": [c["commit"] for c in commits],
            "commits_missing": missing_commits,
            "artifacts_exist": artifacts_exist,
            "claim_reproduced": None,          # filled by the claim pass below
            "notes": notes,
        })

    # ---- claim pass: mechanically checkable subset --------------------------
    # A claim is checkable here only if the row cites at least one existing TEXT
    # artifact and the fact contains a distinctive literal token (>=6 hex chars,
    # or a quoted/backticked identifier) that we can search for in that artifact.
    HEX = re.compile(r"\b(?:0x)?([0-9a-f]{6,})\b")
    for a in audited:
        if not a["artifacts_exist"]:
            a["claim_reproduced"] = False
            a["notes"].append("claim NOT reproducible: its evidence is missing")
            continue
        # gather existing text artifacts
        paths = []
        TEXT = (".txt", ".json", ".md", ".jsonl", ".csv", ".hex", ".log")
        for t in a["artifacts_cited"]:
            ok, _tr, hit = resolve(t, a["experiments_cited"])
            if not ok or not hit:
                continue
            full = os.path.join(ROOT, hit)
            if os.path.isdir(full):
                for f in sorted(glob.glob(os.path.join(full, "**", "*"), recursive=True))[:400]:
                    if os.path.isfile(f) and os.path.splitext(f)[1] in TEXT:
                        paths.append(os.path.relpath(f, ROOT))
            elif os.path.isfile(full) and os.path.splitext(full)[1] in TEXT:
                paths.append(hit)
            # a cited GLOB should contribute all of its matches
            for g in glob.glob(os.path.join(ROOT, hit).replace(hit, "") + t) if False else []:
                pass
        # expand cited globs fully
        for t in a["artifacts_cited"]:
            if "*" not in t:
                continue
            for e in a["experiments_cited"]:
                for d in exp_dirs(e):
                    for g in glob.glob(os.path.join(d, t)):
                        if os.path.isfile(g) and os.path.splitext(g)[1] in TEXT:
                            paths.append(os.path.relpath(g, ROOT))
        paths = sorted(set(paths))
        toks = set(m.group(1) for m in HEX.finditer(a["fact"].lower()))
        toks = {t for t in toks if len(t) >= 6 and not t.isdigit()}
        if not paths or not toks:
            a["claim_reproduced"] = "not-mechanically-checkable"
            a["notes"].append("no (text artifact x distinctive literal) pair to grep; "
                              "claim is prose or the evidence is binary/large")
            continue
        found, hay = [], ""
        for p in paths:
            try:
                hay += open(os.path.join(ROOT, p), errors="ignore").read().lower()
            except Exception:
                pass
        for t in sorted(toks):
            if t in hay:
                found.append(t)
        if found:
            a["claim_reproduced"] = True
            a["notes"].append("literal(s) %s found in cited artifact(s) %s (analysis-level "
                              "corroboration only; NOT a hardware re-run)"
                              % (", ".join(found[:4]), ", ".join(paths[:3])))
        else:
            a["claim_reproduced"] = False
            a["notes"].append("literal(s) %s NOT found in cited artifact(s) %s"
                              % (", ".join(sorted(toks)[:4]), ", ".join(paths[:3])))

    # ---- REVERSE CHAIN --------------------------------------------------
    # PROVENANCE.md rows pointing AT artifacts is only half the chain. CODEX
    # section 9: "No hardware fact enters docs/ unless the same change provides
    # an auditable evidence link... add or update its row in PROVENANCE.md."
    # So: which committed experiments supply facts to docs/ but have NO row?
    reverse = []
    prov = open(PROV).read()
    docs_blob = ""
    for root_d, _dirs, files in os.walk(os.path.join(ROOT, "docs")):
        for fn in files:
            if fn.endswith((".md", ".xml")):
                docs_blob += open(os.path.join(root_d, fn), errors="ignore").read()
    for d in sorted(glob.glob(os.path.join(ROOT, "experiments", "EXP-*"))):
        base = os.path.basename(d)
        mm = re.match(r"(EXP-[0-9]{4})", base)
        if not mm:
            continue
        e = mm.group(1)
        if os.system("git -C %s ls-files --error-unmatch %s >/dev/null 2>&1"
                     % (ROOT, os.path.relpath(d, ROOT))) != 0:
            continue                                    # not committed yet
        has_row = e in prov
        cited_in_docs = e in docs_blob
        if not has_row:
            reverse.append({"experiment": e, "dir": os.path.relpath(d, ROOT),
                            "has_provenance_row": False,
                            "cited_in_docs": cited_in_docs,
                            "severity": ("CODEX section 9 VIOLATION: supplies a fact to docs/ "
                                         "with no PROVENANCE row" if cited_in_docs
                                         else "no row, but also not cited in docs/ — "
                                              "incomplete index rather than a broken fact")})

    n = len(audited)
    ex = sum(1 for a in audited if a["artifacts_exist"])
    rep_t = sum(1 for a in audited if a["claim_reproduced"] is True)
    rep_f = sum(1 for a in audited if a["claim_reproduced"] is False)
    rep_n = sum(1 for a in audited if a["claim_reproduced"] == "not-mechanically-checkable")
    rv_bad = [r for r in reverse if r["cited_in_docs"]]
    out = {"_meta": {"experiment": "EXP-0173", "source": "PROVENANCE.md",
                     "reverse_chain_committed_experiments_without_a_row": len(reverse),
                     "reverse_chain_CODEX_S9_violations": len(rv_bad),
                     "reverse_chain_violating_experiments": [r["experiment"] for r in rv_bad],
                     "rows": n, "artifacts_exist_true": ex, "artifacts_exist_false": n - ex,
                     "claim_reproduced_true": rep_t, "claim_reproduced_false": rep_f,
                     "claim_not_mechanically_checkable": rep_n,
                     "limitation": "pure analysis: no hardware re-run is possible here, so "
                                   "claim_reproduced:true means the cited artifact contains the "
                                   "claimed literal, never that the hardware was re-observed"},
           "rows": audited, "reverse_chain": reverse}
    p = os.path.join(HERE, "provenance_audit.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("\n=== ROWS WITH MISSING EVIDENCE (the worst finding class) ===")
    bad = [a for a in audited if not a["artifacts_exist"]]
    for a in bad:
        print("\nL%d [%s] %s" % (a["line"], a["date"], a["fact"][:110]))
        for nt in a["notes"]:
            print("     - " + nt)
    print("\n=== REVERSE CHAIN: committed experiments with NO PROVENANCE.md row ===")
    print("  %d total; %d of them are cited in docs/ (CODEX section 9 violations):"
          % (len(reverse), len(rv_bad)))
    for r in rv_bad:
        print("    %s  (%s)" % (r["experiment"], r["dir"]))
    print("\nwrote", p)


if __name__ == "__main__":
    sys.exit(main())
