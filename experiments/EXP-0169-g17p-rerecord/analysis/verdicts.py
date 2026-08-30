#!/usr/bin/env python3
"""EXP-0169 raw -> analysis/field_verdicts.json + analysis/reproduction.json

  python3 analysis/verdicts.py raw/<gated_run_A> raw/<gated_run_B>

Two questions are answered separately, because they are different questions:

1. WHAT DOES THE FRESH CAPTURE SHOW? -> field_verdicts.json, flat
   `<mnemonic>.<field>`, FIELD-SWEEP-PROTOCOL section 5, using ONLY the eight
   labels of docs/evidence-classification.md.

2. DOES THE ORIGINAL PROMOTION REPRODUCE? -> reproduction.json. A field whose
   original promotion does NOT reproduce is the most valuable output of this
   experiment: it means the corpus has been carrying a wrong fact. Where the
   comparison cannot be made mechanically (the original `range` is prose), the
   verdict is NEEDS-ADJUDICATION with both sides printed -- never a guess
   dressed as a finding.

PROMOTION GATE (dispatch-mandated, and identical to EXP-0164 audit.py so the
two are directly comparable):
    >= 99% per-value cross-run agreement AND min(movedA, movedB) >= 2 x
    disagreements, over >= MIN_COMMON common values.

GATE-ZERO, applied before anything else: the (arm, carrier)'s LIVENESS LADDER
must have passed. A carrier that never demonstrated it could see a difference
cannot support either a live or an inert conclusion, and its fields are left
`untested`. This is the failure mode that produced the withheld set in the
first place.

Fields the coordinator assigned elsewhere -- the field NAME `dst` on every
descriptor (EXP-0168) and `get_sr.form` (EXP-0172) -- are SWEPT here, because
which register slot changed is this experiment's detection instrument, but NO
verdict is emitted for them.

CLEAN-ROOM: analysis only, over our own raw.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")

HARD = {"fault", "hang", "undecodable", "killed", "not_written",
        "no_draw", "lost_7_of_8", "nondeterministic"}
MIN_COMMON = 2
MIN_AGREE_PCT = 99.0
MOVED_OVER_DISAGREE = 2.0
# Verdicts another experiment owns. Swept here (the sweep is this experiment's
# detection instrument) but never ruled on. `dst` -> EXP-0168; `get_sr.form` ->
# EXP-0172. Matched as a bare field name OR as "<mnemonic>.<field>".
FOREIGN_FIELDS = {"dst", "get_sr.form"}
INERT_WORDS = re.compile(r"inert|no observable effect|no effect|don't care|"
                         r"reserved pad|non-load-bearing", re.I)


def field_geometry():
    """(start, width) per `<mnemonic>.<field>`, from the db the HARDWARE ran
    against where we have it (work/frozen/db.json, pulled off the neo) and the
    EXP-0164 pinned snapshot otherwise. Which one was used is recorded in the
    output, because a drifting descriptor silently re-keys every verdict."""
    for cand, src in ((os.path.join(WORK, "frozen", "db.json"), "work/frozen/db.json"),
                      (os.path.join(WORK, "db.snapshot.json"), "work/db.snapshot.json")):
        if os.path.exists(cand):
            db = json.load(open(cand))
            out = {}
            for i in db["instructions"]:
                for f in i.get("fields", []):
                    out["%s.%s" % (i["mnemonic"], f["name"])] = (f["start"], f["width"])
            return out, src
    return {}, None


def get_field(blk, tgt, start, width):
    """db.json bit numbering: LSB-first across the instruction's bytes."""
    v = 0
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
        if byi >= len(blk):
            return None
        if blk[byi] >> (bit & 7) & 1:
            v |= 1 << i
    return v


