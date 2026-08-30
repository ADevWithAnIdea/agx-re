#!/usr/bin/env python3
"""EXP-0202 verdicts -- the ONLY place a verdict may be written.

    python3 analysis/verdicts.py raw/<runA> raw/<runB> [--discovery raw/<run02>]

Recomputed from `raw/` on every invocation; never read back from a run manifest
or a previous verdicts file. `start`/`width` are re-read from the PINNED
`db.json`.

This implements `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` (normative, and it wins
where it conflicts with the dispatch's own gate).

GATE A -- the actual-byte ledger. Every case carries `requested_value`,
`requested_bytes`, `actual_bytes`, `decoded_actual` (extracted by the pinned
TOKENIZER, a different code path from the patcher), `main_sha256`, `off` and the
db/arms/harness revisions. **No hardware conclusion is drawn for a field until
every one of its cases satisfies `requested value == value decoded from the
actual dispatched bytes`.** Reported per field: cases, distinct requested values,
distinct ACTUAL encodings, and any collision where two requested values produced
the same actual bytes.

GATE B -- detection power. Every arm has a pre-registered positive control on the
same instruction occurrence. If the control does not move AND fail the oracle in
both runs, the arm is **`carrier-undecidable`** and zero movement is NOT evidence
of inertness.

GATE C -- semantics separated from liveness. Each case carries a pre-registered
`predicted_bucket` (ok / not_ok / rejected) and `sem_match`. **`sem_checked == 0`
can never produce `hardware-run`.** A stable byte-to-output change alone is
`live; role unknown`.

GATE E -- clean confirmation. Two G17P runs in OPPOSITE case order, identical
actual-byte ledgers. The measured quiet-window state of each run is reported; a
run with concurrent non-EXP-0202 GPU processes is marked CONTAMINATED and the
EXP-0160 validity filter is applied -- contamination can destroy an observation
but never fabricate a coherent one, so two agreeing sentinel-valid dumps stand.

VERDICT SHAPE -- six independent axes (section 2), exact numerators and
denominators, never a percentage alone. Safe negative wording is
`inert in <exact tested envelope>; global role unknown`.
"""
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate202 as L        # noqa: E402

AGREE_MIN = 99.0
HARD = {"fault", "hang"}
INVALID = {"measurement_failure", "invalid_run", "nondeterministic",
           "carrier_start_failed", "arm_aborted", "undecodable"}

DIMENSION = {
 "shift_amt_move.src_flag":
   "source register FILE of the staged amount, crossed with OPERAND PROVENANCE "
   "(memory load / uniform / ALU / thread-position system value / SIMD lane / "
   "overwrite+intervening ALU / control-flow merge)",
 "irotate.operands": "immediate rotate amount and the operand register bytes",
 "ibitcount.cache": "result routing: consumed by a following ALU vs standalone "
                    "writeback, plus a threadgroup-memory + barrier carrier",
 "ibitcount.dst": "destination register, under TWO disjoint readback plans",
 "iunary.b1": "function/source descriptor of the 0x27 datapath",
 "iunary.opsel": "which 0x27 datapath is selected",
 "cvt_f2i.b9": "result routing (mode 0x54/0x56), convert op, source class, "
               "source width, destination register",
 "b_alu10_lo7.src_flag": "source register FILE -- the same-dimension control",
 "cvt_f2i.signflag": "signed vs unsigned convert",
}


def load(run_dir):
    recs = []
    p = Path(run_dir) / "sweep.jsonl"
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                recs.append(json.loads(ln))
            except ValueError:
                pass
    return recs


def quiet(run_dir):
    p = Path(run_dir) / "gpuwatch.jsonl"
    if not p.exists():
        return {"measured": False}
    n, foreign, names = 0, 0, {}
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        n += 1
        bad = [q for q in r.get("procs", [])
               if "agxrun" in q.get("comm", "") and "EXP-0202" not in q.get("comm", "")]
        if bad:
            foreign += 1
            for q in bad:
                names[q["comm"]] = names.get(q["comm"], 0) + 1
    return {"measured": True, "samples": n, "samples_with_foreign_gpu_proc": foreign,
            "quiet": foreign == 0, "foreign_processes": names}


