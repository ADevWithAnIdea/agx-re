#!/usr/bin/env python3
"""EXP-0208 step 5 -- derive the six independent axes (RE_EXPERIMENT_PROCESS_CORRECTIONS
section 2) plus frozen_gate, hazard and exact counts for every target row, FROM RAW.

Inputs (all our own committed artefacts; no device, no Apple binary):
  analysis/row_evidence.json        L1..L6   exact-name / control-name / byte-span-null /
                                             instruction-only / non-jsonl structural / textual
  analysis/row_evidence_extra.json  L7..L12  sibling descriptor, composite name, byte-position
                                             name, record-carried span, M4-14 prose, containment
  analysis/curated_prose.json       hand-verified pre-EXP-0138 .log extraction
  analysis/label_history.json       every label this row has held, from git
  analysis/raw_index_jsonl.jsonl    per-carrier detection-power indicator

Output: analysis/axes.json, keyed `<mnemonic>.<field>`.
NO LABEL IS CHANGED.  `label` stays the PROMOTION status; `axes` is the EVIDENCE status.
"""
import json, os, re, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda n: json.load(open(os.path.join(HERE, n) if os.path.exists(os.path.join(HERE, n)) else os.path.join(HERE, "..", "work", n)))

EV, EX, CUR, HIST = J("row_evidence.json"), J("row_evidence_extra.json"), \
                    J("curated_prose.json"), J("label_history.json")
EG = {"hardware-run", "isolated-byte-diff"}

detect = collections.defaultdict(lambda: dict(max_okobs=0, ctrl_okobs=0))
for line in open(os.path.join(HERE, "..", "work", "raw_index_jsonl.jsonl")):
    g = json.loads(line)
    d = detect[(g["exp"], g["file"], g["carrier"])]
    d["max_okobs"] = max(d["max_okobs"], g.get("n_validobs", 0))
    if g["field"].startswith("_") and not g["field"].startswith("\x00"):
        d["ctrl_okobs"] = max(d["ctrl_okobs"], g.get("n_validobs", 0))

E0191 = {}
p = os.path.join(ROOT, "experiments/EXP-0191-detection-gate/analysis/gate_results.json")
if os.path.exists(p):
    for k, v in json.load(open(p))["fields"].items():
        E0191[k] = v.get("verdict_carrier") or v.get("verdict")

SILENT = ("silent_zero", "no_draw", "no_store", "silent", "nostore")
HARD = ("fault", "hang", "cmdbuf_error", "error")

def parse_val(s):
    try: v = json.loads(s)
    except Exception: return None
    return v if isinstance(v, int) else None

def predicate_for(vals, domain):
    D = {v for v in domain if 0 <= v <= 0xFFFFFFFF}   # drop sentinel/flag values
    S = {v for v in vals if v in D}
    if not S or not D: return None
    if S == D: return "every dispatched value"
    lo, hi = min(S), max(S)
    if S == {v for v in D if v >= lo}: return "exactly v >= 0x%02X (a contiguous wall)" % lo
    if S == {v for v in D if v <= hi}: return "exactly v <= 0x%02X (a contiguous wall)" % hi
    if max(D) < 256:
        for mask in range(1, 256):
            by = collections.defaultdict(set)
            for v in D: by[v & mask].add(v)
            for const, grp in by.items():
                if grp == S: return "exactly (v & 0x%02X) == 0x%02X" % (mask, const)
    runs = []
    for v in sorted(S):
        if runs and v == runs[-1][1] + 1: runs[-1][1] = v
        else: runs.append([v, v])
    if len(runs) <= 4:
        return "exactly {" + ", ".join("0x%02X" % a if a == b else "0x%02X-0x%02X" % (a, b)
                                       for a, b in runs) + "}"
    return None

def target_of(files, exps):
    t, blob = set(), " ".join(files) + " " + " ".join(exps)
    if re.search(r"g17p|a18|RT-\d|EXP-O2|EXP-00[0-4]\d", blob): t.add("G17P-direct (A18 Pro)")
    if re.search(r"\bm4\b|m4[-_]|_m4|g16g", blob, re.I): t.add("G16G-direct (M4)")
    return sorted(t)

out, stats = {}, collections.Counter()

