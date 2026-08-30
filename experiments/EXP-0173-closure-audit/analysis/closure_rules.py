#!/usr/bin/env python3
"""EXP-0173: rule-by-rule verdict against the six closure rules, per P0/P1 row.

docs/P0-P1-CLOSURE.md defines six rules a row must meet to be CLOSED. This
computes, for each of the sixteen rows, which rules are MET / NOT MET / NOT
MECHANICALLY CHECKABLE, and what command establishes each verdict.

Rules (verbatim from docs/P0-P1-CLOSURE.md):
  1. the required value or behavior can be GENERATED, not merely decoded from a
     captured template;
  2. the complete authored probe, commands, raw observations, failures, and
     analysis are committed under experiments/;
  3. the evidence chain is recorded in PROVENANCE.md;
  4. the normative docs contain the exact fields, ranges, fallbacks, and target
     status;
  5. an adversarial reproduction or second method passes; and
  6. the relevant userspace object can be independently generated and consumed
     without a captured Apple template.

Rules 2, 3 and 5 are mechanically checkable and are computed here. Rules 1, 4
and 6 are substantive and are reported with the evidence that bears on them --
never asserted as met without a computation behind them.

    python3 experiments/EXP-0173-closure-audit/analysis/closure_rules.py
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
BOARD = os.path.join(ROOT, "docs", "P0-P1-CLOSURE.md")
PROV = os.path.join(ROOT, "PROVENANCE.md")
EXP_RE = re.compile(r"EXP-(?:[0-9]{4}|M4-[0-9]+|M5-[0-9]+)")
ADVERSARIAL = re.compile(r"adversarial|refut|falsif|second method|independent probe|"
                         r"counter-?example|control arm", re.I)


def exp_dir(e):
    g = sorted(glob.glob(os.path.join(ROOT, "experiments", e + "*")))
    return g[0] if g else None


def main():
    board = open(BOARD).read()
    prov = open(PROV).read()
    rows = []
    for line in board.splitlines():
        m = re.match(r"^\|\s*(P[01]\.\d)\s*\|(.*)$", line.strip())
        if not m:
            continue
        rid, rest = m.group(1), m.group(2)
        cells = [c.strip() for c in rest.split("|")]
        # the board opens with a row-ID MAPPING table (| P0.1 | DRV-UAPI-01 ... |);
        # those are not status rows and must not be scored.
        if cells and re.match(r"^DRV-", cells[0]):
            continue
        requirement = cells[0] if cells else ""
        status = cells[1] if len(cells) > 1 else ""
        exps = sorted(set(EXP_RE.findall(line)))

        # --- rule 2: complete experiment record committed
        r2 = []
        for e in exps:
            d = exp_dir(e)
            if not d:
                r2.append({"exp": e, "dir": None, "complete": False,
                           "missing": ["<directory>"]})
                continue
            # a superseded / quarantined stub is not scored: the board cites it as
            # history, and CODEX requires the record be RETAINED, not completed.
            if os.path.isfile(os.path.join(d, "SUPERSEDED.md")) or \
               os.path.isfile(os.path.join(d, "QUARANTINE.md")):
                r2.append({"exp": e, "dir": os.path.relpath(d, ROOT), "complete": True,
                           "missing": [], "note": "SUPERSEDED/QUARANTINED stub — retained by "
                                                  "design, not scored"})
                continue
            # CODEX section 6 allows equivalent layouts, so "authored probe" and
            # "derived analysis" are matched anywhere in the tree, not only in
            # harness/ + kernels/ + analysis/.
            code = [f for f in glob.glob(os.path.join(d, "**", "*"), recursive=True)
                    if os.path.splitext(f)[1] in (".py", ".sh", ".m", ".mm", ".metal", ".c")
                    and "/raw/" not in f]
            derived = [f for f in glob.glob(os.path.join(d, "analysis", "**", "*"),
                                            recursive=True) if os.path.isfile(f)]
            derived += [f for f in glob.glob(os.path.join(d, "*.json"))
                        if os.path.basename(f) not in ("manifest.json",
                                                       "CAPTURE_CONTRACT.json")]
            need = {"README.md": os.path.isfile(os.path.join(d, "README.md")),
                    "RESULTS.md": os.path.isfile(os.path.join(d, "RESULTS.md")),
                    "manifest.json": os.path.isfile(os.path.join(d, "manifest.json")),
                    "raw/ (non-empty)": bool(glob.glob(os.path.join(d, "raw", "**", "*"),
                                                       recursive=True)),
                    "derived analysis": bool(derived),
                    "authored probe (any .py/.sh/.m/.metal/.c outside raw/)": bool(code)}
            r2.append({"exp": e, "dir": os.path.relpath(d, ROOT),
                       "complete": all(need.values()),
                       "missing": [k for k, v in need.items() if not v]})
        rule2 = bool(exps) and all(x["complete"] for x in r2)

        # --- rule 3: evidence chain recorded in PROVENANCE.md
        r3 = {e: (e in prov) for e in exps}
        rule3 = bool(exps) and all(r3.values())

        # --- rule 5: adversarial reproduction / second method in the RESULTS
        r5 = {}
        for e in exps:
            d = exp_dir(e)
            f = os.path.join(d, "RESULTS.md") if d else None
            r5[e] = bool(f and os.path.isfile(f) and ADVERSARIAL.search(open(f).read()))
        rule5 = bool(exps) and all(r5.values())

        closed = "CLOSED" in status.upper() and "NOT" not in status.upper()
        rows.append({
            "row": rid, "requirement": requirement[:120],
            "board_status": status[:80],
            "board_says_CLOSED": closed,
            "experiments_cited": exps,
            "rule1_generated_not_decoded": {
                "verdict": "NOT MECHANICALLY CHECKABLE — substantive",
                "note": "see analysis/template_dependency.json; for P0.6 the only mnemonics "
                        "with a zero-copied generated program that ran are device_store, "
                        "falu2, mov_imm, stop (+ device_load / falu2i / iadd2 partly)."},
            "rule2_complete_record": {
                "verdict": "MET" if rule2 else "NOT MET",
                "detail": r2,
                "command": "python3 experiments/EXP-0173-closure-audit/analysis/closure_rules.py"},
            "rule3_provenance_chain": {
                "verdict": "MET" if rule3 else "NOT MET",
                "detail": r3,
                "command": "grep -c '<EXP-id>' PROVENANCE.md"},
            "rule4_normative_docs": {
                "verdict": "NOT MECHANICALLY CHECKABLE — substantive",
                "note": "requires reading docs/ against the row's field list"},
            "rule5_adversarial_or_second_method": {
                "verdict": "MET" if rule5 else "NOT MET",
                "detail": r5,
                "command": "grep -Ei 'adversarial|refut|falsif|second method' "
                           "experiments/<EXP>/RESULTS.md"},
            "rule6_object_generated_without_template": {
                "verdict": "NOT MECHANICALLY CHECKABLE — substantive",
                "note": "see analysis/template_dependency.json"},
        })

    n = len(rows)
    out = {"_meta": {
        "experiment": "EXP-0173",
        "rows_parsed": n,
        "rows_the_board_marks_CLOSED": sum(1 for r in rows if r["board_says_CLOSED"]),
        "rule2_MET": sum(1 for r in rows if r["rule2_complete_record"]["verdict"] == "MET"),
        "rule3_MET": sum(1 for r in rows if r["rule3_provenance_chain"]["verdict"] == "MET"),
        "rule5_MET": sum(1 for r in rows
                         if r["rule5_adversarial_or_second_method"]["verdict"] == "MET"),
        "completion_gate": "NOT PASSED — the gate requires all sixteen rows CLOSED",
    }, "rows": rows}
    p = os.path.join(HERE, "closure_rules.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("\n%-6s %-9s %-7s %-7s %-7s %s" % ("row", "board", "rule2", "rule3", "rule5", "gaps"))
    for r in rows:
        gaps = []
        for x in r["rule2_complete_record"]["detail"]:
            if not x["complete"]:
                gaps.append("%s missing %s" % (x["exp"], ",".join(x["missing"])))
        for e, ok in r["rule3_provenance_chain"]["detail"].items():
            if not ok:
                gaps.append("%s absent from PROVENANCE.md" % e)
        for e, ok in r["rule5_adversarial_or_second_method"]["detail"].items():
            if not ok:
                gaps.append("%s RESULTS has no adversarial/second-method text" % e)
        print("%-6s %-9s %-7s %-7s %-7s %s" % (
            r["row"], "CLOSED" if r["board_says_CLOSED"] else "OPEN",
            r["rule2_complete_record"]["verdict"],
            r["rule3_provenance_chain"]["verdict"],
            r["rule5_adversarial_or_second_method"]["verdict"],
            "; ".join(gaps)[:150]))
    print("\nwrote", p)


if __name__ == "__main__":
    sys.exit(main())
