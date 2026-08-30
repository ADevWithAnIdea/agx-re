#!/usr/bin/env python3
"""EXP-0161 verdict builder (FIELD-SWEEP-PROTOCOL section 5).

  python3 analysis/verdicts.py

Reads the two gated runs, applies the pre-registered gates, cross-run-gates
every case, applies the lease adjudication (section 7A) where one exists, fits
a semantic model per field, and writes `analysis/field_verdicts.json`.

Nothing here consults `tools/agx-isa/validation.json` in the repo: labels are
compared against the FROZEN copy in `work/frozen/`, which is the one the
hardware ran against (the repo copy drifts while sibling experiments land).

CLEAN-ROOM: analysis of our own captured observations only.
"""
from __future__ import print_function

import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H   # noqa: E402
import cases as CM        # noqa: E402

# Each entry is a GATED PAIR: the same frozen matrix executed twice, in
# opposite arm order. A case counts only if both members agree and neither was
# victim-class.
PAIRS = [("g17p_20260829_run01", "g17p_20260829_run02"),      # the main matrix
         ("g17p_20260830_supp02", "g17p_20260830_supp03"),    # 2nd-carrier arms
         ("g17p_20260830_supp04", "g17p_20260830_supp05")]    # the floor arm
ADJ = EXP / "analysis" / "adjudication.json"
DANGER = sorted((EXP / "raw").glob("g17p_*_danger*/sweep.jsonl"))

VAL = json.loads((H.ISA_DIR / "validation.json").read_text())["instructions"]
GOOD = ("hardware-run", "isolated-byte-diff")
EMIT_GRADE = set(GOOD)


def load(p):
    return [json.loads(l) for l in open(str(p))] if Path(p).exists() else []


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# packings a value can use to name a register (project-standard set)
# ---------------------------------------------------------------------------
PACKINGS = [
    ("(reg<<1)|size  reg=v>>1", lambda v: v >> 1),
    ("reg<<2         reg=v>>2", lambda v: v >> 2),
    ("reg=v&0x7F", lambda v: v & 0x7F),
    ("reg=(v>>1)&0x3F", lambda v: (v >> 1) & 0x3F),
    ("reg=v&0x0F", lambda v: v & 0x0F),
    ("reg=v (identity)", lambda v: v),
]


def fit_packing(obs):
    """obs: {value -> register}. Returns the best packing name + fit count."""
    best = (None, -1, 0)
    for name, fn in PACKINGS:
        hit = sum(1 for v, r in obs.items() if fn(v) == r)
        if hit > best[1]:
            best = (name, hit, len(obs))
    return {"packing": best[0], "fit": best[1], "of": best[2]}


def fit_mask(accepted, universe):
    """Smallest (mask, const) with (v & mask) == const fitting `accepted`
    EXACTLY over `universe`. Returns None if no such rule exists."""
    acc = set(accepted)
    if not acc or acc == set(universe):
        return None
    best = None
    for mask in range(256):
        cs = set(v & mask for v in acc)
        if len(cs) != 1:
            continue
        c = cs.pop()
        if all((v & mask) != c for v in universe if v not in acc):
            nbits = bin(mask).count("1")
            if best is None or nbits < best[0]:
                best = (nbits, mask, c)
    if best is None:
        return None
    return {"rule": "(v & 0x%02X) == 0x%02X" % (best[1], best[2]),
            "dont_care_bits": [i for i in range(8) if not (best[1] >> i) & 1],
            "n_accepted": len(acc)}


