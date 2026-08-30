#!/usr/bin/env python3
"""EXP-0208 step 3b -- the four ADDITIONAL keyings found while auditing step 3, plus the
EXP-M4-14 root-evidence-json prose extractor.

Found by listing every raw `field` string that does NOT match a db.json field name for its
instruction (271 distinct such strings, 200k+ records).  Each is a real keying an exact
field-name index cannot see:

  L7  SIBLING DESCRIPTOR   raw carries instr=`ilogic`, the row lives under `b_alu10_loe` --
                           a different db.json descriptor in the same byte0 group with the
                           same (start,width).  Attribution is INFERRED, never direct.
  L8  COMPOSITE NAME       `op_lsb|op|per_lane|op_msb`, `lut_a+lut_b+op_base`,
                           `size+reg_sel`, `src_class+match[8:12]=4`, `cache@bytemate`
  L9  BYTE-POSITION NAME   `byte+12`, `byte3`, `byte+0` -> a byte index inside the span
  L10 RECORD-CARRIED SPAN  the record's own `start`/`width` overlap the row's bit range --
                           this is what recovers the LEGACY names (`fmt_word` 21,892
                           records, `dst_pair` 24,578) that db.json has since split/renamed.
  L11 M4-14 PROSE          experiments/EXP-M4-14-a18-splice/splice_results.json: per-field
                           `evidence` strings recording an A18 splice-and-observe sweep.
                           Real dispatched hardware observations, summary-level only.
"""
import json, os, re, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
NULLF = "\x00NULL"; NOF = "\x00NOFIELD"

db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
GEOM = {}; GROUP = {}; FIELDS = collections.defaultdict(dict)
for d in db["instructions"]:
    mt = tuple(tuple(x) for x in (d.get("match") or []))
    GROUP[d["mnemonic"]] = mt[0] if mt else None
    for f in d.get("fields", []) or []:
        GEOM[(d["mnemonic"], f["name"])] = (f.get("start"), f.get("width"))
        FIELDS[d["mnemonic"]][f["name"]] = (f.get("start"), f.get("width"))

MATCHANN = re.compile(r"match\[[0-9:]+\]\s*=\s*\w+")
BYTEPOS = re.compile(r"^(?:byte[+_]?|b)(\d+)(?:_?(?:hi|lo|hinib|lonib|bit\d+))?$")

def components(name):
    n = MATCHANN.sub("", name)
    n = n.split("@")[0]
    parts = re.split(r"[|+,/]", n)
    return [p.strip() for p in parts if p.strip()]

def byte_pos(name):
    m = BYTEPOS.match(name.strip())
    return int(m.group(1)) if m else None

TRACKED = set(l.strip() for l in open(os.path.join(HERE, "..", "work", "tracked_files.txt")))
groups = [g for g in (json.loads(l) for l in open(os.path.join(HERE, "..", "work", "raw_index_jsonl.jsonl"))) if g["file"] in TRACKED]
by_instr = collections.defaultdict(list)
for g in groups:
    by_instr[g["instr"]].append(g)

val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
TARGET = {"untested", "corpus-correlation", "tokenization-only", "single-template-inference"}
rows = [(m, f) for m, fs in val["instructions"].items() for f, r in fs.items()
        if not f.startswith("_") and isinstance(r, dict) and r.get("label") in TARGET]

# --- L11: EXP-M4-14 root evidence json ------------------------------------------------
M414 = {}
p = os.path.join(ROOT, "experiments/EXP-M4-14-a18-splice/splice_results.json")
if os.path.exists(p):
    for grp in json.load(open(p)):
        for r in grp.get("resolved", []) or []:
            op = r.get("op"); fld = (r.get("field") or "")
            base = fld.split(" ")[0]
            key = (op, base)
            ev = r.get("evidence")
            if isinstance(ev, list): ev = " ".join(map(str, ev))
            M414.setdefault(key, dict(op=op, field=fld, group=grp.get("group"),
                                      provenance=r.get("provenance"), evidence=ev,
                                      rename_from=r.get("rename_from"),
                                      start=r.get("start"), width=r.get("width"),
                                      enum=r.get("enum"), note=r.get("note")))

HEX = re.compile(r"0x[0-9a-fA-F]{1,2}\b")
ARROW = re.compile(r"->\s*([^;,()]{1,40})")   # `=>` introduces the AUTHOR'S CONCLUSION in
                                              # these records, not an observed outcome

