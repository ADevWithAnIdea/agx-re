#!/usr/bin/env python3
"""EXP-0166 — re-derive EXP-0146's 94 field verdicts from its own raw evidence.

Offline only. Reads EXP-0146's append-only JSONL captures plus pinned snapshots of
tools/agx-isa/{db,validation}.json, and writes this experiment's analysis/*.json.
Never touches the device. Never writes db.json, validation.json, docs/, PROVENANCE.md
or work/merge_verdicts.py.

Policy is frozen in ../PRE_REGISTRATION.md §4 and amendments A1-A4. The thresholds are
constants below and are quoted verbatim from §4.4; nothing here is tuned to the answer.

  python3 analysis/adjudicate.py
"""
import hashlib
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXPDIR))
SRC = os.path.join(ROOT, "experiments", "EXP-0146-m4-emit-int-misc")

# EXP-0165 owns tools/agx-isa/db.json this session and edits it live, so the adjudication runs
# against pinned snapshots taken at M2. The live files are still hashed and drift is reported.
DB = os.path.join(EXPDIR, "work", "db_snapshot.json")
VAL = os.path.join(EXPDIR, "work", "validation_snapshot.json")
DB_LIVE = os.path.join(ROOT, "tools", "agx-isa", "db.json")
VAL_LIVE = os.path.join(ROOT, "tools", "agx-isa", "validation.json")

# ------------------------------------------------------------------ frozen policy constants
AGREEMENT_MIN = 0.99            # §4.4
MOVEMENT_OVER_DISAGREE = 2.0    # §4.4   M >= 2*D
GATED_RUNS = ("run01", "run03") # §4.1   run02 contaminated, excluded
# §4.6 G4. The dispatch asks for `target: M4/G16G`, but tools/agx-isa/validate_labels.py
# accepts only ("M4","G16G","A18","G17P","M4+A18","G16G+G17P") and hard-fails anything else,
# so the schema-legal spelling of the same fact is used. M4 == G16G by that file's own comment.
TARGET = "M4"
EVIDENCE = ["EXP-0146", "EXP-0166"]

FROZEN = {
    "raw/run01/sweep.jsonl": "a55a574bdc4ec51f3c455c0b820bf807ff94ea7fd155c65a8e329061415f98f3",
    "raw/run03/sweep.jsonl": "47357d772da1e407ababff2b919128f3a13f9a5683aba6769683ead77b012e2a",
    "raw/run04/sweep.jsonl": "c72794bbcf357c20ae29e4a7dcf6237d45182559580aa4bd4e8d67925f46f0c8",
    "analysis/field_verdicts.json": "5dff397b31146a6e9ea944eb59ae8f47d3253ac06e16f9a9a9f5fe04267cb825",
}
DB_SHA_PINNED = "addf5edaf29cc218954af6fbdc277a4c0dd827267c177bbd8af6a57e90f71b8f"
DB_SHA_AT_PREREG = "83b83a350ece33b8fd9e98b773f02be2da89a5f942824896574ff22827042341"

# AMENDMENT A1 — db.json fields wider than a byte that EXP-0146 swept byte-wise.
COMPOSITES = {
    ("irotate", "operands"): [3, 4, 5, 6, 7],
    ("irotate", "tail"): [8, 9, 10, 11],
    ("n2_op8", "body"): [3, 4, 5, 6, 7],
    ("n2_op10", "immword"): [4, 5, 6, 7, 8, 9],
}

# §4.6 G3 vetoes live in verdicts.py (VETO_TEXT), applied after the statistics so a veto never
# changes a number -- only whether a row merges.
VETOES = {}

LABELS = ["hardware-run", "isolated-byte-diff", "corpus-correlation", "tokenization-only",
          "single-template-inference", "api-accept-reject", "host-private", "untested"]
STRENGTH = {l: i for i, l in enumerate(LABELS)}
EMIT_OK = {"hardware-run", "isolated-byte-diff"}