# ---------------------------------------------------------------------------
# Corrected models. FIELD-SWEEP-PROTOCOL section 6: recorded HERE, never written
# into db.json -- the orchestrator owns that file.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Fields whose INERTNESS has a KNOWN alternative explanation, so "inert in two
# carriers" is NOT two independent observations. Forced to `untested` no matter
# what the mechanical rule says: promoting them would put a confident label on
# a field our carriers are blind to, which is precisely the silent-zero bug
# FIELD-SWEEP-PROTOCOL section 5 warns about.
# ---------------------------------------------------------------------------
CONFOUNDED_INERT = {
 "fspecial_est.srcA":
   "inert over all 256 values in BOTH carriers -- but both are PRECISE "
   "(Newton-Raphson) reciprocal lowerings, and NR converges to the correct "
   "result from a wrong seed, so the observable is blind to the seed op's "
   "operand. The two carriers SHARE the confound, so they are one observation, "
   "not two. The prior M4 label (isolated-byte-diff, EXP-0154) stands; this is "
   "a statement about our carriers, not a retraction.",
 "fspecial_est.subop":
   "same confound: 0x09/0x0b/0x0d select rcp/rsqrt/sqrt ESTIMATE, and every "
   "value of the byte still yields the correct refined result because the NR "
   "iteration corrects it. The prior M4 `hardware-run` label (EXP-0138, dense "
   "0..255) stands untouched; a carrier that can SEE the seed (reading the "
   "estimate register directly, as EXP-0026 did) is what a successor needs.",
 "ibfe.sign_ext":
   "inert in both carriers -- but db.json's own model says signed extract "
   "requires BOTH this bit AND clearing srcC_flags bit0 (b9 0x11 -> 0x10). "
   "This experiment swept the bit alone and never the pair, so inertness here "
   "is exactly what db.json predicts and proves nothing about the field. The "
   "prior label stands.",
}