for key, r in EV.items():
    m, f = r["mnemonic"], r["field"]
    w, st = r["geom"]["width"], r["geom"]["start"]
    enc = (1 << w) if (w and w <= 16) else None
    xr, cu = EX.get(key, {}), CUR.get(key)

    # ---- assemble DIRECT dispatched evidence (this instruction, this field's bits) ----
    src = []
    for nm, lbl in (("L1", "exact (instr,field) records"),
                    ("L3", "field:null byte sweep inside this field's byte span")):
        if r.get(nm): src.append((nm, lbl, r[nm]))
    extra_direct = [(nm, lbl) for nm, lbl in
                    (("L8", "composite field name containing this field"),
                     ("L9", "byte-position field name inside this field's byte span"),
                     ("L10", "record-carried bit span overlapping this field / legacy name"))
                    if nm in xr]

    outcomes = collections.Counter()
    for _, _, s in src: outcomes.update(s["outcomes"])
    for nm, _ in extra_direct: outcomes.update(xr[nm]["outcomes"])
    nrec = sum(s["n"] for _, _, s in src) + sum(xr[nm]["n"] for nm, _ in extra_direct)
    u_values = max([s["u_values"] for _, _, s in src] + [xr[nm]["nv_max"] for nm, _ in extra_direct] + [0])
    u_okvals = max([s["u_okvals"] for _, _, s in src] + [0])
    u_validvals = max([s["u_validvals"] for _, _, s in src] + [0])
    mg_obs = max([s["max_group_obs"] for _, _, s in src] + [xr[nm]["u_obs_max"] for nm, _ in extra_direct] + [0])
    mg_okobs = max([s["max_group_validobs"] for _, _, s in src] +
                   [xr[nm].get("u_validobs_max", 0) for nm, _ in extra_direct] + [0])
    mg_okobs_strict = max([s["max_group_okobs"] for _, _, s in src] + [0])
    mg_orc = max([s["max_group_orc"] for _, _, s in src] + [0])
    sem = sum(s["semchecked"] for _, _, s in src) + sum(xr[nm]["sem"] for nm, _ in extra_direct)
    ncar = max([s["n_carriers"] for _, _, s in src] + [0])
    exps = sorted({e for _, _, s in src for e in s["exps"]} |
                  {e for nm, _ in extra_direct for e in xr[nm]["exps"]})
    files = sorted({fl for _, _, s in src for fl in s["files"]} |
                   {fl for nm, _ in extra_direct for fl in xr[nm]["files"]})
    groups = [g for _, _, s in src for g in s["alias_per_group"]]
    best = max(groups, key=lambda g: (g["nv"], g["nb"]), default=None)
    nb_max = max([g["nb"] for g in groups] + [xr[nm]["nb_max"] for nm, _ in extra_direct] + [0])
    nb_union = max([s["u_abytes_h"] for _, _, s in src] + [0])
    has_direct = bool(src or extra_direct)

    # ---- prose sources ----
    L11 = xr.get("L11")
    L11s = (L11 or {}).get("stats") or {}
    if cu:
        u_values = max(u_values, len(cu.get("dispatched_values", [])))
        mg_okobs = max(mg_okobs, cu.get("distinct_valid_payloads", 0))
    if L11 and not has_direct and not cu:
        u_values = max(u_values, L11s.get("distinct_hex_values_mentioned", 0))

    # EXP-M4-14 marks its own non-dispatched rows: `own-MSL byte-diff ... NOT HW-splice`.
    L11_is_splice = bool(L11) and not re.search(r"NOT HW-splice|byte-diff",
                                                str((L11 or {}).get("provenance") or ""), re.I)
    dispatched = has_direct or bool(cu) or L11_is_splice

    # ---------------- geometry ----------------
    if best and best["nv"]:
        nv, nb = best["nv"], best["nb"]
        if enc and nv >= enc and nb >= nv:
            geometry = ("geometry-mapped: %d of %d encodable values dispatched in one arm, %d "
                        "distinct ACTUAL encodings, no collapse" % (nv, enc, nb))
        elif nb >= nv:
            geometry = ("ledger-verified: %d distinct requested values produced %d distinct "
                        "ACTUAL encodings in one arm; no collapse" % (nv, nb))
        else:
            geometry = ("ledger-verified WITH COLLAPSE: %d distinct requested values produced "
                        "only %d distinct ACTUAL encodings (%d collapsed). Inspect for match-bit "
                        "aliasing vs baseline-identical no-op mutations before calling it an alias"
                        % (nv, nb, nv - nb))
    elif extra_direct and nb_max:
        geometry = ("ledger-verified via a composite/byte-position/legacy-named record: up to %d "
                    "distinct ACTUAL encodings, but the record is not keyed to this field alone, "
                    "so per-value attribution to THIS field is not established" % nb_max)
    elif cu or L11_is_splice:
        geometry = ("unverified: the committed record is a prose splice log with no per-case "
                    "requested-vs-actual byte ledger. The spliced byte values are recorded; the "
                    "Gate A ledger is not")
    else:
        geometry = ("unverified: no per-case dispatched record carrying both a requested value "
                    "and the resulting instruction bytes was found for this field")

    # ---------------- detection power ----------------
    dp = [max(detect[(g["exp"], g["file"], g["carrier"])]["max_okobs"],
              detect[(g["exp"], g["file"], g["carrier"])]["ctrl_okobs"])
          for g in groups if (g["exp"], g["file"], g["carrier"]) in detect]
    has_dp = any(x >= 2 for x in dp)

    # ---------------- liveness ----------------
    hard = sum(v for k, v in outcomes.items() if any(h in k.lower() for h in HARD))
    silent = sum(v for k, v in outcomes.items() if any(s2 in k.lower() for s2 in SILENT))
    okn = outcomes.get("ok", 0) + outcomes.get("OK", 0)
    env = "carriers=%d, distinct values dispatched=%d, records=%d, experiments=%s" % (
        ncar, u_values, nrec, ",".join(exps) or (",".join(cu["files"]) if cu else "-"))
    if cu:
        liveness = {"live": "live in the tested envelope",
                    "carrier-undecidable": "carrier-undecidable",
                    "accepted-inert": "accepted-inert in the tested envelope; global role unknown"
                    }[cu["liveness"]] + " (%d values spliced, %d distinct valid payloads; %s)" % (
                        len(cu["dispatched_values"]), cu["distinct_valid_payloads"],
                        "; ".join(cu["files"]))
        if cu.get("carrier_note"): liveness += " || " + cu["carrier_note"]
    elif not dispatched:
        liveness = ("not-dispatched: no per-case hardware record for this field in ANY raw format "
                    "or keying searched")
    elif not has_direct and L11_is_splice:
        s2 = L11s
        tg2 = s2.get("arrow_targets", [])
        HARDT = re.compile(r"cmdbuf_error|fault|hang|error", re.I)
        BASET = re.compile(r"baseline|unchanged|<baseline>", re.I)
        valid_t = [t for t in tg2 if not HARDT.search(t)]
        nt = len({re.sub(r"^0x[0-9a-f/]+\s*->\s*", "", t, flags=re.I) for t in valid_t})
        if nt <= 1 and any(HARDT.search(t) for t in tg2):
            liveness = ("accepted-inert among the legal values in the tested envelope (%d distinct "
                        "byte values spliced on an A18 carrier); global role unknown. The only "
                        "recorded variation is the legal/hard transition -- a hazard map, not "
                        "liveness. Recorded outcomes: %s"
                        % (s2.get("distinct_hex_values_mentioned", 0), ", ".join(tg2[:8])))
        elif nt >= 2:
            liveness = ("live in the tested envelope (%d distinct byte values spliced on an A18 "
                        "carrier; the committed record maps them to %d DISTINCT observed outcomes: "
                        "%s); global semantics unknown"
                        % (s2.get("distinct_hex_values_mentioned", 0), nt,
                           ", ".join(s2.get("arrow_targets", [])[:8])))
        elif nt == 1 or s2.get("says_inert"):
            liveness = ("accepted-inert in the tested envelope (%d distinct byte values spliced on "
                        "an A18 carrier, all mapping to ONE recorded outcome: %s); global role "
                        "unknown" % (s2.get("distinct_hex_values_mentioned", 0),
                                     ", ".join(s2.get("arrow_targets", [])) or "baseline"))
        else:
            liveness = ("carrier-undecidable: the committed A18 splice record for this field does "
                        "not state a per-value outcome that can be scored")
    elif okn == 0 and hard and hard >= nrec * 0.99:
        liveness = "fault: every dispatched case in the tested envelope came back hard (%s)" % env
    elif mg_okobs >= 2:
        liveness = ("live in the tested envelope (%s): a SINGLE carrier produced %d distinct VALID "
                    "observed payloads across the swept values (EXP-0191 validity rule: "
                    "`silent_zero` / `wrong_value` / `no_draw` ARE observations; faults, hangs, "
                    "undecodables and contaminated cases are not). Payloads among strictly-`ok` "
                    "cases only: %d" % (env, mg_okobs, mg_okobs_strict))
    elif mg_obs >= 2:
        liveness = ("accepted-inert among the legal values in the tested envelope (%s); global role "
                    "unknown. The only variation in the observable is the legal/hard transition -- "
                    "a hazard map, not liveness (EXP-0192 Case C)" % env)
    elif not has_dp:
        liveness = ("carrier-undecidable (%s): ONE observed payload and no detection-power control "
                    "or live sibling in the same carrier -- this arm could not have shown movement "
                    "either way" % env)
    else:
        liveness = ("inert in the tested envelope (%s); global role unknown. A control or sibling "
                    "in the same carrier DID move, so the arm had detection power" % env)
    if E0191.get(key):
        liveness += " | EXP-0191 frozen detection gate (carrier form): %s" % E0191[key]

    # ---------------- semantics ----------------
    if cu and cu.get("semantic", "").startswith("bounded-map"):
        semantics = "bounded-map -- " + cu["semantic"]
    elif cu and cu.get("semantic", "").startswith("hypothesis"):
        semantics = "hypothesis -- " + cu["semantic"]
    elif not dispatched:
        semantics = "unknown: nothing was dispatched, so Gate C was never attempted"
    elif sem == 0 and not L11_is_splice:
        semantics = "unknown: no host oracle was recorded on any case (Gate C never attempted)"
    elif mg_orc <= 1 and not L11_is_splice:
        semantics = ("unknown: the host oracle is CONSTANT across the swept field (1 distinct oracle "
                     "payload per arm). A constant oracle across a varying field is not a semantic "
                     "check")
    elif L11_is_splice and not has_direct:
        semantics = ("hypothesis: the committed A18 splice record states a per-value behaviour but "
                     "no independent predictor was pre-registered and no per-case oracle is committed")
    else:
        semantics = ("unknown: %d distinct oracle payloads recorded, but no committed independent "
                     "predictor maps value -> result over the claimed domain for this field" % mg_orc)

    # ---------------- hazard, computed PER CARRIER ----------------
    # A value that faults in carrier A and runs clean in carrier B is NOT a fault of the field.
    # Unioning fault sets across carriers manufactures "every value faults"; intersecting across
    # RUNS of one carrier is what makes a fault map reproducible.  Both are done here.
    hz = []
    percar = collections.defaultdict(list)
    for g in groups:
        percar[(g["exp"], g["carrier"], g["arm"])].append(g)
    haz_rows = []
    for (e2, c2, a2), gs in sorted(percar.items()):
        # Reproducibility is per VALUE, not per run-set: a value counts as a reproducible
        # fault when EVERY run that dispatched it faulted on it.  Intersecting whole fault
        # sets across runs that swept DIFFERENT ranges (EXP-0168's hang-tolerant mapping
        # pass vs its budgeted runs) silently erases a 64-value wall down to one value.
        disp, flt, hng = collections.Counter(), collections.Counter(), collections.Counter()
        for g in gs:
            for x in (g["vals"] or []):
                v2 = parse_val(x)
                if v2 is not None: disp[v2] += 1
            for x in (g["fvals"] or []):
                v2 = parse_val(x)
                if v2 is not None: flt[v2] += 1
            for x in (g["hvals"] or []):
                v2 = parse_val(x)
                if v2 is not None: hng[v2] += 1
        allv = set(disp)
        finter = {v2 for v2 in flt if flt[v2] >= disp.get(v2, 0) and disp.get(v2, 0) > 0}
        hinter = {v2 for v2 in hng if hng[v2] >= disp.get(v2, 0) and disp.get(v2, 0) > 0}
        funion, hunion = set(flt), set(hng)
        if finter or hinter:
            haz_rows.append(dict(exp=e2, carrier=c2, arm=a2, runs=len(gs), values=len(allv),
                                 fault_all_runs=len(finter), fault_any_run=len(funion),
                                 hang_all_runs=len(hinter), hang_any_run=len(hunion),
                                 fault_predicate=predicate_for(sorted(finter), sorted(allv)) if finter else None,
                                 hang_predicate=predicate_for(sorted(hinter), sorted(allv)) if hinter else None))
    for hr in sorted(haz_rows, key=lambda x: -(x["fault_all_runs"] + x["hang_all_runs"]))[:6]:
        if hr["fault_all_runs"]:
            hz.append("FAULT MAP on carrier `%s` (%s, %d run(s)): %d of %d dispatched values fault "
                      "in EVERY run%s%s"
                      % (hr["carrier"] or "-", hr["exp"], hr["runs"], hr["fault_all_runs"],
                         hr["values"], (" -- " + hr["fault_predicate"]) if hr["fault_predicate"] else "",
                         "" if hr["fault_any_run"] == hr["fault_all_runs"] else
                         " (%d more faulted in at least one run -- not reproducible)"
                         % (hr["fault_any_run"] - hr["fault_all_runs"])))
        if hr["hang_all_runs"]:
            hz.append("HANG MAP on carrier `%s` (%s, %d run(s)): %d of %d dispatched values hang in "
                      "EVERY run%s" % (hr["carrier"] or "-", hr["exp"], hr["runs"],
                                       hr["hang_all_runs"], hr["values"],
                                       (" -- " + hr["hang_predicate"]) if hr["hang_predicate"] else ""))
    fv = sorted(set().union(*[set(parse_val(x) for x in g["fvals"]) - {None} for g in groups]) if groups else [])
    hv = sorted(set().union(*[set(parse_val(x) for x in g["hvals"]) - {None} for g in groups]) if groups else [])
    if len(percar) > 1 and (fv or hv):
        hz.append("CARRIER-DEPENDENT: %d carrier/arm combinations were swept; the union of "
                  "fault values across them is %d and the union of hang values is %d, which is "
                  "NOT a per-field fault map" % (len(percar), len(fv), len(hv)))
    for k2, v2 in sorted(outcomes.items()):
        if any(s2 in k2.lower() for s2 in SILENT):
            hz.append("%d records returned `%s` (a RESULT, not a skipped case)" % (v2, k2))
    if cu and cu.get("hangs"):
        hz.append("HANG at %s (%s)" % (", ".join("0x%02X" % v for v in cu.get("hang_values", [])),
                                       "; ".join(cu["files"])))
    if L11_is_splice and L11s.get("says_hang"):
        hz.append("the committed A18 splice record reports a HANG for at least one spliced value")
    if L11_is_splice and L11s.get("says_fault"):
        hz.append("the committed A18 splice record reports a contained GPU FAULT "
                  "(CMDBUF_ERROR / page fault) for at least one spliced value")
    if not hz:
        hz.append("none recorded: 0 hard outcomes and 0 silent/no-effect outcomes in the tested "
                  "envelope" if dispatched else "no dispatched raw, so no hazard information")
    hazard = " | ".join(hz)

    # ---------------- target ----------------
    tf = files + ([f2 for f2 in cu["files"]] if cu else []) + (["EXP-M4-14-a18-splice"] if L11 else [])
    tg = target_of(tf, exps + (["EXP-M4-14"] if L11 else []))
    target = " + ".join(tg) if tg else (
        "cross-target-inferred: nothing was established directly on either target for this field "
        "(the row declares target=%s)" % r["target"])

    # ---------------- reproducibility ----------------
    nfiles = sum(s["n_files"] for _, _, s in src)
    nsrc_exps = len(exps) + (1 if cu else 0)
    if cu and len(cu["files"]) >= 2:
        repro = ("independently-confirmed: the same substitution is recorded in %d separate "
                 "experiments (%s)" % (len(cu["files"]), "; ".join(cu["files"])))
    elif cu:
        repro = "auditable: 1 committed raw log (%s)" % cu["files"][0]
    elif not dispatched:
        repro = "incomplete: no per-case raw located for this field"
    elif L11_is_splice and not has_direct:
        repro = ("incomplete: the observation is committed only as a summary `evidence` string in "
                 "experiments/EXP-M4-14-a18-splice/splice_results.json -- no per-case raw capture, "
                 "no program hash, no actual-byte ledger. Section 9: this downgrades AUDITABILITY, "
                 "it does not falsify the observation")
    elif nsrc_exps >= 2:
        repro = ("independently-confirmed: per-case raw in %d separate experiments (%s), %d raw files"
                 % (len(exps), ", ".join(exps), nfiles))
    elif nfiles >= 2:
        repro = ("auditable: %d committed raw files (repeat runs of ONE harness -- repeatable, not "
                 "independent) in %s" % (nfiles, exps[0] if exps else "?"))
    else:
        repro = "auditable: 1 committed raw file in %s" % (exps[0] if exps else "?")

    # ---------------- frozen gate ----------------
    h = HIST.get(key, []); labs = [e["label"] for e in h]
    if any(l in EG for l in labs):
        first = next(e for e in h if e["label"] in EG); last = h[-1]
        fg = ("PASSED its own pre-registered gate at the time: the row held `%s` at commit %s (%s, "
              "\"%s\"). Current status `%s` was set at %s (\"%s\"). Per section 9 the earlier "
              "observation is RETAINED as superseded history; the withdrawal scoped the PROMOTION, "
              "not the observation."
              % (first["label"], first["sha"], first["date"], first["subj"][:80],
                 last["label"], last["sha"], last["subj"][:80]))
    elif labs:
        fg = ("no emitter promotion was ever claimed: the row has held only %s across %d committed "
              "revisions of validation.json. Its citing experiment's frozen gate was a decode / "
              "round-trip / corpus gate, which it passed on its own terms."
              % ("/".join(sorted(set(labs))), len(h)))
    else:
        fg = "no label history recorded in any committed revision of validation.json"

    # ---------------- counts ----------------
    counts = dict(
        encodable=enc if enc is not None else "n/a (width=%s bits)" % w,
        dispatched_distinct_values=u_values,
        distinct_instruction_byte_strings_all_arms=nb_union,
        distinct_actual_encodings_best_single_arm=nb_max,
        records=nrec,
        legal_values_ok=u_okvals,
        values_producing_a_valid_observation=u_validvals,
        ok_records=okn,
        silent_or_no_effect_records=silent,
        hard_records=hard,
        fault_values=len(fv) or (0 if not cu else cu.get("faults", 0)),
        hang_values=len(hv) or (0 if not cu else cu.get("hangs", 0)),
        collapsed_encodings=(best["nv"] - best["nb"] if best and best["nb"] and best["nb"] < best["nv"] else 0),
        untested_values=(enc - u_values) if (enc is not None and enc >= u_values) else "n/a",
        distinct_valid_payloads_max_single_carrier=mg_okobs,
        distinct_ok_only_payloads_max_single_carrier=mg_okobs_strict,
        distinct_payloads_max_single_carrier=mg_obs,
        semantic_checks=sem,
        distinct_oracle_payloads_max_single_carrier=mg_orc,
        carriers=ncar,
        outcomes=dict(outcomes))

    searched = ("K1 exact (instr,field) jsonl; K2 `field: null` byte sweeps intersected with this "
                "field's db.json byte span [%s..%s]; K3 dotted `mnem.field`; K4 leading-underscore "
                "control/falsifier records; K5 instruction-only framing records; K6 composite names "
                "(`a|b|c`, `a+b`, `x@bytemate`, `x+match[..]=v`); K7 byte-position names "
                "(`byte+N`, `bN`) and record-carried `byte`/`byte_index`; K8 record-carried "
                "`start`/`width` bit-span overlap (recovers legacy names such as `fmt_word`, "
                "`dst_pair`); K9 name containment (`dst_desc` -> `dst_desc_lo`); non-jsonl .json "
                "structural (op,field) records; non-jsonl .txt/.log/.md textual co-occurrence; and "
                "the EXP-M4-14 root-evidence-json prose records."
                % (r["geom"]["byte_lo"], r["geom"]["byte_hi"]))

    ax = dict(
        geometry=geometry, liveness=liveness, semantics=semantics,
        recipe=("not-generated: no committed record shows a complete instruction for this field "
                "being constructed from documented rules and executed (Gate D)"),
        target=target, reproducibility=repro, frozen_gate=fg, hazard=hazard, counts=counts,
        promotion_status_note=("`label: %s` is a PROMOTION status, NOT an evidence status. Per "
                               "RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 9 the observations "
                               "recorded here are RETAINED as superseded history; nothing here "
                               "withdraws them and nothing here promotes the label." % r["label"]),
        evidence_paths=(files[:10] + ([f2 for f2 in cu["files"]] if cu else []) +
                        (["experiments/EXP-M4-14-a18-splice/splice_results.json"] if L11 else [])),
        evidence_experiments=exps,
        detection_power=("a control or sibling in the same carrier produced >=2 distinct valid "
                         "payloads" if has_dp else
                         "NOT DEMONSTRATED in this field's carrier(s): no control, falsifier or "
                         "sibling in the same (experiment,file,carrier) produced a second valid "
                         "payload"),
        framing_evidence=(("%d instruction-only tokenisation records in %s -- framing/length only, "
                           "no field value" % (r["L4"]["n"], ", ".join(r["L4"]["exps"][:3])))
                          if r.get("L4") else "none"),
        sibling_descriptor_evidence=(
            ("%d records under sibling descriptor(s) %s at the SAME (start,width). This is "
             "CROSS-DESCRIPTOR and therefore INFERRED, never direct evidence for this row."
             % (xr["L7"]["n"], ", ".join(x for x in (xr["L7"]["siblings"] or []) if x)))
            if "L7" in xr else "none"),
        searched=searched,
        derived_by="EXP-0208 analysis/classify_axes.py over committed raw only; no device contacted")
    if L11:
        ax["m4_14_splice_record"] = dict(
            provenance=L11.get("provenance"), field_as_recorded=L11.get("field"),
            group=L11.get("group"), evidence_verbatim=L11.get("evidence"),
            distinct_hex_values_mentioned=L11s.get("distinct_hex_values_mentioned"),
            distinct_recorded_outcomes=L11s.get("distinct_arrow_targets"),
            recorded_outcomes=L11s.get("arrow_targets"))
    if cu:
        ax["curated_prose_record"] = cu
    if L11 and not L11_is_splice:
        ax["m4_14_non_splice_note"] = (
            "EXP-M4-14 records this field explicitly as `%s` -- an own-MSL BYTE-DIFF across "
            "compiled variants, NOT a splice-and-observe dispatch. It is corpus evidence, and "
            "this experiment does not upgrade it to a liveness observation."
            % (L11.get("provenance") or "")[:160])
    if not dispatched:
        ax["no_raw_statement"] = (
            "NO per-case dispatched raw found for this field. Searched: %s Non-jsonl structural "
            "hits: %d (all in derived audit outputs unless named above); textual co-occurrence "
            "hits: %d; instruction-only framing records: %s; sibling-descriptor records: %s."
            % (searched, len(r["L5"]), len(r["L6"]), r["L4"]["n"] if r.get("L4") else 0,
               xr["L7"]["n"] if "L7" in xr else 0))
    out[key] = dict(mnemonic=m, field=f, label=r["label"], axes=ax)
    stats["GEOM " + geometry.split(":")[0]] += 1
    stats["LIVE " + liveness.split(":")[0].split("(")[0].split("|")[0].strip()] += 1
    stats["SEM " + semantics.split(":")[0].split("--")[0].strip()] += 1
    stats["REPRO " + repro.split(":")[0]] += 1
    stats["TGT " + target.split(":")[0]] += 1
    stats["GATE " + ("passed-own-gate" if fg.startswith("PASSED") else "never-promoted")] += 1

json.dump(out, open(os.path.join(HERE, "axes.json"), "w"), indent=1)
for k in sorted(stats): print("%5d %s" % (stats[k], k))
print("rows:", len(out))