# ------------------------------------------------------------------ helpers
def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_jsonl(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def observable(rec):
    obs = rec.get("observed") or {}
    return (rec.get("outcome"), tuple(obs.get("words") or []))


def informative(rec):
    return ((rec.get("observed") or {}).get("fault_class") != "innocent_victim")


def inert_A3(rec):
    """AMENDMENT A3 — reproduces the host-computed oracle."""
    return bool(rec.get("match")) and rec.get("outcome") == "ok"


def getbits(b, start, width):
    v = 0
    for i in range(width):
        bit = start + i
        byi, bii = bit // 8, bit % 8
        if byi >= len(b):
            return None
        v |= ((b[byi] >> bii) & 1) << i
    return v


def locate(cases, width, nbytes):
    """AMENDMENT A2 — the bit range at which the recorded bytes reproduce the recorded values."""
    hits = []
    for start in range(0, nbytes * 8 - width + 1):
        if all(getbits(bytes.fromhex(hx), start, width) == val for val, hx in cases):
            hits.append(start)
    return hits


def changed_span(cases):
    base = bytes.fromhex(min(cases)[1])
    diff = set()
    for _, hx in cases:
        b = bytes.fromhex(hx)
        for i in range(min(len(b), len(base))):
            x = b[i] ^ base[i]
            for k in range(8):
                if (x >> k) & 1:
                    diff.add(i * 8 + k)
    return sorted(diff)


def match_mask(instr):
    """Bit mask (as an int over the whole instruction) that db.json's `match` list pins."""
    mask = 0
    for start, width, _val in instr.get("match", []):
        mask |= ((1 << width) - 1) << start
    return mask


# ------------------------------------------------------------------ main
def main():
    out = []

    def say(s=""):
        print(s)
        out.append(s)

    # ---- input integrity -------------------------------------------------
    drift = []
    for rel, want in FROZEN.items():
        got = sha(os.path.join(SRC, rel))
        if got != want:
            drift.append("%s: frozen %s got %s" % (rel, want[:12], got[:12]))
    db_sha, live_sha = sha(DB), sha(DB_LIVE)
    if db_sha != DB_SHA_PINNED:
        drift.append("work/db_snapshot.json ALTERED: pinned %s got %s" % (DB_SHA_PINNED[:12], db_sha[:12]))
    if live_sha != db_sha:
        drift.append("tools/agx-isa/db.json moved on: snapshot %s vs live %s (EXP-0165 owns it)"
                     % (db_sha[:12], live_sha[:12]))
    if sha(VAL_LIVE) != sha(VAL):
        drift.append("tools/agx-isa/validation.json moved on since the M2 snapshot")
    if drift:
        say("INPUT DRIFT (reported, not patched):")
        for d in drift:
            say("  ! " + d)
        say()

    db = json.load(open(DB))
    val = json.load(open(VAL))
    dbi = {i["mnemonic"]: i for i in db["instructions"]}
    dbf = {m: {f["name"]: (f["start"], f["width"]) for f in i.get("fields", [])}
           for m, i in dbi.items()}

    runs = {r: load_jsonl(os.path.join(SRC, "raw", r, "sweep.jsonl")) for r in GATED_RUNS}
    adj = load_jsonl(os.path.join(SRC, "raw", "run04", "sweep.jsonl"))

    baseline = {r: {} for r in GATED_RUNS}
    cases = {r: defaultdict(dict) for r in GATED_RUNS}
    for r, recs in runs.items():
        for rec in recs:
            ins, fld, car = rec.get("instr"), rec.get("field"), rec.get("carrier")
            if ins in ("_meta", "_i64"):
                continue
            if fld == "_baseline":
                baseline[r][(ins, car)] = rec
                continue
            if fld.startswith("_") or fld == "lut_a+lut_b+op_base":
                continue
            v = rec.get("value")
            if isinstance(v, (list, dict)):
                continue
            cases[r][(ins, fld, car)][v] = rec

    adjmap = defaultdict(dict)
    for rec in adj:
        ins, fld, car = rec.get("instr"), rec.get("field"), rec.get("carrier")
        v = rec.get("value")
        if ins == "_meta" or (fld or "").startswith("_") or isinstance(v, (list, dict)):
            continue
        adjmap[(ins, fld, car)][v] = rec

    # sanity: A3's claim that match <=> outcome=="ok"
    for r, recs in runs.items():
        bad = [x for x in recs if bool(x.get("match")) != (x.get("outcome") == "ok")]
        if bad:
            say("!! A3 SANITY FAILED in %s: %d records where match != (outcome=='ok')" % (r, len(bad)))

    # baseline-record integrity (the reason A3 exists)
    flaked = []
    for r in GATED_RUNS:
        for (ins, car), rec in baseline[r].items():
            if not inert_A3(rec):
                flaked.append({"run": r, "instr": ins, "carrier": car, "outcome": rec["outcome"]})

    # ---- per-arm statistics ---------------------------------------------
    stats = {}
    for key in sorted(set(cases[GATED_RUNS[0]]) & set(cases[GATED_RUNS[1]])):
        ins, fld, car = key
        c1, c3 = cases[GATED_RUNS[0]][key], cases[GATED_RUNS[1]][key]
        vals = sorted(set(c1) & set(c3))

        N = D = M = I = 0
        Nl = Dl = Ml = Il = 0
        victim = 0
        moved_vals, inert_vals, dis_vals = [], [], []
        b1 = baseline[GATED_RUNS[0]].get((ins, car))
        b3 = baseline[GATED_RUNS[1]].get((ins, car))
        ob1, ob3 = (observable(b1) if b1 else None), (observable(b3) if b3 else None)

        for v in vals:
            r1, r3 = c1[v], c3[v]
            if not (informative(r1) and informative(r3)):
                victim += 1
                continue
            o1, o3 = observable(r1), observable(r3)
            # --- A3 primary
            N += 1
            if o1 != o3:
                D += 1
                dis_vals.append(v)
            elif inert_A3(r1) and inert_A3(r3):
                I += 1
                inert_vals.append(v)
            else:
                M += 1
                moved_vals.append(v)
            # --- literal §4.2 secondary
            Nl += 1
            if o1 != o3:
                Dl += 1
            elif o1 != ob1 and o3 != ob3:
                Ml += 1
            elif o1 == ob1 and o3 == ob3:
                Il += 1
            else:
                Dl += 1

        def verdict_of(M_, I_, D_, N_):
            if N_ == 0:
                return "withheld", 0.0
            a = (M_ + I_) / N_
            if M_ >= 1 and a >= AGREEMENT_MIN and M_ >= MOVEMENT_OVER_DISAGREE * D_:
                return "stable-live", a
            if M_ == 0 and a >= AGREEMENT_MIN:
                return "inert-single-carrier", a
            return "withheld", a

        verdict, agree = verdict_of(M, I, D, N)
        verdict_lit, agree_lit = verdict_of(Ml, Il, Dl, Nl)

        # --- A4: real coverage = distinct spliced encodings
        pairs = [(v, c3[v]["bytes"]) for v in vals if c3[v].get("bytes")]
        distinct = sorted({hx for _, hx in pairs})
        width = max(1, max(vals).bit_length()) if vals else 0
        nbytes = len(bytes.fromhex(pairs[0][1])) if pairs else 0
        if fld.startswith("byte+"):
            located = [int(fld.split("+")[1]) * 8]
            width = 8
        else:
            located = locate(pairs, width, nbytes) if pairs else []
        span = changed_span(pairs) if pairs else []

        # which db.json field (if any) occupies exactly the swept bits
        db_field = None
        if located:
            for name, (s, w) in dbf.get(ins, {}).items():
                if s == located[0] and w == width:
                    db_field = name
                    break
        mm = match_mask(dbi[ins]) if ins in dbi else 0
        overlap = 0
        if span:
            fieldmask = 0
            for b in range(span[0], span[-1] + 1):
                fieldmask |= 1 << b
            overlap = mm & fieldmask

        # run04 adjudication of the disagreeing values (classification only, §4.1)
        a4 = adjmap.get(key, {})
        adjud = {}
        for v in dis_vals:
            rec = a4.get(v)
            if rec:
                adjud[str(v)] = {"majority": (rec["observed"] or {}).get("majority"),
                                 "stable": (rec["observed"] or {}).get("stable"),
                                 "n_informative": (rec["observed"] or {}).get("n_informative")}

        oc = defaultdict(int)
        for v in vals:
            if informative(c3[v]):
                oc[c3[v]["outcome"]] += 1

        stats["%s.%s@%s" % (ins, fld, car)] = {
            "instr": ins, "field": fld, "carrier": car,
            "N_A3": N, "D_A3": D, "M_A3": M, "I_A3": I,
            "agreement_A3": round(agree, 5), "verdict_A3": verdict,
            "N_lit": Nl, "D_lit": Dl, "M_lit": Ml, "I_lit": Il,
            "agreement_lit": round(agree_lit, 5), "verdict_lit": verdict_lit,
            "victim_skipped": victim,
            "values_dispatched": len(vals),
            "distinct_encodings": len(distinct),
            "dense": len(distinct) == (1 << width),
            "swept_width": width,
            "located_start": located[0] if located else None,
            "located_ambiguous": len(located) > 1,
            "changed_bit_span": [span[0], span[-1]] if span else [],
            "db_field_at_swept_bits": db_field,
            "match_overlap_mask": hex(overlap) if overlap else None,
            "outcomes_run03": dict(oc),
            "inert_values": inert_vals,
            "moved_count": len(moved_vals),
            "disagree_values": dis_vals,
            "run04_adjudication": adjud,
        }

    json.dump({"baseline_flakes": flaked, "arms": stats},
              open(os.path.join(HERE, "derived_stats.json"), "w"), indent=1, sort_keys=True)
    say("wrote derived_stats.json — %d arms, %d flaked arm-baselines" % (len(stats), len(flaked)))

    # ---- composites (A1) --------------------------------------------------
    comp = {}
    for (ins, fname), byts in COMPOSITES.items():
        car = None
        parts = {}
        for b in byts:
            for k, s in stats.items():
                if s["instr"] == ins and s["field"] == "byte+%d" % b:
                    parts["byte+%d" % b] = s
                    car = s["carrier"]
        vs = [p["verdict_A3"] for p in parts.values()]
        if parts and all(v == "stable-live" for v in vs):
            cv = "stable-live"
        elif parts and all(v == "inert-single-carrier" for v in vs):
            cv = "inert-single-carrier"
        else:
            cv = "withheld"
        comp["%s.%s" % (ins, fname)] = {
            "carrier": car, "verdict_A3": cv,
            "per_byte": {k: {"verdict": p["verdict_A3"], "M": p["M_A3"], "I": p["I_A3"],
                             "D": p["D_A3"], "N": p["N_A3"], "distinct": p["distinct_encodings"]}
                         for k, p in parts.items()},
            "bytes_swept": byts,
            "field_bits": dbf.get(ins, {}).get(fname),
        }

    return stats, comp, dbf, dbi, val, flaked, out


if __name__ == "__main__":
    main()
