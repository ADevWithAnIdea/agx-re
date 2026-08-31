#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""score.py -- the four scored runs that separate MY additions from the indexer's.

  base      fresh modern evidence index, citations AS COMMITTED          the before
  prop      fresh modern evidence index, citations + EXP-0215 additions  MY effect
  base_leg  + EXP-0211's legacy parsers, citations AS COMMITTED          control
  prop_leg  + EXP-0211's legacy parsers, citations + additions           the total

`prop - base` is this experiment's own contribution and `prop_leg - prop` is the
legacy index's, exactly the control EXP-0211 used (`m3 - m3ctl`).

Writes only under EXP-0215/work. `tools/agx-isa/validation.json` is never edited:
the proposed sidecar is a scratch copy with additions APPENDED to `evidence`; no
citation is removed, reordered away, or replaced, and no label, range, note, span
or target is touched.
"""
import copy, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
W = os.path.join(EXP, "work")
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI


def build_proposed():
    val = json.load(open(os.path.join(W, "validation_frozen.json")))
    add = json.load(open(os.path.join(EXP, "analysis", "citation_additions.json")))
    out = copy.deepcopy(val)
    n = 0
    for key, spec in add.items():
        m, f = key.split(".", 1)
        row = out["instructions"][m][f]
        ev = list(row.get("evidence") or [])
        before = list(ev)
        for a in spec["add"]:
            if a["experiment"] not in ev:
                ev.append(a["experiment"])
                n += 1
        assert ev[:len(before)] == before, "an addition must never remove or reorder"
        row["evidence"] = ev
    p = os.path.join(W, "validation_proposed.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=False)
    print("proposed sidecar: %d citations appended over %d rows -> %s" % (n, len(add), p))
    return p


def build_legacy_index():
    src = os.path.join(W, "index")
    dst = os.path.join(W, "index_legacy")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    _o = EI.load_db
    EI.load_db = lambda path=None: _o(os.path.join(W, "db_frozen.json"))
    import legacy_index as LI
    recs = [json.loads(l) for l in open(os.path.join(W, "legacy_index",
                                                     "legacy_records.jsonl")) if l.strip()]
    LI.merge_cache(dst, recs, src_index=src)
    return dst


def run(tag, index_dir, labels):
    rep = os.path.join(W, "reports_" + tag)
    led = os.path.join(W, "ledgers", tag + ".jsonl")
    os.makedirs(os.path.dirname(led), exist_ok=True)
    if os.path.exists(led):
        os.remove(led)
    cmd = [sys.executable, os.path.join(ROOT, "tools", "agx-isa", "dashboards.py"),
           "--index-dir", index_dir, "--labels", labels, "--ledger", led,
           "--reports", rep, "--run-id", "EXP-0215-" + tag]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("dashboards failed for %s" % tag)
    open(os.path.join(W, "score_%s.txt" % tag), "w").write(r.stdout)
    return json.load(open(os.path.join(rep, "dashboards.json")))


def main():
    prop = build_proposed()
    frozen = os.path.join(W, "validation_frozen.json")
    idx = os.path.join(W, "index")
    idxl = build_legacy_index()
    out = {}
    for tag, i, l in (("base", idx, frozen), ("prop", idx, prop),
                      ("base_leg", idxl, frozen), ("prop_leg", idxl, prop)):
        out[tag] = run(tag, i, l)
        print("scored", tag)
    json.dump(out, open(os.path.join(EXP, "analysis", "dashboard_delta.json"), "w"),
              indent=1, default=str)


if __name__ == "__main__":
    main()