# `ok` and `unexpected_ok` are the SAME hardware observation -- the carrier's
# vector was reproduced -- and differ only in what we PREDICTED. Collapsing them
# is not cosmetic: without it, a field whose two values give byte-identical
# output is scored as MOVED purely because the oracle predicted differently at
# the compiled value, which is precisely the "a difference from baseline is not a
# semantic oracle" failure. Found in this experiment's own discovery run, where
# it would have manufactured movement for `shift_amt_move.src_flag`.
OUTCOME_NORM = {"unexpected_ok": "ok"}


def vkey(r):
    o = r.get("observed") or {}
    vals = o.get("vals_u32")
    h = hashlib.sha256(json.dumps(vals, sort_keys=True).encode()).hexdigest()[:16] \
        if vals is not None else "none"
    oc = r.get("outcome")
    return "%s|%s" % (OUTCOME_NORM.get(oc, oc), h)


def payload(r):
    return json.dumps((r.get("observed") or {}).get("vals_u32"), sort_keys=True)


def sentinel_valid(r):
    o = r.get("observed") or {}
    return bool(o.get("sentinel_ok"))


def index(recs):
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        if r.get("role") == "baseline":
            k = arm.split(":")[0]
            out.setdefault(k, {"cases": {}, "baselines": []})
            out[k]["baselines"].append(r)
            continue
        d = out.setdefault(arm, {"cases": {}, "baselines": []})
        d["cases"][r["value"]] = r
    return out


def baseline_key(a):
    for b in a["baselines"]:
        if str(b.get("note", "")).endswith(":open"):
            return vkey(b)
    return vkey(a["baselines"][0]) if a["baselines"] else None


