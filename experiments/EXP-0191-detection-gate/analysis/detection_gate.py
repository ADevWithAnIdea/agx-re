#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0191 -- a DETECTION-POWER GATE on every INERT verdict in the corpus.

DEF-0190-1: `audit.py` reaches INERT-MULTI / INERT-SINGLE from `moved == 0`, and
`moved` is the number of distinct `observed` hashes within a value partition.  An arm
whose observable never varies returns `moved = 0` BY CONSTRUCTION, so the inert buckets
cannot come out the other way, and INERT-MULTI is not withheld.

This script asks the one question the audit never asks:

    for (experiment, arm), did this arm EVER demonstrate that its observable can move?

An arm passes only if a known-live control IN THE SAME ARM produced a different
`observed` payload from the arm's baseline (or two different payloads among themselves),
or if some other field's sweep in that same arm moved the observable.  An arm whose
observable is constant across every case FAILS, and an INERT verdict from it establishes
nothing.  An INERT verdict from an arm that PASSES is a real `proven-dont-care` and is
STRONGER than it was before this gate existed.

Nothing here is a measurement.  `_detect` is consumed EXACTLY as EXP-0163 and EXP-0172
consume it -- as `arms_with_proven_detection_power`, an instrument check -- and never as
a field observation.  No db field is credited, no headline number is moved by it.

The rule, the role table, the validity test and the discrimination proof are frozen in
../PRE_REGISTRATION.md sections 4-7 and are NOT command-line tunable.

