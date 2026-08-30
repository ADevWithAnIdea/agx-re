#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0164 step 1 -- index every per-value raw sweep record in the repository and
attribute it to the db.json FIELDS it actually varied.

READ-ONLY over experiments/*/raw/**.  Writes only work/raw_index.json.gz.

Why this is not a simple name match (PRE_REGISTRATION amendment A2/A3): the raw
records label a case by the *thing the harness spliced*, which is very often a whole
BYTE (`byte+12`, `b6`, `byte0_lonib`) or a composite (`op_lsb|op|per_lane|op_msb`),
while validation.json labels db.json FIELDS.  A pure name match would report
`tile_read.read_en` as having no raw record when in fact EXP-0147 swept all 256
values of the byte that contains it.  Worse, the reverse error is live too: a group
labelled with ONE field name frequently varies a whole byte, so movement credited to
that field may have been produced by a different field sharing the byte.

So attribution is done from the bytes themselves:

  * the varying bit mask of a case group is computed from its `bytes` column;
  * the instruction's byte offset inside `bytes` is recovered by fitting db.json's
    own `match` constraints (EXP-0154's carriers embed the instruction in a 20-byte
    window, so this cannot be assumed to be zero);
  * for db field G the records are partitioned by "the whole instruction word with
    G's bits cleared"; only partitions containing >= 2 distinct G values test G at
    all, and movement is counted WITHIN a partition.  That is the only way to say
    "G is live" rather than "some bit of that byte is live".

Groups whose `bytes` column is missing/constant fall back to label-level
attribution and are marked so.

Usage:  python3 analysis/collect_raw.py
"""
import argparse, collections, gzip, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")
# EXP-0170 D.4: attribution must match EXP-0164's, so read ITS pinned db snapshot.
WORK = os.path.join(EXPDIR, "EXP-0164-inert-audit", "work")

HARD = {"fault", "hang", "undecodable", "killed", "not_written",
        "no_draw", "lost_7_of_8", "nondeterministic"}
CONTAM = {"invalid_run", "victim", "skipped"}

# ===================== EXP-0170 AMENDMENT D.2 (the ONLY behavioural change) ====
# A record is a PLACEHOLDER when no dispatch ever happened, so it carries no
# observation and must not contribute a signature.  Structural markers only --
# none of these names an experiment, a run, or a field.  `outcome == "hang"` is
# deliberately NOT a marker: a genuine hang is a real hardware observation, and
# the rule must stay conservative in the direction of KEEPING records.
PLACEHOLDER_STATUS = {"SKIPPED", "NOT_RUN"}
PLACEHOLDER_OUTCOME = {"skipped", "not_run", "not_written"}


def is_placeholder(rec):
    v = rec.get("validity")
    if isinstance(v, str):
        vl = v.strip().lower()
        if vl.startswith("skip") or vl == "not_run":
            return True                                     # P1
    st = rec.get("status")
    if isinstance(st, str) and st.strip().upper() in PLACEHOLDER_STATUS:
        return True                                         # P2
    at = rec.get("attempts")
    if isinstance(at, list) and len(at) == 0 and rec.get("observed") is None:
        return True                                         # P3
    if "skip_reason" in rec:
        return True                                         # P4
    if rec.get("outcome") in PLACEHOLDER_OUTCOME:
        return True                                         # P5
    return False
# ==============================================================================
HEXRE = re.compile(r"^[0-9a-fA-F]+$")
BYTELABEL = re.compile(r"^b(?:yte)?[_+]?(\d+)(_lonib|_hinib)?$", re.I)
STRIPEQ = re.compile(r"(match)?\[\d+:\d+\]=?\w*")


def sig_of(rec):
    oc = rec.get("outcome")
    hard = oc if oc in HARD else "run"
    obs = rec.get("observed")
    d = "-" if obs is None else hashlib.sha1(
        json.dumps(obs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:10]
    return hard + "|" + d


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


def fit_offset(words, nbytes, spec):
    """Recover the instruction's byte offset inside the `bytes` column by fitting
    db.json's own match constraints.  Returns (byte_offset, n_fitting_records)."""
    if not spec["match"]:
        return 0, len(words)
    L = spec["length"] or nbytes
    best = (None, -1)
    for d in range(0, max(1, nbytes - L + 1)):
        n = 0
        for w in words:
            iw = w >> (8 * d)
            if all(((iw >> s) & ((1 << wd) - 1)) == v for s, wd, v in spec["match"]):
                n += 1
        if n > best[1]:
            best = (d, n)
    return best[0] or 0, best[1]


def identify(words, nbytes, DB):
    """Rescue path: the raw `instr` label is not a db.json mnemonic (EXP-0140 logs
    the whole reg-move family as `regmove`).  Identify the descriptor from the bytes
    by fitting db.json's own match constraints, preferring the descriptor that
    constrains the most bits.  Ambiguous fits are left unresolved, never guessed."""
    best = []
    for m, spec in DB.items():
        L = spec["length"] or nbytes
        if not spec["match"] or L > nbytes:
            continue
        bits = sum(w for _, w, _ in spec["match"])
        for d in range(0, nbytes - L + 1):
            n = 0
            for w in words:
                iw = w >> (8 * d)
                if all(((iw >> s) & ((1 << wd) - 1)) == v for s, wd, v in spec["match"]):
                    n += 1
            if n >= max(1, len(words) // 2):
                best.append((bits, m, d, n))
    if not best:
        return None, None
    top = max(b[0] for b in best)
    cand = {(m, d) for b, m, d, n in best if b == top}
    if len({m for m, _ in cand}) != 1:
        return None, None
    m, d = sorted(cand)[0]
    return m, d


def resolve_label(label, spec):
    """Label -> set of db field names it names or covers (fallback path only)."""
    names = {n for n, _, _ in spec["fields"]}
    if label in names:
        return {label}
    out = set()
    for tok in re.split(r"[|+]", label):
        tok = STRIPEQ.sub("", tok).strip()
        if tok in names:
            out.add(tok)
            continue
        m = BYTELABEL.match(tok)
        if m:
            b = int(m.group(1))
            lo, hi = 8 * b, 8 * b + 8
            if m.group(2) == "_lonib":
                hi = lo + 4
            elif m.group(2) == "_hinib":
                lo = lo + 4
            for n, s, w in spec["fields"]:
                if s < hi and s + w > lo:
                    out.add(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()
    DB = load_db()

    # (exp, instr, label, arm, run) -> [ (value, bytes_hex, sig, contam) ]
    groups = collections.defaultdict(list)
    pseudo = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(set)))
    parse = {}
    partial = set()

    exps = sorted(d for d in os.listdir(EXPDIR)
                  if os.path.isdir(os.path.join(EXPDIR, d, "raw")))
    for exp in exps:
        raw = os.path.join(EXPDIR, exp, "raw")
        st = parse.setdefault(exp, {"files": 0, "jsonl_files": 0, "lines": 0,
                                    "bad_lines": 0, "field_recs": 0})
        for dirpath, _, filenames in os.walk(raw):
            rel = os.path.relpath(dirpath, raw)
            run = "." if rel == "." else rel.split(os.sep)[0]
            if "PARTIAL.md" in filenames:
                partial.add(exp + "/" + run)
            for fn in filenames:
                st["files"] += 1
                if not fn.endswith(".jsonl"):
                    continue
                st["jsonl_files"] += 1
                runid = run if run != "." else os.path.splitext(fn)[0]
                for line in open(os.path.join(dirpath, fn), errors="replace"):
                    line = line.strip()
                    if not line:
                        continue
                    st["lines"] += 1
                    try:
                        rec = json.loads(line)
                    except Exception:
                        st["bad_lines"] += 1
                        continue
                    if not isinstance(rec, dict):
                        st["bad_lines"] += 1
                        continue
                    fld, ins = rec.get("field"), rec.get("instr")
                    if not (isinstance(fld, str) and isinstance(ins, str)):
                        continue
                    # PRE_REGISTRATION amendment A5: the arm key is the PAIR
                    # (carrier, arm) where both exist.  EXP-0140/0156 put the shader
                    # in `carrier` and the occurrence in `arm`; keying on `carrier`
                    # alone would collapse structurally different occurrences into
                    # one arm and manufacture INERT-SINGLE verdicts.
                    ac = [str(rec[k]) for k in ("carrier", "arm")
                          if rec.get(k) not in (None, "")]
                    arm = "|".join(ac) if ac else "-"
                    if fld.startswith("_"):
                        pseudo[exp][arm][runid].add(sig_of(rec))
                        continue
                    st["field_recs"] += 1
                    b = rec.get("bytes")
                    if not (isinstance(b, str) and b and len(b) % 2 == 0 and HEXRE.match(b)):
                        b = None
                    ph = is_placeholder(rec)                       # EXP-0170 D.2
                    cont = ph or rec.get("outcome") in CONTAM or "skip_reason" in rec
                    groups[(exp, ins, fld, arm, runid)].append(
                        (rec.get("value"), b, sig_of(rec), cont, ph))

    # ---- attribute each group to db fields --------------------------------
    # (exp, instr, field, arm, run) -> {key: Counter(sig)}  + bookkeeping
    cell = collections.defaultdict(lambda: {"obs": collections.defaultdict(collections.Counter),
                                            "attr": set(), "n_cases": 0, "n_contam": 0, "n_ph": 0,
                                            "labels": set(), "offsets": set()})
    unresolved = collections.Counter()
    ident_cache = {}
    seen_mn = collections.defaultdict(set)      # exp -> db mnemonics the raw touched

    def touched(words, nbytes):
        """Every db descriptor whose own match constraints are satisfied by at least
        one word of this group, at any legal offset.  Used to tell 'the raw never
        touched this instruction' from 'the raw swept it but not attributably'."""
        out = set()
        for m, sp in DB.items():
            L = sp["length"] or nbytes
            if not sp["match"] or L > nbytes:
                continue
            for d in range(0, nbytes - L + 1):
                for w in words:
                    iw = w >> (8 * d)
                    if all(((iw >> s) & ((1 << wd) - 1)) == v for s, wd, v in sp["match"]):
                        out.add(m)
                        break
                if m in out:
                    break
        return out

    for (exp, ins, label, arm, run), recs in groups.items():
        if ins in DB:
            seen_mn[exp].add(ins)
        n_contam = sum(1 for r in recs if r[3])
        n_ph = sum(1 for r in recs if r[4])            # EXP-0170 D.2
        live = [r for r in recs if not r[3]]
        if label in ("-", ""):
            unresolved[(exp, ins, label, "not-a-field-label")] += len(recs)
            continue
        raw_ins = ins
        spec = DB.get(ins)
        if spec is None:
            hx = [r[1] for r in live if r[1]]
            nb = {len(h) // 2 for h in hx}
            # identification is per GROUP, never cached across groups: EXP-0140
            # sweeps the descriptor-selecting byte itself, so two groups on the same
            # carrier are two different descriptors.
            if len(hx) >= 2 and len(nb) == 1:
                ins2, _ = identify([int.from_bytes(bytes.fromhex(h), "little") for h in hx],
                                   nb.pop(), DB)
            else:
                ins2 = None
            if ins2 is None:
                unresolved[(exp, ins, label, "instr-not-in-db")] += len(recs)
                if len(hx) >= 1 and len({len(h) // 2 for h in hx}) == 1:
                    nb2 = len(hx[0]) // 2
                    seen_mn[exp] |= touched(
                        [int.from_bytes(bytes.fromhex(h), "little") for h in hx], nb2)
                continue
            seen_mn[exp].add(ins2)
            ins, spec = ins2, DB[ins2]
        hexed = [r for r in live if r[1]]
        nb = {len(r[1]) // 2 for r in hexed}
        use_bytes = len(hexed) >= 2 and len(nb) == 1
        targets = None
        if use_bytes:
            nbytes = nb.pop()
            words = [int.from_bytes(bytes.fromhex(r[1]), "little") for r in hexed]
            m = 0
            for w in words[1:]:
                m |= w ^ words[0]
            if m == 0:
                use_bytes = False
            else:
                d, nfit = fit_offset(words, nbytes, spec)
                if nfit < max(1, len(words) // 2):
                    d = 0
                L = spec["length"] or nbytes
                full = (1 << (8 * L)) - 1
                iws = [(w >> (8 * d)) & full for w in words]
                mi = 0
                for w in iws[1:]:
                    mi |= w ^ iws[0]
                targets = [(n, s, wd) for n, s, wd in spec["fields"]
                           if mi & (((1 << wd) - 1) << s)]
                for n, s, wd in targets:
                    mask = ((1 << wd) - 1) << s
                    c = cell[(exp, ins, n, arm, run)]
                    c["attr"].add("bit-exact")
                    c["labels"].add(label if raw_ins == ins else "%s/%s" % (raw_ins, label))
                    c["offsets"].add(d)
                    c["n_cases"] += len(recs)
                    c["n_contam"] += n_contam
                    c["n_ph"] += n_ph
                    for (r, w) in zip(hexed, iws):
                        c["obs"]["%x:%x" % (w & ~mask, (w & mask) >> s)][r[2]] += 1
        if not use_bytes:
            names = resolve_label(label, spec)
            if not names:
                unresolved[(exp, ins, label, "label-unresolved")] += len(recs)
                continue
            for n in names:
                c = cell[(exp, ins, n, arm, run)]
                c["attr"].add("label-level")
                c["labels"].add(label if raw_ins == ins else "%s/%s" % (raw_ins, label))
                c["n_cases"] += len(recs)
                c["n_contam"] += n_contam
                c["n_ph"] += n_ph
                for r in live:
                    v = r[0] if isinstance(r[0], (int, str)) else json.dumps(r[0], sort_keys=True)
                    c["obs"]["~:%s" % v][r[2]] += 1

    # ---- reduce -----------------------------------------------------------
    index = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(dict)))
    for (exp, ins, fld, arm, run), c in cell.items():
        # keep one modal signature per (rest, fieldvalue) key  (amendment A1)
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
            "n_cases": c["n_cases"], "n_contam": c["n_contam"],
            "n_placeholder": c["n_ph"],
            "n_values": len(vals), "moved": moved,
            "n_within_run_unstable": nwru,
            "attribution": sorted(c["attr"]),
            "labels": sorted(c["labels"]),
            "byte_offsets": sorted(c["offsets"]),
            "keys": {k: s for k, s in keys.items() if k.split(":", 1)[0] in
                     {r for r, f in byrest.items() if len(f) >= 2}},
        }

    out = {"_meta": {"generated_by": "EXP-0170/work/collect_raw_D.py = EXP-0164 collect_raw.py + AMENDMENT D.2",
                     "hard_classes": sorted(HARD),
                     "contaminated_outcomes": sorted(CONTAM),
                     "exp0170_placeholder_rule": "D.2 markers P1-P5; outcome==hang is NOT a marker",
                     "partial_runs": sorted(partial),
                     "unresolved_groups": sorted(
                         ["%s|%s|%s|%s|%d" % (a, b, c_, d, n)
                          for (a, b, c_, d), n in unresolved.most_common()]),
                     "mnemonics_seen_per_exp": {e: sorted(v) for e, v in
                                                sorted(seen_mn.items())}},
           "parse": parse,
           "index": {e: {k: dict(v) for k, v in ks.items()} for e, ks in index.items()},
           "pseudo": {e: {a: {r: sorted(s) for r, s in rs.items()}
                          for a, rs in arms.items()} for e, arms in pseudo.items()}}
    os.makedirs(WORK, exist_ok=True)
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_index_D.json.gz")
    with gzip.open(dst, "wt") as fh:
        json.dump(out, fh, sort_keys=True)
    if not args.quiet:
        print("groups: %d   cells: %d   -> %s (%.1f MiB)"
              % (len(groups), len(cell), dst, os.path.getsize(dst) / 1048576.0))
        print("unresolved groups:", sum(unresolved.values()),
              "in", len(unresolved), "kinds")
        bad = {e: p["bad_lines"] for e, p in parse.items() if p["bad_lines"]}
        print("unparseable lines:", bad or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
