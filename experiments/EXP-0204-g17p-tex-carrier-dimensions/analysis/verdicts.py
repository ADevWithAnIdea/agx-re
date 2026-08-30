#!/usr/bin/env python3
"""verdicts.py -- EXP-0204 verdicts on the SIX INDEPENDENT AXES.

Recomputed FROM raw/ only.  Never from a run manifest, never from memory.

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` sec.2: one label must no longer carry four
conclusions.  Every field is scored separately on encoding geometry, liveness,
semantics, compiler recipe, target and reproducibility, with EXACT NUMERATORS AND
DENOMINATORS -- never a percentage alone (sec.5 Phase 2).  The legacy
`docs/evidence-classification.md` label is emitted only as the strictest one all
six axes support.

THE GATES (frozen in PRE_REGISTRATION sec.15; do not edit without a new amendment)

  A  actual-byte ledger: requested value == value decoded from the ACTUAL bytes
     re-read from the dispatched program.  A round trip is not this gate.
  B  a positive control in the arm's own dimension moved the same observable.
     If it failed, the arm is `carrier-undecidable` and zero movement is NOT
     evidence of inertness.
  C  an independent semantic predictor assigned the case to a modelled bucket.
     `sem_checked == 0` can never produce `hardware-run`.
  D  a generated compiler recipe.  NOT ATTEMPTED here, so nothing is `emittable`.
  E  two CLEAN runs (quiet machine) in reversed/shuffled order with identical
     ledgers and no victim/cascade evidence.

  and the arithmetic rule, written LITERALLY:
        moved >= 2*disagree   AND   moved > 0
  NOT `moved >= 2*max(disagree,1)`, which cannot promote any width-1 field
  (FIELD-SWEEP-PROTOCOL sec.5b).  selftest() proves both directions before any
  verdict is computed.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import carriers as CA                       # noqa: E402
import arms as ARMSPEC                      # noqa: E402
import isadb                                # noqa: E402

CONTROL = {"_baseline", "_detect", "_detect_summary", "_baseline_recheck",
           "_baseline_final", "_cascade_check", "_arm_not_run", "_sites"}
HARD = {"fault", "hang", "undecodable", "malformed", "unreproduced", "not_run",
        "ledger_mismatch"}
AGREE_BAR = 99.0



NOTES = {
 "tex_sample.mode": (
   "PRE-REGISTERED MODEL REFUTED (1/30). db.json models this byte as an ENUM "
   "{0x00 gather/read/sample_compare, 0x10 filtered sample, 0x20 LOD query}; it is a "
   "BITFIELD and 0x10 is INERT. Six carriers -- one per operation class, the LOD-query "
   "one authored for the first time in this corpus and needing a mipmapped texture -- "
   "gave compiler-chosen baselines of 0x10, 0x00 and 0x20, so the carrier set provably "
   "spans the dimension. Splicing 0x10<->0x00 across classes leaves the observation "
   "BIT-IDENTICAL on every arm. On the six arms whose two gated runs (opposite case "
   "order) agree at 256/256, the moved set is described EXACTLY, zero exceptions, by "
   "`(mode & 0x2C) != 0` (mscmp/0, mscmp/1, msfilt/0), `(mode & 0x0C) != 0` (msfixl/0, "
   "msfixl/1) and `(mode & 0x08) != 0` (msgath/0, 255/256 with 1 InnocentVictim). Read "
   "straight from raw and identical in both runs: bit 3 is live on EVERY arm; bit 2 is "
   "live exactly where a FILTER is in play (msfilt/msfixl/mscmp) and inert on the "
   "unfiltered arms (msgath nearest, msread integer read); bit 5 is live exactly where an "
   "IMPLICIT LOD is in play (msfilt/mscmp) and inert where the level is explicit or "
   "absent. Bits "
   "0,1,4,6,7 (mask 0xD3) move nothing on any of them. Bit 5 is CONTEXT-DEPENDENT: live "
   "under implicit LOD, inert under explicit level(). That bit rule was derived AFTER "
   "the sweep, so it is a HYPOTHESIS for a successor to pre-register, not a bounded map. "
   "Four arms (msread x2, mslodq x2) are irreproducible (103/256 .. 242/256) and support "
   "nothing. Legacy label `untested` is NOT `no evidence` -- see the axes."),
 "tex_write.amode": (
   "INERT IN THE TESTED ENVELOPE; GLOBAL ROLE UNKNOWN. This is the third-carrier "
   "requirement the prior refusal named (`only 2 distinct carriers with proven detection "
   "power, the bar is 3`): EXP-0163's twdim and twtype are ONE carrier in amode's own "
   "dimension because every write in both is write(colour, uint2(LITERAL,LITERAL)) at "
   "implicit level 0 with amode 0x54. FIVE new carriers with four different ADDRESS FORMS "
   "and five different observation paths (explicit mip level, texture_buffer linear 1-D "
   "index, cube face, 1-/2-component destinations, register-formed coordinate + a no-ALU "
   "contiguous vec4 store) were swept 0..255 dense on 12 arms x 2 gated runs in opposite "
   "case order: 0/3072 moved, 3071/3072 cross-run agreement, 6144/6144 ledger-verified, "
   "256 distinct ACTUAL encodings, and a host-computed semantic predictor says the store "
   "still landed at the predicted destination with the predicted data at 3072/3072. The "
   "census also broke the 0x54 monoculture: the compiler itself emits 0x55 on the LAST "
   "write of twbuf and twcube, so two arms have a different baseline. NOT PROMOTED TO A "
   "GENERAL INERTNESS RULE: sec.7 also wants interaction coverage (none run) and two CLEAN "
   "repetitions (Gate E not met -- every run was on a measurably busy machine). And the "
   "surviving alternative explanation is real: db.json's own vocabulary for this byte "
   "position distinguishes `terminal/standalone` from `non-terminal of a base-sharing "
   "group`, and this harness reads back AFTER command-buffer completion, so it has no "
   "ordering observable at all. The prior `unreached, not inert` wording is preserved."),
 "tex_write.rsv11": (
   "INERT IN THE TESTED ENVELOPE; GLOBAL ROLE UNKNOWN. Same 12 arms / 5 carriers / 2 gated "
   "runs as amode: 0/3072 moved, 3071/3072 agreement, 6144/6144 ledger-verified, 256 "
   "distinct ACTUAL encodings, semantic predictor 3072/3072. byte+11's positional sibling "
   "is device_store.st_desc_hi, the store data-format descriptor tail whose neighbour is "
   "documented as set only for a NON-4-component store, so this experiment added 1-component "
   "R32Float and 2-component RG32Float destinations -- every destination ever swept before "
   "was 4-component. The compiler emits rsv11 = 0 on ALL of them, which is a compiler "
   "differential against the format hypothesis, not support for it. Same two unmet sec.7 "
   "items as amode (interaction coverage, clean repetitions). Reported UNREACHED-and-bounded, "
   "not `unused` or `reserved`."),
 "tex_deriv.dstsrc": (
   "LIVE; ROLE UNKNOWN -- and that ceiling was stated in advance, not discovered afterwards. "
   "NO semantic model was pre-registered (the deriv carriers are deliberately AFFINE, which "
   "is what makes each derivative exactly host-computable but also, per sec.5 Phase 3, makes "
   "many candidate operations indistinguishable), so sem_checked = 0 and sec.2 makes "
   "`hardware-run` unreachable here. What the named debt asked for IS answered on the "
   "liveness axis: on the values comparable in both gated runs, dispatched in OPPOSITE case "
   "order, the per-value partition agrees 73/73 with 72 moving -- EXP-0189's `UNSTABLE` is "
   "explained. The reason it looked unstable is now mapped: the declared hang-tolerant "
   "MAPPING PASS (budget 8, not 2) swept 65/65 values and showed the hazard is a FAMILY, not "
   "the two isolated values EXP-0172's budget could reach: pooled over every arm and run the "
   "reproduced fault/hang set is 0x03FFFF, 0x07FFFF, 0x0FFFFF, 0x1FFFFF, 0x3FFFFF, 0x7FFFFF, "
   "0xFFFFFE, 0xFFFFFF -- every all-ones prefix from 2^18-1 upward plus max-1 and max -- "
   "plus the isolated 0xFBEEE7. The device survived all of them: no wedge, no reboot. "
   "Gate A additionally found that "
   "three requested encodings (e.g. dstsrc=0x80 on deriv2/0) are written to disk exactly as "
   "asked but decode as NO descriptor -- an encoding-geometry fact no prior experiment could "
   "see. Gate E NOT met: both runs were on a busy machine."),
}

def selftest():
    """This gate must be able to say NO.  Thirteen checks in this corpus could not."""
    def gate(moved, disagree):
        return moved >= 2 * disagree and moved > 0
    assert gate(1, 0), "width-1 trap: 1 moved / 0 disagreements MUST pass"
    assert not gate(0, 0), "a field that never moved must NOT pass"
    assert not gate(1, 1), "moved must be >= 2x disagreements"
    assert gate(4, 2)
    return True


def load(run_dir):
    p = os.path.join(run_dir, "sweep.jsonl")
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p, errors="replace"):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def quietness(run_dir):
    """A MEASUREMENT of whether the machine was quiet, not a claim."""
    p = os.path.join(run_dir, "procs.jsonl")
    if not os.path.exists(p):
        return {"quiet": None, "reason": "no procs.jsonl (run predates the sampler)"}
    n = busy = worst = 0
    names = collections.Counter()
    for line in open(p, errors="replace"):
        try:
            s = json.loads(line)
        except Exception:
            continue
        n += 1
        if s.get("n_foreign", 0) > 0:
            busy += 1
            worst = max(worst, s["n_foreign"])
            for f in s.get("foreign", []):
                names[f["cmd"].split()[0].split("/")[-1][:40]] += 1
    return {"quiet": (busy == 0 and n > 0), "samples": n, "busy_samples": busy,
            "max_concurrent_foreign_procs": worst,
            "foreign_process_names": dict(names.most_common(6))}


def payload(r):
    o = r.get("observed") or {}
    return json.dumps(o.get("hh"), sort_keys=True)


# Only AMENDMENT-2 runs may enter the gate.  `raw/g17p_20260830_run01` ran under
# the ORIGINAL sec.8 gate, without an actual-byte ledger and without a semantic
# oracle, and was killed by an SSH hang-up at 404 cases.  It is retained as a
# DISCOVERY sweep (its liveness observations and its tex_deriv hazard map are real
# evidence) and is reported separately -- never paired with an A2 run, which would
# manufacture ledger and semantic gaps that belong to the older design.
def is_gated(rid):
    return ("A2run" in rid) or rid.endswith("_C1") or rid.endswith("_C2")


def main():
    selftest()
    allruns = sorted(d for d in glob.glob(os.path.join(HERE, "raw", "g17p_*"))
                     if os.path.isdir(d))
    runs = [d for d in allruns if is_gated(os.path.basename(d))]
    discovery = [os.path.basename(d) for d in allruns
                 if not is_gated(os.path.basename(d))]
    q = {os.path.basename(d): quietness(d) for d in allruns}
    baseline_val = {(a["id"], f): a["baseline_fields"][f]
                    for a in ARMSPEC.ARMS for f in a["fields"]}

    # per (mnemonic, field, arm, run): value -> record
    cell = collections.defaultdict(dict)
    detect = collections.defaultdict(dict)
    base_pl = collections.defaultdict(dict)
    base_oracle = collections.defaultdict(dict)
    for d in runs:
        rid = os.path.basename(d)
        for r in load(d):
            arm, f = r.get("carrier"), r.get("field")
            if f == "_detect_summary":
                try:
                    detect[arm][rid] = json.loads(r["note"])
                except Exception:
                    pass
                continue
            if f == "_baseline":
                base_pl[arm][rid] = payload(r)
                o = r.get("oracle") or {}
                base_oracle[arm][rid] = {"checked": o.get("checked"),
                                         "agree": o.get("agree"),
                                         "match": r.get("match")}
                continue
            if f in CONTROL or r.get("value", -1) < 0:
                continue
            cell[(r["instr"], f, arm, rid)][r["value"]] = r

    fields = collections.defaultdict(list)
    for (m, f, arm, rid) in cell:
        if arm not in fields[(m, f)]:
            fields[(m, f)].append(arm)

    out = {
        "_experiment": "EXP-0204",
        "_target": "G17P (Apple A18 Pro, applegpu_g17p) -- DIRECT, not INFERRED",
        "_spec": ("RE_EXPERIMENT_PROCESS_CORRECTIONS.md (normative, wins) + "
                  "docs/evidence-classification.md sec.2 + FIELD-SWEEP-PROTOCOL sec.5; "
                  "gates frozen in PRE_REGISTRATION sec.15"),
        "_runs_gated": {os.path.basename(d): q[os.path.basename(d)] for d in runs},
        "_runs_discovery_not_gated": {
            r: dict(q[r], why=("ran under the ORIGINAL sec.8 gate: no actual-byte "
                               "ledger, no semantic oracle, busy machine, killed by "
                               "an SSH hang-up at 404 cases. Retained as evidence, "
                               "excluded from every gate (sec.9: nothing captured "
                               "is discarded, but it is not topped up or reused)."))
            for r in discovery},
        "_gate_selftest": ("passed: promotes (moved=1,disagree=0); refuses (moved=0); "
                           "refuses (moved=1,disagree=1)"),
        "_gate_D_note": ("Gate D (generated compiler recipe) was NOT ATTEMPTED in this "
                         "experiment.  Every arm splices one field of a compiler-emitted "
                         "occurrence, which is a liveness/semantics instrument, not a "
                         "generation proof.  No instruction here is claimed emittable."),
        "_arms": {}, "_db_defects": {
            "DEF-0204-1": {
                "descriptor": "tex_sample.mode",
                "claim_in_db": ("`mode` is modelled as an 8-bit ENUM with "
                                "{0x00: gather/read/sample_compare, 0x10: filtered "
                                "sample, 0x20: LOD query}."),
                "measured": ("It is a BITFIELD, not an enum, and 0x10 is INERT. On "
                             "every one of the six arms whose two gated runs agree "
                             "at 256/256, the set of values that change the "
                             "observation is described EXACTLY -- zero exceptions "
                             "over 256 values in both runs -- by a mask rule: "
                             "`(mode & 0x2C) != 0` on mscmp/0, mscmp/1 and msfilt/0; "
                             "`(mode & 0x0C) != 0` on msfixl/0 and msfixl/1; "
                             "`(mode & 0x08) != 0` on msgath/0. Bits 0,1,4,6,7 "
                             "(mask 0xD3) move nothing on any of them -- including "
                             "bit 4 = 0x10, which db.json names 'filtered sample' "
                             "and which is the COMPILER'S OWN baseline on msfilt "
                             "and msfixl. Splicing 0x10 -> 0x00 on a filtered "
                             "carrier and 0x00 -> 0x10 on a gather/read/compare "
                             "carrier both leave the observation bit-identical."),
                "consequence": ("The enum must not be used as an operation-class "
                                "selector by an emitter. It also reproduces and "
                                "extends RT-5's negative ('op+6 0x00/0x10 on a "
                                "linear sample: filtering does NOT change') from a "
                                "different direction and with per-value records."),
                "evidence": "analysis/mode_bits.json; raw/g17p_20260830_A2run0{1,2}",
            },
            "DEF-0204-2": {
                "descriptor": "tex_sample.mode bit 5 (0x20) is CONTEXT-DEPENDENT",
                "measured": ("0x20 is live on the three implicit-LOD arms "
                             "(mask 0x2C) and INERT on the two explicit-`level()` "
                             "arms (mask 0x0C), reproduced at 256/256 in both runs "
                             "on all five. This is a field-dependency edge "
                             "(RE_EXPERIMENT_PROCESS_CORRECTIONS sec.5 Phase 4) "
                             "between `mode` bit 5 and whether the occurrence "
                             "carries an explicit LOD."),
                "consequence": ("A single-carrier sweep of `mode` cannot describe "
                                "the field; the live-bit set depends on the "
                                "occurrence's LOD mode."),
                "evidence": "analysis/mode_bits.json",
            },
            "DEF-0204-3": {
                "descriptor": "cubearray_coord_const is SHADOWED, not merely unprovoked",
                "measured": ("Synthesised by hand, `f0 c0 04 <b3>` decodes as "
                             "`cubearray_coord_const` (len 4) STANDALONE for all "
                             "256 values of b3, and also in context when placed at "
                             "the carrier's trailing 4-byte boundary (@296). But "
                             "placed at the OTHER proven 4-byte boundary in the "
                             "same program (@250) it decodes as `pad_operand` "
                             "(len 2) for all 256 values -- another descriptor "
                             "claims the same leading bytes first."),
                "consequence": ("The two prior negatives (EXP-0148: 0 firings in "
                                "1080 files; EXP-0187: 31 authored cube constructs, "
                                "0 hits) are consistent with a DECODE-TABLE "
                                "SHADOWING problem rather than with the opcode not "
                                "existing. Whether the descriptor should be deleted, "
                                "re-anchored or given a tighter match is an "
                                "orchestrator decision; this experiment supplies the "
                                "decode evidence and makes NO claim about b3."),
                "evidence": "analysis/cube_decode.json; raw/cube_probe/",
            },
            "DEF-0204-4": {
                "descriptor": "tex_write.rsv10 (byte+11-1, i.e. byte+10) carries the WRITE LEVEL",
                "measured": ("In the pre-freeze census, the three explicit-level "
                             "writes of `twmip` differ only in byte+10: "
                             "0x00 for `write(c,coord,0)`, 0x10 for level 1 and "
                             "0x20 for level 2, with byte+11 (`rsv11`) 0 in all "
                             "three. db.json calls byte+10 `rsv10` (a `mod` with no "
                             "semantics) yet EXP-0155 already found it live "
                             "(240/256 moved)."),
                "consequence": ("`rsv10` is not reserved: on this evidence it is the "
                                "explicit mip-LEVEL operand of a texture store. "
                                "Reported as a CENSUS/compiler-differential "
                                "observation (three points), not as a swept result."),
                "evidence": "raw/prefreeze/census_run2.json (carrier twmip)",
            },
        },
    }

    for (m, f), armlist in sorted(fields.items()):
        key = f"{m}.{f}"
        desc = isadb._BY_MNEM[m]
        fd = next(x for x in desc["fields"] if x["name"] == f)
        w = fd["width"]
        per_arm = {}
        for arm in armlist:
            rids = sorted(rid for (mm, ff, aa, rid) in cell
                          if (mm, ff, aa) == (m, f, arm))
            bval = baseline_val.get((arm, f))
            rows = {rid: cell[(m, f, arm, rid)] for rid in rids}
            # ---- Gate A: the actual-byte ledger -------------------------
            led_ok = led_seen = 0
            bytes_ok = bytes_seen = 0
            unreachable = 0            # requested bytes that decode to NO descriptor
            actual_enc = set()
            requested = set()
            for rid in rids:
                for v, r in rows[rid].items():
                    L = r.get("ledger") or {}
                    requested.add(v)
                    if L.get("actual_bytes"):
                        actual_enc.add(L["actual_bytes"])
                    if L.get("bytes_match") is not None:
                        bytes_seen += 1
                        bytes_ok += 1 if L["bytes_match"] else 0
                    if L.get("gate_a_ok") is None:
                        continue
                    if L.get("decoded_mnemonic") is None:
                        # The bytes ARE on disk as requested (bytes_match) but no
                        # descriptor claims them: that is an ENCODING-GEOMETRY fact
                        # -- part of the nominal field space is unreachable under
                        # this descriptor -- not a ledger failure.  Counted apart,
                        # and excluded from every hardware conclusion.
                        unreachable += 1
                        continue
                    led_seen += 1
                    led_ok += 1 if L["gate_a_ok"] else 0
            # ---- outcome census over the FIRST run ----------------------
            oc = collections.Counter()
            sem = collections.Counter()
            sem_checked = 0
            r0 = rows[rids[0]] if rids else {}
            for v, r in r0.items():
                oc[r.get("outcome")] += 1
                s = r.get("semantic") or {}
                sem[s.get("bucket", "none")] += 1
                if s.get("checked"):
                    sem_checked += 1
            # ---- liveness + cross-run ------------------------------------
            moved = disagree = common = 0
            moved_vals = []
            if len(rids) >= 2:
                a, b = rows[rids[0]], rows[rids[1]]
                ba = base_pl.get(arm, {}).get(rids[0])
                bb = base_pl.get(arm, {}).get(rids[1])
                for v in sorted(set(a) & set(b)):
                    ra, rb = a[v], b[v]
                    if ra.get("outcome") in HARD or rb.get("outcome") in HARD:
                        continue
                    if ra.get("outcome") == "foreign" or rb.get("outcome") == "foreign":
                        continue
                    common += 1
                    pa, pb = payload(ra), payload(rb)
                    if pa != pb:
                        disagree += 1
                        continue
                    if ba is not None and pa != ba:
                        moved += 1
                        moved_vals.append(v)
            V = len({payload(r) for r in r0.values()
                     if r.get("outcome") not in HARD and r.get("outcome") != "foreign"})
            dm = detect.get(arm, {})
            powered = all(bool((dm.get(r) or {}).get("detect_ok")) for r in rids) if rids else False
            dim = [c for r in rids
                   for c in ((dm.get(r) or {}).get("dimension_controls_moved", {})
                             .get(key, []))]
            dim_ok = bool(dim) and all(
                bool((dm.get(r) or {}).get("dimension_controls_moved", {}).get(key))
                for r in rids)
            per_arm[arm] = {
                "runs": rids,
                "baseline_field_value": bval,
                "baseline_host_oracle": base_oracle.get(arm, {}),
                "gate_A_ledger": {"cases_with_ledger": led_seen, "cases_ok": led_ok,
                                  "requested_bytes_on_disk": f"{bytes_ok}/{bytes_seen}",
                                  "unreachable_requested_encodings": unreachable,
                                  "distinct_requested_values": len(requested),
                                  "distinct_actual_encodings": len(actual_enc),
                                  "passed": (led_seen > 0 and led_ok == led_seen
                                             and bytes_seen > 0 and bytes_ok == bytes_seen)},
                "gate_B_control": {"detection_power": powered,
                                   "dimension_controls_moved": sorted(set(dim)),
                                   "passed": bool(powered and dim_ok)},
                "gate_C_semantics": {"sem_checked": sem_checked,
                                     "buckets": dict(sem),
                                     "passed": sem_checked > 0},
                "outcomes_run1": dict(oc),
                "cross_run": {"common_values": common, "disagreements": disagree,
                              "agreement": (f"{common - disagree}/{common}"
                                            if common else "0/0"),
                              "agreement_pct": (round(100.0 * (common - disagree) / common, 2)
                                                if common else None)},
                "moved": moved, "moved_values_sample": moved_vals[:24],
                "distinct_valid_payloads": V,
            }
            out["_arms"][f"{key}@{arm}"] = per_arm[arm]

        rows = list(per_arm.values())
        clean_runs = [r for r in sorted({x for a in per_arm.values() for x in a["runs"]})
                      if (q.get(r) or {}).get("quiet")]
        # ---------------- axis scoring ---------------------------------
        gA = [r for r in rows if r["gate_A_ledger"]["passed"]]
        gB = [r for r in rows if r["gate_B_control"]["passed"]]
        gC = [r for r in rows if r["gate_C_semantics"]["passed"]]
        n_moved_arms = sum(1 for r in rows if r["moved"] > 0)
        agr = [r["cross_run"]["agreement_pct"] for r in rows
               if r["cross_run"]["agreement_pct"] is not None]
        repro_arms = [r for r in rows
                      if r["cross_run"]["agreement_pct"] is not None
                      and r["cross_run"]["agreement_pct"] >= AGREE_BAR
                      and r["moved"] >= 2 * r["cross_run"]["disagreements"]
                      and r["moved"] > 0]
        # A model-CONFIRMING bucket.  For tex_sample.mode that is `correct` (the
        # observation fell in the class the model predicted); for tex_write it is
        # `correct_all_writes_landed` (the store still landed where and with what
        # the host predicted -- which for a descriptor byte is a POSITIVE
        # semantic result, the model "this byte does not redirect the store"
        # being confirmed at that value).
        SEM_OK = ("correct", "correct_all_writes_landed")
        sem_correct = sum(sum(r["gate_C_semantics"]["buckets"].get(b, 0) for b in SEM_OK)
                          for r in rows)
        sem_total = sum(r["gate_C_semantics"]["sem_checked"] for r in rows)

        geometry = ("ledger-verified" if gA and len(gA) == len(rows) else
                    ("ledger-verified(partial)" if gA else "unverified"))
        if not gB:
            liveness = "carrier-undecidable"
        elif n_moved_arms:
            liveness = "live"
        else:
            liveness = "accepted-inert"
        # sec.2: a model that the observations REFUTE is not a bounded map.
        # `bounded-map` requires the pre-registered predictor to have held on
        # EVERY case it made a definite prediction for; anything less is a
        # `hypothesis`, and a hit rate below half is recorded as an explicit
        # refutation of the pre-registered model.
        if sem_total == 0:
            semantics = "unknown"
        elif sem_correct == sem_total:
            semantics = "bounded-map"
        else:
            semantics = "hypothesis"
        model_refuted = bool(sem_total and sem_correct * 2 < sem_total)
        # An INERT field can never pass a MOVEMENT gate, so its reproducibility
        # is scored on cross-run agreement instead (FIELD-SWEEP-PROTOCOL sec.5a:
        # a classifier that reads `moved == 0` as a verdict cannot fail either
        # way; here `moved == 0` simply routes to the agreement test).
        inert_repro = [r for r in rows
                       if r["cross_run"]["agreement_pct"] is not None
                       and r["cross_run"]["agreement_pct"] >= AGREE_BAR]
        basis = repro_arms if liveness == "live" else inert_repro
        repro = ("independently-confirmed" if (basis and len(clean_runs) >= 2)
                 else ("auditable" if basis else "incomplete"))
        # legacy label = the strictest all six axes support
        if (geometry.startswith("ledger-verified") and liveness == "live"
                and semantics == "bounded-map" and repro == "independently-confirmed"):
            legacy = "hardware-run"
        elif (geometry.startswith("ledger-verified") and liveness == "live"
              and semantics == "bounded-map" and repro_arms):
            legacy = "isolated-byte-diff"
        else:
            # RE_EXPERIMENT_PROCESS_CORRECTIONS sec.2, strict mapping:
            # `isolated-byte-diff` "requires a PREDICTED SEMANTIC EFFECT at the
            # tested point, not merely an isolated byte difference", and
            # `hardware-run` requires semantic checks against an independent
            # predictor.  Reproducible liveness with a refuted or absent semantic
            # model therefore maps to the legacy `untested` -- which is NOT "no
            # evidence".  The evidence is in `axes` and `counts`; do not round
            # liveness up into the legacy label.
            legacy = "untested"

        enc = (1 << w) if w <= 8 else None
        disp = max((r["gate_A_ledger"]["distinct_requested_values"] for r in rows),
                   default=0)
        out[key] = {
            "label": legacy,
            "axes": {
                "encoding_geometry": geometry,
                "_pre_registered_semantic_model_refuted": model_refuted,
                "liveness": liveness,
                "semantics": semantics,
                "compiler_recipe": "not-generated",
                "target": "G17P-direct",
                "reproducibility": repro,
            },
            "target": "G17P",
            "evidence": ["EXP-0204"],
            "start": fd["start"], "width": fd["width"],
            "range": (f"0..{enc - 1} dense (all {enc} values) x {len(rows)} arms"
                      if enc else
                      f"{disp} sampled values of 2^{w} (boundaries + powers of two + "
                      f"all-ones prefixes + 16 hashed interior) x {len(rows)} arms"),
            "counts": {
                "encodable_values": enc,
                "dispatched_values_per_arm": disp,
                "distinct_requested_values": disp,
                "distinct_bytes": max((r["gate_A_ledger"]["distinct_actual_encodings"]
                                       for r in rows), default=0),
                "ledger_cases_ok_over_checked":
                    f"{sum(r['gate_A_ledger']['cases_ok'] for r in rows)}/"
                    f"{sum(r['gate_A_ledger']['cases_with_ledger'] for r in rows)}",
                "unreachable_requested_encodings":
                    sum(r["gate_A_ledger"]["unreachable_requested_encodings"] for r in rows),
                "arms": len(rows),
                "arms_with_detection_power": sum(1 for r in rows
                                                 if r["gate_B_control"]["detection_power"]),
                "arms_with_dimension_control_moved": len(gB),
                "arms_where_field_moved": n_moved_arms,
                "moved_total": sum(r["moved"] for r in rows),
                "disagreements_total": sum(r["cross_run"]["disagreements"] for r in rows),
                "cross_run_common_total": sum(r["cross_run"]["common_values"] for r in rows),
                "cross_run_agreement_min": (min(agr) if agr else None),
                "sem_checked_total": sem_total,
                "sem_correct_total": sem_correct,
                "sem_buckets_total": dict(sum(
                    (collections.Counter(r["gate_C_semantics"]["buckets"]) for r in rows),
                    collections.Counter())),
                "outcome_totals_run1": dict(sum(
                    (collections.Counter(r["outcomes_run1"]) for r in rows),
                    collections.Counter())),
                "distinct_valid_payloads_max": max((r["distinct_valid_payloads"]
                                                    for r in rows), default=0),
                "arms_passing_movement_repro_gate": len(repro_arms),
                "arms_at_or_above_99pct_agreement": len(inert_repro),
                "sem_model_hit_rate": f"{sem_correct}/{sem_total}",
                "clean_quiet_runs": clean_runs,
            },
            "gates": {"A": bool(gA), "B": bool(gB), "C": bool(gC),
                      "D": False, "E": bool(len(clean_runs) >= 2 and repro_arms)},
            "dimension": CA.DIMENSION.get(key, ""),
            "arms": [f"{key}@{a}" for a in armlist],
            "note": NOTES.get(key, ""),
        }

    p = os.path.join(HERE, "analysis", "field_verdicts.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote", p)
    for k, v in sorted((k, v) for k, v in out.items()
                       if not k.startswith("_") and "." in k):
        c = v["counts"]
        print(f"  {k:22s} {v['label']:18s} "
              f"geom={v['axes']['encoding_geometry']:26s} live={v['axes']['liveness']:20s} "
              f"sem={v['axes']['semantics']:12s} repro={v['axes']['reproducibility']}")
        print(f"      arms={c['arms']} moved_arms={c['arms_where_field_moved']} "
              f"moved={c['moved_total']} disagree={c['disagreements_total']} "
              f"common={c['cross_run_common_total']} ledger={c['ledger_cases_ok_over_checked']} "
              f"distinct_bytes={c['distinct_bytes']} sem={c['sem_correct_total']}/{c['sem_checked_total']}")


if __name__ == "__main__":
    main()
