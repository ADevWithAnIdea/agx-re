#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""build_proposals.py -- propose citation ADDITIONS, never a removal.

For every field row in validation.json, every experiment whose committed raw holds
records for THAT EXACT FIELD AT ITS CURRENT db.json span is a candidate. A
candidate becomes a proposal only under the rules below; every other candidate is
written to work/refusals.json WITH ITS REASON, because a refusal that is not
recorded is indistinguishable from a search that was never run.

ADMISSION
  H1  the experiment resolves to a directory, is not quarantined, HAS a raw/ tree,
      and commits an authored probe. An addition failing H1 pushes the row from
      `auditable` to `incomplete` on dashboard 6 -- an addition that makes the row
      WORSE (promotion_check.rule_R1).
  H2  the records are in raw/ (append-only), not analysis/ or work/. EXP-0209 found
      a prior audit's own scan output indexable as dispatches.
  H3  >= 2 OBSERVATION records -- a record carrying an execution outcome. The
      `00_manifest.json` files in this corpus carry instr+field+arm+n_cases and no
      value, bytes or outcome: they are the plan, not the run, and they sort first.
  H4  the attribution is anchored to BITS, not to a NAME:
        T1  >= 2 distinct values of this field's own bits, decoded at the CURRENT
            span out of committed actual bytes.
        T2  the record declares fstart/fwidth EQUAL to the current span, requests
            >= 2 distinct values, and commits NO bytes at all (nothing to check
            against, but the harness named the bits rather than the name).
        T3  a legacy byte sweep at a byte index PROVEN inside the field's current
            span, whose distinct requested byte values imply >= 2 distinct values
            of the field's own bits. legacy_index deliberately commits no actual
            bytes (its rule 1), so this is liveness evidence and not a Gate A
            ledger, and it is labelled as such.
      Refused, with the reason recorded:
        * records declaring a DIFFERENT span (EXP-0197 4.1: `mov_zext16.src_reg`'s
          896 named records sweep byte+1 and hold today's field at ONE value);
        * committed bytes present and the field's own bits take <= 1 value (the
          byte moved, the field did not -- EXP-0214 `half_pack.dst`);
        * K3 group-string attribution only (EXP-0197 6.2: nearly worthless);
        * a named field with no declared span and no bytes (the `carry_gen`
          subop->srcA->srcB rename hazard);
        * P4 dispatched-program corpora, which credit every field of every
          instruction in a program that ran -- tier S1, reported, never proposed.

Output: analysis/citation_additions.json, work/secondary.json, work/refusals.json.
No label, span, removal, or db/docs/PROVENANCE edit.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI

W = os.path.join(EXP, "work")
SPEC = EI.load_db(os.path.join(W, "db_frozen.json"))
VAL = json.load(open(os.path.join(W, "validation_frozen.json")))
LOC = json.load(open(os.path.join(W, "locators.json")))
SPANREP = json.load(open(os.path.join(W, "span_repair.json")))
POSTREPAIR = set(SPANREP["added"]) | set(SPANREP["moved"].keys())

_res, _h1 = {}, {}


def resolve(slug):
    if slug not in _res:
        base = slug.split("/")[0]
        _res[slug] = sorted(os.path.basename(d)
                            for d in glob.glob(os.path.join(EXPS, base + "*"))
                            if os.path.isdir(d))
    return _res[slug]


def h1(exp):
    if exp not in _h1:
        d = os.path.join(EXPS, exp)
        authored = any(os.path.isdir(os.path.join(d, s)) and os.listdir(os.path.join(d, s))
                       for s in ("kernels", "harness", "probe", "probes", "src",
                                 "shaders", "analysis")) or \
            bool(glob.glob(os.path.join(d, "*.metal")) or glob.glob(os.path.join(d, "*.py")))
        _h1[exp] = {"has_raw": os.path.isdir(os.path.join(d, "raw")),
                    "authored": authored,
                    "quarantined": os.path.exists(os.path.join(d, "QUARANTINE.md"))}
    return _h1[exp]


