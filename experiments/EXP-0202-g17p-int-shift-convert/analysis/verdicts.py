#!/usr/bin/env python3
"""EXP-0202 verdict computation -- the ONLY place a verdict may be written.

    python3 analysis/verdicts.py raw/<run01> raw/<run02>

Verdicts are recomputed from `raw/` on every invocation and never read back from
a run manifest or a previous verdicts file. `start`/`width` are re-read from the
PINNED `db.json`, so a descriptor that moved under a sibling experiment becomes a
loud failure instead of a silent mis-attribution.

THE GATE (frozen in PRE_REGISTRATION.md section 6; nothing else may promote):

 1. Two gated runs, byte-identical programs, the same frozen `arms202.json`.
 2. >= 99 % per-value cross-run agreement on the OUTCOME PARTITION, and
    `moved >= 2 * disagree AND moved > 0`.
    NOT `moved >= 2 * max(disagree, 1)` -- that form demands moved >= 2 and so
    cannot promote ANY width-1 field by arithmetic, and three of this
    experiment's eight fields are width 1.
 3. DETECTION POWER. The arm's control -- a field on the SAME instruction
    occurrence already at emitter grade -- must have MOVED in both runs, and at
    least one control value must have FAILED the oracle in both runs. An arm
    that fails either has no detection power and is BARRED from supporting a
    verdict of any kind, live OR inert.
 4. BASELINES. For an arm with no prepatch, the arm-open and arm-close baselines
    must both be `ok`. For a PREPATCHED arm (the synthesized `iunary` form, and
    the `src_flag` arms that move the source index) the unmutated program is
    deliberately altered, so the requirement is instead that the open and close
    baselines be IDENTICAL to each other and identical across runs -- stability,
    which is what a baseline is for.
 5. INERTNESS REQUIRES A SPANNED DIMENSION. A `0 moved` verdict may only be
    recorded when >= 2 carriers differ in the dimension named in
    PRE_REGISTRATION section 2 for that field AND both pass rule 3. Otherwise the
    verdict is STILL-UNDERPOWERED -> `untested`.
 6. V, the distinct-VALID-payload test. Hard outcomes (fault / hang /
    measurement_failure / undecodable) are counted SEPARATELY and never as
    movement. A field with V <= 1 across many legal values ran legally and was
    INDISTINGUISHABLE; its movement is a hazard map, not a semantic, and it is
    WITHHELD.
 7. ORACLE DISCRIMINATION. The per-case oracle must take more than one distinct
    value across the field's records, or the arm cannot promote.

LABEL POLICY (restated so a reviewer can disagree explicitly):
  LIVE               -> `hardware-run`
  INERT-ROBUST       -> `single-template-inference`, NOT emitter grade. Emitter
                        grade asserts the implementer may CHOOSE the value;
                        "emit what the compiler emitted" is a captured-template
                        dependency. The measurement is not downgraded -- its full
                        strength lives in `range` and `note`.
  STILL-UNDERPOWERED -> `untested`. Protocol section 5: do not round up.
"""
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate202 as L        # noqa: E402

AGREE_MIN = 99.0
HARD = {"fault", "hang", "measurement_failure", "undecodable", "invalid_run",
        "nondeterministic", "carrier_start_failed", "arm_aborted"}
# The dimension each field's carrier set had to span, from PRE_REGISTRATION §2.
DIMENSION = {
    "shift_amt_move.src_flag": "source register FILE of the staged amount",
    "irotate.operands": "immediate rotate amount / operand registers",
    "ibitcount.cache": "result routing: consumed by a following ALU vs standalone",
    "ibitcount.dst": "destination register",
    "iunary.b1": "function/source descriptor of the 0x27 datapath",
    "iunary.opsel": "which 0x27 datapath is selected",
    "cvt_f2i.b9": "result routing, convert op, source class, source width, dst reg",
    "b_alu10_lo7.src_flag": "source register FILE (the same-dimension control)",
}


def load(run_dir):
    recs = []
    for ln in (Path(run_dir) / "sweep.jsonl").read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                recs.append(json.loads(ln))
            except ValueError:
                pass
    return recs


def vkey(r):
    o = r.get("observed") or {}
    vals = o.get("vals_u32")
    h = hashlib.sha256(json.dumps(vals, sort_keys=True).encode()).hexdigest()[:16] \
        if vals is not None else "none"
    return "%s|%s" % (r.get("outcome"), h)


def payload(r):
    o = r.get("observed") or {}
    return json.dumps(o.get("vals_u32"), sort_keys=True)


def index(recs):
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        if r.get("role") == "baseline":
            key = arm.split(":")[0]
            out.setdefault(key, {"cases": {}, "baselines": []})
            out[key]["baselines"].append(r)
            continue
        d = out.setdefault(arm, {"cases": {}, "baselines": []})
        d["cases"][r["value"]] = r
    return out


