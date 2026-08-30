#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0189 step 4 -- two RESCUE passes over the UNVERIFIABLE set.

An `UNVERIFIABLE` verdict from audit.py means "no per-value raw record could be
attributed to this field", which is an AUDITABILITY statement about the citation and
the indexer, not a statement about the silicon. Two mechanical causes of a false
UNVERIFIABLE were found by hand during this audit and are now tested for at scale:

  R1 UNDERSCORE RESCUE.  collect_raw.py routes any record whose `field` begins with
     `_` into the baseline/pseudo bucket (it is meant to catch `__baseline`,
     `__falsifier_*`, `__ladder_*`).  EXP-0180 records the ONLY sweep of
     `half_alu_ext8.dst` -- byte0's high nibble, 16 values x 2 carriers x 2 gated runs
     -- under `field: "__dst_nibble"`, so the field reads UNVERIFIABLE purely because
     of the record's NAME.  This pass re-attributes underscore-named groups
     bit-exactly, exactly as collect_raw does for ordinary ones.

  R2 CITATION RESCUE.  audit.py only looks in the experiments a field's `evidence`
     list cites.  `call.offset` cites EXP-0035 (2026-08, unstructured) while
     EXP-0179 holds 100%-attributable per-value records for that exact key, because
     the evidence list was never updated when EXP-0179 landed.  This pass searches
     the WHOLE index for each unverifiable key and reports where records exist.

Neither pass changes a threshold or a bucket rule; both re-run the FROZEN rules over
a corrected input.  Every rescue is reported individually so the orchestrator can
accept or reject it row by row.