def byte_match_ok(mnem, bidx, byteval):
    """Would setting byte `bidx` to `byteval` still satisfy the descriptor's match?

    A legacy byte sweep runs 0x00..0xff through a byte that may carry match bits;
    for most of those values the dispatched program is no longer this instruction.
    EXP-0211's P5 refuses exactly this (`splice_changes_descriptor_identity`, 3 of
    6 on EXP-0003's `stop`); P1 cannot, because it never synthesizes the bytes. The
    check is applied here instead, to the REQUESTED byte, so a legacy citation is
    never justified by values that destroy the descriptor.
    """
    lo = 8 * bidx
    for m in (SPEC.get(mnem, {}).get("match") or []):
        try:
            st, w, val = m[0], m[1], m[2]
        except Exception:
            continue
        a, b = max(st, lo), min(st + w - 1, lo + 7)
        if a > b:
            continue
        want = (val >> (a - st)) & ((1 << (b - a + 1)) - 1)
        got = (byteval >> (a - lo)) & ((1 << (b - a + 1)) - 1)
        if want != got:
            return False
    return True


def field_bits_of_byte(st, w, bidx, byteval):
    """The part of field (st,w) that byte `bidx` carries, given that byte's value.

    Returns None when the byte lies outside the field. Used to test whether a
    legacy BYTE sweep actually moved the field's own bits: a 3-value sweep of byte
    12 does not move a bit-3 sub-field if all three values agree in bit 3.
    """
    lo, hi = 8 * bidx, 8 * bidx + 7
    a, b = max(st, lo), min(st + w - 1, hi)
    if a > b:
        return None
    return (byteval >> (a - lo)) & ((1 << (b - a + 1)) - 1)


# ------------------------------------------------------------ legacy aggregation

def legacy_cells():
    """EXP-0211's parsers, re-run against the FROZEN db.json. P4 kept apart."""
    ix = EI.Indexer(SPEC)
    def blank():
        return {"records": 0, "parsers": collections.Counter(),
                "confidence": collections.Counter(), "req": set(), "afv": set(),
                "bytes": set(), "first": None, "first_obs": None,
                "outcomes": collections.Counter(),
                "byte_req": collections.defaultdict(set),
                "src_files": collections.Counter(), "p4_records": 0}
    agg = collections.defaultdict(blank)
    p = os.path.join(W, "legacy_index", "legacy_records.jsonl")
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        m, f = r.get("instr"), r.get("field")
        if not isinstance(m, str) or not isinstance(f, str) or m not in SPEC:
            continue
        if f not in SPEC[m]["fields"]:
            continue
        if "%sraw%s" % (os.sep, os.sep) not in (r.get("_src_file", "") + os.sep):
            continue                                        # H2
        c = agg[(r["_exp"], "%s.%s" % (m, f))]
        c["parsers"][r.get("_parser")] += 1
        c["src_files"][r.get("_src_file")] += 1
        if r.get("_parser") == "P4":
            c["p4_records"] += 1
            b = r.get("bytes")
            if isinstance(b, str) and b:
                c["bytes"].add(b)
            continue                     # P4 never contributes to a proposal
        c["records"] += 1
        c["confidence"][r.get("parse_confidence")] += 1
        if isinstance(r.get("value"), int):
            c["req"].add(r["value"])
            if isinstance(r.get("byte_index"), int):
                c["byte_req"][r["byte_index"]].add(r["value"])
        b = r.get("bytes")
        if isinstance(b, str) and b:
            c["bytes"].add(b)
            v, _ = ix.decode_actual(m, f, b)
            if v is not None:
                c["afv"].add(v)
        if r.get("outcome"):
            c["outcomes"][r["outcome"]] += 1
            if c["first_obs"] is None:
                c["first_obs"] = [r.get("_src_file"), r.get("_src_line")]
        if c["first"] is None:
            c["first"] = [r.get("_src_file"), r.get("_src_line")]
    return agg


LEG = legacy_cells()
LEGBY = collections.defaultdict(list)
for (e, k), c in LEG.items():
    LEGBY[k].append((e, c))


# ------------------------------------------------------------------- the rules

