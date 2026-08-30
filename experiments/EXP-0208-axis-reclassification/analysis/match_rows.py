#!/usr/bin/env python3
"""EXP-0208 step 3 -- for every target row, gather EVERY raw group that could bear on it.

Target rows = validation.json field rows whose label is untested / corpus-correlation /
tokenization-only / single-template-inference.

Six lookups, so that "no raw" cannot be a filter artefact:
  L1 exact (instr, field)                 K1/K3
  L2 (instr, field) with a leading _ / __ or a _detect/_control/_ladder suffix   K4
  L3 (instr, field==null) whose byte_index / mut index lands inside the field's
     db.json byte span [start//8 .. (start+width-1)//8]                          K2
  L4 (instr, no field)                     K5   (framing / tokenization only)
  L5 non-jsonl STRUCTURAL (op, field) records
  L6 non-jsonl TEXTUAL co-occurrence of the mnemonic with this field name
"""
import json, os, sys, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))

TARGET = {"untested", "corpus-correlation", "tokenization-only", "single-template-inference"}
NULLF = "\x00NULL"; NOF = "\x00NOFIELD"

val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
GEOM = {}
for d in db["instructions"]:
    for f in d.get("fields", []) or []:
        GEOM[(d["mnemonic"], f["name"])] = (f.get("start"), f.get("width"), f.get("type"))

rows = []
for m, fields in val["instructions"].items():
    for f, rec in fields.items():
        if f.startswith("_") or not isinstance(rec, dict):
            continue
        if rec.get("label") in TARGET:
            rows.append((m, f, rec))

idx = collections.defaultdict(list)     # (instr, field) -> groups
idx_instr = collections.defaultdict(list)
for line in open(os.path.join(HERE, "raw_index_jsonl.jsonl")):
    g = json.loads(line)
    idx[(g["instr"], g["field"])].append(g)
    idx_instr[g["instr"]].append(g)

nj_struct = collections.defaultdict(list)
nj_text = collections.defaultdict(list)
for line in open(os.path.join(HERE, "raw_index_nonjsonl.jsonl")):
    r = json.loads(line)
    for s in r.get("struct", []):
        nj_struct[(s["op"], s["field"])].append(dict(file=r["file"], exp=r["exp"], n=s["n"],
                                                     path=s["path"], keys=s["keys"], is_raw=r["is_raw"]))
    for a, b, n in r.get("pairs", []):
        nj_text[(a, b)].append(dict(file=r["file"], exp=r["exp"], n=n, is_raw=r["is_raw"], ext=r["ext"]))

UNIONS = ("obs", "okobs", "orc", "values", "okvals", "faultvals", "hangvals", "abytes_h")

def sumgroups(gs):
    """UNION the distinct-payload sets across groups. Summing per-group counts (what
    EXP-0194's scanner did) reports `2 distinct observed payloads` for a field that was
    inert in BOTH of two runs -- the exact mistake this experiment exists to undo."""
    if not gs: return None
    o = collections.Counter(); mt = collections.Counter()
    tot = dict(n=0, semchecked=0, invalid=0, victim=0, sentinel_bad=0,
               falsifier=0, moved_true=0)
    U = {k: set() for k in UNIONS}
    exps = set(); files = set(); carriers = set(); arms = set(); keyings = set()
    percase_alias = []   # per-group (distinct requested values, distinct actual encodings)
    for g in gs:
        o.update(g["outcomes"]); mt.update(g["match"])
        for k in tot: tot[k] += g.get(k, 0)
        for k in UNIONS: U[k] |= set(g.get(k) or [])
        exps.add(g["exp"]); files.add(g["file"]); keyings.add(g["keying"])
        if g["carrier"]: carriers.add(g["carrier"])
        if g["arm"]: arms.add(g["arm"])
        percase_alias.append(dict(exp=g["exp"], file=g["file"], carrier=g["carrier"], arm=g["arm"],
                                  n=g["n"], nv=g.get("n_values", 0), nb=g.get("n_abytes", 0),
                                  nobs=g.get("n_obs", 0), nokobs=g.get("n_okobs", 0),
                                  norc=g.get("n_orc", 0), sem=g.get("semchecked", 0),
                                  nfault=g.get("n_faultvals", 0), nhang=g.get("n_hangvals", 0),
                                  out=g["outcomes"], keying=g["keying"]))
    r = dict(groups=len(gs), exps=sorted(exps), n_files=len(files),
             files=sorted(files)[:12], carriers=sorted(carriers)[:24],
             n_carriers=len(carriers), arms=sorted(arms)[:24], n_arms=len(arms),
             keyings=sorted(keyings), outcomes=dict(o), match=dict(mt),
             alias_per_group=percase_alias[:60], **tot)
    for k in UNIONS:
        r["u_" + k] = len(U[k])
    r["max_group_obs"] = max([p["nobs"] for p in percase_alias] or [0])
    r["max_group_okobs"] = max([p["nokobs"] for p in percase_alias] or [0])
    r["max_group_orc"] = max([p["norc"] for p in percase_alias] or [0])
    r["alias_groups"] = sum(1 for p in percase_alias if p["nv"] and p["nb"] and p["nb"] < p["nv"])
    r["values_list"] = sorted(U["values"], key=lambda x: (len(x), x))[:600]
    r["faultvals_list"] = sorted(U["faultvals"], key=lambda x: (len(x), x))[:600]
    r["hangvals_list"] = sorted(U["hangvals"], key=lambda x: (len(x), x))[:600]
    return r

out = {}
for m, f, rec in rows:
    start, width, ftype = GEOM.get((m, f), (None, None, None))
    b0 = b1 = None
    if start is not None and width:
        b0, b1 = start // 8, (start + width - 1) // 8
    L1 = idx.get((m, f), [])
    L2 = []
    for k, gs in idx.items():
        if k[0] != m: continue
        fk = k[1]
        if fk in (NULLF, NOF) or fk == f: continue
        if fk.lstrip("_") == f or fk.startswith(f + "_") or fk.endswith("_" + f):
            L2 += gs
    L3 = []
    if b0 is not None:
        for g in idx.get((m, NULLF), []):
            hits = [i for i in (g["fidx"] + g["mutidx"]) if b0 <= i <= b1]
            if hits:
                gg = dict(g); gg["span_hits"] = sorted(set(hits)); L3.append(gg)
    L4 = idx.get((m, NOF), [])
    L5 = nj_struct.get((m, f), [])
    L6 = nj_text.get((m, f), [])
    out[f"{m}.{f}"] = dict(
        mnemonic=m, field=f, label=rec.get("label"), range=rec.get("range"),
        target=rec.get("target"), evidence=rec.get("evidence") or [],
        note=(rec.get("note") or ""), has_axes=bool(rec.get("axes")),
        geom=dict(start=start, width=width, type=ftype, byte_lo=b0, byte_hi=b1),
        L1=sumgroups(L1), L2=sumgroups(L2), L3=sumgroups(L3), L4=sumgroups(L4),
        L3_span_hits=sorted({i for g in L3 for i in g["span_hits"]}),
        L5=L5[:20], L6=sorted(L6, key=lambda r: -r["n"])[:20])

json.dump(out, open(os.path.join(HERE, "row_evidence.json"), "w"), indent=1)
hits = collections.Counter()
for k, v in out.items():
    tags = tuple(l for l in ("L1", "L2", "L3", "L4") if v[l]) + \
           tuple(l for l in ("L5", "L6") if v[l])
    hits[tags] += 1
for k, n in hits.most_common(40):
    print(n, k)
print("rows:", len(out))
