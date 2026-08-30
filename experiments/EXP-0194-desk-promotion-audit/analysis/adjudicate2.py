#!/usr/bin/env python3
"""EXP-0194 step 5 (FINAL): adjudicate the 566 blocked field-labels against committed raw.

This supersedes adjudicate.py, which had THREE holes that let five rows through.
Each hole is a "check that could not come out the other way", and each is now a gate:

  H1  It keyed on the harness's NOMINAL `value`, not the bits that actually reached
      the encoding.  EXP-0138's falu2_srcmod10/falu3_srcmod12 `opsel` sweeps dispatch
      0..7 onto only FOUR distinct byte strings (bits the descriptor's `match` pins
      cannot be cleared -- DEF-0166-1), so `value` 4 and `value` 6 ran the SAME
      program and were scored differently only because the harness computed its
      oracle from the value it MEANT to encode.  -> gate G2b (injectivity).
  H2  It read "the oracle varies" as "the run predicted the field's effect".  In
      EXP-0178's tile_read the second oracle payload is the CLASSIFIER's did-nothing
      reference, written after the observation, and every genuinely matching case
      shares one constant oracle -- a prediction about the INSTRUCTION, not the
      field.  -> gate G7 now demands two MATCHING cases at different encoded values
      with DIFFERENT oracles.
  H3  It never left the single run it was looking at.  EXP-0178's own RESULTS.md
      records tile_read.b7/.tail as 91.0 % / 91.7 % cross-run agreement and refuses
      them; a one-run view cannot see that.  -> gate G8 (cross-run reproduction).

Every gate can return NO.  G8 in particular refuses any field whose movement was
only ever seen once.
"""
import json, os, sys, collections, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRATCH = os.environ.get("E0194_RECORDS",
    "/private/tmp/claude-501/-Users-user-asahi-re-public-agx-re/"
    "c16be4eb-79fc-4aa2-9097-f170fdc17d7b/scratchpad/candidate_records.jsonl")

db = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "db.json")))
GEOM = {}
for i in db["instructions"]:
    for f in i.get("fields", []):
        GEOM[(i["mnemonic"], f["name"])] = (f["start"], f["width"])

VOLATILE = {"gputime_ns", "t", "ts", "time", "elapsed", "duration", "seq", "idx",
            "wall", "ns", "us", "ms", "timestamp", "restarts", "attempt", "attempts",
            "foreign_retries", "innocent_retries"}
ERRISH = {"error", "errdom", "os_class", "fault_class", "fault_classes", "exception"}
# executed observations of the field.  faults/hangs/victims/no_draw/undecodable/
# unstable/nondeterministic are NOT observations of the field (protocol 3.4d, 7).
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
    return hashlib.sha256(json.dumps(strip(o), sort_keys=True, default=str).encode()).hexdigest()[:16]


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
    at = r.get("attempts")
    for a in (at if isinstance(at, list) else []):
        if isinstance(a, dict):
            if a.get("victim"):
                return False
            if a.get("status") is not None and str(a["status"]).upper() != "OK":
                return False
    return True


def enc_val(b, start, width):
    """The bits that ACTUALLY reached the encoding -- not what the harness meant."""
    try:
        n = int.from_bytes(bytes.fromhex(b), "little")
    except ValueError:
        return None
    return (n >> start) & ((1 << width) - 1)


def outside(b, start, width):
    try:
        n = int.from_bytes(bytes.fromhex(b), "little")
    except ValueError:
        return None
    return (len(b), n & ~(((1 << width) - 1) << start))


def run_of(path):
    return "/".join(path.split("/")[:4])          # experiments/EXP-x/raw/<run>