def prose_stats(ev):
    """Parse an EXP-M4-14 `evidence` string WITHOUT substring traps.

    The first version of this function used `"hang" in text`, which matched the word
    `unchanged` and reported a GPU hang for a byte the record calls `fully inert`.
    Word boundaries everywhere, and liveness is decided by counting DISTINCT arrow
    targets rather than by keyword sentiment."""
    if not ev: return None
    vals = sorted({int(h, 16) for h in HEX.findall(ev)})
    targets = [t.split(".")[0].strip() if not re.match(r"^\s*[-+]?[0-9]*\.[0-9]", t) else t.strip()
               for t in ARROW.findall(ev)]
    targets = [t for t in targets if len(t.split()) <= 5]
    targets = [t for t in targets if t]
    norm = set()
    for t in targets:
        t2 = re.sub(r"\s+", " ", t.lower())
        t2 = re.sub(r"\(.*", "", t2).strip()
        if t2 in ("baseline", "base", "unchanged"): t2 = "<baseline>"
        norm.add(t2)
    return dict(
        distinct_hex_values_mentioned=len(vals), values=vals[:64],
        arrow_targets=sorted(norm)[:24], distinct_arrow_targets=len(norm),
        says_hang=bool(re.search(r"\bhangs?\b|\bhung\b|ErrorHang", ev, re.I)),
        says_fault=bool(re.search(r"\bfaults?\b|CMDBUF_ERROR|PageFault|ErrorPageFault", ev, re.I)),
        says_inert=bool(re.search(r"\bunchanged\b|\bno effect\b|\b(fully )?inert\b|"
                                  r"\ball\b[^.;]{0,40}(->|=>)", ev, re.I)),
        chars=len(ev))

out = {}
for m, f in rows:
    st, w = GEOM.get((m, f), (None, None))
    b0 = b1 = None
    if st is not None and w:
        b0, b1 = st // 8, (st + w - 1) // 8
    L7 = []; L8 = []; L9 = []; L10 = []
    for g in by_instr.get(m, []):
        fl = g["field"]
        if fl.startswith("\x00"):
            continue
        if fl == f:
            continue
        comps = components(fl)
        if f in comps and fl != f:
            L8.append(g); continue
        bp = byte_pos(fl)
        if bp is not None and b0 is not None and b0 <= bp <= b1:
            L9.append(g); continue
        # L9' the record's own byte index (`byte`, `byte_index`, ...) landing in the span
        if b0 is not None and g.get("fidx") and any(b0 <= i <= b1 for i in g["fidx"]):
            L9.append(g); continue
        # L12 name containment: legacy/split names (`dst_desc` -> `dst_desc_lo`)
        na, nb2 = re.sub(r"[^a-z0-9]", "", fl.lower()), re.sub(r"[^a-z0-9]", "", f.lower())
        if len(na) >= 3 and len(nb2) >= 3 and (na.startswith(nb2) or nb2.startswith(na)):
            L10.append(dict(g, why="name-containment")); continue
        if st is not None and w and g.get("fstart") and g.get("fwidth"):
            for s2 in g["fstart"]:
                for w2 in g["fwidth"]:
                    if s2 < st + w and st < s2 + w2:
                        L10.append(g); break
                else:
                    continue
                break
    if st is not None and w and GROUP.get(m):
        for m2, gm in GROUP.items():
            if m2 == m or gm != GROUP[m]:
                continue
            for f2, (s2, w2) in FIELDS[m2].items():
                if s2 == st and w2 == w:
                    for g in by_instr.get(m2, []):
                        if g["field"] == f2:
                            L7.append(dict(g, sibling_mnemonic=m2, sibling_field=f2))
    ent = dict(mnemonic=m, field=f, geom=dict(start=st, width=w, byte_lo=b0, byte_hi=b1))
    for nm, L in (("L7", L7), ("L8", L8), ("L9", L9), ("L10", L10)):
        if L:
            ent[nm] = dict(groups=len(L), n=sum(g["n"] for g in L),
                           exps=sorted({g["exp"] for g in L}),
                           fields=sorted({g["field"] for g in L})[:12],
                           siblings=sorted({g.get("sibling_mnemonic", "") for g in L}) if nm == "L7" else None,
                           files=sorted({g["file"] for g in L})[:8],
                           u_okobs_max=max(g.get("n_okobs", 0) for g in L),
                           u_validobs_max=max(g.get("n_validobs", 0) for g in L),
                           u_obs_max=max(g.get("n_obs", 0) for g in L),
                           nv_max=max(g.get("n_values", 0) for g in L),
                           nb_max=max(g.get("n_abytes", 0) for g in L),
                           sem=sum(g.get("semchecked", 0) for g in L),
                           outcomes=dict(sum((collections.Counter(g["outcomes"]) for g in L),
                                             collections.Counter())))
    mk = M414.get((m, f))
    if not mk:
        for (op, base), v in M414.items():
            if op == m and (v.get("rename_from") or "").startswith(f):
                mk = v; break
    if mk:
        ent["L11"] = dict(mk, stats=prose_stats(mk.get("evidence")))
    if len(ent) > 3:
        out[f"{m}.{f}"] = ent

json.dump(out, open(os.path.join(HERE, "row_evidence_extra.json"), "w"), indent=1)
c = collections.Counter()
for k, v in out.items():
    c[tuple(sorted(set(v) & {"L7", "L8", "L9", "L10", "L11"}))] += 1
for k, n in c.most_common(30): print(n, k)
print("rows with extra evidence:", len(out))