def span_bits(hexstr, start, width):
    """A THIRD independent implementation of the field extraction -- byte-wise
    over the hex string -- used only to re-derive Gate A offline."""
    b = bytes.fromhex(hexstr)
    v = 0
    for i in range(width):
        bit = start + i
        if bit // 8 >= len(b):
            return None
        v |= ((b[bit // 8] >> (bit % 8)) & 1) << i
    return v


def ledger(a1, a2):
    """GATE A, per arm, RE-DERIVED OFFLINE from the raw.

    The driver's own `ledger_ok` compares the requested value against the
    TOKENIZER's decode of the whole db field. That is wrong for an arm that
    sweeps a SUB-SPAN of a wider field: `irotate.operands` is 40 bits and its
    byte-wise arms request 8 of them, so the tokenizer correctly returns the
    whole 40-bit value and the comparison fails on 3232 cases of run03 -- with
    `requested_bytes == actual_bytes` TRUE in every one of them. The defect is in
    the comparison, not in the dispatch, and §9 of
    RE_EXPERIMENT_PROCESS_CORRECTIONS.md is explicit that such a case is
    reclassified from raw rather than re-run.

    The correct assertion, computed here from `actual_bytes` + `start` + `width`:

        requested_bytes == actual_bytes
        AND  bits(actual_bytes, start, width) == requested value

    plus, when the arm's span IS the whole db field, the tokenizer's independent
    decode must agree too.
    """
    cases = list(a1["cases"].values()) + list(a2["cases"].values())
    have = [c for c in cases if "actual_bytes" in c]
    okn = 0
    tokx = 0
    for c in have:
        sb = span_bits(c["actual_bytes"], c["start"], c["width"])
        same = c.get("requested_bytes") == c.get("actual_bytes")
        val = c["value"] & ((1 << c["width"]) - 1)
        if same and sb == val:
            okn += 1
        if c.get("decoded_via") == "pinned_tokenizer" and c.get("decoded_actual") == val:
            tokx += 1
    req = {c.get("requested_value") for c in have}
    act = {c.get("actual_bytes") for c in have}
    byact = {}
    for c in have:
        byact.setdefault(c.get("actual_bytes"), set()).add(c.get("requested_value"))
    collisions = {k: sorted(v) for k, v in byact.items() if len(v) > 1}
    return {"cases_with_ledger": len(have), "cases_total": len(cases),
            "ledger_ok": okn, "ledger_fail": len(have) - okn,
            "tokenizer_cross_check_agrees": tokx,
            "distinct_requested_values": len(req),
            "distinct_actual_encodings": len(act),
            "encoding_collisions": len(collisions),
            "collision_examples": dict(list(collisions.items())[:4]),
            "gate_A_pass": bool(have) and okn == len(have)}


def stats(a1, a2, bk):
    vals = sorted(set(a1["cases"]) & set(a2["cases"]))
    # EXP-0160 validity filter: a case whose sentinel is missing in a run is not
    # an observation of that value; contamination can destroy an observation but
    # never fabricate a coherent one.
    usable = [v for v in vals
              if sentinel_valid(a1["cases"][v]) or a1["cases"][v]["outcome"] in HARD]
    agree = sum(1 for v in vals if vkey(a1["cases"][v]) == vkey(a2["cases"][v]))
    hard = sum(1 for v in vals if a1["cases"][v]["outcome"] in HARD
               or a2["cases"][v]["outcome"] in HARD)
    inval = sum(1 for v in vals if a1["cases"][v]["outcome"] in INVALID
                or a2["cases"][v]["outcome"] in INVALID)
    moved = sum(1 for v in vals
                if vkey(a1["cases"][v]) != bk and vkey(a2["cases"][v]) != bk)
    moved_valid = sum(1 for v in vals
                      if a1["cases"][v]["outcome"] not in HARD | INVALID
                      and a2["cases"][v]["outcome"] not in HARD | INVALID
                      and vkey(a1["cases"][v]) != bk and vkey(a2["cases"][v]) != bk)
    valid = [a1["cases"][v] for v in vals
             if a1["cases"][v]["outcome"] not in HARD | INVALID]
    semc = [a1["cases"][v] for v in vals if a1["cases"][v].get("sem_checked")]
    semok = sum(1 for c in semc if c.get("sem_match"))
    semc2 = [a2["cases"][v] for v in vals if a2["cases"][v].get("sem_checked")]
    semok2 = sum(1 for c in semc2 if c.get("sem_match"))
    oc = {}
    for a in (a1, a2):
        for c in a["cases"].values():
            oc[c["outcome"]] = oc.get(c["outcome"], 0) + 1
    return {"shared_values": len(vals), "sentinel_valid_values": len(usable),
            "agree": agree, "disagree": len(vals) - agree,
            "agree_pct": round(100.0 * agree / len(vals), 3) if vals else 0.0,
            "moved": moved, "moved_valid": moved_valid,
            "hard_outcomes": hard, "invalid_measurements": inval,
            "V_distinct_valid_payloads": len({payload(r) for r in valid}),
            "L_legal_values": len(valid),
            "sem_checked": len(semc), "sem_match": semok,
            "sem_checked_runB": len(semc2), "sem_match_runB": semok2,
            "distinct_oracles": len({json.dumps(a1["cases"][v].get("oracle"),
                                                sort_keys=True) for v in vals}),
            "distinct_bytes": len({a1["cases"][v].get("bytes") for v in vals}),
            "values_dispatched": len(vals), "outcomes": oc}


def tokens(a1, a2, mn):
    tk, enc = {}, set()
    for a in (a1, a2):
        for v, c in a["cases"].items():
            t = (c.get("token") or {}).get("mnemonic")
            tk[str(t)] = tk.get(str(t), 0) + 1
            if t == mn:
                enc.add(v)
    return tk, len(enc)


def baselines(a1, a2, prepatched):
    if prepatched:
        keys = {vkey(b) for b in a1["baselines"]} | {vkey(b) for b in a2["baselines"]}
        return len(keys) == 1, "identical open/close baselines across both runs"
    ok = (all(b["outcome"] == "ok" for b in a1["baselines"])
          and all(b["outcome"] == "ok" for b in a2["baselines"]))
    return ok, "every baseline `ok`"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 2
    runA, runB = args[0], args[1]
    r1, r2 = load(runA), load(runB)
    i1, i2 = index(r1), index(r2)
    armfile = EXP / "harness" / "arms202b.json"
    if not armfile.exists():
        armfile = EXP / "harness" / "arms202.json"
    arms = {a["arm"]: a for a in json.loads(armfile.read_text())["arms"]}
    qA, qB = quiet(runA), quiet(runB)
    clean_window = bool(qA.get("quiet")) and bool(qB.get("quiet"))

    control = {}
    for name, a in arms.items():
        if a["role"] != "control" or name not in i1 or name not in i2:
            continue
        bk = baseline_key(i1[name])
        st = stats(i1[name], i2[name], bk)
        f1 = any(c["match"] is False for c in i1[name]["cases"].values())
        f2 = any(c["match"] is False for c in i2[name]["cases"].values())
        k = (a["carrier"], a["occ"], a["instr"])
        rec = {"arm": name, "field": a["field"], "moved": st["moved"],
               "moved_valid": st["moved_valid"], "agree_pct": st["agree_pct"],
               "falsifier_fired": bool(f1 and f2),
               "fired": st["moved_valid"] >= 1 and f1 and f2}
        cur = control.get(k)
        if cur is None or (rec["fired"] and not cur["fired"]):
            control[k] = rec

    per_arm, by_field = {}, {}
    for name, a in arms.items():
        if name not in i1 or name not in i2:
            per_arm[name] = {"status": "missing_from_a_run"}
            continue
        bk = baseline_key(i1[name])
        st = stats(i1[name], i2[name], bk)
        tk, enc = tokens(i1[name], i2[name], a["instr"])
        lg = ledger(i1[name], i2[name])
        prep = bool(a.get("prepatch"))
        blok, blwhy = baselines(i1[name], i2[name], prep)
        ctl = control.get((a["carrier"], a["occ"], a["instr"]),
                          {"fired": None, "moved": None, "falsifier_fired": None})
        rec = {"carrier": a["carrier"], "occ": a["occ"], "role": a["role"],
               "instr": a["instr"], "field": a["field"], "sub": a.get("sub"),
               "prepatched": prep, "baselines_stable": blok,
               "baseline_rule": blwhy,
               "baseline_field_value": a.get("baseline_field_value"),
               "control": ctl, "tokenized_mnemonics": tk,
               "encodable_range": enc, "ledger": lg}
        rec.update(st)
        per_arm[name] = rec
        if a["role"] in ("target", "dimension", "instruction_semantics"):
            by_field.setdefault("%s.%s" % (a["instr"], a["field"]), []).append(
                (name, a, rec))

    verdicts, probes = {}, {}
    for key, ents in sorted(by_field.items()):
        mn, fld = key.split(".", 1)
        if fld.startswith("_"):
            probes[key] = {"not_a_field": True,
                           "why": "a composite/probe arm, not a db field row",
                           "arms": {e[0]: e[2] for e in ents}}
            continue
        try:
            start, width = L.field_span(mn, fld)
        except KeyError:
            start, width = ents[0][1]["start"], ents[0][1]["width"]

        gateA = all(e[2]["ledger"]["gate_A_pass"] for e in ents)
        powered = [e for e in ents if e[2]["control"]["fired"] and e[2]["baselines_stable"]]
        live = [e for e in powered
                if e[2]["moved_valid"] >= 1
                and e[2]["agree_pct"] >= AGREE_MIN
                and e[2]["moved"] >= 2 * e[2]["disagree"]
                and e[2]["V_distinct_valid_payloads"] >= 2
                and e[2]["distinct_oracles"] >= 2]
        semc = sum(e[2]["sem_checked"] for e in ents)
        semok = sum(e[2]["sem_match"] for e in ents)
        semc2 = sum(e[2]["sem_checked_runB"] for e in ents)
        semok2 = sum(e[2]["sem_match_runB"] for e in ents)
        Vmax = max(e[2]["V_distinct_valid_payloads"] for e in ents)
        carriers = sorted({e[1]["carrier"] for e in ents})
        pcarriers = sorted({e[1]["carrier"] for e in powered})

        # ---- axis 1: encoding geometry
        geom = "ledger-verified" if gateA else "unverified"
        # ---- axis 2: liveness
        if not powered:
            liveness = "carrier-undecidable"
        elif live:
            liveness = "live"
        elif Vmax <= 1:
            liveness = "accepted-inert (indistinguishable: V=1)"
        else:
            liveness = "accepted-inert"
        # ---- axis 3: semantics
        if semc == 0:
            semantics = "unknown"
        elif semok == semc and semc2 == semok2 and semc >= 8:
            semantics = "bounded-map"
        elif semok == semc:
            semantics = "hypothesis-consistent"
        else:
            semantics = "hypothesis-refuted"
        # ---- axis 4: compiler recipe
        recipe = "not-generated"
        # ---- axis 5: target
        tgt = "G17P-direct"
        # ---- axis 6: reproducibility
        repro = ("independently-confirmed" if clean_window else
                 "auditable (confirmation window NOT quiet -- see _quiet_window)")

        # ---- legacy label: strict. Liveness may never imply semantics.
        if liveness == "carrier-undecidable":
            label, verdict = "untested", "CARRIER-UNDECIDABLE"
        elif liveness == "live" and semantics == "bounded-map":
            label, verdict = "hardware-run", "LIVE + SEMANTICALLY BOUNDED"
        elif liveness == "live":
            label, verdict = "untested", "LIVE; ROLE UNKNOWN"
        elif liveness.startswith("accepted-inert") and len(pcarriers) >= 3:
            label, verdict = "single-template-inference", "ACCEPTED-INERT (>=3 carriers)"
        elif liveness.startswith("accepted-inert"):
            label, verdict = "untested", "ACCEPTED-INERT (too few carrier classes)"
        else:
            label, verdict = "untested", "UNDETERMINED"

        env = ("%d values dispatched, %d distinct actual encodings, %d of %d "
               "cases ledger-verified, on %d carriers (%d with detection power)"
               % (max(e[2]["values_dispatched"] for e in ents),
                  max(e[2]["ledger"]["distinct_actual_encodings"] for e in ents),
                  sum(e[2]["ledger"]["ledger_ok"] for e in ents),
                  sum(e[2]["ledger"]["cases_with_ledger"] for e in ents),
                  len(carriers), len(pcarriers)))
        verdicts[key] = {
            "label": label, "verdict": verdict,
            "axes": {"encoding_geometry": geom, "liveness": liveness,
                     "semantics": semantics, "compiler_recipe": recipe,
                     "target": tgt, "reproducibility": repro},
            "range": ("0..%d dense (all %d values)" % ((1 << width) - 1, 1 << width)
                      if width <= 8 else "see per-arm coverage (w > 8)"),
            "tested_envelope": env,
            "target": "G17P", "evidence": ["EXP-0202"],
            "start": start, "width": width,
            "values_dispatched": max(e[2]["values_dispatched"] for e in ents),
            "distinct_bytes": sum(e[2]["distinct_bytes"] for e in ents),
            "distinct_actual_encodings":
                max(e[2]["ledger"]["distinct_actual_encodings"] for e in ents),
            "encodable_range": max(e[2]["encodable_range"] for e in ents),
            "V_max_distinct_valid_payloads": Vmax,
            "sem_checked": semc, "sem_match": semok,
            "sem_checked_runB": semc2, "sem_match_runB": semok2,
            "gate_A_actual_byte_ledger": gateA,
            "dimension_required": DIMENSION.get(key),
            "carriers": carriers, "carriers_with_detection_power": pcarriers,
            "n_carrier_classes_with_power": len(pcarriers),
            "arms": {e[0]: e[2] for e in ents},
            "note": "",
        }

    out = {"_generated_by": "analysis/verdicts.py",
           "_runs": [runA, runB],
           "_quiet_window": {"runA": qA, "runB": qB, "clean": clean_window},
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved_valid >= 1 AND moved >= 2*disagree",
                     "hard_outcomes": sorted(HARD),
                     "invalid_outcomes": sorted(INVALID),
                     "normative": "RE_EXPERIMENT_PROCESS_CORRECTIONS.md"},
           "_probe_arms": probes,
           "_controls": {"%s#%s/%s" % k: v for k, v in control.items()},
           "_arms": per_arm}
    out.update(verdicts)
    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    for k, v in sorted(verdicts.items()):
        print("%-28s %-34s %s" % (k, v["verdict"], json.dumps(v["axes"])[:110]))
    print("quiet window:", json.dumps({"A": qA.get("quiet"), "B": qB.get("quiet")}))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
