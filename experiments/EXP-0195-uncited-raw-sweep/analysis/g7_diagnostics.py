#!/usr/bin/env python3
"""EXP-0195 step 4: WHY does each surviving row stop at G7 -- evidence, or schema?

A gate that refuses a row because the harness spelled its prediction key differently
would be a false NO.  For every row that reached G7 on uncited evidence this prints,
per best carrier group:

  distinct oracles over ALL clean cases        (did the committed prediction vary at all?)
  distinct oracles over MATCHING cases         (adjudicate2's G7 number)
  is the oracle a FUNCTION of the encoded value (i.e. does it discriminate)?
  the same three numbers for every alternative prediction key the raw actually carries
  (`predict`, `predicts`, `expect_match`), so a schema-only NO is visible.

Nothing here promotes anything: a prediction that discriminated but did NOT match is a
REFUTATION of the model, not evidence for it.
"""
import json, os, collections, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.environ["E0195_RECORDS_IN"]
db = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "db.json")))
GEOM = {(i["mnemonic"], f["name"]): (f["start"], f["width"])
        for i in db["instructions"] for f in i.get("fields", [])}

# adjudicate2.py calls main() at import time, so its predicates cannot be imported without
# re-running the whole gate.  The VOLATILE / ERRISH / CLEAN_OUTCOMES / is_clean / strip / h
# definitions below are therefore transcribed from it UNCHANGED.  This script is a diagnostic,
# not a gate: it never issues a verdict, and its `n_matching` column is cross-checked against
# adjudicate2.py's own `n_matched` in verdicts_uncited_only.json (they agree on all 27 rows).
VOLATILE = {"gputime_ns", "t", "ts", "time", "elapsed", "duration", "seq", "idx", "wall", "ns",
            "us", "ms", "timestamp", "restarts", "attempt", "attempts", "foreign_retries",
            "innocent_retries"}
ERRISH = {"error", "errdom", "os_class", "fault_class", "fault_classes", "exception"}
CLEAN_OUTCOMES = {"ok", "silent_zero", "wrong_value", "exploratory"}


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in sorted(o.items()) if k not in VOLATILE}
    if isinstance(o, list):
        return [strip(x) for x in o]
    if isinstance(o, float):
        return repr(o)
    return o


def h(o):
    return hashlib.sha256(json.dumps(strip(o), sort_keys=True, default=str).encode()).hexdigest()[:12]


def is_clean(r):
    if r.get("outcome") not in CLEAN_OUTCOMES:
        return False
    if r.get("invalid_run") or r.get("victim") or r.get("sentinel_bad") or r.get("foreign"):
        return False
    if r.get("sentinel_ok") is False or r.get("poison_intact") is False:
        return False
    st = r.get("status")
    if st is not None and str(st).upper() not in ("OK", "TRUE", "1"):
        return False
    o = r.get("observed")
    if not isinstance(o, dict) or not o:
        return False
    if any(k in o and o[k] for k in ERRISH):
        return False
    ost = o.get("status")
    if ost is not None and str(ost).upper() not in ("OK", "TRUE", "1"):
        return False
    for a in (r.get("attempts") if isinstance(r.get("attempts"), list) else []):
        if isinstance(a, dict):
            if a.get("victim"):
                return False
            if a.get("status") is not None and str(a["status"]).upper() != "OK":
                return False
    return True


def encv(b, s, w):
    try:
        return (int.from_bytes(bytes.fromhex(b), "little") >> s) & ((1 << w) - 1)
    except ValueError:
        return None


verd = {(r["instr"], r["field"]): r for r in json.load(open(os.path.join(HERE, "verdicts_uncited_only.json")))}
want = {k for k, v in verd.items() if v["verdict"] in ("AMBIGUOUS", "DESK-PROMOTABLE")}
grp = {k: tuple(verd[k]["group"]["carrier"]) for k in want}

recs = collections.defaultdict(list)
for line in open(SRC):
    r = json.loads(line)
    k = (str(r.get("instr")), str(r.get("field")))
    if k in want and (r["__exp"], str(r.get("carrier", "")), str(r.get("arm", ""))) == grp[k]:
        recs[k].append(r)

PKEYS = ["oracle", "predict", "predicts"]
print("%-20s %-13s %-7s | %-30s | %-30s" % ("instr", "field", "verdict",
      "ALL-clean: key -> n_oracles/func?", "MATCHING: key -> n_oracles"))
rows = []
for k in sorted(want):
    s, w = GEOM[k]
    clean = [r for r in recs[k] if is_clean(r)]
    e = {id(r): encv(r["bytes"], s, w) for r in clean if isinstance(r.get("bytes"), str)}
    a_txt, m_txt, detail = [], [], {}
    for pk in PKEYS:
        have = [r for r in clean if pk in r and e.get(id(r)) is not None]
        if not have:
            continue
        allmap = collections.defaultdict(set)
        for r in have:
            allmap[e[id(r)]].add(h(r[pk]))
        n_all = len({x for v in allmap.values() for x in v})
        func = all(len(v) == 1 for v in allmap.values())
        disc_all = n_all >= 2 and len(allmap) >= 2
        mt = [r for r in have if r.get("match") is True]
        n_m = len({h(r[pk]) for r in mt})
        n_mv = len({e[id(r)] for r in mt})
        a_txt.append("%s->%d%s" % (pk, n_all, "/fn" if func else "/NOTfn"))
        m_txt.append("%s->%d(vals %d,n=%d)" % (pk, n_m, n_mv, len(mt)))
        detail[pk] = dict(n_oracles_all_clean=n_all, oracle_is_function_of_encoded_value=func,
                          discriminates_over_all_clean=disc_all, n_matching=len(mt),
                          n_distinct_oracles_matching=n_m, n_distinct_values_matching=n_mv,
                          G7_would_pass=bool(n_m >= 2 and n_mv >= 2))
    # EXP-0138-family flag: was the prediction PRE-REGISTERED, or the null hypothesis?
    em = [r for r in clean if r.get("expect_match") is True]
    detail["_pre_registered_expect_match_true_cases"] = len(em)
    detail["_n_clean"] = len(clean)
    print("%-20s %-13s %-7s | %-30s | %-30s" % (k[0], k[1], verd[k]["verdict"][:7],
          " ".join(a_txt)[:30], " ".join(m_txt)[:30]))
    rows.append(dict(instr=k[0], field=k[1], verdict=verd[k]["verdict"], group=list(grp[k]),
                     start=s, width=w, keys=detail))

json.dump(rows, open(os.path.join(HERE, "g7_diagnostics.json"), "w"), indent=1)
print()
sch = [r for r in rows if r["verdict"] == "AMBIGUOUS"
       and any(isinstance(v, dict) and v.get("G7_would_pass") for kk, v in r["keys"].items() if kk in PKEYS)]
print("AMBIGUOUS rows that WOULD pass G7 under some ALTERNATIVE prediction key: %d" % len(sch))
for r in sch:
    print("   %s.%s  %s" % (r["instr"], r["field"],
          {kk: v for kk, v in r["keys"].items() if kk in PKEYS and v.get("G7_would_pass")}))
disc = [r for r in rows if r["verdict"] == "AMBIGUOUS"
        and any(isinstance(v, dict) and v.get("discriminates_over_all_clean")
                and not v.get("G7_would_pass") for kk, v in r["keys"].items() if kk in PKEYS)]
print("\nAMBIGUOUS rows whose committed prediction DID vary with the value but never matched")
print("at two values (a refutation of the model, not evidence for it): %d" % len(disc))
for r in disc:
    print("   %s.%s" % (r["instr"], r["field"]))
