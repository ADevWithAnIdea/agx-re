#!/usr/bin/env python3
"""EXP-0208 step 5 -- derive the six independent axes (RE_EXPERIMENT_PROCESS_CORRECTIONS
section 2) for every target row, FROM RAW.

Reads analysis/row_evidence.json (the six-lookup raw bundle), analysis/raw_index_jsonl.jsonl
(for the per-carrier detection-power indicator) and analysis/label_history.json (for the
frozen-gate fact). Writes analysis/axes.json keyed `<mnemonic>.<field>`.

No label is changed. `axes` is an EVIDENCE status; `label` remains the PROMOTION status.
"""
import json, os, re, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))

EV = json.load(open(os.path.join(HERE, "row_evidence.json")))
HIST = json.load(open(os.path.join(HERE, "label_history.json")))
EG = {"hardware-run", "isolated-byte-diff"}

# ---- per-carrier detection power ------------------------------------------------
# EXP-0191's frozen gate ("did this arm ever demonstrate that its observable can MOVE?")
# applied to all rows, in its PASS_SIB form: some group in the same (exp,file,carrier)
# produced >=2 distinct payloads among NON-fault cases.  EXP-0191 itself covers only the
# 79 INERT fields; its verdicts are carried through verbatim where they exist.
detect = collections.defaultdict(lambda: dict(max_okobs=0, ctrl_okobs=0, groups=0))
for line in open(os.path.join(HERE, "raw_index_jsonl.jsonl")):
    g = json.loads(line)
    k = (g["exp"], g["file"], g["carrier"])
    d = detect[k]
    d["groups"] += 1
    d["max_okobs"] = max(d["max_okobs"], g.get("n_okobs", 0))
    if g["field"].startswith("_") and not g["field"].startswith("\x00"):
        d["ctrl_okobs"] = max(d["ctrl_okobs"], g.get("n_okobs", 0))

E0191 = {}
p = os.path.join(ROOT, "experiments/EXP-0191-detection-gate/analysis/gate_results.json")
if os.path.exists(p):
    for k, v in json.load(open(p))["fields"].items():
        E0191[k] = v.get("verdict_carrier") or v.get("verdict") or None

SILENT = ("silent_zero", "no_draw", "no_store", "silent", "nostore")
HARD = ("fault", "hang", "cmdbuf_error", "error", "gpu_hang")

def parse_val(s):
    """values are JSON-encoded; ints stay ints, 'byte3=0x22' style stays a string."""
    try:
        v = json.loads(s)
    except Exception:
        return None
    return v if isinstance(v, int) else None

def predicate_for(vals, domain):
    """Describe a fault/hang set exactly, or return None. Domains up to 8 bits."""
    S = set(vals)
    if not S or not S <= set(domain):
        return None
    D = set(domain)
    if S == D:
        return "every dispatched value"
    lo = min(S)
    if S == {v for v in D if v >= lo}:
        return "exactly v >= 0x%02X (a contiguous wall)" % lo
    hi = max(S)
    if S == {v for v in D if v <= hi}:
        return "exactly v <= 0x%02X (a contiguous wall)" % hi
    for mask in range(1, 256):
        by = collections.defaultdict(set)
        for v in D:
            by[v & mask].add(v)
        for const, grp in by.items():
            if grp == S:
                return "exactly (v & 0x%02X) == 0x%02X" % (mask, const)
    # union of at most 3 mask predicates is not attempted; report shape instead
    runs = []
    for v in sorted(S):
        if runs and v == runs[-1][1] + 1:
            runs[-1][1] = v
        else:
            runs.append([v, v])
    if len(runs) <= 4:
        return "exactly {" + ", ".join("0x%02X" % a if a == b else "0x%02X-0x%02X" % (a, b)
                                       for a, b in runs) + "}"
    return None

def target_of(files, exps):
    t = set()
    blob = " ".join(files) + " " + " ".join(exps)
    if re.search(r"g17p|a18", blob, re.I): t.add("G17P-direct")
    if re.search(r"\bm4\b|m4[-_]|_m4|g16g", blob, re.I): t.add("G16G-direct")
    return sorted(t)

