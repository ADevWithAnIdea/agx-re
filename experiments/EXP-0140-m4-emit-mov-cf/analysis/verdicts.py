#!/usr/bin/env python3
"""EXP-0140 analysis: cross-run gate + per-field verdicts.

No GPU.  Reads the two gated `raw/<run>/sweep.jsonl` captures, gates them
against each other, derives the semantics each sweep established, and writes
`analysis/field_verdicts.json` in the FIELD-SWEEP-PROTOCOL §5 shape (labels
strictly from `docs/evidence-classification.md` §2) plus a `db_defects` block.

Usage: verdicts.py [run01 run02]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(EXP.parents[1] / "tools" / "agx-isa"))
import cases as C  # noqa: E402

TARGET = "M4"
EVID = ["EXP-0140"]


def load(run):
    cases, checks = {}, []
    with open(EXP / "raw" / run / "sweep.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r.get("kind") == "baseline_check":
                checks.append(r)
            else:
                cases[r["i"]] = r
    return cases, checks


def repair_signed_compare(cases):
    """The capture driver compared the raw u32 output word against a SIGNED int32
    oracle, so any expected value with bit 31 set was scored a mismatch even when
    the stored `observed` and `oracle` fields are identical.  Only one oracle in
    the frozen matrix has bit 31 set (the bound constant u0 = 0xA1B2C3D4), plus
    the poison fill.  `raw/` is append-only evidence and is NOT edited: the
    outcome is recomputed here, from the record's own `observed` and `oracle`
    fields, and the number of repairs is reported.  The harness was fixed for any
    future capture.  Returns the number of records whose outcome changed."""
    n = 0
    for r in cases.values():
        if r["outcome"] in ("hang", "fault", "skipped", "invalid_run"):
            continue
        obs, orc = r["observed"], r["oracle"]
        if not orc or any(obs.get(k) is None for k in orc):
            continue
        match = all(obs.get(k) == v for k, v in orc.items())
        prim = obs[sorted(orc, key=int)[0]]
        outcome = "ok" if match else ("silent_zero" if prim == 0 else "wrong_value")
        if (match, outcome) != (r["match"], r["outcome"]):
            r["match"], r["outcome"] = match, outcome
            r["repaired_signed_compare"] = True
            n += 1
    return n


def reclassify_no_store(a, b):
    """`invalid_run` means "the integrity check failed": on `uni` the sentinel word
    was missing; on `dsel5`/`gsel4`/`cf`, which have no room for a sentinel
    prologue, it means EVERY oracle word was still at its poison fill.

    On the control-flow carrier that second condition has a second, entirely
    legitimate cause: a field value that corrupts the mask stack so the final
    `device_store` never executes.  Contamination does not reproduce; a real
    encoding effect does.  So a case that is `invalid_run` in BOTH gated runs,
    with every trial reporting STATUS OK (no OS fault string at all), is
    re-labelled `wrong_value` with the note `no_store`.  Anything else stays
    `invalid_run` and is excluded from the cross-run gate as environmental.

    Returns the number of cases re-labelled."""
    n = 0
    for i, ra in a.items():
        rb = b.get(i)
        if rb is None:
            continue
        if ra["outcome"] != "invalid_run" or rb["outcome"] != "invalid_run":
            continue
        allok = all(st == "OK" for r in (ra, rb) for st in r.get("trial_statuses", []))
        if not allok:
            continue
        for r in (ra, rb):
            r["outcome"] = "wrong_value"
            r["note"] = (r.get("note") or "") + " | no_store: no output word was written " \
                        "(reproduced in both gated runs, every trial STATUS OK)"
            r["reclassified_no_store"] = True
        n += 1
    return n


def gate(a, b):
    """Cross-run comparison.  Environmental classes (`invalid_run`) are
    segregated exactly as EXP-0136 segregated InnocentVictim failures."""
    common = sorted(set(a) & set(b))
    agree, disagree, env = 0, [], 0
    for i in common:
        ra, rb = a[i], b[i]
        if "invalid_run" in (ra["outcome"], rb["outcome"]):
            env += 1
            continue
        if (ra["outcome"], ra["observed"]) == (rb["outcome"], rb["observed"]):
            agree += 1
        else:
            disagree.append({"i": i, "group": ra["group"], "value": ra["value"],
                              "run01": [ra["outcome"], ra["observed"]],
                              "run02": [rb["outcome"], rb["observed"]]})
    return {"n_common": len(common), "agree": agree, "disagree": len(disagree),
            "environmental_excluded": env, "disagreements": disagree[:60]}


def group_rows(cases, prefix):
    return [r for r in cases.values() if r["group"] == prefix]


def summarise(rows):
    return dict(Counter(r["outcome"] for r in rows))


def coverage(rows):
    vals = sorted({r["value"] for r in rows})
    if not vals:
        return "none"
    if len(vals) == 256 and vals[0] == 0 and vals[-1] == 255:
        return "0..255 dense (all 256 values)"
    if len(vals) == 16 and vals == list(range(16)):
        return "0..15 dense (all 16 values)"
    if len(vals) == 32 and vals == list(range(32)):
        return "0..31 dense (all 32 values)"
    return "%d values sampled: %s%s" % (len(vals), vals[:10],
                                         " ..." if len(vals) > 10 else "")


def main():
    runs = sys.argv[1:3] or ["m4_20260828_run02", "m4_20260828_run03"]
    a, ca = load(runs[0])
    b, cb = load(runs[1])
    n_rep = repair_signed_compare(a) + repair_signed_compare(b)
    n_nostore = reclassify_no_store(a, b)
    g = gate(a, b)
    g["reclassified_no_store"] = n_nostore
    g["repaired_signed_compare"] = n_rep

    out = {"experiment": "EXP-0140", "target": TARGET, "runs": runs,
           "cross_run_gate": g,
           "baseline_checks": {"run01": summarise_checks(ca), "run02": summarise_checks(cb)},
           "fields": {}, "db_defects": {}, "falsifiers": {}, "notes": []}

    # ---- falsifiers: every pre-registered expect_match=False must have failed
    for r in list(a.values()) + list(b.values()):
        if r.get("expect_match") is False:
            key = r["group"]
            ok = (r["match"] is False)
            out["falsifiers"].setdefault(key, []).append(
                {"run_outcome": r["outcome"], "behaved_as_predicted": ok})

    def emit(key, label, rng, semantics, note="", extra=None):
        d = {"label": label, "range": rng, "target": TARGET, "evidence": EVID,
             "semantics": semantics}
        if note:
            d["note"] = note
        if extra:
            d.update(extra)
        out["fields"][key] = d

    # -------------------------------------------------------------- MOV arm
    analyse_mov(a, b, out, emit)
    analyse_get_sr(a, b, out, emit)
    analyse_regmove(a, b, out, emit)
    analyse_sel(a, b, out, emit, "sel", "dsel5")
    analyse_sel(a, b, out, emit, "psel", "gsel4")
    analyse_cf(a, b, out, emit)

    (HERE / "field_verdicts.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    g_print = {k: v for k, v in g.items() if k != "disagreements"}
    g_print["disagreement_groups"] = dict(Counter(x["group"] for x in g["disagreements"]))
    print(json.dumps({"cross_run_gate": g_print,
                      "n_fields": len(out["fields"]),
                      "labels": dict(Counter(v["label"] for v in out["fields"].values())),
                      "falsifiers_ok": all(x["behaved_as_predicted"]
                                            for v in out["falsifiers"].values() for x in v),
                      "db_defects": list(out["db_defects"])}, indent=1))


def summarise_checks(checks):
    return {"n": len(checks), "outcomes": dict(Counter(c["outcome"] for c in checks))}


def both(a, b, group):
    return group_rows(a, group), group_rows(b, group)


def split_by_prediction(rows):
    """Cases whose oracle is a real PREDICTION (`expect_match` True/False) versus
    cases whose oracle is the carrier's own baseline (an INERTNESS test, no
    prediction claimed).  `ok` means opposite things in the two sets, so they
    are never mixed."""
    pred = [r for r in rows if r.get("expect_match") is not None]
    inert = [r for r in rows if r.get("expect_match") is None]
    return pred, inert


def moved_values(rows, target_value):
    """Values whose observed word 0 equals `target_value` -- read straight off
    the observation, independent of which oracle the case carried."""
    return sorted({r["value"] for r in rows
                   if r["observed"].get("0") == target_value})


def comparable(ra, rb):
    """Case pairs that are eligible for the cross-run comparison at all.  Keyed
    by the frozen matrix's case index `i`, NOT by field value: several groups run
    the same value twice (two `sel` input vectors, two `psel` dispatch shapes),
    so keying by value would silently compare a grid-8 row against a grid-4 row.
    Pairs where either side is `invalid_run` (the integrity check failed) or
    `skipped` (lost to the hang budget) are EXCLUDED, exactly as EXP-0136
    excluded InnocentVictim failures from its own cross-run gate -- they are
    facts about the machine, not about the encoding."""
    ib = {r["i"]: r for r in rb}
    out = []
    for r in ra:
        s = ib.get(r["i"])
        if s is None:
            continue
        if r["outcome"] in ("invalid_run", "skipped") or s["outcome"] in ("invalid_run", "skipped"):
            continue
        out.append((r, s))
    return out


def stable(ra, rb):
    """Comparable cases whose outcome+observed agree across both gated runs."""
    return [r for r, s in comparable(ra, rb)
            if (r["outcome"], r["observed"]) == (s["outcome"], s["observed"])]


# ---------------------------------------------------------------- analysers
def analyse_mov(a, b, out, emit):
    ra, rb = both(a, b, "mov_imm.dst")
    st = stable(ra, rb)
    allok = all(r["outcome"] == "ok" for r in st)
    scan_a, scan_b = both(a, b, "mov_imm.dst.alias_scan")
    scan_ok = all(r["outcome"] == "ok" for r in stable(scan_a, scan_b))
    emit("mov_imm.dst",
         "hardware-run" if (allok and len(st) == 16 and scan_ok) else "untested",
         coverage(ra), "4-bit GPR selector: mov_imm(D, imm) writes r_D and no other register",
         note="all 16 values executed with a host-computed oracle; four 12-register aliasing "
              "scans confirm no second register changes; %d/16 values reproduced identically "
              "across both gated runs" % len(st),
         extra={"outcomes": summarise(ra), "alias_scans_ok": scan_ok})
    # imm_top boundary correction
    ub = group_rows(a, "mov_imm.dst.imm_boundary")
    pb = group_rows(a, "mov_imm.dst.imm_boundary_padded")
    if ub and pb:
        out["db_defects"]["mov_imm.imm_top"] = {
            "claim": "`mov_imm` with imm_top=1 (immediate 128..255) does NOT write the "
                     "destination register at all, and unpadded it consumes the FOLLOWING "
                     "2-byte instruction. EXP-0128 read it as a 'silent zero' because its "
                     "read-back buffer was zero-initialised; against a POISONED buffer the "
                     "register is seen to keep its previous value.",
            "evidence": {"unpadded": [ub[0]["outcome"], ub[0]["observed"]],
                          "padded_control": [pb[0]["outcome"], pb[0]["observed"]],
                          "poison_word0": C.POISON_WORD(0), "seed_value": C.POISON},
            "implication": "an emitter must treat mov_imm's immediate as 7 bits; bit 7 selects "
                            "a different (longer) instruction, it does not extend the immediate"}
    out["db_defects"]["mov_imm.imm7==12"] = {
        "claim": "the 2-byte encoding of `mov_imm` with imm7 == 12 does not tokenize under the "
                 "current length rule (byte+1 = 0x0C makes the pair look like the 4-byte 0x?c "
                 "preamble/get_sr group); it is the ONLY immediate in 0..127 with this property, "
                 "checked exhaustively over all 16 dst values",
        "evidence": "static check, tools/agx-isa/isadb.instr_length",
        "implication": "decoder defect, not necessarily a hardware one; every immediate this "
                        "experiment emits avoids 12"}


def analyse_get_sr(a, b, out, emit):
    for field, group in (("form", "get_sr.form"), ("dp_width", "get_sr.dp_width"),
                          ("dp_marker", "get_sr.dp_marker")):
        ra, rb = both(a, b, group)
        st = stable(ra, rb)
        inert = sorted(r["value"] for r in st if r["outcome"] == "ok")
        bad = sorted(r["value"] for r in st if r["outcome"] not in ("ok",))
        cmp_ = comparable(ra, rb)
        unstable = sorted({r["value"] for r, _ in cmp_} - {r["value"] for r in st})
        emit("get_sr." + field,
             "hardware-run" if (cmp_ and len(st) >= 0.98 * len(cmp_)
                                 and len(cmp_) >= 0.9 * len(ra)) else "untested",
             coverage(ra),
             "swept against a per-lane thread_position_in_grid.x oracle (out[i] == i for a "
             "working read); values not in `inert_values` change or destroy the SR read",
             note="%d/%d values reproduced identically across both gated runs" % (len(st), len(ra)),
             extra={"outcomes": summarise(ra), "inert_values": inert,
                     "non_inert_count": len(bad), "non_inert_values": bad[:64],
                     "n_stable_across_runs": len(st), "n_comparable": len(cmp_),
                     "values_not_reproducing": unstable})


def analyse_regmove(a, b, out, emit):
    groups = {"dst": "regmove.dst", "usrc": "regmove.usrc",
              "byte2": "regmove.byte2", "byte3": "regmove.byte3"}
    res = {}
    for k, gname in groups.items():
        ra, rb = both(a, b, gname)
        st = stable(ra, rb)
        res[k] = (ra, st)
    # which byte2 / byte3 values actually moved the value?
    moving_b2 = moved_values(res["byte2"][1], C.REGMOVE_IMM_K)
    moving_b3 = moved_values(res["byte3"][1], C.REGMOVE_IMM_K)
    inert_b2 = sorted({r["value"] for r in res["byte2"][1]
                       if r["observed"].get("0") == C.POISON})
    inert_b3 = sorted({r["value"] for r in res["byte3"][1]
                       if r["observed"].get("0") == C.POISON})
    imm_ok = [r for r in res["usrc"][1] if r["value"] >= 0x80 and r["outcome"] == "ok"]
    uni_ok = [r for r in res["usrc"][1]
              if r["value"] in C.USRC_UNIFORM_MAP and r["outcome"] == "ok"]

    shared = ("the five db.json descriptors reg_move_c0/c1/c2var/c9/cb and uniform_mov are ONE "
              "4-byte instruction  (dst<<4)|0x0B, byte+1 = src, byte+2 = form, byte+3 = opdesc")
    for mnem in ("reg_move_c0", "reg_move_c1", "reg_move_c2var", "reg_move_c9",
                 "reg_move_cb", "uniform_mov"):
        emit(mnem + ".dst",
             "hardware-run" if len(res["dst"][1]) == 16 else "untested",
             coverage(res["dst"][0]),
             "byte0 high nibble = destination GPR r0..r15. " + shared,
             note="16/16 dense, verified by reading r_D back and checking a control register",
             extra={"outcomes": summarise(res["dst"][0])})
    emit("uniform_mov.usrc",
         "hardware-run" if (len(imm_ok) == 128 and len(uni_ok) == 8) else
         ("hardware-run" if len(imm_ok) >= 120 else "untested"),
         coverage(res["usrc"][0]),
         "byte+1. usrc >= 0x80 MATERIALISES THE IMMEDIATE (usrc & 0x7F) into the destination "
         "GPR -- a 7-bit immediate move, not a uniform read. usrc < 0x80 selects a uniform "
         "register, pair-quantised (usrc and usrc^1 read the same 32-bit word, distinct "
         "uniforms step by 4); our four bound constants were read back exactly at usrc "
         "{0x18,0x19},{0x1C,0x1D},{0x20,0x21},{0x24,0x25}",
         note="%d/128 immediate-region values matched their host-computed oracle exactly; "
              "%d/8 mapped uniform indices returned the bound magic constant" % (len(imm_ok), len(uni_ok)),
         extra={"outcomes": summarise(res["usrc"][0]),
                 "immediate_region_matches": len(imm_ok),
                 "uniform_indices_matched": sorted(r["value"] for r in uni_ok)})
    for mnem, fld in (("reg_move_c0", "src_flag"), ("reg_move_c1", "src_flag"),
                       ("reg_move_c9", "src_flag"), ("reg_move_c2var", "src_flag"),
                       ("reg_move_c2var", "src_reg"), ("reg_move_cb", "src")):
        emit("%s.%s" % (mnem, fld),
             "hardware-run" if len(imm_ok) >= 120 else "untested",
             coverage(res["usrc"][0]),
             "part of the SAME byte+1 as uniform_mov.usrc (bit7 = the immediate/uniform-file "
             "selector, bits 0..6 = the immediate value or the pair-quantised uniform index); "
             + shared,
             note="the whole byte was swept 0..255 in one sweep; db.json's split of this byte "
                  "into src_reg + src_flag does not match the observed behaviour",
             extra={"outcomes": summarise(res["usrc"][0])})
    for mnem, fld in (("reg_move_c0", "src_class"), ("reg_move_c1", "src_class"),
                       ("reg_move_c9", "src_class"), ("reg_move_c2var", "subform"),
                       ("reg_move_cb", "form")):
        emit("%s.%s" % (mnem, fld), "hardware-run" if res["byte2"][1] else "untested",
             coverage(res["byte2"][0]),
             "byte+2 = the form selector for the whole 0x?B family; only the values in "
             "`moving_values` move a value into the destination -- every other value leaves "
             "the destination untouched or destroys it. " + shared,
             note="db.json models this byte as a 4-bit nibble per descriptor; it is one 8-bit "
                  "field and the descriptors are not distinct instructions",
             extra={"outcomes": summarise(res["byte2"][0]), "moving_values": moving_b2,
                     "inert_values_count": len(inert_b2),
                     "n_stable_across_runs": len(res["byte2"][1])})
    for mnem, fld in (("reg_move_c0", "op_desc"), ("reg_move_c1", "op_desc"),
                       ("reg_move_c9", "op_desc"), ("reg_move_c2var", "op_desc"),
                       ("reg_move_cb", "b3")):
        emit("%s.%s" % (mnem, fld), "hardware-run" if res["byte3"][1] else "untested",
             coverage(res["byte3"][0]),
             "byte+3 = the operation descriptor; only the values in `moving_values` move a "
             "value. " + shared,
             extra={"outcomes": summarise(res["byte3"][0]), "moving_values": moving_b3,
                     "inert_values_count": len(inert_b3),
                     "n_stable_across_runs": len(res["byte3"][1])})
    desc = {}
    for nm in ("reg_move_c0", "reg_move_c1", "reg_move_c2var", "reg_move_c9", "reg_move_cb"):
        rows = group_rows(a, "regmove.descriptor_" + nm)
        if rows:
            desc[nm] = {"outcome": rows[0]["outcome"], "moved": rows[0]["match"]}
    out["db_defects"]["reg_move_family"] = {
        "claim": "reg_move_c0 / reg_move_c1 / reg_move_c2var / reg_move_c9 / reg_move_cb / "
                 "uniform_mov are NOT six instructions. They are one 4-byte instruction whose "
                 "byte+2 is a form selector; db.json's five descriptors are five values of that "
                 "one field. Confirmed by sweeping byte+2 over all 256 values in a single "
                 "carrier and observing which move a value.",
        "descriptor_probe": desc, "moving_byte2_values": moving_b2,
        "moving_byte3_values": moving_b3,
        "implication": "an emitter needs ONE descriptor with four byte fields, not five "
                        "descriptors; and the byte+1 split into src_reg + src_flag does not "
                        "match hardware -- bit7 selects immediate-vs-uniform-file"}


def analyse_sel(a, b, out, emit, mnem, carrier):
    if mnem == "sel":
        groups = [("b1", "sel.body.b1"), ("b2", "sel.body.b2"), ("b3", "sel.body.b3")]
        fieldname = "body"
    else:
        groups = [("flag", "psel.flag"), ("mode", "psel.mode"), ("sel", "psel.sel")]
        fieldname = None
    per = {}
    for tag, gname in groups:
        ra, rb = both(a, b, gname)
        st = stable(ra, rb)
        pred, inert = split_by_prediction(st)
        cmp_ = comparable(ra, rb)
        per[tag] = {"n": len(ra), "stable": len(st), "comparable": len(cmp_),
                     "outcomes": summarise(ra),
                     "matched_prediction": sorted({r["value"] for r in pred
                                                    if r["outcome"] == "ok"}),
                     "n_predictions": len(pred),
                     "inert_values": sorted({r["value"] for r in inert
                                              if r["outcome"] == "ok"}),
                     "changed_values_count": sum(1 for r in inert if r["outcome"] != "ok"),
                     "faults": sorted({r["value"] for r in st if r["outcome"] == "fault"}),
                     "coverage": coverage(ra)}
    wide = group_rows(a, "sel.body.wide") if mnem == "sel" else []
    imm_tag = "b3" if mnem == "sel" else "sel"
    imm_matches = [v for v in per[imm_tag]["matched_prediction"] if v >= 128]
    low_matches = [v for v in per[imm_tag]["matched_prediction"] if v < 128]
    label = ("hardware-run" if (len(imm_matches) + len(low_matches)) >= 240
             else "untested")
    sem = ("4-byte branchless conditional select. byte+3 is the predicate-FALSE operand: with "
           "bit7 set it is an 8-bit immediate whose VALUE IS THE BYTE (128..255); with bit7 "
           "clear it selects a register/other-file operand which read 0 in this carrier. "
           "byte+1 and byte+2 are the predicate/operand-source selectors -- see "
           "`per_byte` for the exhaustive outcome map of all 256 values of each.")
    if mnem == "sel":
        emit("sel.body", label, "each of the three body bytes swept 0..255 dense (x2 input "
                                "vectors), plus whole-field boundaries, all 24 powers of two "
                                "and 16 interior samples",
             sem,
             note="db.json models `body` as one opaque 24-bit raw field; it is three located "
                  "byte-fields. %d/128 byte+3 values >=0x80 and %d/128 values <0x80 matched "
                  "their host-computed oracle exactly."
                  % (len(imm_matches), len(low_matches)),
             extra={"per_byte": per, "wide_field_outcomes": summarise(wide)})
        out["db_defects"]["sel.body"] = {
            "claim": "`sel.body` is not an opaque 24-bit field: byte+3 is the predicate-FALSE "
                     "operand (bit7 = immediate flag, value = the byte itself), byte+2 and "
                     "byte+1 are operand/predicate source selectors with distinct outcome "
                     "classes across their full 256-value range.",
            "byte3_immediate_matches": len(imm_matches),
            "byte3_register_region_matches": len(low_matches),
            "per_byte_outcomes": {k: v["outcomes"] for k, v in per.items()}}
    else:
        for tag, gname in groups:
            lbl = ("hardware-run"
                   if (per[tag]["comparable"] >= 0.9 * per[tag]["n"]
                       and per[tag]["stable"] >= 0.98 * per[tag]["comparable"])
                   else "untested")
            if tag == "sel":
                lbl = label
            emit("psel." + tag, lbl, per[tag]["coverage"],
                 sem if tag == "sel" else
                 ("byte+%d of the 4-byte grid-predicate select; swept 0..255 dense against the "
                  "carrier's own baseline (an inertness test) at two dispatch shapes"
                  % (1 if tag == "flag" else 2)),
                 note="%d/%d comparable values reproduced identically across both gated runs "
                      "(of %d swept)"
                      % (per[tag]["stable"], per[tag]["comparable"], per[tag]["n"]),
                 extra={"outcomes": per[tag]["outcomes"],
                         "matched_prediction": per[tag]["matched_prediction"][:64],
                         "inert_values": per[tag]["inert_values"][:64],
                         "faults": per[tag]["faults"][:64]})


CF_FIELDS = [("if_push", "scope", "if_push.scope@7"),
             ("if_push", "scope_kind", "if_push.scope_kind@7"),
             ("if_push_pred", "scope", "if_push_pred.scope@4"),
             ("if_push_pred", "level", "if_push_pred.level@4"),
             ("jump", "branch_ctrl", "jump.branch_ctrl@13"),
             ("jump", "link", "jump.link@13"),
             ("jump_cond", "cf_scope", "jump_cond.cf_scope@5"),
             ("jump_cond", "reserved", "jump_cond.reserved@5"),
             ("pop_reconverge", "scope", "pop_reconverge.scope@14"),
             ("pop_reconverge", "scope_kind", "pop_reconverge.scope_kind@14"),
             ("ret", "linkmode", "ret.linkmode@12"),
             ("ret", "scoreboard", "ret.scoreboard@12")]


# LIVENESS ARGUMENT, per control-flow instruction (FIELD-SWEEP-PROTOCOL SS3.2).
# A field that is inert across its whole range is only a hardware fact if the
# instruction carrying it demonstrably executed.  The frozen skeleton's own
# per-lane oracle supplies that proof for three of the four:
#   * `jump`            -- the backward branch IS the loop; the oracle requires
#                          1,2,3,4,8,16 and 32 iterations on lanes 1..7, so any
#                          value that disabled it would change the result.
#   * `if_push` /
#     `pop_reconverge`  -- lane 7 takes the if/else TRUE arm and lanes 0..6 the
#                          FALSE arm, so the mask stack must push and reconverge
#                          correctly for the oracle to hold; and their own
#                          `scope_kind` sweeps DO produce non-`ok` outcomes,
#                          proving the sweep has discriminating power there.
#   * `ret`             -- `linkmode` faults on 224 of 256 values, so it plainly
#                          discriminates.
# `jump_cond` is the exception and is NOT claimed: it is the loop-entry guard,
# and the only lane whose guard is true has trip count 0, so both paths compute
# the same value.  Every one of its fields -- including `offset` pointed outside
# the program -- reproduced the baseline exactly.  The experiment therefore
# cannot show the branch was observably taken, and all three `jump_cond` fields
# stay `untested` with that stated.
CF_LIVENESS_PROVEN = {"jump", "if_push", "pop_reconverge", "ret", "if_push_pred"}


def analyse_cf(a, b, out, emit):
    # which instructions showed ANY non-`ok` executed outcome in this capture?
    discriminating = set()
    for mnem, field, group in CF_FIELDS:
        for r in group_rows(a, group):
            if r["outcome"] not in ("ok", "skipped", "invalid_run"):
                discriminating.add(mnem)
    out["notes"].append(
        "CF instructions whose sweeps produced at least one non-`ok` executed outcome "
        "(i.e. the method demonstrably discriminates on them): %s"
        % sorted(discriminating))
    for mnem, field, group in CF_FIELDS:
        ra, rb = both(a, b, group)
        if not ra:
            continue
        st = stable(ra, rb)
        skipped = [r for r in ra if r["outcome"] == "skipped"]
        inert = sorted(r["value"] for r in st if r["outcome"] == "ok")
        faults = sorted(r["value"] for r in st if r["outcome"] == "fault")
        hangs = sorted(r["value"] for r in st if r["outcome"] == "hang")
        done = len(ra) - len(skipped)
        cmp_ = comparable(ra, rb)
        unstable = sorted({r["value"] for r, _ in cmp_} - {r["value"] for r in st})
        # A dense 256-value sweep on a shared, contended GPU is not expected to be
        # bit-identical twice (FIELD-SWEEP-PROTOCOL SS7).  The bar used here: the whole
        # sweep must have executed (nothing lost to the hang budget) and at least 98% of
        # its values must reproduce identically across the two gated runs.  The values
        # that did NOT reproduce are listed, never hidden.
        live = (mnem in CF_LIVENESS_PROVEN) and (mnem in discriminating
                                                  or mnem in ("jump",))
        label = "hardware-run" if (live and done == len(ra) and cmp_ and
                                    len(cmp_) >= 0.9 * len(ra) and
                                    len(st) >= 0.98 * len(cmp_)) else "untested"
        emit("%s.%s" % (mnem, field), label, coverage([r for r in ra if r["outcome"] != "skipped"]),
             "swept inside EXP-0090/EXP-0112's frozen, HW-validated loop+if/else->select "
             "skeleton against its host-computed per-lane float oracle; branch displacements "
             "were never recomputed. `inert_values` reproduce the skeleton's correct result; "
             "all other values change or destroy it. LIVENESS: the oracle itself proves the "
             "surrounding control flow executed -- the per-lane results require the loop to "
             "run 1,2,3,4,8,16 and 32 times and require both if/else arms to be selected -- "
             "so a field that is inert here is inert in a program that provably branched.",
             note="%d/%d values executed (%d skipped by the hang budget); %d comparable "
                  "across the two gated runs (pairs where either side failed its integrity "
                  "check or was skipped are excluded), %d of those identical"
                  % (done, len(ra), len(skipped), len(cmp_), len(st)),
             extra={"outcomes": summarise(ra), "inert_values": inert,
                     "fault_values": faults, "hang_values": hangs,
                     "n_stable_across_runs": len(st), "n_executed": done,
                     "n_comparable": len(cmp_), "values_not_reproducing": unstable,
                     "instruction_liveness_proven": bool(live),
                     "sweep_discriminates_on_this_instruction": mnem in discriminating})
    # pop_reconverge.reserved + jump_cond.offset
    ra, rb = both(a, b, "pop_reconverge.reserved@14")
    if ra:
        st = stable(ra, rb)
        emit("pop_reconverge.reserved",
             "hardware-run" if len(st) >= 0.98 * len(ra) else "untested", coverage(ra),
             "16-bit tail; swept at boundaries, every power of two and 16 interior samples "
             "inside the frozen CF skeleton",
             extra={"outcomes": summarise(ra),
                     "inert_values": sorted(r["value"] for r in st if r["outcome"] == "ok")})
    ra, rb = both(a, b, "jump_cond.offset")
    if ra:
        st = stable(ra, rb)
        executed = [r for r in ra if r["outcome"] != "skipped"]
        nonok = [r for r in executed if r["outcome"] != "ok"]
        # LIVENESS (FIELD-SWEEP-PROTOCOL SS3.2).  Every structured offset -- including
        # targets that are not instruction starts and targets OUTSIDE the program --
        # reproduced the skeleton's baseline exactly.  A displacement whose target can
        # be moved anywhere without changing the output is a displacement the carrier
        # never takes: the only lane whose guard is true has trip count 0, so both
        # paths compute the same value.  The sweep therefore has NO discriminating
        # power over this field and must not be promoted, however clean it looks.
        live = bool(nonok)
        emit("jump_cond.offset", "hardware-run" if (live and len(st) >= 0.98 * len(ra))
             else "untested", coverage(ra),
             "signed 48-bit byte displacement. NOT ESTABLISHED by this experiment: on the "
             "frozen EXP-0090/EXP-0112 skeleton the conditional branch is not observably "
             "taken, so moving its target -- even outside the program -- does not change the "
             "output. EXP-0115's reach was measured on `jump` and does NOT transfer to "
             "`jump_cond`; that gap remains open.",
             note="structured, bounded offset set (%d values: valid instruction starts in the "
                  "frozen skeleton, +-1..4 around the natural target, and far probes) -- "
                  "deliberately NOT a dense displacement sweep, which is the EXP-0128 hang "
                  "construction. %d of the executed cases differed from the baseline, so the "
                  "carrier does not make this field live. A successor needs a carrier whose "
                  "conditional branch target is observable." % (len(ra), len(nonok)),
             extra={"outcomes": summarise(ra), "n_tested": len(ra),
                     "carrier_makes_field_live": live,
                     "values_tested": sorted(r["value"] for r in executed)})


if __name__ == "__main__":
    main()