DB_DEFECTS = {
 "DEF-0161-1": {
  "instr": "fspecial", "severity": "emitter-breaking",
  "db_says": "dst = byte+1 high nibble (GPR); src = byte+3 (reg low); "
             "src_ext = byte+5 (reg ext)",
  "hardware_says":
      "byte+3 (db `src`) is the DESTINATION register, packed (reg<<1)|size, "
      "reg = v>>1. byte+5 (db `src_ext`) is the SOURCE register, packed reg<<2, "
      "reg = v>>2 (low two bits don't-care). byte+1's high nibble (db `dst`) is "
      "HW-TESTED INERT: all 16 values reproduce the unmutated result exactly in "
      "BOTH the synthesized and the natural carrier, and the result always lands "
      "in the same register.",
  "how_established":
      "(a) 16-register dumps: sweeping byte+5 moves which register is READ (and "
      "released to zero) in blocks of 4 values, and the computed rsqrt matches "
      "that register's seed exactly; sweeping byte+3 moves which register "
      "RECEIVES the result in blocks of 2. (b) the INPLACE functional oracle "
      "agrees. (c) 20/20 GENERATED encodings `r_i = rsqrt(r_j)` for arbitrary "
      "i,j, predicted host-side before dispatch, all pass.",
  "consequence_if_unfixed":
      "an emitter following db.json puts the destination in a byte that does "
      "nothing and the source in the byte that redirects the destination -- the "
      "program runs, faults nothing, and silently writes the wrong register.",
  "explains": "EXP-0138's byte+3 observations ('only 2 and 3 give the correct "
              "rsqrt; 188 values silently return 0.0; 6 and 7 leave the poison "
              "intact') are exactly what a DESTINATION selector does in a "
              "carrier whose store reads r1.",
  "evidence": ["raw/g17p_20260829_run01", "raw/g17p_20260829_run02",
               "raw/g17p_20260830_gen03", "analysis/fspecial_function_map.json"]},
 "DEF-0161-2": {
  "instr": "mov_zext16", "severity": "emitter-breaking",
  "db_says": "byte0 is a fixed 8-bit match == 0x13; byte+1 bits0-6 = source "
             "register, bit7 = uniform/special-file flag",
  "hardware_says":
      "byte0's HIGH NIBBLE is a REGISTER field. The instruction is "
      "`r[n] = r[n] & 0xFFFF` -- one register, used as BOTH source and "
      "destination. n = 0..10 are reachable (nibbles 0x0..0xA); nibbles "
      "0xB..0xF execute as a no-op. byte+1 is therefore NOT a source-register "
      "selector: all 128 values of bits0-6 and both values of bit7 reproduce "
      "the result exactly, in a carrier where the instruction is demonstrably "
      "live (its byte0 falsifier fires) and where ALU forwarding cannot explain "
      "it (fifteen loads and a store separate the source from the instruction).",
  "how_established":
      "16-register dumps over a dense byte0 sweep: byte0 = 0xN3 narrows r[N] "
      "and nothing else; plus 11/16 GENERATED `r[n] = r[n] & 0xFFFF` encodings "
      "passing a host-computed 16-register prediction.",
  "resolves": "EXP-0146 left byte+1's inertness OPEN between (a) it is not a "
              "source-register selector and (b) the operand was ALU-forwarded "
              "from the preceding device_load. This is (a).",
  "evidence": ["raw/g17p_20260829_run01", "raw/g17p_20260829_run02",
               "raw/g17p_20260830_gen03"]},
 "DEF-0161-3": {
  "instr": "fspecial", "severity": "model refinement",
  "db_says": "fnclass is a 4-bit opcode with 5 enumerated values",
  "hardware_says":
      "on the standard-SFU datapath (byte+6/+7 = 0xb0/0x40) only the LOW TWO "
      "BITS of the nibble are live: values 1,3,5,7,9,11,13,15 all compute the "
      "same function. Measured by COMPUTED VALUE, not by byte pattern: with "
      "byte0 = 0xaf, (fnclass & 3) == 1 -> rsqrt and == 2 -> exp2; with "
      "byte0 = 0x2f, == 0 -> rint, == 1 -> rsqrt, == 2 -> log2. So `fn_hi` "
      "selects log2 vs exp2 at class 2, exactly as db.json's enum says, and "
      "that enum is now HW-confirmed on G17P by the value the SFU produced.",
  "evidence": ["analysis/fspecial_function_map.json"]},
 "DEF-0161-4": {
  "instr": "fspecial", "severity": "emitter-critical safety",
  "db_says": "roundmode (byte+8): 0 nearest / 2 floor / 4 ceil / 6 trunc, or "
             "0x20 = reciprocal precision flag",
  "hardware_says":
      "on the rsqrt (0xaf) and log2 (0x2f) SFU datapaths only BIT 0 of byte+8 "
      "is live, and setting it makes the instruction return NaN for EVERY "
      "input -- 128 of 256 values, all-NaN in 12/12 output lanes, in three "
      "independent carriers. All 128 even values reproduce the correct result "
      "to >= 24 good mantissa bits. The round-mode enum is a property of the "
      "ROUND family, not of byte+8 in general.",
  "analysis_bug_disclosed":
      "the first version of analysis/fspecial_functions.py matched these NaN "
      "vectors as a '~1% low-precision estimate', because every "
      "`abs(nan - w) > tol` comparison is False in IEEE semantics. The NaN "
      "guard is the fix and the claim above is the corrected reading.",
  "evidence": ["analysis/sfu_precision.json", "analysis/fspecial_function_map.json"]},
 "DEF-0161-5": {
  "instr": "device_store / device_load (scoreboard_model)",
  "severity": "emitter-relevant hardware hazard",
  "db_says": "scoreboard_model: G17P has a hardware register interlock; "
             ">= 20 independent device loads may be outstanding, 'all consumed "
             "correctly with no wait' (EXP-0025 manyload20)",
  "hardware_says":
      "that holds for ALU consumers. It does NOT hold for a `device_store` "
      "consumer: with a single wave of 15 loads, the registers read by the "
      "FIRST ~5 STORES issued afterwards come back with their PRE-LOAD value. "
      "The effect follows the STORE order, not the load order -- dumping "
      "r15..r0 instead of r0..r15 moved the stale set from r0..r4 to r11..r14 "
      "-- and it reproduces with only 5 loads outstanding.",
  "how_established": "harness/pilot_seed.py, 8 controlled variants (P1..P8), "
                     "raw/prefreeze/pilot_seed.json",
  "workaround_used_here": "two load waves plus 6 drain stores; verified 15/15 "
                          "correct and stable over 8 consecutive dispatches",
  "evidence": ["raw/prefreeze/pilot_seed.json", "raw/prefreeze/smoke_postfix.json"]},
 "DEF-0161-6": {
  "instr": "carry_gen", "severity": "decode over-constraint (REPRODUCES EXP-0146)",
  "db_says": "byte+2 is pinned to the full byte 0x35",
  "hardware_says":
      "only (v & 0xCD) == 0x05 is required: bits 1, 4 and 5 are DON'T-CARE and "
      "8 of 256 values work -- {0x05,0x07,0x15,0x17,0x25,0x27,0x35,0x37}. "
      "IDENTICAL to EXP-0146's M4 result, in BOTH of this experiment's carriers. "
      "A G16G -> G17P reproduction, not a new claim. Relaxing the match is a "
      "DECODE change and stays deferred to a corpus A/B.",
  "evidence": ["raw/g17p_20260829_run01", "raw/g17p_20260829_run02"]},
 "DEF-0161-7": {
  "instr": "carry_gen", "severity": "semantics extension",
  "db_says": "p[dst] = (r[srcA] <u r[srcB]); operand packing inferred",
  "hardware_says":
      "the low bit of each operand byte is a real SIZE bit. With it SET the "
      "compare is 32-bit; with it CLEAR the hardware compares only the LOW 16 "
      "BITS. Established the hard way: 16 generated encodings built with "
      "is32 = 0 while predicting a 32-bit compare failed 9 of 16, and ALL 16 "
      "outcomes are explained exactly by the 16-bit rule. The corrected model "
      "then passed 48/48 generated encodings across both widths and both "
      "settings of the inert bit 7.",
  "evidence": ["raw/g17p_20260830_gen02", "raw/g17p_20260830_gen03"]},
}