READ-ONLY over experiments/*/raw/**, tools/agx-isa/validation.json and
EXP-0190/analysis/{audit,blind_arms}.json.  Writes analysis/gate_results.json and, only
if the frozen trigger fires, analysis/reclassify.json.

Usage: python3 analysis/detection_gate.py
"""
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
REPO = os.path.abspath(os.path.join(EXPDIR, ".."))
E190 = os.path.join(EXPDIR, "EXP-0190-indexer-refilter")

sys.path.insert(0, os.path.join(E190, "analysis"))
from classify_underscore import TABLE as U_TABLE          # noqa: E402  (the 96-name intent table)

# --- frozen validity sets (PRE_REGISTRATION section 5; EXP-0164/0190's own sets) ----
HARD = {"fault", "hang", "undecodable", "killed", "not_written",
        "no_draw", "lost_7_of_8", "nondeterministic"}
CONTAM = {"invalid_run", "victim", "skipped"}
# run bookkeeping that varies for reasons unrelated to the hardware observable
STRIP = {"errdom", "os_class", "foreign_retries", "error", "ovr", "restarts",
         "gputime_ns", "t_ns"}
EMIT_OK = ("hardware-run", "isolated-byte-diff")
POISON = 0xDEADBEEF
HEXRE = re.compile(r"^[0-9a-fA-F]+$")

# --- frozen role partition (PRE_REGISTRATION section 4) ----------------------------
# Every name below is one of EXP-0190's hand-classified 96, with its emitter file:line
# recorded there.  The partition is BY INTENT: `_ANCHOR_VERDICT` stores a boolean verdict
# in `value` yet 50 of its 94 groups vary their bytes, so a structural rule would read
# bookkeeping as evidence.
ROLE = {}
for _n in ("_detect", "_live_control", "_L1_opcode_group", "_L2_erase", "_litmus_power",
           "_sensitivity", "_liveness_src_alt", "_liveness_dst_alt", "_liveness_spatial",
           "_liveness_vp_alt", "_poscontrol", "__power_sr_sel", "__power_b7",
           "__power_fmt", "__sens_byte0_bit2", "__sens_byte1",
           "_ERASE4", "_ERASE16", "_ERASE64", "_ERASE256"):
    ROLE[_n] = "CONTROL_LIVE"
for _n in U_TABLE:
    if _n.startswith("__ladder_L_"):
        ROLE[_n] = "CONTROL_LIVE"
for _n in ("_falsifier_oracle", "_falsifier_dst00", "_falsifier_extmode0",
           "_falsifier_op_and", "_falsifier_op_bit", "_falsifier_ldformat0",
           "_falsifier_barrier_off", "_falsifier_fwd_am54", "_refuter_modlo2_unbound",
           "__falsifier_byte0", "__falsifier_b2", "__falsifier_F1_opsel_hadd",
           "__falsifier_F2_srcA_zerolane", "__falsifier_F3_dstnib_r7",
           "__falsifier_F4_zero_point", "_byte0",
           "__split_at0_r6", "__split_at0and2", "__split_at2_r6", "__split_at2_r7"):
    ROLE[_n] = "CONTROL_FALSIFIER"
for _n in ("_byte1_11", "_byte2_56", "_rounding", "_ZERO4", "_INERT4"):
    ROLE[_n] = "CONTROL_NEG"
for _n in ("_baseline", "__baseline", "_baseline_recheck", "_baseline_final",
           "_baseline_health", "_baseline_check", "_baseline_fwd", "_smoke_baseline",
           "_smoke_calib", "_smoke_store_shape", "_natural", "_identity_splice",
           "_start", "_cascade_check", "_detect_summary", "_calibprobe",
           "_latency_E1", "_latency_E2", "_ANCHOR_VERDICT"):
    ROLE[_n] = "BASELINE"
for _n, (_c, _e, _r) in U_TABLE.items():
    if _c == "FIELD-SWEEP":
        ROLE[_n] = "SIBLING"        # EXP-0190's 14 genuine sweeps, underscore-named

MAX_PAYLOADS = 8      # we only ever need to know whether a role reached 2


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def leaves(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in STRIP:
                continue
            leaves(v, out)
    elif isinstance(o, list):
        for v in o:
            leaves(v, out)
    else:
        out.append(o)


def is_poison_leaf(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return v == POISON
    if isinstance(v, str) and len(v) >= 8 and len(v) % 8 == 0 and HEXRE.match(v):
        return {v[i:i + 8].lower() for i in range(0, len(v), 8)} == {"deadbeef"}
    return False


def payload_of(rec):
    """Canonical observation payload, or None if the record is not a valid observation.

    PRE_REGISTRATION section 5.  Rule 4 is load-bearing: a `_detect` record can carry
    outcome 'moved' with an `observed` payload that is a GPU-hang error string.  A
    command buffer that FAILED is not a demonstration that the readback can move, and
    DEF-0178-1 says a watchdog timeout can be manufactured outright."""
    oc = rec.get("outcome")
    if oc in HARD or oc in CONTAM or "skip_reason" in rec:
        return None, "outcome:%s" % oc
    ob = rec.get("observed")
    if ob in (None, {}, [], ""):
        return None, "no-observation"
    if isinstance(ob, dict):
        if "error" in ob or ob.get("errdom") or ob.get("os_class"):
            return None, "error-payload"
        ob = {k: v for k, v in ob.items() if k not in STRIP}
        if not ob:
            return None, "bookkeeping-only"
    return json.dumps(ob, sort_keys=True, separators=(",", ":")), None


def poison_only(payload):
    try:
        ob = json.loads(payload)
    except Exception:
        return False
    lv = []
    leaves(ob, lv)
    content = [v for v in lv if isinstance(v, (int, float, str)) and v not in ("", 0)]
    if not content:
        return False
    return all(is_poison_leaf(v) for v in content)


def blank():
    return {"payloads": collections.defaultdict(set),      # role -> {payload_sha}
            "example": {},                                 # role -> {sha: (name, value)}
            "n": collections.Counter(),                    # role -> record count
            "n_valid": collections.Counter(),
            "names": collections.defaultdict(collections.Counter),   # role -> name -> n
            "invalid": collections.Counter(),              # reason -> n
            "sib_poison": 0, "sib_valid": 0,
            "detect_summary": []}


def add(st, role, name, payload, why, rec):
    st["n"][role] += 1
    st["names"][role][name] += 1
    if payload is None:
        st["invalid"][why or "?"] += 1
        return
    st["n_valid"][role] += 1
    h = sha(payload)
    if len(st["payloads"][role]) < MAX_PAYLOADS or h in st["payloads"][role]:
        st["payloads"][role].add(h)
        st["example"].setdefault(role, {}).setdefault(
            h, {"field": name, "value": rec.get("value"), "outcome": rec.get("outcome"),
                "payload_prefix": payload[:160]})
    if role == "SIBLING":
        st["sib_valid"] += 1
        if poison_only(payload):
            st["sib_poison"] += 1


def scan():
    """One pass over every append-only raw record in the repository."""
    strict = collections.defaultdict(blank)      # (exp, armkey)     -> stats
    carrier = collections.defaultdict(blank)     # (exp, carrierkey) -> stats
    unknown = collections.Counter()
    nfiles = nlines = 0
    for exp in sorted(os.listdir(EXPDIR)):
        raw = os.path.join(EXPDIR, exp, "raw")
        if not os.path.isdir(raw):
            continue
        for dp, _, fns in os.walk(raw):
            for fn in fns:
                if not fn.endswith(".jsonl"):
                    continue
                nfiles += 1
                for line in open(os.path.join(dp, fn), errors="replace"):
                    line = line.strip()
                    if not line:
                        continue
                    nlines += 1
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    f, i = rec.get("field"), rec.get("instr")
                    if not (isinstance(f, str) and isinstance(i, str)):
                        continue
                    if f.startswith("_"):
                        if f not in ROLE:
                            unknown[f] += 1
                            continue
                        role = ROLE[f]
                    else:
                        role = "SIBLING"
                    ac = [str(rec[k]) for k in ("carrier", "arm")
                          if rec.get(k) not in (None, "")]
                    armkey = "|".join(ac) if ac else "-"
                    ckey = (str(rec["carrier"]) if rec.get("carrier") not in (None, "")
                            else armkey)
                    p, why = payload_of(rec)
                    for st in (strict[(exp, armkey)], carrier[(exp, ckey)]):
                        add(st, role, f, p, why, rec)
                        if f == "_detect_summary":
                            st["detect_summary"].append(rec.get("note") or "")
    return strict, carrier, unknown, nfiles, nlines


def verdict(st):
    """The frozen gate (PRE_REGISTRATION section 6)."""
    P = st["payloads"]
    base = P.get("BASELINE", set())

    def role_pass(r):
        s = P.get(r, set())
        if not s:
            return False
        if base:
            return len(s | base) >= 2 and bool(s - base)
        return len(s) >= 2
    pl, pf = role_pass("CONTROL_LIVE"), role_pass("CONTROL_FALSIFIER")
    ps = len(P.get("SIBLING", set())) >= 2
    return {
        "pass": bool(pl or pf or ps),
        "pass_live_control": pl, "pass_falsifier": pf, "pass_sibling_field": ps,
        "n_distinct_payloads": {r: len(v) for r, v in sorted(P.items()) if v},
        "records": {r: int(n) for r, n in sorted(st["n"].items())},
        "records_valid": {r: int(n) for r, n in sorted(st["n_valid"].items())},
        "invalid_reasons": dict(st["invalid"]),
        "control_records_relied_on": {
            r: {n: int(c) for n, c in sorted(st["names"][r].items())}
            for r in ("CONTROL_LIVE", "CONTROL_FALSIFIER", "BASELINE", "CONTROL_NEG")
            if st["names"].get(r)},
        "control_payload_examples": {
            r: st["example"].get(r, {}) for r in ("CONTROL_LIVE", "CONTROL_FALSIFIER")
            if st["example"].get(r)},
        "sibling_observations_valid": st["sib_valid"],
        "sibling_observations_poison_only": st["sib_poison"],
        "all_poison": bool(st["sib_valid"] and st["sib_poison"] == st["sib_valid"]),
        "detect_any_self_reported": detect_any(st),
    }


def detect_any(st):
    """EXP-0163/0172's OWN published verdict for the arm, from its `_detect_summary`
    note.  An external oracle: written by a different experiment, for a different
    purpose, before this gate existed."""
    if not st["detect_summary"]:
        return None
    vals = set()
    for note in st["detect_summary"]:
        try:
            vals.add(bool(json.loads(note).get("detect_any")))
        except Exception:
            m = re.search(r'"detect_any"\s*:\s*(true|false)', note)
            if m:
                vals.add(m.group(1) == "true")
    if not vals:
        return None
    return True if True in vals else False


def resolver():
    dirs = sorted(d for d in os.listdir(EXPDIR) if os.path.isdir(os.path.join(EXPDIR, d)))

    def rd(eid):
        if eid in dirs:
            return eid
        c = [d for d in dirs if d.startswith(eid + "-")]
        return c[0] if len(c) == 1 else eid
    return rd


def main():
    strict_st, carrier_st, unknown, nfiles, nlines = scan()
    if unknown:
        print("FAIL: %d underscore name(s) have no frozen role: %s"
              % (len(unknown), dict(unknown)), file=sys.stderr)
        return 2

    SV = {k: verdict(v) for k, v in strict_st.items()}
    CV = {k: verdict(v) for k, v in carrier_st.items()}

    audit = json.load(open(os.path.join(E190, "analysis", "audit.json")))["fields"]
    blind = json.load(open(os.path.join(E190, "analysis", "blind_arms.json")))
    live = json.load(open(os.path.join(REPO, "tools", "agx-isa", "validation.json")))
    rd = resolver()

    def carrier_key_of(exp, armkey):
        """The carrier this arm key belongs to, as recorded by the harness."""
        if (exp, armkey) in CV:
            return armkey
        head = armkey.split("|")[0]
        return head if (exp, head) in CV else armkey

    # ---------------- per-field gate ---------------------------------------
    fields, arms_used = {}, set()
    for key, r in sorted(audit.items()):
        if not r["bucket"].startswith("INERT"):
            continue
        mn, fn = r["mnemonic"], r["field"]
        lab = live["instructions"].get(mn, {}).get(fn, {}).get("label")
        rows = []
        for a in r["arms_tested"]:
            eid, _, armkey = a.partition(":")
            exp = rd(eid)
            ck = carrier_key_of(exp, armkey)
            sv = SV.get((exp, armkey))
            cv = CV.get((exp, ck))
            arms_used.add((exp, armkey))
            rows.append({
                "arm": "%s|%s" % (exp, armkey),
                "carrier_join_key": "%s|%s" % (exp, ck),
                "strict": sv or {"pass": False, "note": "no raw records under this arm key"},
                "carrier": cv or {"pass": False, "note": "no raw records under this carrier"},
            })
        ns = sum(1 for x in rows if x["strict"]["pass"])
        nc = sum(1 for x in rows if x["carrier"]["pass"])
        n = len(rows)

        def verd(k):
            return ("FAILS" if k == 0 else "SURVIVES-FULLY" if k == n else "SURVIVES")
        fields[key] = {
            "mnemonic": mn, "field": fn,
            "bucket": r["bucket"], "cohort_in_EXP0190_snapshot": r["cohort"],
            "label_now": lab,
            "emitter_grade_now": lab in EMIT_OK,
            "target": r["target"], "evidence": r["evidence"],
            "max_values_dispatched": r["max_values_dispatched"],
            "moved_total": r["moved_total"],
            "gating_fallback": r.get("gating_fallback"),
            "n_arms_tested": n,
            "n_arms_passing_strict": ns, "n_arms_passing_carrier": nc,
            "verdict_strict": verd(ns), "verdict_carrier": verd(nc),
            "multi_degraded": bool(r["bucket"] == "INERT-MULTI" and nc < 2),
            "all_poison_arms": [x["arm"] for x in rows
                                if x["strict"].get("all_poison")],
            "arms": rows,
        }

    # ---------------- discrimination proof (section 7) ----------------------
    d1 = {}
    for a in blind["arms_with_no_observation_at_all"]:
        exp, _, armkey = a.partition("|")
        v = SV.get((exp, armkey))
        d1[a] = {"gate_pass": bool(v and v["pass"]),
                 "n_distinct": (v or {}).get("n_distinct_payloads", {})}
    d2 = {}
    for (exp, armkey), v in SV.items():
        if v["detect_any_self_reported"] is None:
            continue
        d2["%s|%s" % (exp, armkey)] = {"self_reported_detect_any": v["detect_any_self_reported"],
                                       "gate_pass": v["pass"],
                                       "agree": v["detect_any_self_reported"] == v["pass"]}
    d4 = {}
    for key, r in audit.items():
        for m in r.get("mixed_arm_liveness") or []:
            exp = rd(m["experiment"])
            for a in m["stable_live_arms"]:
                v = SV.get((exp, a))
                d4["%s|%s" % (exp, a)] = {"stable_live_on": key,
                                          "gate_pass": bool(v and v["pass"])}
    npass = sum(1 for a in arms_used if SV.get(a, {}).get("pass"))
    nfail = len(arms_used) - npass

    # ---------------- POST-HOC, NOT PRE-REGISTERED --------------------------
    # (a) EXP-0190's blind-arm scan buckets an arm as blind only if it recorded NO
    #     observation at all, or >= 8 records with exactly one distinct `observed` AND
    #     zero empty ones.  An arm that mixes empty and single-valued observations falls
    #     through both buckets.  Report the strict failures it did not see.
    blindset = set()
    for grp in ("arms_with_no_observation_at_all",
                "arms_with_exactly_one_distinct_observation"):
        for a in blind[grp]:
            e, _, k = a.partition("|")
            blindset.add((e, k))
    missed = sorted("%s|%s" % a for a in arms_used
                    if not SV.get(a, {}).get("pass", False) and a not in blindset)

    # (b) D4 raised it, so it is measured rather than left as an anecdote: audit.py's
    #     `sig_of` returns "<hard-class>|<hash>", so an `ok` observation and a `fault`
    #     differ as signatures and `moved` counts the difference as MOVEMENT.  A
    #     STABLE-LIVE promotion can therefore be carried by faults.  For every arm
    #     audit.py marked stable_live, report how many DISTINCT VALID payloads it
    #     actually has.  < 2 means the movement cannot have come from observations.
    slcheck = {}
    for k, r in sorted(audit.items()):
        for eid, ex in (r.get("per_experiment") or {}).items():
            for armkey, v in ex.items():
                if not v.get("stable_live"):
                    continue
                exp = rd(eid)
                sv = SV.get((exp, armkey))
                slcheck.setdefault("%s|%s" % (exp, armkey),
                                   {"fields": [], "distinct_valid_sibling_payloads":
                                    (sv["n_distinct_payloads"].get("SIBLING", 0)
                                     if sv else None),
                                    "records": (sv or {}).get("records", {}),
                                    "invalid_reasons": (sv or {}).get("invalid_reasons", {}),
                                    "gate_pass": bool(sv and sv["pass"])})["fields"].append(k)
    sl_suspect = {a: v for a, v in slcheck.items()
                  if v["distinct_valid_sibling_payloads"] is not None
                  and v["distinct_valid_sibling_payloads"] < 2}

    reclass = {k: v for k, v in fields.items()
               if v["emitter_grade_now"] and v["verdict_carrier"] == "FAILS"}

    out = {
        "_meta": {
            "experiment": "EXP-0191-detection-gate",
            "question": "did this arm ever demonstrate that its observable can move?",
            "rule": "PRE_REGISTRATION.md sections 4-7, frozen before computation",
            "repo_revision_at_preregistration": "cd2f05dd96e8bef4ffb797ca0cdb1fa7c1f6604f",
            "raw_files_scanned": nfiles, "raw_lines_scanned": nlines,
            "n_arms_seen_strict": len(SV), "n_carriers_seen": len(CV),
            "n_inert_fields": len(fields),
            "n_inert_fields_emitter_grade_now": sum(1 for v in fields.values()
                                                    if v["emitter_grade_now"]),
            "arms_of_inert_fields": {
                "n": len(arms_used), "pass_strict": npass, "fail_strict": nfail,
                "pass_carrier": sum(1 for a in arms_used
                                    if CV.get((a[0], carrier_key_of(*a)), {}).get("pass")),
            },
            "field_verdicts_strict": dict(collections.Counter(
                v["verdict_strict"] for v in fields.values())),
            "field_verdicts_carrier": dict(collections.Counter(
                v["verdict_carrier"] for v in fields.values())),
            "field_verdicts_carrier_emitter_grade_now": dict(collections.Counter(
                v["verdict_carrier"] for v in fields.values() if v["emitter_grade_now"])),
            "n_multi_degraded": sum(1 for v in fields.values() if v["multi_degraded"]),
            "n_fields_with_an_all_poison_arm": sum(1 for v in fields.values()
                                                   if v["all_poison_arms"]),
            "n_reclassify": len(reclass),
            "discrimination": {
                "D1_no_observation_arms_must_fail": {
                    "n": len(d1), "n_passing": sum(1 for v in d1.values() if v["gate_pass"]),
                    "verdict": "PASS" if not any(v["gate_pass"] for v in d1.values())
                               else "BROKEN"},
                "D2_detect_summary_oracle": {
                    "n": len(d2), "n_agree": sum(1 for v in d2.values() if v["agree"]),
                    "disagreements": {k: v for k, v in d2.items() if not v["agree"]}},
                "D3_both_outcomes_present": {
                    "pass": npass, "fail": nfail,
                    "verdict": "PASS" if npass > 0 and nfail > 0 else "NON-DISCRIMINATING"},
                "D4_mixed_arm_liveness_arms_must_pass": {
                    "n": len(d4), "n_passing": sum(1 for v in d4.values() if v["gate_pass"]),
                    "failures": {k: v for k, v in d4.items() if not v["gate_pass"]}},
            },
            "post_hoc_not_pre_registered": {
                "strict_failures_EXP0190_blind_scan_did_not_see": {
                    "n": len(missed), "arms": missed,
                    "why": "blind_arm_scan.py buckets an arm only if it recorded NO "
                           "observation, or >=8 records with exactly one distinct "
                           "`observed` AND zero empty ones; an arm mixing empty and "
                           "single-valued observations falls through both buckets."},
                "stable_live_arms_with_fewer_than_2_distinct_valid_payloads": {
                    "n": len(sl_suspect), "n_stable_live_arms_checked": len(slcheck),
                    "why": "audit.py's sig_of() is '<hard-class>|<hash>', so an `ok` "
                           "observation and a `fault` differ as SIGNATURES and `moved` "
                           "counts that as movement. An arm with <2 distinct valid "
                           "payloads cannot have moved on observations. REPORTED ONLY; "
                           "no label is changed on it here.",
                    "arms": sl_suspect},
            },
        },
        "discrimination_detail": {"D1": d1, "D2": d2, "D4": d4},
        "fields": fields,
    }
    json.dump(out, open(os.path.join(HERE, "gate_results.json"), "w"),
              indent=1, sort_keys=True)

    # reclassify.json -- FIELD-SWEEP-PROTOCOL section 5 flat form, with start/width,
    # because the merger refuses a row whose bits have moved.  `fields` carries ONLY the
    # frozen trigger of PRE_REGISTRATION section 6.  `post_hoc_candidates` carries the
    # STABLE-LIVE rows the post-hoc check raised: they are NOT a verdict of this
    # experiment and MUST NOT be merged on its authority -- they need their own
    # pre-registered successor.  They are written out only so the orchestrator has the
    # exact rows, with bit geometry, rather than a prose list.
    db = json.load(open(os.path.join(REPO, "tools", "agx-isa", "db.json")))
    geo = {}
    for i in db["instructions"]:
        for f in i.get("fields", []):
            geo[(i["mnemonic"], f["name"])] = (f["start"], f["width"])
    doc = {}
    for k, v in sorted(reclass.items()):
        s, w = geo.get((v["mnemonic"], v["field"]), (None, None))
        doc[k] = {"label": "untested", "start": s, "width": w,
                  "target": v["target"], "evidence": v["evidence"],
                  "range": "%d values dispatched" % v["max_values_dispatched"],
                  "note": ("EXP-0191 detection gate: the %s verdict rests on %d arm(s), "
                           "NONE of which ever demonstrated that its observable can "
                           "move (no known-live control, no falsifier and no sibling "
                           "field in the same arm produced a second distinct `observed` "
                           "payload). DEF-0190-1: `moved = 0` is returned by "
                           "construction, so the inert verdict establishes nothing."
                           % (v["bucket"], v["n_arms_tested"]))}
    cand = {}
    for a, v in sorted(sl_suspect.items()):
        for k in v["fields"]:
            mn, _, fn = k.partition(".")
            lab = live["instructions"].get(mn, {}).get(fn, {}).get("label")
            if lab not in EMIT_OK:
                continue
            sl_arms = [aa for aa, vv in slcheck.items() if k in vv["fields"]]
            if any(aa not in sl_suspect for aa in sl_arms):
                continue          # a clean STABLE-LIVE arm still carries the row
            s, w = geo.get((mn, fn), (None, None))
            cand[k] = {"current_label": lab, "start": s, "width": w,
                       "stable_live_arms": sorted(sl_arms),
                       "distinct_valid_payloads_per_arm":
                           {aa: slcheck[aa]["distinct_valid_sibling_payloads"]
                            for aa in sorted(sl_arms)},
                       "invalid_reasons_per_arm":
                           {aa: slcheck[aa]["invalid_reasons"] for aa in sorted(sl_arms)},
                       "note": "POST-HOC, NOT PRE-REGISTERED, NOT A VERDICT OF EXP-0191. "
                               "Every arm carrying this row's STABLE-LIVE promotion has "
                               "fewer than 2 distinct VALID observation payloads, so "
                               "audit.py's `moved` can only have counted fault-vs-ok "
                               "SIGNATURE differences as movement. Needs its own "
                               "pre-registered successor before any label changes."}
    json.dump({"_meta": {"experiment": "EXP-0191-detection-gate",
                         "form": "FIELD-SWEEP-PROTOCOL section 5, flat "
                                 "<mnemonic>.<field>, with start/width",
                         "n_triggered_by_the_frozen_rule": len(doc),
                         "n_post_hoc_candidates": len(cand),
                         "frozen_rule": "live label in (hardware-run, isolated-byte-diff) "
                                        "AND the INERT verdict FAILS the gate at the "
                                        "CARRIER join level"},
               "fields": doc, "post_hoc_candidates": cand},
              open(os.path.join(HERE, "reclassify.json"), "w"),
              indent=1, sort_keys=True)

    m = out["_meta"]
    print(json.dumps({k: v for k, v in m.items() if k != "discrimination"},
                     indent=1, sort_keys=True))
    print("discrimination:", json.dumps(m["discrimination"], indent=1, sort_keys=True))
    for k, v in sorted(fields.items()):
        if v["verdict_carrier"] == "FAILS":
            print("  FAILS %-30s %-13s label_now=%-16s arms=%s"
                  % (k, v["bucket"], v["label_now"], [a["arm"] for a in v["arms"]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