def sig_of(rec):
    """EXP-0164 collect_raw.py::sig_of, same shape, so a verdict here and an
    audit there are computed from the same notion of 'the observation'."""
    oc = rec.get("outcome")
    hard = oc if oc in HARD else "run"
    obs = rec.get("observed")
    d = "-" if obs is None else hashlib.sha1(
        json.dumps(obs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:10]
    return hard + "|" + d


def load_run(path):
    """-> (groups, counts, sem, ladder, meta, fvals, dbytes).
    groups[(instr, arm, carrier, field)] is {(cross, value): sig};
    ladder[(arm, carrier)] is the pass/fail record;
    fvals/dbytes are the coverage sets described below."""
    groups = collections.defaultdict(dict)
    counts = collections.defaultdict(collections.Counter)
    sem = collections.defaultdict(list)
    ladder = collections.defaultdict(dict)
    # COVERAGE, the thing no gate we have actually tests. `fvals` is the set of
    # distinct FIELD values dispatched (recovered from the bytes, so a byte-wise
    # sweep of a >8-bit field is counted in the field's own units, not the
    # byte's). `dbytes` is the set of distinct ENCODINGS dispatched -- the only
    # thing that reveals under-coverage, i.e. a sweep that dispatched 256 values
    # but only ever produced 8 distinct encodings (the DEF-0166-1 signature).
    fvals = collections.defaultdict(set)
    dbytes = collections.defaultdict(set)
    GEO, _geosrc = field_geometry()
    n = 0
    with open(os.path.join(path, "sweep.jsonl")) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            n += 1
            fld = r.get("field")
            if not isinstance(fld, str):
                continue
            ac = (r.get("arm"), r.get("carrier"))
            if fld.startswith("__"):
                ok = None
                if r.get("predict") == "not_ok":
                    ok = (r.get("outcome") != "ok")
                elif r.get("predict") == "move":
                    ok = bool(r.get("outcome") != "ok"
                              or r.get("match") is False)
                ladder[ac][fld] = {"outcome": r.get("outcome"),
                                   "match": r.get("match"), "pass": ok,
                                   "note": r.get("note", "")}
                continue
            key = (r.get("instr"), r.get("arm"), r.get("carrier"), fld)
            k = (r.get("cross") or "", r.get("value"))
            groups[key][k] = sig_of(r)
            counts[key][r.get("outcome")] += 1
            hx = r.get("bytes")
            if isinstance(hx, str) and hx:
                dbytes[key].add(hx)
                geo = GEO.get("%s.%s" % (r.get("instr"), fld))
                if geo:
                    try:
                        fv = get_field(bytes.fromhex(hx), r.get("tgt") or 0,
                                       geo[0], geo[1])
                    except Exception:
                        fv = None
                    if fv is not None:
                        fvals[key].add(fv)
            if r.get("sem_match") is not None:
                sem[key].append({"cross": r.get("cross"), "value": r.get("value"),
                                 "sem_match": r["sem_match"],
                                 "want": (r.get("oracle") or {}).get("sem"),
                                 "observed": r.get("observed")})
    meta = {"records": n, "path": path, "field_geometry_source": _geosrc}
    for extra in ("00_env.json", "02_summary.json"):
        p = os.path.join(path, extra)
        if os.path.exists(p):
            meta[extra] = json.load(open(p))
    return groups, counts, sem, ladder, meta, fvals, dbytes


def moved_of(sigs):
    """How many values differ from the group's modal signature."""
    if len(sigs) < 2:
        return 0
    modal = collections.Counter(sigs.values()).most_common(1)[0][0]
    return sum(1 for s in sigs.values() if s != modal)


def cross_run(a, b):
    common = set(a) & set(b)
    agree = sum(1 for k in common if a[k] == b[k])
    n = len(common)
    return {"common": n, "agree": agree, "disagreements": n - agree,
            "agree_pct": round(100.0 * agree / n, 2) if n else None,
            "movedA": moved_of(a), "movedB": moved_of(b),
            "n_valuesA": len(a), "n_valuesB": len(b)}


def gate(c):
    if c is None or c["common"] < MIN_COMMON:
        return False
    if c["agree_pct"] is None or c["agree_pct"] < MIN_AGREE_PCT:
        return False
    if c["movedA"] < 1 or c["movedB"] < 1:
        return False
    return min(c["movedA"], c["movedB"]) >= MOVED_OVER_DISAGREE * c["disagreements"]


def stable_inert(c):
    """Exhaustively swept, cross-run agreeing, and nothing ever moved."""
    if c is None or c["common"] < MIN_COMMON:
        return False
    if c["agree_pct"] is None or c["agree_pct"] < MIN_AGREE_PCT:
        return False
    return c["movedA"] == 0 and c["movedB"] == 0


def coverage_of(key, arms, GEO):
    """The machine-readable coverage a `range` prose string cannot carry.

    `values_dispatched`  distinct FIELD values actually dispatched, recovered
                         from the `bytes` column so a byte-wise sweep of a
                         >8-bit field is counted in the field's own units.
    `distinct_bytes`     distinct ENCODINGS dispatched. This is the one that
                         reveals UNDER-COVERAGE: a sweep that reports 256
                         values but produced only 8 distinct encodings never
                         tested what it claims (the DEF-0166-1 signature, where
                         an assembler left match-overlapping bits stuck).
    `encodable_range`    2^width.
    THIN            <=>  values_dispatched < encodable_range
    UNDER_COVERED   <=>  distinct_bytes < values_dispatched
    """
    geo = GEO.get(key)
    start, width = geo if geo else (None, None)
    enc = (1 << width) if width is not None else None
    fv = set()
    for x in arms:
        fv |= set(x.get("_fvals", []))
    nb = max([x.get("distinct_bytes", 0) for x in arms] + [0])
    nv = len(fv)
    thin = bool(enc is not None and nv < enc)
    under = bool(nb < nv)
    keys = {"values_dispatched": nv, "distinct_bytes": nb,
            "encodable_range": enc, "start": start, "width": width,
            "coverage_pct": (round(100.0 * nv / enc, 1) if enc else None),
            "thin": thin, "under_covered": under,
            "n_carriers": len({x["carrier"] for x in arms})}
    if enc is None:
        rs = "%d distinct values over %d encodings, %d carriers" % (
            nv, nb, keys["n_carriers"])
    elif not thin:
        rs = "0..%d dense (all %d values), %d distinct encodings, %d carriers" % (
            enc - 1, enc, nb, keys["n_carriers"])
    else:
        rs = "%d of %d encodable values (%.1f%%), %d distinct encodings, %d carriers" % (
            nv, enc, 100.0 * nv / enc, nb, keys["n_carriers"])
    if under:
        rs += " -- UNDER-COVERED: fewer distinct encodings than values"
    return {"keys": keys, "range_str": rs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=HERE,
                    help="where to write field_verdicts.json / reproduction.json "
                         "(default: analysis/). harness/selftest.py points this at "
                         "work/ so a CODE test never overwrites real verdicts.")
    ap.add_argument("runs", nargs="+",
                    help="two or more gated run directories. Arms captured in "
                         "different pairs (the DSTORE arm runs last, in its own "
                         "pair, because it stores through unbound binding slots) "
                         "are handled per field: the two runs with the most "
                         "distinct attributed values are the gated pair for that "
                         "field, exactly as EXP-0164's cross_run does.")
    a = ap.parse_args()
    loaded = [(r, load_run(r)) for r in a.runs]
    metas = {r: L[4] for r, L in loaded}
    GEO, geosrc = field_geometry()

    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    valins = val.get("instructions", val)
    W = json.load(open(os.path.join(EXPDIR, "EXP-0164-inert-audit", "analysis",
                                    "withhold_unverifiable.json")))

    keys = sorted({k for _, L in loaded for k in L[0]})
    per_arm = {}
    for k in keys:
        instr, arm, carrier, fld = k
        # The gated pair FOR THIS CELL is the two runs that reached the most
        # distinct attributed values -- the same rule EXP-0164's cross_run uses.
        # This is what lets the DSTORE arm be captured in its own later pair
        # without the earlier pair diluting it.
        have = sorted(((len(L[0][k]), r, L) for r, L in loaded if k in L[0]),
                      key=lambda x: (-x[0], x[1]))
        if len(have) < 2:
            runs_used = [h[1] for h in have]
            c = None
            gAk = have[0][2][0][k] if have else {}
            gBk = {}
            La = have[0][2] if have else None
            Lb = None
        else:
            runs_used = [have[0][1], have[1][1]]
            La, Lb = have[0][2], have[1][2]
            gAk, gBk = La[0][k], Lb[0][k]
            c = cross_run(gAk, gBk)
        lad = {}
        for L in (La, Lb):
            if L:
                lad.update(L[3].get((arm, carrier), {}))
        lad_pass = (bool(lad) and
                    all(v["pass"] for v in lad.values() if v["pass"] is not None))
        semrecs = []
        for L in (La, Lb):
            if L:
                semrecs += L[2].get(k, [])
        semfail = [s for s in semrecs if s["sem_match"] is False]
        arm_fv, arm_db = set(), set()
        for L in (La, Lb):
            if L:
                arm_fv |= L[5].get(k, set())
                arm_db |= L[6].get(k, set())
        per_arm.setdefault("%s.%s" % (instr, fld), []).append({
            "arm": arm, "carrier": carrier, "runs_used": runs_used,
            "values_dispatched": len(arm_fv),
            "distinct_bytes": len(arm_db),
            "_fvals": sorted(arm_fv), "_dbytes_n": len(arm_db),
            "cross_run": c,
            "ladder_pass": lad_pass, "ladder": lad,
            "gate_live": gate(c), "gate_inert": stable_inert(c),
            "outcomesA": dict(La[1].get(k, {})) if La else {},
            "outcomesB": dict(Lb[1].get(k, {})) if Lb else {},
            "sem_checked": len(semrecs), "sem_failures": semfail[:32],
            "n_sem_failures": len(semfail),
        })

    verdicts = {"_meta": {
        "experiment": "EXP-0169-g17p-rerecord",
        "target": "G17P",
        "gated_runs": list(a.runs),
        "pairing": ("per field, the two runs with the most distinct attributed "
                    "values (EXP-0164 cross_run's own rule), so an arm captured "
                    "in a separate later pair is not diluted by the earlier one"),
        "gate": ("cross-run agreement >= %.0f%% AND min(movedA,movedB) >= %.1f x "
                 "disagreements, over >= %d common values; the (arm,carrier) "
                 "liveness ladder must have passed first"
                 % (MIN_AGREE_PCT, MOVED_OVER_DISAGREE, MIN_COMMON)),
        "labels": "docs/evidence-classification.md section 2, and nothing else",
        "foreign_fields": ("`dst` on every descriptor is EXP-0168's verdict "
                           "(coordinator directive 2026-08-30). Swept here as "
                           "this experiment's detection instrument; NO verdict "
                           "emitted."),
        "runs_meta": metas,
        "field_geometry_source": geosrc,
        "coverage_keys": ("every row carries values_dispatched / distinct_bytes / "
                          "encodable_range / start / width / coverage_pct / thin / "
                          "under_covered. THIN = values_dispatched < encodable_range. "
                          "UNDER-COVERED = distinct_bytes < values_dispatched, which is "
                          "the only signal that a sweep dispatched values it never "
                          "actually encoded (DEF-0166-1)."),
    }}
    repro = {"_meta": dict(verdicts["_meta"])}
    repro["_meta"]["question"] = ("does the ORIGINAL promotion recorded in "
                                  "validation.json reproduce in this fresh "
                                  "capture?")

    for key in sorted(per_arm):
        instr, fld = key.split(".", 1)
        arms = per_arm[key]
        cov = coverage_of(key, arms, GEO)
        if fld in FOREIGN_FIELDS or key in FOREIGN_FIELDS:
            verdicts[key] = {"label": "untested", "target": "G17P",
                             "evidence": ["EXP-0169"],
                             "range": "swept but NOT ruled on here: "
                                      + cov["range_str"],
                             "note": ("another experiment owns this field's "
                                      "verdict (coordinator directive "
                                      "2026-08-30): `dst` -> EXP-0168, "
                                      "`get_sr.form` -> EXP-0172. The raw is "
                                      "committed and attributable; the ruling "
                                      "is theirs."),
                             "arms": arms}
            verdicts[key].update(cov["keys"])
            continue
        usable = [x for x in arms if x["ladder_pass"]]
        live = [x for x in usable if x["gate_live"]]
        inert = [x for x in usable if x["gate_inert"]]
        nval = max([x["cross_run"]["n_valuesA"] for x in arms] +
                   [x["cross_run"]["n_valuesB"] for x in arms] + [0])
        semfail = sum(x["n_sem_failures"] for x in arms)
        semchk = sum(x["sem_checked"] for x in arms)

        if not usable:
            label, cls = "untested", "NO-DETECTION-POWER"
            note = ("no (arm,carrier) passed its liveness ladder, so neither a "
                    "live nor an inert reading is supportable from this run")
        elif live:
            label, cls = "hardware-run", "LIVE"
            note = "moved on %d of %d ladder-passing carriers" % (len(live),
                                                                  len(usable))
        elif len(inert) >= 2:
            label, cls = "hardware-run", "INERT-MULTI"
            note = ("no observable effect over the swept range on %d "
                    "structurally different ladder-passing carriers" % len(inert))
        elif len(inert) == 1:
            label, cls = "untested", "INERT-SINGLE"
            note = ("inert on the ONE carrier that had detection power; a "
                    "second, structurally different carrier is required before "
                    "this can be called inert (EXP-0164's own rule)")
        else:
            label, cls = "untested", "UNSTABLE"
            note = ("movement does not reproduce across the two gated runs at "
                    ">=%.0f%% per-value agreement" % MIN_AGREE_PCT)
        if semchk and semfail:
            label, cls = "untested", "SEMANTIC-ORACLE-FAILED"
            note = ("%d of %d values disagreed with the HOST-COMPUTED oracle; "
                    "see reproduction.json" % (semfail, semchk))

        verdicts[key] = {
            "label": label, "verdict_class": cls, "target": "G17P",
            "evidence": ["EXP-0169"],
            "range": cov["range_str"],
            "carriers": sorted({x["carrier"] for x in arms}),
            "note": note, "arms": arms,
            "sem_checked": semchk, "sem_failures": semfail,
        }
        verdicts[key].update(cov["keys"])

        # ---- reproduction against the pinned snapshot --------------------
        orig = (valins.get(instr, {}) or {}).get(fld, {}) or {}
        wentry = W.get(key, {})
        orig_label = orig.get("label", wentry.get("label_now", "untested"))
        orig_range = orig.get("range", wentry.get("range", ""))
        orig_note = orig.get("note", "")
        claims_inert = bool(INERT_WORDS.search((orig_range or "")
                                               + " " + (orig_note or "")))
        if cls in ("NO-DETECTION-POWER", "INERT-SINGLE", "UNSTABLE"):
            rv = "INCONCLUSIVE"
        elif cls == "SEMANTIC-ORACLE-FAILED":
            rv = "DOES-NOT-REPRODUCE"
        elif cls == "LIVE":
            rv = "REPRODUCES" if not claims_inert else "CONTRADICTS-INERT-CLAIM"
        else:                                   # INERT-MULTI
            rv = "REPRODUCES" if claims_inert else "DOES-NOT-REPRODUCE"
        if orig_label not in ("hardware-run", "isolated-byte-diff") and \
                rv in ("DOES-NOT-REPRODUCE", "CONTRADICTS-INERT-CLAIM"):
            rv = "NEEDS-ADJUDICATION"
        repro[key] = {
            "reproduction": rv,
            "original_label": orig_label,
            "original_range": orig_range,
            "original_evidence": orig.get("evidence", wentry.get("evidence")),
            "original_claims_inert": claims_inert,
            "fresh_class": cls,
            "fresh_label": label,
            "sem_checked": semchk, "sem_failures": semfail,
            "sem_failure_examples": [f for x in arms
                                     for f in x["sem_failures"]][:12],
        }

    # `_fvals` is an internal working set, not evidence; drop it before writing.
    for kk, vv in verdicts.items():
        for x in (vv.get("arms") or []):
            x.pop("_fvals", None)
            x.pop("_dbytes_n", None)
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "field_verdicts.json"), "w") as fh:
        json.dump(verdicts, fh, indent=1, sort_keys=True)
    with open(os.path.join(a.out_dir, "reproduction.json"), "w") as fh:
        json.dump(repro, fh, indent=1, sort_keys=True)

    cnt = collections.Counter(v["verdict_class"] for k, v in verdicts.items()
                              if k != "_meta" and "verdict_class" in v)
    rcnt = collections.Counter(v["reproduction"] for k, v in repro.items()
                               if k != "_meta")
    print("fields ruled on:", sum(cnt.values()))
    for k, v in sorted(cnt.items()):
        print("   %-24s %d" % (k, v))
    thin = sum(1 for k, v in verdicts.items()
               if k != "_meta" and v.get("thin"))
    under = sorted(k for k, v in verdicts.items()
                   if k != "_meta" and v.get("under_covered"))
    print("coverage: %d rows THIN (values_dispatched < encodable_range), "
          "%d UNDER-COVERED" % (thin, len(under)))
    for k in under:
        print("   UNDER-COVERED %s: %d values but only %d distinct encodings"
              % (k, verdicts[k]["values_dispatched"], verdicts[k]["distinct_bytes"]))
    print("reproduction:")
    for k, v in sorted(rcnt.items()):
        print("   %-24s %d" % (k, v))
    bad = sorted(k for k, v in repro.items()
                 if k != "_meta" and v["reproduction"] in
                 ("DOES-NOT-REPRODUCE", "CONTRADICTS-INERT-CLAIM"))
    if bad:
        print("\nDOES NOT REPRODUCE (report these first):")
        for k in bad:
            print("   %-34s %s  (was %s: %s)"
                  % (k, repro[k]["reproduction"], repro[k]["original_label"],
                     (repro[k]["original_range"] or "")[:70]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