def main():
    adj = json.loads(ADJ.read_text()) if ADJ.exists() else {}
    adjmap = dict((int(k), v) for k, v in adj.get("cases", {}).items())

    gates, agreed, disagree = {}, {}, []
    victims = 0
    used_pairs, n_cases = [], 0
    for (n1, n2) in PAIRS:
        r1 = load(EXP / "raw" / n1 / "sweep.jsonl")
        r2 = load(EXP / "raw" / n2 / "sweep.jsonl")
        if not r1 or not r2:
            continue
        used_pairs.append([n1, n2])
        n_cases += len(r1)
        i1 = dict((r["idx"], r) for r in r1)
        i2 = dict((r["idx"], r) for r in r2)
        for arm in sorted(set(r["arm"] for r in r1)):
            g = {}
            for r in r1:
                if r["arm"] == arm and (r["field"].startswith("__falsifier")
                                        or r["field"] == "__baseline"):
                    o2 = i2[r["idx"]]["outcome"]
                    g[r["field"]] = {"runA": r["outcome"], "runB": o2,
                                     "victim": r["victim"] or i2[r["idx"]]["victim"]}
            g["pair"] = [n1, n2]
            g["baseline_ok"] = g.get("__baseline", {}).get("runA") == "ok" and \
                g.get("__baseline", {}).get("runB") == "ok"
            fals = [k for k in g if k.startswith("__falsifier")]
            g["falsifiers_fired"] = all(
                g[k]["runA"] != "ok" and g[k]["runB"] != "ok" for k in fals)
            g["USABLE"] = bool(g["baseline_ok"] and g["falsifiers_fired"] and fals)
            gates[arm] = g
        for idx, a in i1.items():
            b = i2.get(idx)
            if b is None:
                continue
            key = (n1, idx)
            if a["victim"] or b["victim"]:
                victims += 1
                continue
            if a["outcome"] != b["outcome"]:
                disagree.append({"pair": n1, "idx": idx, "arm": a["arm"],
                                 "field": a["field"], "value": a["value"],
                                 "runA": a["outcome"], "runB": b["outcome"]})
                continue
            oc = a["outcome"]
            if n1 == PAIRS[0][0] and idx in adjmap:
                oc = adjmap[idx]["final"]
            agreed[key] = (a, oc)
    meta = {"gated_pairs": used_pairs, "cases_per_run": n_cases, "target": "G17P",
            "fault_adjudication": (ADJ.name if ADJ.exists() else "NOT RUN"),
            "n_adjudicated": adj.get("_meta", {}).get("n_adjudicated"),
            "n_adjudication_changed": adj.get("_meta", {}).get("n_changed")}
    meta["gates"] = gates
    meta["cross_run"] = {"agreed": len(agreed), "victim_excluded": victims,
                         "disagreements": len(disagree)}
    meta["cross_run_disagreements"] = disagree[:200]

    # ---- per-field statistics -------------------------------------------
    stats = defaultdict(lambda: defaultdict(dict))     # arm -> field -> value -> (rec,oc)
    for idx, (rec, oc) in agreed.items():
        stats[rec["arm"]][rec["field"]][rec["value"]] = (rec, oc)

    ARM = dict((a["arm"], a) for a in
               list(CM.ARMS) + list(CM.SUPP_ARMS) + list(CM.SUPP2_ARMS)
               + [CM.DANGER_ARM])
    out = {}
    notes = {}

    # semantic recovery, per arm, from the SYNTH 16-register dumps
    sem = {}
    for arm in stats:
        if ARM.get(arm, {}).get("style") != "synth":
            continue
        bl = stats[arm].get("__baseline", {}).get(0)
        if not bl or not bl[0].get("observed"):
            continue
        base = bl[0]["observed"]["regs"]
        seeds = H.seeds_for(ARM[arm]["kind"])
        for field, vals in stats[arm].items():
            if field.startswith("__"):
                continue
            released, destmap = {}, {}
            for v, (rec, oc) in sorted(vals.items()):
                o = rec.get("observed")
                if not o or not o.get("regs"):
                    continue
                rg = o["regs"]
                # register the mutated instruction RELEASED (read): non-zero in
                # the baseline dump, zero here, and not zero in the baseline
                rel = [i for i in range(15)
                       if rg[i] == 0 and base[i] != 0]
                # register that RECEIVED the baseline's result value
                res = base[0]
                dst = [i for i in range(1, 15)
                       if rg[i] == res and base[i] != res]
                if len(rel) == 1:
                    released[v] = rel[0]
                if len(dst) == 1:
                    destmap[v] = dst[0]
            s = {}
            if len(released) >= 6:
                s["released_register_map"] = fit_packing(released)
                s["released_examples"] = dict(list(sorted(released.items()))[:8])
            if len(destmap) >= 6:
                s["destination_register_map"] = fit_packing(destmap)
                s["destination_examples"] = dict(list(sorted(destmap.items()))[:8])
            if s:
                sem["%s.%s" % (arm, field)] = s
    meta["semantic_maps"] = sem

    # ---- verdict per (instr, field) -------------------------------------
    perfield = defaultdict(lambda: defaultdict(dict))   # instr -> field -> arm -> info
    for arm in stats:
        instr = ARM[arm]["instr"]
        for field, vals in stats[arm].items():
            if field.startswith("__base") or field.startswith("__falsifier"):
                continue
            cnt = Counter(oc for (_, oc) in vals.values())
            accepted = sorted(v for v, (_, oc) in vals.items() if oc == "ok")
            universe = sorted(vals.keys())
            info = {"arm": arm, "style": ARM.get(arm, {}).get("style", "inplace"),
                    "n": len(vals), "outcomes": dict(cnt),
                    "n_accepted": len(accepted),
                    "accepted": accepted if len(accepted) <= 40 else
                                accepted[:40] + ["...(%d)" % len(accepted)],
                    "range_lo": universe[0], "range_hi": universe[-1]}
            m = fit_mask(accepted, universe)
            if m:
                info["accept_rule"] = m
            k = "%s.%s" % (arm, field)
            if k in sem:
                info["semantics"] = sem[k]
            perfield[instr][field][arm] = info

    # the DANGER arm is single-run by design (each case resets the device, so a
    # second full run is not a proportionate cost); it is reported separately
    # and never enters the cross-run-gated verdicts.
    danger = {}
    for p in DANGER:
        rs = load(p)
        cnt = Counter(r["outcome"] for r in rs)
        oshang = sum(1 for r in rs for a in r["attempts"]
                     if a["error"] and "ErrorHang" in a["error"])
        first_att = Counter(
            ("ErrorHang" if (r["attempts"][0]["error"] or "").find("ErrorHang") >= 0
             else ("InnocentVictim" if r["attempts"][0]["victim"]
                   else r["attempts"][0]["status"]))
            for r in rs if r["attempts"])
        # A case is only CLEANLY OBSERVED if at least one of its attempts
        # produced OUR OWN `...ErrorHang` rather than a neighbour's
        # `...InnocentVictim`. In a region where every value resets the device,
        # a case's neighbours swamp it -- so this split is load-bearing and is
        # reported, not smoothed over.
        per = {}
        for r in rs:
            if r["field"] != "src":
                continue
            per[r["value"]] = sum(1 for a in r["attempts"]
                                  if "ErrorHang" in (a["error"] or ""))
        clean = sorted(v for v, n in per.items() if n)
        dirty = sorted(v for v, n in per.items() if not n)
        danger[p.parent.name] = {
            "cases": len(rs), "outcomes": dict(cnt),
            "os_ErrorHang_attempts": oshang,
            "attempts_per_case": 3,
            "first_attempt_classification": dict(first_att),
            "swept_values": [min(per), max(per)] if per else None,
            "n_values": len(per),
            "values_with_a_GENUINE_ErrorHang": len(clean),
            "values_NEVER_CLEANLY_OBSERVED": dirty,
            "n_never_cleanly_observed": len(dirty),
            "values_that_WORKED": [v for v, n in
                                   ((r["value"], r["outcome"]) for r in rs
                                    if r["field"] == "src") if n == "ok"],
            "watchdog_hangs": cnt.get("hang", 0),
            "reading": "%d of %d values in the swept region produced a genuine "
                       "contained ErrorHang; %d were never cleanly observed "
                       "(all three attempts were victim-class, swamped by their "
                       "neighbours' resets). NO value in the region was ever "
                       "observed to work."
                       % (len(clean), len(per), len(dirty))}
    meta["danger_arm"] = danger

    for instr in sorted(perfield):
        for field in sorted(perfield[instr]):
            arms = perfield[instr][field]
            usable = dict((a, v) for a, v in arms.items() if gates[a]["USABLE"])
            key = "%s.%s" % (instr, field)
            fdef = [f for f in CM.INS[instr]["fields"] if f["name"] == field]
            width = fdef[0]["width"] if fdef else None
            prior = VAL.get(instr, {}).get(field, {})
            if not usable:
                out[key] = {"label": "untested", "target": "G17P",
                            "evidence": ["EXP-0161"],
                            "range": "swept, but no carrier passed its gate",
                            "note": "arms %s all failed the pre-registered "
                                    "falsifier/baseline gate; per PRE_REGISTRATION "
                                    "section 6 nothing is promoted from them"
                                    % sorted(arms), "arms": arms,
                            "prior_label": prior.get("label", "untested")}
                continue
            # coverage: dense over the whole encodable range?
            dense = all(v["n"] >= (1 << width) * 0.75 for v in usable.values()) \
                if width else False
            full = all(v["range_lo"] == 0 and v["range_hi"] == (1 << width) - 1
                       for v in usable.values()) if width else False
            # discrimination: does ANY usable arm see more than one outcome?
            multi = any(len(v["outcomes"]) > 1 for v in usable.values())
            inert = all(set(v["outcomes"]) == {"ok"} for v in usable.values())
            semk = [k for k in sem if k.split(".", 1)[1] == field
                    and k.split(".", 1)[0] in usable]
            has_sem = any("released_register_map" in sem[k]
                          or "destination_register_map" in sem[k] for k in semk)
            if key in CONFOUNDED_INERT:
                out[key] = {"label": "untested", "target": "G17P",
                            "evidence": ["EXP-0161"],
                            "range": " / ".join(
                                "%s: %d..%d (%d values)"
                                % (a, v["range_lo"], v["range_hi"], v["n"])
                                for a, v in sorted(usable.items())),
                            "note": "NOT PROMOTED. " + CONFOUNDED_INERT[key],
                            "arms": arms,
                            "prior_label": prior.get("label", "untested"),
                            "prior_target": prior.get("target", "")}
                continue
            if multi and dense:
                label = "hardware-run"
            elif inert and len(usable) >= 2 and dense:
                label = "hardware-run"      # inert confirmed in >=2 carriers
            elif multi:
                label = "isolated-byte-diff"
            else:
                label = "untested"
            rng = " / ".join("%s: %d..%d (%d values%s)"
                             % (a, v["range_lo"], v["range_hi"], v["n"],
                                ", dense" if width and v["n"] == (1 << width) else "")
                             for a, v in sorted(usable.items()))
            note = []
            if inert:
                note.append("HW-TESTED INERT over the whole swept range in %d "
                            "independent carrier%s (%s): every value reproduces "
                            "the unmutated result exactly. Role UNKNOWN -- an "
                            "emitter may use any value, but must NOT synthesize "
                            "a meaning for it.%s"
                            % (len(usable), "" if len(usable) == 1 else "s",
                               ", ".join(sorted(usable)),
                               "" if len(usable) >= 2 else
                               " NOT PROMOTED: one carrier is not enough for an "
                               "INERT field -- the falu2.srcA_reg_top precedent "
                               "needed six families before the project would say "
                               "'any value is safe'. The prior label stands."))
            for a, v in sorted(usable.items()):
                if "accept_rule" not in v and 0 < v["n_accepted"] <= 12:
                    note.append("%s: accepted set is %s (no mask rule fits)"
                                % (a, v["accepted"]))
            for a, v in sorted(usable.items()):
                if "accept_rule" in v:
                    note.append("%s: accepted set fits %s (%d of %d values)"
                                % (a, v["accept_rule"]["rule"],
                                   v["accept_rule"]["n_accepted"], v["n"]))
            for k in semk:
                s = sem[k]
                for nm in ("released_register_map", "destination_register_map"):
                    if nm in s and s[nm]["fit"] >= max(6, int(0.8 * s[nm]["of"])):
                        note.append("%s: %s -> %s, fit %d/%d"
                                    % (k, nm.replace("_", " "),
                                       s[nm]["packing"], s[nm]["fit"], s[nm]["of"]))
            out[key] = {"label": label, "target": "G17P",
                        "evidence": ["EXP-0161"], "range": rng,
                        "note": " | ".join(note), "arms": arms,
                        "prior_label": prior.get("label", "untested"),
                        "prior_target": prior.get("target", "")}

    # ---- emittability ----------------------------------------------------
    emit = {}
    for instr in sorted(set(list(perfield.keys()))):
        fields = [f["name"] for f in CM.INS[instr]["fields"]]
        rows = {}
        for f in fields:
            k = "%s.%s" % (instr, f)
            new = out.get(k, {}).get("label")
            old = VAL.get(instr, {}).get(f, {}).get("label", "untested")
            oldt = VAL.get(instr, {}).get(f, {}).get("target", "")
            rows[f] = {"prior": old, "prior_target": oldt, "this_exp": new,
                       "best": new if (new in EMIT_GRADE) else old,
                       "grade_from": ("EXP-0161 / G17P" if new in EMIT_GRADE
                                      else ("prior / %s" % (oldt or "?")
                                            if old in EMIT_GRADE else "NONE"))}
        blocking = [f for f, v in rows.items() if v["best"] not in EMIT_GRADE]
        defects = [k for k, v in DB_DEFECTS.items()
                   if v["instr"].split(" /")[0] == instr
                   and "emitter" in v["severity"]]
        emit[instr] = {"fields": rows, "blocking_before":
                       [f for f in fields
                        if VAL.get(instr, {}).get(f, {}).get("label", "untested")
                        not in EMIT_GRADE],
                       "blocking_after": blocking,
                       "EMITTABLE_AFTER": not blocking,
                       "descriptor_defects_that_must_be_fixed_first": defects,
                       "fields_at_grade_only_via_a_NON_G17P_prior_label":
                           [f for f, v in rows.items()
                            if v["grade_from"].startswith("prior")
                            and "G17P" not in v["grade_from"]],
                       "caveat": ("EMITTABLE ONLY AFTER %s is applied to "
                                  "db.json: every field is at emitter grade, "
                                  "but the descriptor as committed would make "
                                  "an emitter write the WRONG REGISTER without "
                                  "faulting." % ", ".join(defects))
                       if (defects and not blocking) else ""}
    meta["emittability"] = emit

    # ---- generation proof -------------------------------------------------
    gen = {}
    for p in sorted((EXP / "raw").glob("g17p_*_gen*/sweep.jsonl")):
        rs = load(p)
        c = Counter((r.get("gen"), r.get("verdict")) for r in rs if r.get("verdict"))
        per = defaultdict(Counter)
        for r in rs:
            if r.get("verdict"):
                per[r["gen"]][r["verdict"]] += 1
        gen[p.parent.name] = dict((k, dict(v)) for k, v in per.items())
    meta["generation_proof"] = gen

    doc = {"_meta": meta, "verdicts": out}
    (EXP / "analysis" / "field_verdicts_raw.json").write_text(
        json.dumps(doc, indent=1, sort_keys=True))

    # ---- protocol section 5 output ---------------------------------------
    slim, rawprobes = {}, {}
    for k, v in out.items():
        rec = {"label": v["label"], "range": v["range"], "target": "G17P",
               "evidence": ["EXP-0161"], "note": v["note"],
               "prior_label": v.get("prior_label"),
               "prior_target": v.get("prior_target")}
        if ".__raw_b" in k:
            rawprobes[k] = rec
        else:
            slim[k] = rec
    final = {"_meta": {k: meta[k] for k in
                       ("gated_pairs", "cases_per_run", "target",
                        "fault_adjudication", "n_adjudicated",
                        "n_adjudication_changed", "cross_run", "gates",
                        "danger_arm", "generation_proof", "semantic_maps",
                        "cross_run_disagreements") if k in meta},
             "verdicts": slim,
             "raw_byte_probes": rawprobes,
             "emittability": meta["emittability"],
             "db_defects": DB_DEFECTS}
    (EXP / "analysis" / "field_verdicts.json").write_text(
        json.dumps(final, indent=1, sort_keys=True))
    print("== gates")
    for a in sorted(gates):
        print("  %-18s baseline_ok=%-5s falsifiers_fired=%-5s USABLE=%s"
              % (a, gates[a]["baseline_ok"], gates[a]["falsifiers_fired"],
                 gates[a]["USABLE"]))
    print("== cross-run:", meta["cross_run"])
    print("== verdict labels:", dict(Counter(v["label"] for v in out.values())))
    for instr in sorted(emit):
        print("  %-14s blocking %d -> %d  EMITTABLE=%s"
              % (instr, len(emit[instr]["blocking_before"]),
                 len(emit[instr]["blocking_after"]),
                 emit[instr]["EMITTABLE_AFTER"]))
    return doc, slim


if __name__ == "__main__":
    main()