def main():
    recs = collections.defaultdict(list)
    for line in open(SCRATCH):
        r = json.loads(line)
        recs[(str(r["instr"]), str(r["field"]))].append(r)

    blocked = json.load(open(os.path.join(HERE, "blocked_rows.json")))
    results = []
    for row in blocked:
        key = (row["mn"], row["field"])
        out = dict(instr=key[0], field=key[1], label=row["label"], evidence=row["ev"])
        rs = recs.get(key, [])
        out["n_raw"] = len(rs)
        if key[1] == "_instruction":
            out["verdict"] = "HARDWARE-BLOCKED"
            out["reason"] = ("instruction-level label, not a field: the open question is whether "
                             "the opcode/match bits do what the descriptor claims. A byte diff of "
                             "a field cannot answer it; it needs an emit-and-check dispatch.")
            results.append(out); continue
        if not rs:
            out["verdict"] = "HARDWARE-BLOCKED"
            out["reason"] = "no per-case raw record anywhere in experiments/**/raw/*.jsonl"
            results.append(out); continue
        geom = GEOM.get(key)
        if not geom:
            out["verdict"] = "HARDWARE-BLOCKED"
            out["reason"] = "field has no db.json geometry; cannot verify byte isolation"
            results.append(out); continue
        start, width = geom

        # carrier-level groups, but keep every run so G8 can compare them
        cgroups = collections.defaultdict(list)
        for r in rs:
            cgroups[(r["__exp"], str(r.get("carrier", "")), str(r.get("arm", "")))].append(r)
        stage = collections.Counter()
        best, passing = None, None
        RANK = {"G2": 1, "G2b": 2, "G3": 3, "G4": 4, "G5": 5, "G7": 6, "G8": 7, "PASS": 8}

        def keep(n):
            # keep the FURTHEST-progressing group, not the first failing one --
            # otherwise the reported reason describes a group that was never the
            # best evidence, and the bucket boundary moves for no evidential reason.
            nonlocal best
            if best is None or RANK.get(n.get("stop"), 0) > RANK.get(best.get("stop"), 0):
                best = n
        for ck, g in sorted(cgroups.items()):
            clean = [r for r in g if is_clean(r)]
            note = dict(carrier=list(ck), n_records=len(g), n_clean=len(clean))
            if len(clean) < 2:
                stage["G1_fail"] += 1; continue
            stage["G1"] += 1
            # G2b: nominal value -> bytes must be injective, else the harness's own
            # bookkeeping (and therefore its oracle) does not describe what ran.
            v2b = collections.defaultdict(set)
            b2v = collections.defaultdict(set)
            for r in clean:
                if isinstance(r.get("bytes"), str):
                    v2b[json.dumps(r.get("value"), sort_keys=True)].add(r["bytes"])
                    b2v[r["bytes"]].add(json.dumps(r.get("value"), sort_keys=True))
            aliased = sum(1 for b, vs in b2v.items() if len(vs) > 1)
            note["aliased_encodings"] = aliased
            enc = {}
            for r in clean:
                if isinstance(r.get("bytes"), str):
                    enc[id(r)] = enc_val(r["bytes"], start, width)
            byenc = collections.defaultdict(list)
            for r in clean:
                e = enc.get(id(r))
                if e is not None:
                    byenc[e].append(r)
            note["n_encoded_values"] = len(byenc)
            if len(byenc) < 2:
                stage["G2_fail"] += 1; note["stop"] = "G2"; keep(note); continue
            stage["G2"] += 1
            if aliased:
                stage["G2b_fail"] += 1
                note["stop"] = "G2b"
                note["why"] = ("%d byte strings each carry >1 nominal value: the harness's "
                               "value->encoding map is not injective (DEF-0166-1), so its "
                               "per-case oracle does not describe the program that ran" % aliased)
                keep(note); continue
            stage["G2b"] += 1
            outs = {outside(r["bytes"], start, width) for r in clean if isinstance(r.get("bytes"), str)}
            if len(outs) != 1 or None in outs:
                stage["G3_fail"] += 1; note["stop"] = "G3"; keep(note); continue
            stage["G3"] += 1
            payload = {e: {h(r["observed"]) for r in rr} for e, rr in byenc.items()}
            allp = set().union(*payload.values())
            note["n_payloads"] = len(allp)
            if len(allp) < 2:
                stage["G4_fail"] += 1
                note["stop"] = "G4"
                note["why"] = "observable never moved across %d encoded values" % len(byenc)
                keep(note); continue
            stage["G4"] += 1
            if any(len(p) > 1 for p in payload.values()):
                stage["G5_fail"] += 1; note["stop"] = "G5"; keep(note); continue
            stage["G5"] += 1
            # G7: a prediction that DISCRIMINATES between encoded values, and matched.
            matched = [(enc[id(r)], h(r["oracle"])) for r in clean
                       if r.get("match") is True and "oracle" in r and enc.get(id(r)) is not None]
            disc = len({o for _, o in matched}) >= 2 and len({v for v, _ in matched}) >= 2
            note["n_matched"] = len(matched)
            note["n_distinct_matched_oracles"] = len({o for _, o in matched})
            if not disc and not os.environ.get("E0194_NO_G7"):
                stage["G7_fail"] += 1
                note["stop"] = "G7"
                note["why"] = ("no two MATCHING cases at different encoded values carry different "
                               "oracles: the run predicted the instruction's effect, not the field's")
                keep(note); continue
            stage["G7"] += 1
            # G8: cross-run reproduction of the value->payload map.
            runs = collections.defaultdict(dict)
            for r in clean:
                e = enc.get(id(r))
                if e is not None:
                    runs[run_of(r["__file"])].setdefault(e, set()).add(h(r["observed"]))
            note["n_runs"] = len(runs)
            if len(runs) < 2:
                stage["G8_fail"] += 1
                note["stop"] = "G8"
                note["why"] = ("seen in only ONE raw run directory: no reproduction conjunct, so "
                               "an unstable field is indistinguishable from a stable one")
                keep(note); continue
            rl = sorted(runs)
            shared = agree = 0
            for e in set.intersection(*[set(runs[r]) for r in rl]):
                shared += 1
                if len({frozenset(runs[r][e]) for r in rl}) == 1:
                    agree += 1
            note["cross_run_shared"] = shared
            note["cross_run_agreeing"] = agree
            if shared < 2 or agree != shared:
                stage["G8_fail"] += 1
                note["stop"] = "G8"
                note["why"] = "cross-run map disagrees: %d of %d shared encoded values agree" % (agree, shared)
                keep(note); continue
            stage["G8"] += 1
            note["stop"] = "PASS"
            note["runs"] = rl
            passing = note
            break
        out["stages"] = dict(stage)
        out["group"] = passing or best
        far = (passing or best or {}).get("stop")
        if passing:
            out["verdict"] = "DESK-PROMOTABLE"
            out["reason"] = ("committed raw already contains an isolated, injective, "
                             "cross-run-reproduced per-value sweep whose observable moved and "
                             "whose host oracle discriminated between values and matched")
        elif far in ("G7", "G8"):
            out["verdict"] = "AMBIGUOUS"
            out["reason"] = (best or {}).get("why", "stopped at " + str((best or {}).get("stop")))
        else:
            out["verdict"] = "HARDWARE-BLOCKED"
            b = best or {}
            out["reason"] = b.get("why") or ("no group reached the movement gate (stopped at %s)"
                                             % b.get("stop", "G1"))
        results.append(out)

    json.dump(results, open(os.path.join(HERE, os.environ.get("E0194_OUT", "verdicts_final.json")), "w"), indent=1)
    c = collections.Counter(r["verdict"] for r in results)
    print("TOTAL blocked field-labels: %d" % len(results))
    for k in ("DESK-PROMOTABLE", "AMBIGUOUS", "HARDWARE-BLOCKED"):
        print("  %-18s %d" % (k, c[k]))
    print("\nHARDWARE-BLOCKED, by reason:")
    for k, v in collections.Counter(r["reason"][:90] for r in results
                                    if r["verdict"] == "HARDWARE-BLOCKED").most_common():
        print("  %4d  %s" % (v, k))
    print("\nAMBIGUOUS, by reason:")
    for k, v in collections.Counter(r["reason"][:90] for r in results
                                    if r["verdict"] == "AMBIGUOUS").most_common():
        print("  %4d  %s" % (v, k))
    print("\nNon-HARDWARE-BLOCKED rows:")
    for r in results:
        if r["verdict"] != "HARDWARE-BLOCKED":
            g = r.get("group") or {}
            print("  %-16s %-22s %-16s stop=%-5s clean=%-5s enc=%-5s pay=%-4s runs=%s"
                  % (r["verdict"], r["instr"], r["field"], g.get("stop"), g.get("n_clean"),
                     g.get("n_encoded_values"), g.get("n_payloads"), g.get("n_runs")))


main()
