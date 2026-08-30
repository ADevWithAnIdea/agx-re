#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm B step 1 -- index every per-value raw sweep record in the repository
and, for each sweep group, count DISTINCT `bytes` strings against DISTINCT dispatched
`value`s.  That comparison is the decisive test for DEF-0166-1 (EXP-0166): a sweep
built through the old OR-only isadb.assemble() dispatched N values but only ever
spliced N / 2^p distinct encodings, and the raw records say so.

REUSES experiments/EXP-0164-inert-audit/analysis/collect_raw.py rather than
reimplementing the indexer: its `fit_offset` (recover the instruction's byte offset
inside the `bytes` column by fitting db.json's own match constraints), `identify`
(rescue a raw `instr` label that is not a db mnemonic), `resolve_label`
(byte-label -> db field names) and its (carrier, arm) group key (amendment A5) are
imported and called directly.  This script adds only the two counters EXP-0164 did
not compute.

READ-ONLY over experiments/*/raw/**.  Writes only work/coverage_index.json.gz.

Usage: python3 analysis/coverage_index.py
"""
import collections, gzip, importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
ROOT = os.path.abspath(os.path.join(EXPDIR, ".."))
WORK = os.path.join(EXP, "work")
CR_PATH = os.path.join(EXPDIR, "EXP-0164-inert-audit", "analysis", "collect_raw.py")

_spec = importlib.util.spec_from_file_location("exp0164_collect_raw", CR_PATH)
CR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CR)          # module has no import-time side effects

HEXRE = CR.HEXRE

# frozen thresholds (PRE_REGISTRATION 3, Arm B)
INFORMATIVE_MIN_VALUES = 4


def load_db():
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    out = {}
    for i in db["instructions"]:
        out[i["mnemonic"]] = {
            "length": i.get("length"),
            "match": i.get("match") or [],
            "fields": [(f["name"], f["start"], f["width"]) for f in i.get("fields", [])],
        }
    return out


def canon(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return repr(v)
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def main():
    DB = load_db()

    # (exp, instr, field_label, arm, run) -> records
    groups = collections.defaultdict(list)
    gfiles = collections.defaultdict(set)
    stats = collections.Counter()
    per_exp = collections.defaultdict(lambda: collections.Counter())

    exps = sorted(d for d in os.listdir(EXPDIR)
                  if os.path.isdir(os.path.join(EXPDIR, d, "raw")))
    for exp in exps:
        raw = os.path.join(EXPDIR, exp, "raw")
        for dirpath, _, filenames in os.walk(raw):
            rel = os.path.relpath(dirpath, raw)
            run = "." if rel == "." else rel.split(os.sep)[0]
            for fn in filenames:
                if not fn.endswith(".jsonl"):
                    continue
                path = os.path.join(dirpath, fn)
                relpath = os.path.relpath(path, ROOT)
                runid = run if run != "." else os.path.splitext(fn)[0]
                for line in open(path, errors="replace"):
                    line = line.strip()
                    if not line:
                        continue
                    stats["lines"] += 1
                    try:
                        rec = json.loads(line)
                    except Exception:
                        stats["bad_lines"] += 1
                        continue
                    if not isinstance(rec, dict):
                        stats["bad_lines"] += 1
                        continue
                    fld, ins = rec.get("field"), rec.get("instr")
                    if not (isinstance(fld, str) and isinstance(ins, str)):
                        stats["no_field_or_instr"] += 1
                        continue
                    if fld.startswith("_"):
                        stats["pseudo_field"] += 1
                        continue
                    stats["field_recs"] += 1
                    per_exp[exp]["field_recs"] += 1
                    # EXP-0164 amendment A5 group key
                    ac = [str(rec[k]) for k in ("carrier", "arm")
                          if rec.get(k) not in (None, "")]
                    arm = "|".join(ac) if ac else "-"
                    b = rec.get("bytes")
                    if not (isinstance(b, str) and b and len(b) % 2 == 0 and HEXRE.match(b)):
                        b = None
                    else:
                        per_exp[exp]["recs_with_bytes"] += 1
                    key = (exp, ins, fld, arm, runid)
                    groups[key].append((canon(rec.get("value")), b))
                    gfiles[key].add(relpath)

    # ---- per-group counters + attribution ---------------------------------
    out_groups = []
    for key, recs in sorted(groups.items()):
        exp, ins, fld, arm, runid = key
        usable = [(v, b) for (v, b) in recs if b is not None]
        n_values_all = len({v for v, _ in recs})
        n_values = len({v for v, _ in usable})
        n_bytes = len({b for _, b in usable})
        lens = {len(b) // 2 for _, b in usable}

        g = {"exp": exp, "instr_raw": ins, "field_label": fld, "arm": arm, "run": runid,
             "n_records": len(recs), "n_usable": len(usable),
             "n_values_all_records": n_values_all,
             "n_values": n_values, "n_bytes": n_bytes,
             "bytes_lengths": sorted(lens),
             "files": sorted(gfiles[key]),
             "informative": n_values >= INFORMATIVE_MIN_VALUES,
             "degenerate_bytes_constant": (n_bytes == 1 and n_values >= INFORMATIVE_MIN_VALUES),
             "ratio": (n_bytes / n_values) if n_values else None,
             "attribution": "none", "attributed": [], "instr_db": None,
             "byte_offset": None}
        g["collapse"] = bool(g["informative"] and not g["degenerate_bytes_constant"]
                             and n_bytes < n_values)

        # ---- attribute to db fields ---------------------------------------
        mn = ins if ins in DB else None
        words = None
        nbytes = None
        if len(lens) == 1 and len(usable) >= 2:
            nbytes = lens.copy().pop()
            words = [int.from_bytes(bytes.fromhex(b), "little") for _, b in usable]
        if mn is None and words is not None:
            mn2, _ = CR.identify(words, nbytes, DB)
            if mn2:
                mn = mn2
                g["instr_rescued_to"] = mn2
        g["instr_db"] = mn
        if mn is not None:
            spec = DB[mn]
            if words is not None:
                d, nfit = CR.fit_offset(words, nbytes, spec)
                if nfit < max(1, len(words) // 2):
                    d = 0
                g["byte_offset"] = d
                L = spec["length"] or nbytes
                full = (1 << (8 * L)) - 1
                iws = [(w >> (8 * d)) & full for w in words]
                mi = 0
                for w in iws[1:]:
                    mi |= w ^ iws[0]
                targets = [(n, s, wd) for n, s, wd in spec["fields"]
                           if mi & (((1 << wd) - 1) << s)]
                if targets:
                    g["attribution"] = "bit-exact"
                    for n, s, wd in targets:
                        mask = (1 << wd) - 1
                        span = {(w >> s) & mask for w in iws}
                        g["attributed"].append({"field": n, "start": s, "width": wd,
                                                "n_span": len(span),
                                                "span_values": sorted(span)[:300]})
            if not g["attributed"]:
                names = CR.resolve_label(fld, spec)
                if names:
                    g["attribution"] = "label-level"
                    byname = {n: (s, wd) for n, s, wd in spec["fields"]}
                    for n in sorted(names):
                        s, wd = byname[n]
                        g["attributed"].append({"field": n, "start": s, "width": wd,
                                                "n_span": None, "span_values": []})
        out_groups.append(g)

    doc = {"_meta": {"generated_by": "EXP-0170/analysis/coverage_index.py",
                     "reuses": "experiments/EXP-0164-inert-audit/analysis/collect_raw.py",
                     "informative_min_values": INFORMATIVE_MIN_VALUES,
                     "parse_stats": dict(stats),
                     "per_exp": {e: dict(c) for e, c in sorted(per_exp.items())}},
           "groups": out_groups}
    os.makedirs(WORK, exist_ok=True)
    dst = os.path.join(WORK, "coverage_index.json.gz")
    with gzip.open(dst, "wt") as fh:
        json.dump(doc, fh, sort_keys=True)

    inf = [g for g in out_groups if g["informative"]]
    deg = [g for g in inf if g["degenerate_bytes_constant"]]
    col = [g for g in out_groups if g["collapse"]]
    print("raw lines parsed: %d   per-value field records: %d   unparseable: %d"
          % (stats["lines"], stats["field_recs"], stats["bad_lines"]))
    print("sweep groups: %d   informative (>=%d distinct values): %d"
          % (len(out_groups), INFORMATIVE_MIN_VALUES, len(inf)))
    print("  degenerate (bytes column constant): %d   -> NOT counted as collapse" % len(deg))
    print("  COLLAPSED (distinct bytes < distinct values): %d" % len(col))
    print("-> %s (%.1f MiB)" % (dst, os.path.getsize(dst) / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