out = {}
stats = collections.Counter()

for key, r in EV.items():
    m, f = r["mnemonic"], r["field"]
    w = r["geom"]["width"]
    enc = (1 << w) if (w and w <= 16) else None
    L1, L3, L4 = r["L1"], r["L3"], r["L4"]
    disp = None
    for cand in (L1, L3):
        if cand and cand["n"]:
            disp = cand if disp is None else disp
    # merge L1+L3 counting when both exist
    src = []
    if L1: src.append(("L1 (instr+field records)", L1))
    if L3: src.append(("L3 (field:null byte sweep at this field's byte span)", L3))

    outcomes = collections.Counter()
    for _, s in src:
        outcomes.update(s["outcomes"])
    nrec = sum(s["n"] for _, s in src)
    u_values = max([s["u_values"] for _, s in src] or [0])
    u_okvals = max([s["u_okvals"] for _, s in src] or [0])
    u_fault = max([s["u_faultvals"] for _, s in src] or [0])
    u_hang = max([s["u_hangvals"] for _, s in src] or [0])
    mg_obs = max([s["max_group_obs"] for _, s in src] or [0])
    mg_okobs = max([s["max_group_okobs"] for _, s in src] or [0])
    mg_orc = max([s["max_group_orc"] for _, s in src] or [0])
    sem = sum(s["semchecked"] for _, s in src)
    ncar = max([s["n_carriers"] for _, s in src] or [0])
    exps = sorted({e for _, s in src for e in s["exps"]})
    files = sorted({fl for _, s in src for fl in s["files"]})
    groups = [g for _, s in src for g in s["alias_per_group"]]

    # ---------------- geometry ----------------
    alias_groups = [g for g in groups if g["nv"] and g["nb"] and g["nb"] < g["nv"]]
    best = max(groups, key=lambda g: (g["nv"], g["nb"]), default=None)
    if not src or not best or not best["nv"]:
        geometry = ("unverified: no per-case dispatched record carrying both a requested "
                    "value and the resulting instruction bytes was found for this field")
    else:
        nv, nb = best["nv"], best["nb"]
        if enc and nv >= enc and nb >= nv:
            geometry = ("geometry-mapped: %d of %d encodable values dispatched, %d distinct "
                        "ACTUAL encodings, no collapse" % (nv, enc, nb))
        elif nb >= nv:
            geometry = ("ledger-verified: %d distinct requested values produced %d distinct "
                        "ACTUAL encodings in one arm; no aliasing" % (nv, nb))
        else:
            geometry = ("ledger-verified WITH COLLAPSE: %d distinct requested values produced "
                        "only %d distinct ACTUAL encodings (%d collapsed) -- inspect for "
                        "match-bit aliasing vs baseline-identical no-op mutations"
                        % (nv, nb, nv - nb))
    # ---------------- detection power ----------------
    dp = []
    for g in groups:
        d = detect.get((g["exp"], g["file"], g["carrier"]))
        if d:
            dp.append(max(d["max_okobs"], d["ctrl_okobs"]))
    has_dp = any(x >= 2 for x in dp)

    # ---------------- liveness ----------------
    hard = sum(v for k, v in outcomes.items() if any(h in k.lower() for h in HARD))
    silent = sum(v for k, v in outcomes.items() if any(s2 in k.lower() for s2 in SILENT))
    okn = outcomes.get("ok", 0) + outcomes.get("OK", 0)
    env = "carriers=%d, values=%d, records=%d, exps=%s" % (ncar, u_values, nrec, ",".join(exps))
    if not src or nrec == 0:
        liveness = ("not-dispatched: no per-case hardware record for this field in any raw "
                    "format or keying searched")
    elif okn == 0 and hard and hard >= nrec * 0.99:
        liveness = "fault: every dispatched case in the tested envelope came back hard (%s)" % env
    elif mg_okobs >= 2:
        liveness = ("live in the tested envelope (%s): a single carrier produced %d distinct "
                    "VALID observed payloads across the swept values" % (env, mg_okobs))
    elif mg_obs >= 2 and mg_okobs <= 1:
        liveness = ("accepted-inert among the legal values in the tested envelope (%s); global "
                    "role unknown. The only variation in the observable is the legal/hard "
                    "transition -- a hazard map, not liveness (EXP-0192 Case C)" % env)
    elif mg_obs <= 1 and not has_dp:
        liveness = ("carrier-undecidable (%s): one observed payload and NO detection-power "
                    "control in the same carrier -- the arm could not have shown movement "
                    "either way" % env)
    else:
        liveness = ("inert in the tested envelope (%s); global role unknown. A detection-power "
                    "control in the same carrier did move" % env)
    if E0191.get(key):
        liveness += " | EXP-0191 frozen detection gate (carrier form): %s" % E0191[key]

    # ---------------- semantics ----------------
    if sem == 0:
        semantics = "unknown: no host oracle was recorded on any case (Gate C never attempted)"
    elif mg_orc <= 1:
        semantics = ("unknown: the host oracle is CONSTANT across the swept field (1 distinct "
                     "oracle payload per arm) -- a constant oracle is not a semantic check")
    else:
        semantics = ("unknown: %d distinct oracle payloads recorded, but no independent "
                     "predictor mapping value -> result over the claimed domain is committed "
                     "for this field" % mg_orc)

    # ---------------- hazard ----------------
    hz = []
    faultvals, hangvals = [], []
    for _, s in src:
        faultvals += [parse_val(x) for x in s.get("faultvals_list", [])]
        hangvals += [parse_val(x) for x in s.get("hangvals_list", [])]
    faultvals = sorted({v for v in faultvals if v is not None})
    hangvals = sorted({v for v in hangvals if v is not None})
    allvals = sorted({parse_val(x) for _, s in src for x in s.get("values_list", [])} - {None})
    if faultvals:
        pr = predicate_for(faultvals, allvals) if allvals else None
        hz.append("FAULT MAP: %d of %d dispatched values fault%s" %
                  (len(faultvals), len(allvals) or u_values, (" -- " + pr) if pr else ""))
    if hangvals:
        pr = predicate_for(hangvals, allvals) if allvals else None
        hz.append("HANG MAP: %d of %d dispatched values hang%s" %
                  (len(hangvals), len(allvals) or u_values, (" -- " + pr) if pr else ""))
    for k2, v2 in sorted(outcomes.items()):
        if any(s2 in k2.lower() for s2 in SILENT):
            hz.append("%d records returned `%s` (a RESULT, not a skipped case)" % (v2, k2))
    if not hz:
        hz.append("none recorded: 0 hard outcomes and 0 silent/no-effect outcomes in the "
                  "tested envelope" if src else "no dispatched raw")
    hazard = " | ".join(hz)

    # ---------------- target ----------------
    tg = target_of(files, exps)
    if not tg:
        target = ("cross-target-inferred: no dispatched raw, so nothing was established "
                  "directly on either target (row declares target=%s)" % r["target"])
    else:
        target = " + ".join(tg)
        if r["target"] and r["target"] not in ("G17P", "A18") and "G17P-direct" in tg:
            target += " (row's `target` field says %s)" % r["target"]

    # ---------------- reproducibility ----------------
    nfiles = sum(s["n_files"] for _, s in src)
    if not src:
        repro = "incomplete: no per-case raw located for this field"
    elif len(exps) >= 2:
        repro = ("independently-confirmed: per-case raw in %d separate experiments (%s), "
                 "%d raw files" % (len(exps), ", ".join(exps), nfiles))
    elif nfiles >= 2:
        repro = ("auditable: %d committed raw files (repeat runs of ONE harness -- repeatable, "
                 "not independent) in %s" % (nfiles, exps[0]))
    else:
        repro = "auditable: 1 committed raw file in %s" % exps[0]

    # ---------------- frozen gate ----------------
    h = HIST.get(key, [])
    labs = [e["label"] for e in h]
    if any(l in EG for l in labs):
        first = next(e for e in h if e["label"] in EG)
        last = h[-1]
        fg = ("PASSED its own pre-registered gate at the time: the row held `%s` at commit %s "
              "(%s, %s). Current status `%s` was set at %s (%s). Per section 9 the earlier "
              "observation is RETAINED as superseded history; the withdrawal scoped the "
              "PROMOTION, not the observation."
              % (first["label"], first["sha"], first["date"], first["subj"][:70],
                 last["label"], last["sha"], last["subj"][:70]))
    elif labs:
        fg = ("no emitter promotion was ever claimed for this row: it has held only %s across "
              "%d committed revisions. Its citing experiment's frozen gate was a decode / "
              "round-trip / corpus gate, which it passed on its own terms."
              % ("/".join(sorted(set(labs))), len(h)))
    else:
        fg = "no label history recorded"

    # ---------------- counts ----------------
    counts = dict(
        encodable=enc if enc is not None else "n/a (width=%s bits)" % w,
        dispatched_distinct_values=u_values,
        distinct_actual_encodings=(best["nb"] if best else 0),
        records=nrec,
        legal_values_ok=u_okvals,
        ok_records=okn,
        silent_or_no_effect_records=silent,
        hard_records=hard,
        fault_values=u_fault, hang_values=u_hang,
        aliased_value_groups=len(alias_groups),
        untested_values=(enc - u_values) if (enc is not None and enc >= u_values) else "n/a",
        distinct_valid_payloads_max_single_carrier=mg_okobs,
        distinct_payloads_max_single_carrier=mg_obs,
        semantic_checks=sem,
        distinct_oracle_payloads_max_single_carrier=mg_orc,
        carriers=ncar,
        outcomes=dict(outcomes),
    )

    searched = ("jsonl K1 instr+field; K2 field:null byte sweeps intersected with this "
                "field's db.json byte span [%s..%s]; K3 dotted `mnem.field`; K4 leading-"
                "underscore control/falsifier records; K5 instruction-only framing records; "
                "non-jsonl .json structural (op,field) records; non-jsonl .txt/.log/.md "
                "textual co-occurrence" % (r["geom"]["byte_lo"], r["geom"]["byte_hi"]))

    ax = dict(
        geometry=geometry,
        liveness=liveness,
        semantics=semantics,
        recipe=("not-generated: no committed record shows a complete instruction for this "
                "field being constructed from documented rules and run (Gate D)"),
        target=target,
        reproducibility=repro,
        frozen_gate=fg,
        hazard=hazard,
        counts=counts,
        promotion_status_note=("`label: %s` is a PROMOTION status, NOT an evidence status. Per "
                               "RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 9 the observations "
                               "recorded here are RETAINED; nothing below withdraws them."
                               % r["label"]),
        evidence_paths=files[:12],
        evidence_experiments=exps,
        detection_power=("a control or sibling in the same carrier produced >=2 distinct valid "
                         "payloads" if has_dp else
                         "NOT DEMONSTRATED in this field's carrier(s) -- no control or sibling "
                         "in the same (experiment,file,carrier) produced a second valid payload"),
        framing_evidence=(("%d instruction-only tokenisation records in %s (framing/length only, "
                           "no field value)" % (L4["n"], ", ".join(L4["exps"][:3]))) if L4 else
                          "none"),
        searched=searched,
        derived_by="EXP-0208 analysis/classify_axes.py over committed raw only",
    )
    if not src:
        ax["no_raw_statement"] = (
            "NO per-case raw found for this field. Searched: %s. Non-jsonl structural hits: %d; "
            "textual co-occurrence hits: %d; instruction-only framing records: %s."
            % (searched, len(r["L5"]), len(r["L6"]), L4["n"] if L4 else 0))
    out[key] = dict(mnemonic=m, field=f, label=r["label"], axes=ax)
    stats[geometry.split(":")[0]] += 1
    stats["LIVENESS " + liveness.split(":")[0].split("(")[0].strip()] += 1

json.dump(out, open(os.path.join(HERE, "axes.json"), "w"), indent=1)
for k, v in sorted(stats.items()):
    print(v, k)
print("rows:", len(out))
