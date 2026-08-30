#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0190 step 1 -- enumerate EVERY distinct `_`-prefixed `field` value in
experiments/*/raw/**/*.jsonl and gather the facts needed to classify each one
(PRE_REGISTRATION section 4).

This script does NOT classify.  It produces the inventory that classification is
done from, so that the classification is auditable against the same numbers.

READ-ONLY over experiments/*/raw/**.  Writes only work/underscore_census.json.

Usage: python3 analysis/census_underscore.py
"""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")
HEXRE = re.compile(r"^[0-9a-fA-F]+$")


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


def field_hits(words, nbytes, DB, mn):
    """Which db fields of descriptor `mn` do the varying bits of this group land in?
    Uses the same offset-fit as collect_raw.py.  Returns (fields, offset) or ([], None)."""
    spec = DB.get(mn)
    if spec is None or len(words) < 2:
        return [], None
    L = spec["length"] or nbytes
    best, bestn = 0, -1
    for d in range(0, max(1, nbytes - L + 1)):
        n = 0
        for w in words:
            iw = w >> (8 * d)
            if all(((iw >> s) & ((1 << wd) - 1)) == v for s, wd, v in spec["match"]):
                n += 1
        if n > bestn:
            best, bestn = d, n
    if spec["match"] and bestn < max(1, len(words) // 2):
        best = 0
    full = (1 << (8 * L)) - 1
    iws = [(w >> (8 * best)) & full for w in words]
    mi = 0
    for w in iws[1:]:
        mi |= w ^ iws[0]
    return [n for n, s, wd in spec["fields"] if mi & (((1 << wd) - 1) << s)], best


def main():
    DB = load_db()
    # name -> stats
    stat = collections.defaultdict(lambda: {
        "n_records": 0, "experiments": collections.Counter(), "instr": collections.Counter(),
        "runs": set(), "arms": set(), "outcomes": collections.Counter(),
        "n_with_bytes": 0, "distinct_values": set(), "sample": None,
        "keys_seen": collections.Counter(), "files": set()})
    # (name, exp, instr, arm, run) -> [bytes]
    grp = collections.defaultdict(list)

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
                runid = run if run != "." else os.path.splitext(fn)[0]
                path = os.path.join(dirpath, fn)
                for line in open(path, errors="replace"):
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
                    if not fld.startswith("_"):
                        continue
                    s = stat[fld]
                    s["n_records"] += 1
                    s["experiments"][exp] += 1
                    s["instr"][ins] += 1
                    s["runs"].add(exp + "/" + runid)
                    s["files"].add(os.path.relpath(path, EXPDIR))
                    for k in rec:
                        s["keys_seen"][k] += 1
                    ac = [str(rec[k]) for k in ("carrier", "arm")
                          if rec.get(k) not in (None, "")]
                    arm = "|".join(ac) if ac else "-"
                    s["arms"].add(arm)
                    s["outcomes"][str(rec.get("outcome"))] += 1
                    v = rec.get("value")
                    s["distinct_values"].add(
                        v if isinstance(v, (int, float, str, bool, type(None)))
                        else json.dumps(v, sort_keys=True))
                    b = rec.get("bytes")
                    if isinstance(b, str) and b and len(b) % 2 == 0 and HEXRE.match(b):
                        s["n_with_bytes"] += 1
                        grp[(fld, exp, ins, arm, runid)].append(b)
                    if s["sample"] is None:
                        s["sample"] = rec

    # structural test per name: does ANY group vary its bytes, and do the varying
    # bits land in db fields?
    struct = collections.defaultdict(lambda: {
        "n_groups": 0, "n_groups_bytes_vary": 0, "fields_hit": collections.Counter(),
        "descriptors": collections.Counter(), "max_group_size": 0,
        "example_group": None})
    for (fld, exp, ins, arm, run), hx in grp.items():
        st = struct[fld]
        st["n_groups"] += 1
        st["max_group_size"] = max(st["max_group_size"], len(hx))
        nb = {len(h) // 2 for h in hx}
        if len(hx) < 2 or len(nb) != 1:
            continue
        nbytes = nb.pop()
        words = [int.from_bytes(bytes.fromhex(h), "little") for h in hx]
        m = 0
        for w in words[1:]:
            m |= w ^ words[0]
        if m == 0:
            continue
        st["n_groups_bytes_vary"] += 1
        if ins in DB:
            st["descriptors"][ins] += 1
            fs, d = field_hits(words, nbytes, DB, ins)
            for f in fs:
                st["fields_hit"]["%s.%s" % (ins, f)] += 1
            if st["example_group"] is None and fs:
                st["example_group"] = {"experiment": exp, "instr": ins, "arm": arm,
                                       "run": run, "n": len(hx),
                                       "fields_hit": sorted(set(fs)),
                                       "byte_offset": d,
                                       "bytes_sample": sorted(set(hx))[:4]}
        else:
            st["descriptors"]["<not-in-db>:" + ins] += 1

    out = {}
    for fld, s in sorted(stat.items()):
        st = struct.get(fld, {})
        dv = s["distinct_values"]
        out[fld] = {
            "n_records": s["n_records"],
            "experiments": dict(s["experiments"].most_common()),
            "instr_labels": dict(s["instr"].most_common()),
            "n_runs": len(s["runs"]), "runs": sorted(s["runs"])[:12],
            "n_arms": len(s["arms"]), "arms": sorted(s["arms"])[:12],
            "outcomes": dict(s["outcomes"].most_common()),
            "n_with_bytes": s["n_with_bytes"],
            "n_distinct_values": len(dv),
            "distinct_values_sample": sorted((str(x) for x in dv))[:12],
            "record_keys": dict(s["keys_seen"].most_common()),
            "files_sample": sorted(s["files"])[:6],
            "n_groups": st.get("n_groups", 0),
            "n_groups_bytes_vary": st.get("n_groups_bytes_vary", 0),
            "descriptors": dict(st.get("descriptors", {})),
            "db_fields_hit": dict(st.get("fields_hit", collections.Counter()).most_common()),
            "example_group": st.get("example_group"),
            "sample_record": s["sample"],
        }
    os.makedirs(WORK, exist_ok=True)
    json.dump({"_meta": {"experiment": "EXP-0190-indexer-refilter",
                         "n_distinct_underscore_names": len(out),
                         "total_underscore_records": sum(v["n_records"] for v in out.values())},
               "names": out},
              open(os.path.join(WORK, "underscore_census.json"), "w"),
              indent=1, sort_keys=True)
    print("distinct `_` names: %d   records: %d"
          % (len(out), sum(v["n_records"] for v in out.values())))
    for k, v in sorted(out.items(), key=lambda kv: -kv[1]["n_records"]):
        print("  %-34s n=%-6d exps=%-28s vary=%d/%d  fields_hit=%s"
              % (k, v["n_records"], ",".join(list(v["experiments"])[:2]),
                 v["n_groups_bytes_vary"], v["n_groups"],
                 ",".join(list(v["db_fields_hit"])[:4]) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