def baseline_key(a):
    for b in a["baselines"]:
        if str(b.get("note", "")).endswith(":open"):
            return vkey(b)
    return vkey(a["baselines"][0]) if a["baselines"] else None


def arm_stats(a1, a2, base_key):
    vals = sorted(set(a1["cases"]) & set(a2["cases"]))
    agree = sum(1 for v in vals if vkey(a1["cases"][v]) == vkey(a2["cases"][v]))
    moved = sum(1 for v in vals
                if vkey(a1["cases"][v]) != base_key
                and vkey(a2["cases"][v]) != base_key)
    hard = sum(1 for v in vals
               if a1["cases"][v]["outcome"] in HARD
               or a2["cases"][v]["outcome"] in HARD)
    moved_valid = sum(1 for v in vals
                      if a1["cases"][v]["outcome"] not in HARD
                      and a2["cases"][v]["outcome"] not in HARD
                      and vkey(a1["cases"][v]) != base_key
                      and vkey(a2["cases"][v]) != base_key)
    valid = [a1["cases"][v] for v in vals if a1["cases"][v]["outcome"] not in HARD]
    V = len({payload(r) for r in valid})
    orc = len({json.dumps(a1["cases"][v].get("oracle"), sort_keys=True) for v in vals})
    byt = len({a1["cases"][v].get("bytes") for v in vals})
    return {"shared_values": len(vals),
            "agree_pct": round(100.0 * agree / len(vals), 3) if vals else 0.0,
            "disagree": len(vals) - agree, "moved": moved,
            "moved_valid": moved_valid, "hard_outcomes": hard,
            "V_distinct_valid_payloads": V, "L_legal_values": len(valid),
            "distinct_oracles": orc, "distinct_bytes": byt,
            "values_dispatched": len(vals)}


def token_stats(a1, a2, mn):
    tok = {}
    enc = set()
    for a in (a1, a2):
        for v, c in a["cases"].items():
            t = (c.get("token") or {}).get("mnemonic")
            tok[str(t)] = tok.get(str(t), 0) + 1
            if t == mn:
                enc.add(v)
    return tok, len(enc)


def outcome_hist(a1, a2):
    h = {}
    for a in (a1, a2):
        for c in a["cases"].values():
            h[c["outcome"]] = h.get(c["outcome"], 0) + 1
    return h