def classify_modern(key, c, st, w):
    if c["in_raw"] == 0:
        return None, "records exist only outside raw/ (derived artifact, not append-only evidence)"
    if c["outcome_records"] < 2:
        return None, ("%d record(s) but only %d carry an execution outcome: this is the "
                      "run plan (00_manifest.json), not the run"
                      % (c["records"], c["outcome_records"]))
    # K3 -- an arm/carrier/group STRING that contains the field's name -- is a
    # substring match, not an observation. EXP-0172 carries `carrier:
    # "simd_shuffle@dead**src**/compute#0"` on a `_baseline` record, which K3 hands
    # to `simd_shuffle.src`. EXP-0197 6.2 says K3 is nearly worthless and nearly
    # cost two rows; it is refused outright here, whatever the byte counts say.
    if set(c["keying"]) == {"k3"}:
        return None, ("attributed only by a group/arm string containing the field's name "
                      "(K3): a substring match, not an observation of the field "
                      "(EXP-0197 6.2)")
    # The caller's own declared bits must overlap the field's CURRENT span. A
    # record that names `ext` while declaring byte_index 4 swept byte 4; after
    # EXP-0212 moved `half_alu_fma12.ext` from (32,64) to (48,48) byte 4 is not in
    # the field any more, and the 1531 "distinct encodings of ext" in that cell are
    # cross-arm anchor differences, not a sweep of ext.
    span_bytes = set(range(st // 8, (st + w - 1) // 8 + 1))
    bidx = {int(k): v for k, v in (c.get("byte_indices") or {}).items()}
    b_in = sum(v for k, v in bidx.items() if k in span_bytes)
    b_out = sum(v for k, v in bidx.items() if k not in span_bytes)
    if bidx and b_in == 0:
        return None, ("every record declares a swept byte %s, and the field's current span "
                      "(%d,%d) covers byte(s) %s: the records swept a different byte under "
                      "this field's NAME"
                      % (",".join(str(k) for k in sorted(bidx)), st, w,
                         ",".join(str(k) for k in sorted(span_bytes))))
    if c["span_mismatch"] and c["span_match"] == 0:
        return None, ("records declare span(s) %s, not the current (%d,%d): they swept "
                      "different bits under the same NAME (EXP-0197 4.1)"
                      % (",".join(sorted(c["declared_spans"])), st, w))
    mixed = ("; %d of %d byte-keyed record(s) declare a byte OUTSIDE the span"
             % (b_out, b_in + b_out)) if b_out else ""
    nafv, nreq = c["n_actual_field_values"], c["n_req_value_ints"]
    nafvm = c.get("n_actual_field_values_matching", 0)
    if nafv >= 2 and nafvm < 2 and c.get("match_bytes", 0) >= 0:
        return None, ("%d distinct actual encodings, but only %d of them survive the "
                      "descriptor's own match bits (%d of %d committed encodings decode "
                      "to a different instruction): the field's bits moved only in "
                      "programs that are no longer %s (EXP-0197 4.4)"
                      % (nafv, nafvm, c.get("nonmatch_bytes", 0),
                         c.get("match_bytes", 0) + c.get("nonmatch_bytes", 0),
                         key.split(".")[0]))
    if nafv >= 2 and nreq >= 2:
        return "T1", (mixed[2:] + ("; " if mixed else "") +
                      "%d distinct actual encodings of bits %d..%d decoded from committed "
                      "bytes (%d of them match-preserving), over %d distinct requested "
                      "values, on %d observation record(s)"
                      % (nafv, st, st + w - 1, nafvm, nreq, c["outcome_records"]))
    if nafv >= 2 and nreq < 2:
        return "S1", ("%d distinct actual encodings of bits %d..%d but %d distinct requested "
                      "value(s): a dispatched-program credit, not a per-field sweep"
                      % (nafv, st, st + w - 1, nreq))
    if c["ledger_records"] and nafv <= 1:
        return None, ("%d record(s) carry actual bytes (%d distinct) yet the field's own "
                      "bits %d..%d take %d value(s): the byte moved, the field did not "
                      "(EXP-0214 half_pack.dst; %d Gate A disagreement(s))"
                      % (c["ledger_records"], c["n_actual_bytes"], st, st + w - 1, nafv,
                         c["ledger_disagree"]))
    if c["span_match"] >= 1 and nreq >= 2 and c["ledger_records"] == 0:
        return "T2", ("harness declared fstart/fwidth == the CURRENT span (%d,%d) on %d "
                      "record(s) over %d distinct requested values; the experiment commits "
                      "no actual bytes, so this is liveness, not a Gate A ledger"
                      % (st, w, c["span_match"], nreq))
    if nreq < 2:
        return None, ("%d distinct requested value(s) and %d distinct actual encoding(s): "
                      "below the 2-value bar" % (nreq, nafv))
    return None, ("named-only attribution: %d record(s), keying %s, no declared span and no "
                  "committed bytes varying the field -- the carry_gen rename hazard"
                  % (c["records"], ",".join(sorted(c["keying"]))))


def classify_legacy(key, c, st, w):
    ps = set(c["parsers"])
    if c["records"] == 0:
        return None, ("only P4 dispatched-program records (%d): program-level credit for "
                      "every field of every instruction in a program that ran"
                      % c["p4_records"])
    span_bytes = set(range(st // 8, (st + w - 1) // 8 + 1))
    if c["byte_req"] and not (set(c["byte_req"]) & span_bytes):
        return None, ("every legacy record declares byte %s; the field's current span "
                      "(%d,%d) covers byte(s) %s"
                      % (",".join(str(k) for k in sorted(c["byte_req"])), st, w,
                         ",".join(str(k) for k in sorted(span_bytes))))
    nafv, nreq = len(c["afv"]), len(c["req"])
    if not c["outcomes"]:
        return None, "no legacy record for this field carries an execution outcome"
    if nafv >= 2 and nreq >= 2:
        return "T1", ("%d distinct actual encodings of bits %d..%d, %d distinct requested "
                      "values, parsers %s" % (nafv, st, st + w - 1, nreq, ",".join(sorted(ps))))
    # T3: the byte sweep must move the FIELD's bits, not merely the byte.
    partials = collections.defaultdict(set)
    dropped = 0
    m = key.split(".")[0]
    for bidx, vals in c["byte_req"].items():
        for v in vals:
            if not byte_match_ok(m, bidx, v):
                dropped += 1
                continue
            x = field_bits_of_byte(st, w, bidx, v)
            if x is not None:
                partials[bidx].add(x)
    best = max((len(v) for v in partials.values()), default=0)
    if best >= 2 and c["records"] >= 2:
        return "T3", ("%d legacy record(s) with an outcome, %d distinct requested byte "
                      "values at byte index/indices %s (%d dropped as match-destroying), "
                      "which move the field's own bits "
                      "%d..%d over %d distinct values; parsers %s, confidence %s; "
                      "legacy_index commits no actual bytes so there is NO Gate A ledger"
                      % (c["records"], nreq,
                         ",".join(str(k) for k in sorted(c["byte_req"])), dropped,
                         st, st + w - 1,
                         best, ",".join(sorted(ps)), ",".join(sorted(c["confidence"]))))
    return None, ("%d legacy record(s), %d distinct requested byte values (%d dropped as "
                  "match-destroying), but only %d distinct value(s) of the field's own "
                  "bits %d..%d survive: the byte moved, the field did not"
                  % (c["records"], nreq, dropped, best, st, st + w - 1))


# ------------------------------------------------------------------------ main

def main():
    primary, secondary, refused = {}, {}, {}
    stats = collections.Counter()
    bykey = collections.defaultdict(list)
    for e, keys in LOC.items():
        for k, c in keys.items():
            bykey[k].append((e, c))
    for m, fs in VAL["instructions"].items():
        for f, row in fs.items():
            if f == "_instruction" or not isinstance(row, dict):
                continue
            if m not in SPEC or f not in SPEC[m]["fields"]:
                continue
            key = "%s.%s" % (m, f)
            st, w = SPEC[m]["fields"][f]
            cited = set()
            for e in (row.get("evidence") or []):
                if isinstance(e, str):
                    cited.update(resolve(e))
            adds, secs, refs, seen = [], [], [], set()
            for exp, c in bykey.get(key, []):
                if exp in cited:
                    stats["modern_already_cited"] += 1
                    continue
                seen.add(exp)
                g = h1(exp)
                tier, why = classify_modern(key, c, st, w)
                loc = ("%s:%s" % (c.get("obs_file"), c.get("obs_line"))
                       if c.get("obs_file") else None)
                ent = {"experiment": exp, "source": "modern-index", "tier": tier,
                       "why": why, "locator": loc,
                       "locator_is_observation": bool(loc),
                       "first_record": "%s:%s" % (c["first_file"], c["first_line"]),
                       "records": c["records"], "observation_records": c["outcome_records"],
                       "distinct_requested_values": c["n_req_value_ints"],
                       "distinct_actual_encodings": c["n_actual_field_values"],
                       "distinct_actual_encodings_match_preserving":
                           c.get("n_actual_field_values_matching", 0),
                       "encodings_destroying_match": c.get("nonmatch_bytes", 0),
                       "distinct_actual_bytes": c["n_actual_bytes"],
                       "current_span": [st, w], "keying": c["keying"],
                       "byte_indices": c.get("byte_indices") or {},
                       "declared_spans": c["declared_spans"],
                       "raw_runs": c["raw_runs"], "targets": c["targets"],
                       "outcomes": c["outcomes"],
                       "ledger_agree": c["ledger_agree"],
                       "ledger_disagree": c["ledger_disagree"],
                       "byte_ledger_disagree": c["byte_ledger_disagree"],
                       "sem_checks": c["sem_checks"],
                       "post_repair_span": key in POSTREPAIR, "H1": g}
                if not (g["has_raw"] and g["authored"] and not g["quarantined"]):
                    ent["tier"], ent["why"] = None, ("H1 fails %s: adding it would push the "
                                                     "row to `incomplete` on dashboard 6"
                                                     % json.dumps(g))
                    refs.append(ent)
                elif tier in ("T1", "T2"):
                    if not loc:
                        ent["tier"], ent["why"] = None, "no observation record to point at"
                        refs.append(ent)
                    else:
                        adds.append(ent)
                elif tier == "S1":
                    secs.append(ent)
                else:
                    refs.append(ent)
            for exp, c in LEGBY.get(key, []):
                if exp in cited or exp in seen:
                    stats["legacy_already_cited_or_covered"] += 1
                    continue
                g = h1(exp)
                tier, why = classify_legacy(key, c, st, w)
                loc = ("%s:%s" % (c["first_obs"][0], c["first_obs"][1])
                       if c["first_obs"] else None)
                ent = {"experiment": exp, "source": "legacy-index", "tier": tier,
                       "why": why, "locator": loc,
                       "locator_is_observation": bool(loc),
                       "records": c["records"],
                       "observation_records": sum(c["outcomes"].values()),
                       "p4_records_excluded": c["p4_records"],
                       "distinct_requested_values": len(c["req"]),
                       "distinct_actual_encodings": len(c["afv"]),
                       "current_span": [st, w],
                       "parsers": dict(c["parsers"]),
                       "parse_confidence": dict(c["confidence"]),
                       "byte_indices": {str(k): len(v) for k, v in c["byte_req"].items()},
                       "outcomes": dict(c["outcomes"]),
                       "source_files": sorted(c["src_files"])[:4],
                       "post_repair_span": key in POSTREPAIR, "H1": g}
                if not (g["has_raw"] and g["authored"] and not g["quarantined"]):
                    ent["tier"], ent["why"] = None, "H1 fails %s" % json.dumps(g)
                    refs.append(ent)
                elif tier in ("T1", "T3") and loc:
                    adds.append(ent)
                elif tier in ("T1", "T3"):
                    ent["tier"], ent["why"] = None, "no observation record to point at"
                    refs.append(ent)
                else:
                    refs.append(ent)
            if adds:
                primary[key] = {"label": row.get("label"), "target": row.get("target"),
                                "current_evidence": row.get("evidence") or [],
                                "current_span": [st, w],
                                "post_repair_span": key in POSTREPAIR,
                                "add": sorted(adds, key=lambda a: a["experiment"])}
                stats["rows_with_primary"] += 1
                stats["primary_additions"] += len(adds)
            if secs:
                secondary[key] = {"current_evidence": row.get("evidence") or [],
                                  "add": sorted(secs, key=lambda a: a["experiment"])}
                stats["rows_with_secondary"] += 1
                stats["secondary_additions"] += len(secs)
            if refs:
                refused[key] = sorted(refs, key=lambda a: a["experiment"])
                stats["refusals"] += len(refs)
    json.dump(primary, open(os.path.join(EXP, "analysis", "citation_additions.json"), "w"),
              indent=1, sort_keys=True)
    json.dump(secondary, open(os.path.join(W, "secondary.json"), "w"), indent=1, sort_keys=True)
    json.dump(refused, open(os.path.join(W, "refusals.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(dict(stats), indent=1))


# ------------------------------------------------------------------- selftest

def _cell(**kw):
    c = {"records": 10, "in_raw": 10, "outcome_records": 10, "keying": {"k1": 10},
         "n_actual_field_values": 0, "n_actual_field_values_matching": 0,
         "n_req_value_ints": 0, "n_actual_bytes": 0, "ledger_records": 0,
         "ledger_agree": 0, "ledger_disagree": 0, "span_declared": 0,
         "span_match": 0, "span_mismatch": 0, "declared_spans": {},
         "byte_indices": {}, "match_bytes": 0, "nonmatch_bytes": 0}
    c.update(kw)
    return c


def _leg(**kw):
    c = {"records": 10, "parsers": collections.Counter({"P1": 10}),
         "confidence": collections.Counter({"table": 10}), "req": set(), "afv": set(),
         "bytes": set(), "outcomes": collections.Counter({"ok": 10}),
         "byte_req": collections.defaultdict(set), "p4_records": 0}
    c.update(kw)
    return c


def selftest():
    """Both directions. A rule that only refuses is as useless as one that only admits."""
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-4s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            ok = False

    # ---- must ADMIT -------------------------------------------------------
    t, why = classify_modern("falu2.dst", _cell(
        n_actual_field_values=16, n_actual_field_values_matching=16,
        n_req_value_ints=16, n_actual_bytes=16, ledger_records=16, ledger_agree=16,
        match_bytes=16), 4, 4)
    chk("ADMIT: 16 match-preserving encodings of the field's own bits -> T1", t == "T1")
    t, _ = classify_modern("falu2.dst", _cell(
        n_req_value_ints=16, span_declared=16, span_match=16,
        declared_spans={"(4, 4)": 16}), 4, 4)
    chk("ADMIT: harness declared the CURRENT span and swept it, no bytes -> T2", t == "T2")
    c = _leg(req={0x1f, 0x9f})
    c["byte_req"][0] = {0x1f, 0x9f}
    t, _ = classify_legacy("iadd2.addsub", c, 7, 1)
    chk("ADMIT: legacy byte-0 sweep whose match-preserving values move bit 7 -> T3",
        t == "T3")

    # ---- must REFUSE ------------------------------------------------------
    t, why = classify_modern("carry_gen.srcA", _cell(
        n_req_value_ints=256, span_declared=512, span_mismatch=512,
        declared_spans={"(24, 8)": 512}), 8, 8)
    chk("REFUSE: records declaring a DIFFERENT span (the carry_gen rename hazard)",
        t is None and "not the current" in why)
    t, why = classify_modern("half_pack.dst", _cell(
        n_actual_field_values=1, n_actual_bytes=256, n_req_value_ints=256,
        ledger_records=256, match_bytes=256), 4, 4)
    chk("REFUSE: 256 distinct bytes, ONE value of the field's own bits (EXP-0214)",
        t is None and "the byte moved, the field did not" in why)
    t, why = classify_modern("bf_alu.srcA", _cell(
        n_actual_field_values=256, n_actual_field_values_matching=0,
        n_req_value_ints=256, n_actual_bytes=256, ledger_records=2048,
        nonmatch_bytes=2048, byte_indices={"3": 2048}, keying={"k2": 2048}), 24, 8)
    chk("REFUSE: every committed encoding fails the descriptor's own match bits",
        t is None and "match bits" in why)
    t, why = classify_modern("simd_shuffle.src", _cell(
        keying={"k3": 162}, n_actual_field_values=5, n_actual_field_values_matching=5,
        n_req_value_ints=15, match_bytes=162), 16, 8)
    chk("REFUSE: attribution by a group string containing the field's name (K3)",
        t is None and "substring" in why)
    t, why = classify_modern("half_alu_fma12.ext", _cell(
        n_actual_field_values=1531, n_actual_field_values_matching=1531,
        n_req_value_ints=256, byte_indices={"4": 4096}, match_bytes=4096), 48, 48)
    chk("REFUSE: every record sweeps a byte OUTSIDE the field's current span",
        t is None and "different byte" in why)
    t, why = classify_modern("atomic_tg.op_desc", _cell(
        records=380, outcome_records=1, n_actual_field_values=256,
        n_actual_field_values_matching=256, n_req_value_ints=256, match_bytes=256), 40, 8)
    chk("REFUSE: the run PLAN (00_manifest.json) with no observation records",
        t is None and "not the run" in why)
    t, why = classify_modern("falu2.dst", _cell(in_raw=0), 4, 4)
    chk("REFUSE: records that live outside raw/ (a prior audit's own scan output)",
        t is None and "raw/" in why)
    t, why = classify_modern("falu2.dst", _cell(
        n_actual_field_values=1, n_req_value_ints=1), 4, 4)
    chk("REFUSE: a single value is not a sweep", t is None and "2-value bar" in why)
    c = _leg(req={0x00, 0x01, 0x02})
    c["byte_req"][0] = {0x00, 0x01, 0x02}
    t, why = classify_legacy("iadd2.addsub", c, 7, 1)
    chk("REFUSE: a legacy byte sweep whose match-preserving values never move the bit",
        t is None and "the field did not" in why)
    c = _leg(records=0, parsers=collections.Counter({"P4": 900}), p4_records=900,
             outcomes=collections.Counter())
    t, why = classify_legacy("falu2.dst", c, 4, 4)
    chk("REFUSE: a P4 dispatched-program corpus is a program-level credit",
        t is None and "program-level credit" in why)
    c = _leg(req={1, 2}, outcomes=collections.Counter())
    c["byte_req"][0] = {1, 2}
    t, why = classify_legacy("falu2.dst", c, 4, 4)
    chk("REFUSE: legacy records with no execution outcome", t is None and "outcome" in why)
    c = _leg(req={1, 2})
    c["byte_req"][9] = {1, 2}
    t, why = classify_legacy("falu2.dst", c, 4, 4)
    chk("REFUSE: a legacy sweep of a byte the field does not cover",
        t is None and "current span" in why)

    # ---- byte_match_ok / field_bits_of_byte both ways ---------------------
    chk("match: iadd2 byte0 0x1f and 0x9f keep the descriptor",
        byte_match_ok("iadd2", 0, 0x1f) and byte_match_ok("iadd2", 0, 0x9f))
    chk("match: iadd2 byte0 0x00 destroys it", not byte_match_ok("iadd2", 0, 0x00))
    chk("match: a byte carrying no match bits is always fine",
        byte_match_ok("iadd2", 5, 0x00) and byte_match_ok("iadd2", 5, 0xff))
    chk("field bits: bit 7 of byte 0 is 1 for 0x9f and 0 for 0x1f",
        field_bits_of_byte(7, 1, 0, 0x9f) == 1 and field_bits_of_byte(7, 1, 0, 0x1f) == 0)
    chk("field bits: byte 3 is outside a byte-0 field",
        field_bits_of_byte(4, 4, 3, 0xff) is None)

    print("\nEXP-0215 PROPOSAL-RULE SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()