Usage: python3 analysis/rescue.py      (after collect_raw.py, audit.py, recount.py)
"""
import collections, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect_raw as CR          # noqa: E402   frozen indexer, reused not rebuilt
import audit as AUD               # noqa: E402   frozen thresholds, reused not rebuilt
import recount as RC              # noqa: E402

EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")

assert (AUD.MIN_COMMON, AUD.MIN_AGREE_PCT, AUD.MOVED_OVER_DISAGREE) == (2, 99.0, 2.0), \
    "frozen thresholds moved -- refusing to run"

# Underscore names that are genuinely NOT field sweeps and must stay excluded.
NOT_A_FIELD = re.compile(r"^_*(baseline|ladder|falsifier|control|sentinel|health|"
                         r"anchor|probe|integrity|smoke|warm)", re.I)


def underscore_index():
    """Re-run collect_raw's bit-exact attribution over ONLY the underscore-named
    groups it discards, using the identical offset fit and partition rule."""
    DB = CR.load_db()
    groups = collections.defaultdict(list)
    partial = set()
    exps = sorted(d for d in os.listdir(EXPDIR)
                  if os.path.isdir(os.path.join(EXPDIR, d, "raw")))
    for exp in exps:
        raw = os.path.join(EXPDIR, exp, "raw")
        for dirpath, _, filenames in os.walk(raw):
            rel = os.path.relpath(dirpath, raw)
            run = "." if rel == "." else rel.split(os.sep)[0]
            if "PARTIAL.md" in filenames:
                partial.add(exp + "/" + run)
            for fn in filenames:
                if not fn.endswith(".jsonl"):
                    continue
                runid = run if run != "." else os.path.splitext(fn)[0]
                for line in open(os.path.join(dirpath, fn), errors="replace"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    fld, ins = rec.get("field"), rec.get("instr")
                    if not (isinstance(fld, str) and isinstance(ins, str)):
                        continue
                    if not fld.startswith("_") or NOT_A_FIELD.match(fld):
                        continue
                    ac = [str(rec[k]) for k in ("carrier", "arm")
                          if rec.get(k) not in (None, "")]
                    arm = "|".join(ac) if ac else "-"
                    b = rec.get("bytes")
                    if not (isinstance(b, str) and b and len(b) % 2 == 0
                            and CR.HEXRE.match(b)):
                        b = None
                    cont = rec.get("outcome") in CR.CONTAM or "skip_reason" in rec
                    groups[(exp, ins, fld, arm, runid)].append(
                        (rec.get("value"), b, CR.sig_of(rec), cont))

    cell = collections.defaultdict(lambda: {"obs": collections.defaultdict(collections.Counter),
                                            "n_cases": 0, "n_contam": 0, "labels": set()})
    for (exp, ins, label, arm, run), recs in groups.items():
        spec = DB.get(ins)
        if spec is None:
            continue
        live = [r for r in recs if not r[3]]
        hexed = [r for r in live if r[1]]
        nb = {len(r[1]) // 2 for r in hexed}
        if len(hexed) < 2 or len(nb) != 1:
            continue
        nbytes = nb.pop()
        words = [int.from_bytes(bytes.fromhex(r[1]), "little") for r in hexed]
        m = 0
        for w in words[1:]:
            m |= w ^ words[0]
        if m == 0:
            continue
        d, nfit = CR.fit_offset(words, nbytes, spec)
        if nfit < max(1, len(words) // 2):
            d = 0
        L = spec["length"] or nbytes
        full = (1 << (8 * L)) - 1
        iws = [(w >> (8 * d)) & full for w in words]
        mi = 0
        for w in iws[1:]:
            mi |= w ^ iws[0]
        for n, s, wd in spec["fields"]:
            if not (mi & (((1 << wd) - 1) << s)):
                continue
            mask = ((1 << wd) - 1) << s
            c = cell[(exp, ins, n, arm, run)]
            c["labels"].add(label)
            c["n_cases"] += len(recs)
            c["n_contam"] += sum(1 for r in recs if r[3])
            for (r, w) in zip(hexed, iws):
                c["obs"]["%x:%x" % (w & ~mask, (w & mask) >> s)][r[2]] += 1

    index = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(dict)))
    for (exp, ins, fld, arm, run), c in cell.items():
        keys = {k: cnt.most_common(1)[0][0] for k, cnt in c["obs"].items()}
        nwru = sum(1 for cnt in c["obs"].values() if len(cnt) > 1)
        byrest = collections.defaultdict(dict)
        for k, s in keys.items():
            rest, fv = k.split(":", 1)
            byrest[rest][fv] = s
        moved, vals = 0, set()
        for rest, fvs in byrest.items():
            if len(fvs) < 2:
                continue
            modal = collections.Counter(fvs.values()).most_common(1)[0][0]
            moved += sum(1 for s in fvs.values() if s != modal)
            vals |= set(fvs)
        index[exp]["%s.%s" % (ins, fld)][arm][run] = {
            "n_cases": c["n_cases"], "n_contam": c["n_contam"], "n_values": len(vals),
            "moved": moved, "n_within_run_unstable": nwru,
            "attribution": ["bit-exact-underscore"], "labels": sorted(c["labels"]),
            "byte_offsets": [], "keys": {k: s for k, s in keys.items()
                                         if k.split(":", 1)[0] in
                                         {r for r, f in byrest.items() if len(f) >= 2}}}
    return {e: {k: dict(v) for k, v in ks.items()} for e, ks in index.items()}, sorted(partial)


def main():
    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    audit = json.load(open(os.path.join(HERE, "audit.json")))["fields"]
    idx = json.load(gzip.open(os.path.join(WORK, "raw_index.json.gz"), "rt"))
    resolve = AUD.resolver()
    partial = set(idx["_meta"]["partial_runs"])
    index, pseudo = idx["index"], idx["pseudo"]

    uix, upart = underscore_index()
    json.dump(uix, gzip.open(os.path.join(WORK, "underscore_index.json.gz"), "wt"),
              sort_keys=True)

    unver = sorted(k for k, r in audit.items() if r["bucket"] == "UNVERIFIABLE")

    # merged index = the frozen index PLUS the underscore-rescued cells.  Collisions
    # keep the frozen cell (the underscore pass never overwrites a real record).
    merged = {d: {k: {a: dict(rs) for a, rs in arms.items()}
                  for k, arms in keys.items()} for d, keys in index.items()}
    for d, keys in uix.items():
        for k, arms in keys.items():
            for a, rs in arms.items():
                for r, v in rs.items():
                    merged.setdefault(d, {}).setdefault(k, {}).setdefault(a, {}).setdefault(r, v)

    r1, r2, rescued, still = {}, {}, {}, []
    for k in unver:
        rec = audit[k]
        cited = [d for d in (resolve(e) for e in rec["evidence"]) if d]
        u_dirs = sorted(d for d in cited if k in uix.get(d, {}))
        other = sorted(d for d in merged
                       if k in merged[d] and d not in cited)
        if not u_dirs and not other:
            still.append(k)
            continue
        # RE-RUN THE FROZEN RULE over the widened evidence set.  Nothing is assumed
        # to pass: a rescued field can land in any bucket, withheld ones included.
        pe = AUD.gather(k, sorted(set(cited) | set(u_dirs) | set(other)),
                        merged, partial, resolve, pseudo)
        b, arms, tested, moved = AUD.classify(pe)
        entry = {"new_bucket": b, "n_arms_tested": len(tested), "moved_total": moved,
                 "max_values": max((v["n_values_max"] for ex in pe.values()
                                    for v in ex.values()), default=0),
                 "cited_dirs": cited, "underscore_dirs": u_dirs,
                 "uncited_dirs_with_records": other,
                 "old_reason": rec["unverifiable_reason"],
                 "raw_files": sorted({"experiments/%s/raw/%s/" % (d, run)
                                      for d, ex in pe.items() for v in ex.values()
                                      for run in v["runs"]})}
        rescued[k] = entry
        if u_dirs:
            r1[k] = entry
        if other:
            r2[k] = entry
        if b == "UNVERIFIABLE":
            still.append(k)

    # ---- recompute emittability with rescues applied ----------------------
    rescued_ok = sorted(k for k, v in rescued.items()
                        if v["new_bucket"] not in AUD.WITHHOLD)
    strict = sorted(k for k, r in audit.items() if r["bucket"] in AUD.WITHHOLD)
    strict_rescued = sorted(set(strict) - set(rescued_ok))
    ia = json.load(open(os.path.join(HERE, "emittability.json")))["instruction_entry_audit"]
    instr_withheld = sorted(m for m, v in ia.items()
                            if v["label"] in RC.EMIT_OK and v["verdict"] != "dispatched")
    base, rel, _ = RC.emittable_current(val, db, [], [])
    out = {}
    for name, wf, wi in (("strict", strict, instr_withheld),
                         ("strict_after_rescue", strict_rescued, instr_withheld),
                         ("strict_after_rescue_fields_only", strict_rescued, [])):
        e, _r, why = RC.emittable_current(val, db, wf, wi)
        out[name] = {"n_fields_withheld": len(wf), "emittable": len(e),
                     "lost_vs_published": sorted(set(base) - set(e)), "mnemonics": e}
    bucket_after = collections.Counter(v["new_bucket"] for v in rescued.values())

    res = {"_meta": {"experiment": "EXP-0189-closing-audit",
                     "thresholds_frozen": {"min_common": AUD.MIN_COMMON,
                                           "min_agree_pct": AUD.MIN_AGREE_PCT,
                                           "moved_over_disagree": AUD.MOVED_OVER_DISAGREE},
                     "n_unverifiable_in_audit": len(unver),
                     "n_with_widened_evidence": len(rescued),
                     "n_touched_by_R1_underscore": len(r1),
                     "n_touched_by_R2_citation": len(r2),
                     "n_cleared_the_frozen_rule": len(rescued_ok),
                     "buckets_after_rescue": dict(bucket_after),
                     "n_still_unverifiable": len(still)},
           "rescued": rescued,
           "R1_underscore_touched": sorted(r1),
           "R2_citation_touched": sorted(r2),
           "still_unverifiable": still,
           "emittability": out}
    json.dump(res, open(os.path.join(HERE, "rescue.json"), "w"), indent=1, sort_keys=True)
    print("UNVERIFIABLE %d -> widened evidence for %d (R1 %d, R2 %d); "
          "cleared the frozen rule: %d; still UNVERIFIABLE %d"
          % (len(unver), len(rescued), len(r1), len(r2), len(rescued_ok), len(still)))
    print("  buckets after rescue:", dict(bucket_after))
    for n, v in out.items():
        print("  %-34s emittable %3d of %d (withheld %d)"
              % (n, v["emittable"], len(rel), v["n_fields_withheld"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
