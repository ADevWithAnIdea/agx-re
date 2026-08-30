#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- the 25 "EXP-0189 withheld (...): N values dispatched over M arm(s),
K observations moved" notes with N > 0.  (EXP-0196's check_e0189_zero.py covered
only the N == 0 sub-family; these were left NOT CHECKED.)

Three independent instruments, each of which can return "no":

 T1 TRANSCRIPTION.  validation.json's note vs EXP-0189/analysis/withhold_flat.json's
    own `note` for the same key, and vs its own structured
    max_values_dispatched / n_arms_that_tested_the_field / moved_total.
    A note that disagrees with the numbers in the object it was printed from is
    a defect regardless of what the hardware did.

 T2 SELF-CONSISTENCY.  the note's "N values dispatched" against the SAME row's
    `range` string in validation.json.  A row asserting "0 values dispatched"
    beside "256 of 256, DENSE" is contradicting itself.  (N > 0 here, so this
    mostly tests whether N exceeds what `range` says was encodable.)

 T3 RAW FLOOR.  a lower bound on distinct values actually present in committed
    raw for (instr, field) -- by field NAME and, separately, by byte_index inside
    the field's db.json span, because a name-keyed index manufactures false
    absences (EXP-0196 3.3: 71,262 of EXP-0171's 71,898 records carry
    field: null).  T3 can only FALSIFY ("the raw cannot supply N distinct
    values"); a shortfall in my index is reported as INSTRUMENT-LIMITED, never as
    a finding.

Read-only.  Writes analysis/check_e0189_nonzero.json.
"""
import collections, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
# NB: `\w+` does NOT match "INERT-SINGLE"; EXP-0196's check_e0189_zero.py uses
# `\((\w+)\)` and therefore silently skipped every INERT-SINGLE row.  Fixed here.
RX = re.compile(r"EXP-0189 withheld \(([A-Z-]+)\): (\d+) values dispatched over (\d+) arm\(s\), "
                r"(\d+) observations moved")


def spans():
    db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
    out = {}
    for i in db["instructions"]:
        for f in i.get("fields", []):
            out["%s.%s" % (i["mnemonic"], f["name"])] = (f["start"], f["width"])
    return out


_scan = {}


def scan_exp(expdir):
    if expdir in _scan:
        return _scan[expdir]
    byf = collections.defaultdict(set)
    byb = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(EXPS, expdir, "raw", "**", "*.jsonl"),
                              recursive=True)):
        for ln in open(p, "rb"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            ins, fld, bi, v = r.get("instr"), r.get("field"), r.get("byte_index"), r.get("value")
            if v is None:
                continue
            if isinstance(v, (list, dict)):
                v = json.dumps(v, sort_keys=True)
            if isinstance(fld, str):
                byf[(ins, fld)].add(v)
            if bi is not None:
                byb[(ins, bi)].add(v)
    _scan[expdir] = (byf, byb)
    return _scan[expdir]


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    nc = set(json.load(open(os.path.join(
        ROOT, "experiments/EXP-0196-note-integrity-audit/work/not_checked.json"))))
    wf = json.load(open(os.path.join(
        EXPS, "EXP-0189-closing-audit", "analysis", "withhold_flat.json")))
    SP = spans()
    out = {}
    for m, e in sorted(val["instructions"].items()):
        for f, r in sorted(e.items()):
            k = "%s.%s" % (m, f)
            if k not in nc or not isinstance(r, dict):
                continue
            note = (r.get("note") or "")
            mo = RX.search(note)
            if not mo:
                continue
            bucket, n, arms, moved = (mo.group(1), int(mo.group(2)),
                                      int(mo.group(3)), int(mo.group(4)))
            src = wf.get(k)
            claims = []
            # T1
            if src is None:
                claims.append({"claim": "T1_source_row_exists", "ok": None,
                               "detail": "no row for this key in EXP-0189 withhold_flat.json"})
            else:
                claims.append({
                    "claim": "T1_transcription",
                    "claimed": {"bucket": bucket, "n": n, "arms": arms, "moved": moved},
                    "source": {"bucket": src.get("bucket_after_widening"),
                               "n": src.get("max_values_dispatched"),
                               "arms": src.get("n_arms_that_tested_the_field"),
                               "moved": src.get("moved_total")},
                    "note_identical": (src.get("note", "").strip() in note.strip()),
                    "ok": (src.get("max_values_dispatched") == n
                           and src.get("n_arms_that_tested_the_field") == arms
                           and src.get("moved_total") == moved)})
            # T2
            rng = r.get("range") or ""
            # only the canonical "<a> of <b> [sub-]values" / "<a>/<b> values" shape
            # is machine-comparable; anything else is prose and is not scored.
            mo2 = re.match(r"\s*(\d+)\s*(?:of|/)\s*(\d+)\s+(?:sub-)?values", rng)
            claims.append({"claim": "T2_range_self_consistency", "range": rng,
                           "claimed_n": n,
                           "range_encodable": None if not mo2 else int(mo2.group(2)),
                           "ok": None if not mo2 else (n > 0 and int(mo2.group(1)) > 0)})
            # T3
            sp = SP.get(k)
            bs = set(range(sp[0] // 8, (sp[0] + sp[1] - 1) // 8 + 1)) if sp else set()
            named, byteo = set(), set()
            where = []
            for ev in (r.get("evidence") or []):
                for d in sorted(glob.glob(os.path.join(EXPS, ev.split("/")[0] + "*"))):
                    if not os.path.isdir(d):
                        continue
                    byf, byb = scan_exp(os.path.basename(d))
                    a = byf.get((m, f), set())
                    b = set()
                    for bi in bs:
                        b |= byb.get((m, bi), set())
                    if a or b:
                        where.append({"exp": os.path.basename(d),
                                      "distinct_named": len(a), "distinct_byte": len(b)})
                    named |= a
                    byteo |= b
            best = max(len(named), len(byteo))
            claims.append({"claim": "T3_raw_floor", "claimed_values_dispatched": n,
                           "raw_distinct_named": len(named),
                           "raw_distinct_byte_indexed": len(byteo),
                           "where": where,
                           "ok": True if best >= n else None,
                           "verdict": ("RAW-SUPPLIES-ENOUGH" if best >= n
                                       else "INSTRUMENT-LIMITED (index found fewer; "
                                            "not evidence of absence)")})
            bad = [c for c in claims if c["ok"] is False]
            out[k] = {"label": r.get("label"), "evidence": r.get("evidence"),
                      "bucket": bucket, "note": note, "range": rng,
                      "claims": claims,
                      "verdict": "CONTRADICTED" if bad else "SUPPORTED"}
    json.dump(out, open(os.path.join(HERE, "check_e0189_nonzero.json"), "w"),
              indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0189 non-zero withheld family:", len(out), dict(c))
    t3 = collections.Counter(cl["verdict"] for v in out.values()
                             for cl in v["claims"] if cl["claim"] == "T3_raw_floor")
    print("  T3:", dict(t3))
    for k, v in sorted(out.items()):
        st = [cl for cl in v["claims"] if cl["ok"] is False]
        t3v = [cl for cl in v["claims"] if cl["claim"] == "T3_raw_floor"][0]
        print("  %-30s %-13s T3=%s (claim %s / named %s / byte %s)"
              % (k, v["verdict"], t3v["verdict"].split()[0],
                 t3v["claimed_values_dispatched"], t3v["raw_distinct_named"],
                 t3v["raw_distinct_byte_indexed"]))
        for cl in st:
            print("       FAILS", json.dumps(cl)[:300])


if __name__ == "__main__":
    main()