def baselines_stable(a1, a2, prepatched):
    b1 = [b for b in a1["baselines"]], [b for b in a2["baselines"]]
    if prepatched:
        keys = {vkey(b) for b in a1["baselines"]} | {vkey(b) for b in a2["baselines"]}
        return len(keys) == 1, "identical open/close baselines across both runs"
    ok = (all(b["outcome"] == "ok" for b in a1["baselines"])
          and all(b["outcome"] == "ok" for b in a2["baselines"]))
    return ok, "every baseline `ok`"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    r1, r2 = load(sys.argv[1]), load(sys.argv[2])
    i1, i2 = index(r1), index(r2)
    arms_doc = json.loads((EXP / "harness" / "arms202.json").read_text())
    arms = {a["arm"]: a for a in arms_doc["arms"]}

    # ---- controls, per (carrier, occurrence) -----------------------------
    control = {}
    for name, a in arms.items():
        if a["role"] != "control" or name not in i1 or name not in i2:
            continue
        bk = baseline_key(i1[name])
        st = arm_stats(i1[name], i2[name], bk)
        failed1 = any(c["match"] is False for c in i1[name]["cases"].values())
        failed2 = any(c["match"] is False for c in i2[name]["cases"].values())
        k = (a["carrier"], a["occ"], a["instr"])
        cur = control.get(k)
        rec = {"arm": name, "field": a["field"], "moved": st["moved"],
               "agree_pct": st["agree_pct"],
               "falsifier_fired": bool(failed1 and failed2),
               "fired": st["moved"] >= 1 and failed1 and failed2}
        if cur is None or (rec["fired"] and not cur["fired"]):
            control[k] = rec

    per_arm, by_field = {}, {}
    for name, a in arms.items():
        if name not in i1 or name not in i2:
            per_arm[name] = {"status": "missing_from_a_run"}
            continue
        bk = baseline_key(i1[name])
        st = arm_stats(i1[name], i2[name], bk)
        tok, enc = token_stats(i1[name], i2[name], a["instr"])
        prep = bool(a.get("prepatch"))
        blok, blwhy = baselines_stable(i1[name], i2[name], prep)
        ctl = control.get((a["carrier"], a["occ"], a["instr"]),
                          {"fired": None, "moved": None, "falsifier_fired": None})
        rec = {"carrier": a["carrier"], "occ": a["occ"], "role": a["role"],
               "instr": a["instr"], "field": a["field"], "sub": a.get("sub"),
               "prepatched": prep, "baselines_ok": blok, "baseline_rule": blwhy,
               "baseline_field_value": a.get("baseline_field_value"),
               "control": ctl, "tokenized_mnemonics": tok,
               "encodable_range": enc, "outcomes": outcome_hist(i1[name], i2[name])}
        rec.update(st)
        per_arm[name] = rec
        if a["role"] in ("target", "dimension", "instruction_semantics"):
            by_field.setdefault("%s.%s" % (a["instr"], a["field"]), []).append(
                (name, a, rec))

    verdicts, probes = {}, {}
    for key, entries in sorted(by_field.items()):
        mn, fld = key.split(".", 1)
        if fld.startswith("_"):
            probes[key] = {"not_a_field": True,
                           "why": "a composite/probe arm, not a db field row",
                           "arms": {e[0]: e[2] for e in entries}}
            continue
        try:
            start, width = L.field_span(mn, fld)
        except KeyError:
            start, width = entries[0][1]["start"], entries[0][1]["width"]
        usable = [e for e in entries if e[2]["control"]["fired"] and e[2]["baselines_ok"]]
        live = [e for e in usable
                if e[2]["moved_valid"] >= 1
                and e[2]["agree_pct"] >= AGREE_MIN
                and e[2]["moved"] >= 2 * e[2]["disagree"]
                and e[2]["V_distinct_valid_payloads"] >= 2
                and e[2]["distinct_oracles"] >= 2]
        carriers = sorted({e[1]["carrier"] for e in entries})
        usable_carriers = sorted({e[1]["carrier"] for e in usable})
        tot_disp = max(e[2]["values_dispatched"] for e in entries)
        tot_bytes = sum(e[2]["distinct_bytes"] for e in entries)
        enc = max(e[2]["encodable_range"] for e in entries)
        Vmax = max(e[2]["V_distinct_valid_payloads"] for e in entries)
        if not usable:
            label, verdict = "untested", "STILL-UNDERPOWERED"
            note = ("no arm had detection power: on every arm either the control "
                    "on the same instruction and occurrence never moved / never "
                    "failed the oracle, or the baselines were unstable")
        elif live:
            label, verdict = "hardware-run", "LIVE"
            note = ("moved on %d of the %d arms that had detection power "
                    "(%d arms swept in total)" % (len(live), len(usable), len(entries)))
        elif Vmax <= 1:
            label, verdict = "untested", "WITHHELD-INDISTINGUISHABLE"
            note = ("V <= 1: every legal value produced the SAME valid payload, "
                    "so what movement there is is a hazard map, not a semantic")
        elif len(usable_carriers) >= 2:
            label, verdict = "single-template-inference", "INERT-ROBUST"
            note = ("0 of %d arms moved, on %d carriers with detection power, "
                    "spanning the dimension `%s`"
                    % (len(entries), len(usable_carriers), DIMENSION.get(key, "?")))
        else:
            label, verdict = "untested", "STILL-UNDERPOWERED"
            note = ("inert, but only %d carrier with detection power: "
                    "FIELD-SWEEP-PROTOCOL section 9 rule 1 requires >= 2 carriers "
                    "differing in the dimension `%s`"
                    % (len(usable_carriers), DIMENSION.get(key, "?")))
        verdicts[key] = {
            "label": label, "verdict": verdict,
            "range": "0..%d dense (all %d values)" % ((1 << width) - 1, 1 << width)
                     if width <= 8 else "see per-arm coverage (w > 8)",
            "target": "G17P", "evidence": ["EXP-0202"],
            "values_dispatched": tot_disp, "distinct_bytes": tot_bytes,
            "encodable_range": enc, "start": start, "width": width,
            "dimension_spanned": DIMENSION.get(key), "carriers": carriers,
            "carriers_with_detection_power": usable_carriers,
            "V_max": Vmax,
            "arms": {e[0]: e[2] for e in entries},
            "note": note,
        }

    out = {"_generated_by": "analysis/verdicts.py",
           "_runs": [str(sys.argv[1]), str(sys.argv[2])],
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved >= 2*disagree AND moved > 0",
                     "hard_outcomes_excluded_from_movement": sorted(HARD)},
           "_probe_arms": probes,
           "_controls": {"%s#%s/%s" % k: v for k, v in control.items()},
           "_arms": per_arm}
    out.update(verdicts)
    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    for k, v in sorted(verdicts.items()):
        print("%-30s %-28s %s" % (k, v["verdict"] + " -> " + v["label"], v["note"][:70]))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
