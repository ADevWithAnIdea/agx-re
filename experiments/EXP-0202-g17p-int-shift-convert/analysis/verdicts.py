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

# A field whose believed role is a DIMENSION we can only observe through another
# field must not be called inert when that other field is itself not shown live.
# FIELD-SWEEP-PROTOCOL section 9 rule 1 and Gate B: "If the positive control
# fails, the arm is `carrier-undecidable`; zero movement is not evidence of
# inertness."
DIMENSION_CONTROL = {
    "shift_amt_move.src_flag": "b_alu10_lo7.src_flag",
}

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


NOTES = {
 "shift_amt_move.src_flag":
   "TESTED ENVELOPE: 11 boundary-aligned occurrences on 9 carriers spanning SEVEN operand-producer "
   "classes (device memory load, thread-invariant `constant uint&`, ALU chain, thread-position "
   "system value, SIMD lane index, overwrite with an intervening independent ALU op, control-flow "
   "merge), each swept at BOTH values of the bit and, on six occurrences, jointly with all 128 "
   "source indices (the byte+1 composite arm). In every one of 768 index/flag comparisons across "
   "two gated runs in opposite case order the two flag values give BYTE-IDENTICAL output. "
   "SEPARATELY: across all 56 authored carriers the COMPILER emits src_flag = 0 in every one of "
   "the 11 occurrences -- a compiler-differential result in its own right, and a negative one. "
   "The verdict is nevertheless `carrier-undecidable`, not inert: the positive control in the "
   "dimension this bit is believed to select -- `b_alu10_lo7.src_flag`, the same bit, the same 7+1 "
   "byte+1 split, the same enum, the same 0x?b family, and one the compiler DOES emit at both "
   "values -- is itself indistinguishable at both values. Nothing here has shown the harness can "
   "observe a source-class change at all, so `inert in this envelope; global role unknown` is the "
   "strongest safe statement, and even that is bounded by the missing control.",
 "b_alu10_lo7.src_flag":
   "Dispatched as the SAME-DIMENSION POSITIVE CONTROL for shift_amt_move.src_flag, and reported "
   "here as a field in its own right. Three boundary-aligned occurrences on two carriers; the "
   "compiler emits 1 at cvt_i64@46 and cvt_i64@78 and 0 at pc_tg@12. Splicing the other value "
   "leaves the output BYTE-IDENTICAL at all three, in both gated runs. Its own `src_reg` control "
   "DOES move (19 of 20 values break the result), so the source OPERAND is being read -- what has "
   "not been shown is that any FILE selection is observable. Two carriers is below section 7's "
   "three-carrier bar for a general accepted-inert rule.",
 "ibitcount.cache":
   "byte+2 bit 1, the only free bit of byte+2 under this descriptor's match (byte+2 in {0x54, "
   "0x56}), so 2 of 2 encodable values is the FULL range. Ten occurrences on nine carriers "
   "spanning standalone-store, ALU-consumed, compare-consumed, two-occurrence, find-msb, "
   "reverse-bits, threadgroup-memory+barrier (grid 64 / tg 32) and wide-readback carriers. "
   "ASYMMETRIC, exactly as `irotate.b2` is: on the SEVEN occurrences the compiler compiled to 1, "
   "forcing 0 breaks the result (`wrong_value`) in both runs; on the THREE it compiled to 0, BOTH "
   "values reproduce the host vector. So value 1 is universally safe here and value 0 is "
   "context-dependent. The pre-registered symmetric writeback-enable model is therefore REFUTED at "
   "3 of 20 checks and refined; the refinement is post-hoc and is offered as a hypothesis for a "
   "successor, not as a mapped semantic.",
 "ibitcount.dst":
   "Dense 0..255 on five occurrences under TWO DISJOINT READBACK PLANS (four single-word carriers "
   "and `pc_dump`, which keeps four mutually distinct live values per lane at fixed store "
   "indices). Two corrections to db.json's `dst = reg<<1` model, both reproduced in two gated runs "
   "in opposite case order: (1) the program reproduces its host vector at EXACTLY TWO values, "
   "{compiled, compiled+1}, on every one of the five occurrences -- so bit 0 of `dst` is NOT part "
   "of the register index; (2) values 192..255 fault, CONTIGUOUSLY, all 64 of them, on all five "
   "occurrences. `dst[7:6] == 0b11` is illegal, exactly the shape already established for "
   "`frag_color_pack.dst` (there a hang wall, here a contained fault wall). The whole hazard region "
   "was mapped deliberately with NO abort path and the device survived; there were no hangs. "
   "CROSS-TARGET: EXP-0139 found the same byte on M4 (`iunary.dst`) faulting at 192-241 and "
   "243-255 -- with 242 NOT faulting. On G17P 242 DOES fault. The pre-registered M4-transferred "
   "prediction is refuted at exactly that one value, which is why it was made.",
 "irotate.operands":
   "THE 40-BIT FIELD IS NOT ONE FIELD, and this is the headline. Byte-wise dense sweeps on two "
   "carriers plus the first JOINT 40-bit arm this field has ever had (70 values: {0,1,2,max-1,max}, "
   "all 40 powers of two, the compiled value and +/-1, and 24 fixed asymmetric interior samples) "
   "give a clean five-way split with EXACTLY the meanings EXP-0139 established for the same blob "
   "in `iunary` (DEF-0139-1): byte+3 = dst (reproduces at {0,1}, faults 192-255), byte+4 = an "
   "op-enable gate (128 of 256 values reproduce), byte+5 = src (reproduces at 0..3), byte+6 = THE "
   "IMMEDIATE ROTATE AMOUNT, byte+7 = tail (reproduces at the 8 even values 0..14). "
   "BYTE+6 IS SEMANTICALLY MAPPED. The census byte-diff over compiled amounts {1,5,7,13,19,31} "
   "gave byte+6 = 4*(32-K); the sweep then confirmed the EXACT host-computed rotate-left-by-K "
   "vector at all 33 modelled values on four carriers in both runs, 264 exact vector matches with "
   "zero misses. Independently -- without using the formula at all -- searching all 32 amounts for "
   "one that reproduces each observation recovers a single rotate-LEFT amount at exactly those 33 "
   "values, 32 DISTINCT amounts, every one agreeing with the formula. The codewords are asymmetric "
   "(0x8000000B + t*0x01234567), so direction and amount are both determined by the data. "
   "An emitter can therefore synthesise `rotate(x, K)` for any K in 0..31. Values with byte+6 >> 2 "
   "> 32 are NOT a rotate by any amount -- bounded negative, role unknown. The FIELD-level label "
   "stays `isolated-byte-diff` because only one of its five bytes is mapped; byte+6 bits[6:2] alone "
   "meets the `hardware-run` bar and the orchestrator should consider splitting the descriptor.",
 "iunary.b1":
   "NO `iunary` INSTRUCTION EXISTS IN OUR COMPILED CODE. Requiring instruction-BOUNDARY alignment, "
   "zero of 56 authored carriers emit one (EXP-0139 found zero in 30 of its own); every "
   "byte0 == 0x27 instruction our compute MSL produces is claimed by a tighter descriptor. The "
   "apparent hits before the boundary check were INTERIORS of longer instructions. So the field is "
   "reached by SYNTHESIS: an 8-byte `ibitcount` occurrence is rewritten in place to `27 2d 22 ..`, "
   "which tokenizes as `iunary` and -- confirmed by the arm's own baseline in both runs -- still "
   "computes the popcount. Dense 0..255 on two carriers. STRUCTURE, reproduced identically in both "
   "runs: the low three bits alone decide. b1 & 7 == 5 delivers the correct count (32 of 256 "
   "values); b1 & 7 == 6 delivers a different coherent value (32); the other 192 do not deliver at "
   "all, and their hardness is CARRIER-DEPENDENT -- `not_written` on the store carrier, `fault` on "
   "the ALU-consumed carrier. That map is post-hoc, so the label stays at liveness.",
 "iunary.opsel":
   "Same synthesized carrier as `iunary.b1`. Dense 0..255 on two carriers, identical in both runs: "
   "128 of 256 values deliver the correct count and 128 do not, and the deciding bit is BIT 1 of "
   "byte+2 -- the same bit the tight `ibitcount` descriptor models as `cache`. Values 0x54..0x57 "
   "re-tokenize as `ibitcount`, so the encodable range under this descriptor is 252 of 256, and "
   "those four are excluded from it rather than counted as movement. The map is post-hoc.",
 "cvt_f2i.b9":
   "ACCEPTED-INERT over a materially wider envelope than the refusal that preceded it. EXP-0168 "
   "refused this field as INERT-SINGLE (256/256 ok, one distinct payload); EXP-0184 then supplied "
   "five carriers that all varied DESTINATION WIDTH/SIGN -- the dimension db.json assigns to "
   "byte+8 -- so for byte+9 they were one carrier. The six occurrences here span RESULT ROUTING "
   "(byte+2 = 0x54 and 0x56), CONVERT OP (0x96 / 0xac / 0xb4), SOURCE CLASS (2 and 3), SOURCE "
   "WIDTH (float and half), a VECTOR form and four destination registers; every one has a control "
   "(`dst`) that moves and fails the oracle. 256 of 256 values are `ok` on all six, with ONE "
   "distinct payload per arm, in two gated runs in opposite case order -- 3072 ledger-verified "
   "cases. The pre-registered LIVE model is refuted at 255 of 256 values per arm, which is the "
   "result. Safe wording: inert in this envelope; global role unknown. Untested here: the fragment "
   "and vertex stages, which need a render harness.",
}


def INSTRUCTION_ROW(per_arm, quiet_note):
    """`cvt_f2i._instruction` -- a behavioural claim, not a bit-field claim."""
    return {
     "label": "hardware-run", "verdict": "INSTRUCTION EXECUTED WITH PREDICTED SEMANTICS",
     "axes": {"encoding_geometry": "ledger-verified", "liveness": "live",
              "semantics": "bounded-map", "compiler_recipe": "generated-point",
              "target": "G17P-direct",
              "reproducibility": ("independently-confirmed" if quiet_note else
                                  "INCOMPLETE -- Gate E not met: the window was "
                                  "measured and was NOT quiet")},
     "range": "seven authored carriers, host-computed oracles; byte+7 swept dense 0..255",
     "target": "G17P", "evidence": ["EXP-0202"],
     "note":
       "Raises the instruction-level row from `corpus-correlation` (EXP-0013 on M4/A18, never "
       "re-run on G17P). Directly observed on G17P, identically in two gated runs in opposite case "
       "order: (a) seven authored convert carriers -- stored, ALU-consumed, rint-rounded, vector, "
       "uniform-sourced, half-sourced and the out-of-range carrier -- each reproduce a host-computed "
       "truncate-toward-zero vector at their unmutated baseline; (b) with lane 7 fed "
       "2147483904.0 = 2^31 + 2^8 (exactly representable in f32, OUTSIDE int32), the SIGNED convert "
       "returns 0x7FFFFFFF: the hardware SATURATES, it does not wrap. That is a hardware fact no "
       "in-range test can reach. (c) Sweeping byte+7 dense 0..255 gives an exact, reproducible "
       "seven-way map of that out-of-range lane: 0x0000FFFF at 0x08-0x1F, 0x7FFFFFFF at 0x40-0x5F, "
       "0x80000000 at 0x60-0x7F, 0x000000FF at 0x80-0x9F, 0x00007FFF at 0xC0-0xDF, 0x00008000 at "
       "0xE0-0xFF, and 0 elsewhere -- always with bit 3 SET and bit 4 a don't-care. Read as a "
       "descriptor: bit 3 = enable, bits 7..5 = destination class, and the observed saturation "
       "bounds are exactly {u8, u16, s16, s32} maxima and their minima. This CONFIRMS EXP-0013's "
       "'bit 6 selects signed vs unsigned' only in part and REFINES it: byte+7 is a destination "
       "width + signedness + saturation-bound descriptor, and bit 6 alone does not isolate the "
       "sign. Corroborated by our own compiler, which emits 0x48 for float->int and 0x08 for "
       "half->ushort. The bit-field row `cvt_f2i.signflag` is NOT relabelled here: its arm carries "
       "no pre-registered control on that occurrence, so the mechanical gate returns "
       "`carrier-undecidable` for the FIELD even though the instruction-level claim stands. That "
       "arm-design gap is recorded, not papered over.",
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
        # Gate E is currently unmeetable on this device: the quiet window was
        # MEASURED in both runs and was never quiet (the concurrent fan-out).
        # That is reported as an incomplete axis, not smoothed away -- and it is
        # the only axis this experiment leaves open.
        repro = ("independently-confirmed" if clean_window else
                 "INCOMPLETE -- Gate E not met: the confirmation window was "
                 "measured and was NOT quiet (see _quiet_window). Cross-run "
                 "agreement is nevertheless 10156/10156 across the pair, in "
                 "opposite case order.")

        # Did the PRE-REGISTERED predictor hold, completely, on some arm in BOTH
        # runs? That is `isolated-byte-diff`'s literal definition -- "the
        # resulting program ran with the predicted effect at one or more points".
        # The threshold must scale with the field's own domain, or it repeats the
        # width-1 arithmetic trap: a 1-bit field has TWO encodable values, so a
        # flat "at least 8 semantic checks per arm" refuses it by arithmetic
        # rather than by evidence. An arm qualifies when its predictor held on
        # every check IN BOTH RUNS and it checked at least min(8, encodable).
        held_arms = [e for e in ents
                     if e[2]["sem_checked"] >= min(8, max(e[2]["encodable_range"], 2))
                     and e[2]["sem_checked"] >= 2
                     and e[2]["sem_match"] == e[2]["sem_checked"]
                     and e[2]["sem_match_runB"] == e[2]["sem_checked_runB"]]
        held_checks = sum(e[2]["sem_checked"] for e in held_arms)
        ratio = (float(semok) / semc) if semc else 0.0
        ratioB = (float(semok2) / semc2) if semc2 else 0.0

        # ---- legacy label: strict. Liveness may never imply semantics.
        if liveness == "carrier-undecidable":
            label, verdict = "untested", "CARRIER-UNDECIDABLE"
        elif liveness == "live" and semantics == "bounded-map" and not (
                set(e[0] for e in ents) - set(e[0] for e in held_arms)):
            label, verdict = "hardware-run", "LIVE + SEMANTICALLY BOUNDED"
        elif liveness == "live" and ((held_arms and held_checks >= 4)
                                     or (ratio >= 0.95 and ratioB >= 0.95)):
            label, verdict = "isolated-byte-diff", "LIVE + PREDICTED EFFECT AT TESTED POINTS"
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
            "predictor_held_on_arms": sorted(e[0] for e in held_arms),
            "sem_ratio_runA": round(ratio, 4), "sem_ratio_runB": round(ratioB, 4),
            "note": "",
        }

    # --- the dimension-control dependency, applied AFTER every row is scored
    for dep, ctlkey in DIMENSION_CONTROL.items():
        if dep not in verdicts:
            continue
        c = verdicts.get(ctlkey)
        ok = bool(c) and c["axes"]["liveness"] == "live"
        verdicts[dep]["dimension_control"] = {
            "field": ctlkey, "live": ok,
            "why": "the same bit, same 7+1 byte+1 split, same enum, same 0x?b "
                   "family -- and the COMPILER emits both of its values while "
                   "emitting only one of the dependent field's"}
        if not ok:
            verdicts[dep]["axes"]["liveness"] = "carrier-undecidable"
            verdicts[dep]["verdict"] = "CARRIER-UNDECIDABLE"
            verdicts[dep]["label"] = "untested"
            verdicts[dep]["note"] = (
                "The positive control IN THE DIMENSION THIS BIT IS BELIEVED TO "
                "SELECT (%s) did not move either, so the harness has not been "
                "shown able to observe that dimension at all. Zero movement is "
                "therefore NOT evidence of inertness -- this is "
                "`carrier-undecidable`, a recorded result and not a failure."
                % ctlkey)

    # --- per-arm semantic breakdown, so a field whose one sub-span HAS a
    #     confirmed predictor does not lose it in the field-level aggregate
    for key, v in verdicts.items():
        subs = {}
        for arm, rec in v["arms"].items():
            if not rec.get("sem_checked"):
                continue
            subs[arm] = {"sub": rec.get("sub"), "carrier": rec.get("carrier"),
                         "sem_checked": rec["sem_checked"],
                         "sem_match": rec["sem_match"],
                         "sem_checked_runB": rec["sem_checked_runB"],
                         "sem_match_runB": rec["sem_match_runB"],
                         "predictor_held": (rec["sem_match"] == rec["sem_checked"]
                                            and rec["sem_match_runB"] == rec["sem_checked_runB"])}
        v["semantics_per_arm"] = subs
        held = [a for a, d in subs.items() if d["predictor_held"]]
        v["arms_where_the_pre_registered_predictor_HELD"] = sorted(held)

    for k, n in NOTES.items():
        if k in verdicts:
            verdicts[k]["note"] = (verdicts[k].get("note") or "") + (" " if verdicts[k].get("note") else "") + n

    verdicts["cvt_f2i._instruction"] = INSTRUCTION_ROW(per_arm, quiet_note=clean_window)

    out = {"_generated_by": "analysis/verdicts.py",
           "_runs": [runA, runB],
           "_quiet_window": {"runA": qA, "runB": qB, "clean": clean_window},
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved_valid >= 1 AND moved >= 2*disagree",
                     "hard_outcomes": sorted(HARD),
                     "invalid_outcomes": sorted(INVALID),
                     "normative": "RE_EXPERIMENT_PROCESS_CORRECTIONS.md"},
           "_cross_run": {
              "shared_cases": None,
              "note": "computed by analysis/report.py; run03 vs run04, opposite "
                      "case order: 10156 of 10156 shared cases agree, ZERO "
                      "disagreements -- and zero even WITHOUT collapsing "
                      "ok/unexpected_ok. EXP-0189's `UNSTABLE` refusal of "
                      "irotate.operands does not reproduce."},
           "_contamination": {
              "runs_utc": "run02 19:18-19:30, run03 19:31-19:38, run04 19:39-19:46",
              "exp0204_hang_window_utc": "20:00-20:25 -- ENTIRELY AFTER all three "
                      "runs, so EXP-0204's ~18 declared device hangs are not in "
                      "this raw",
              "innocent_victim_cases": "run03 167, run04 160 -- every one RETRIED "
                      "up to 3x before being scored",
              "watchdog_timeouts": 0, "malformed_responses": 0, "hangs": 0,
              "note": "The `ErrorHang` fault-classification STRING appears on 514 "
                      "contained command-buffer faults, all of them on the two "
                      "mapped hazard walls (ibitcount.dst and irotate byte+3, "
                      "192-255, 64 values x 5 and x 2 arms). They are CONTAINED: "
                      "outcome `fault`, no watchdog timeout, no child restart, no "
                      "device wedge, and the next case runs clean. "
                      "`ErrorPageFault` appears 192 times, all on IU/pc_alu#0/b1 "
                      "-- the same 192 b1 values merely fail to write on the "
                      "store carrier, so the hardness is carrier-dependent."},
           "db_defects": [
             {"id": "DEF-0202-1", "descriptor": "irotate", "field": "operands",
              "claim": "the 40-bit `operands` raw field is NOT one field; it is five "
                       "one-byte sub-fields with the SAME meanings EXP-0139 established "
                       "for the identical blob in `iunary` (DEF-0139-1), plus one that "
                       "descriptor does not have",
              "evidence": "byte-wise dense 0..255 on two carriers + the first joint "
                          "40-bit arm, two gated runs in opposite case order, 0 "
                          "disagreements: byte+3 = dst (reproduces at {0,1}, faults "
                          "192-255), byte+4 = op-enable gate (128 of 256 reproduce), "
                          "byte+5 = src (reproduces at 0..3), byte+6 = THE IMMEDIATE "
                          "ROTATE AMOUNT with byte+6 = 4*(32-K) confirmed at 33 of 33 "
                          "modelled values on 4 carriers, byte+7 = tail (reproduces at "
                          "the 8 even values 0..14)",
              "action": "orchestrator's call; db.json NOT edited by this experiment"},
             {"id": "DEF-0202-2", "descriptor": "ibitcount", "field": "dst",
              "claim": "`dst = reg << 1` is incomplete in two ways: bit 0 is NOT part "
                       "of the register index (the program reproduces at EXACTLY "
                       "{compiled, compiled+1} on all five occurrences), and "
                       "dst[7:6] == 0b11 is ILLEGAL -- 192..255 fault contiguously, all "
                       "64 values, on all five occurrences, in both runs",
              "evidence": "PC/{pc_store,pc_alu,pc_two,iu_ctz,pc_dump}#0/dst, 2560 "
                          "ledger-verified cases",
              "action": "orchestrator's call"},
             {"id": "DEF-0202-3", "descriptor": "shift_amt_move / b_alu10_lo7 / the "
                                                "whole reg_move_cX family", "field": "src_flag",
              "claim": "the enum {0: gpr, 1: uniform/class} is UNSUPPORTED on G17P by "
                       "any observation we can make. Across 56 authored carriers the "
                       "compiler emits src_flag = 0 in all 11 `shift_amt_move` "
                       "occurrences; on `b_alu10_lo7`, where it emits BOTH values, "
                       "splicing either leaves the output byte-identical",
              "action": "NOT a request to remove the enum -- the honest status is "
                        "`carrier-undecidable`; recorded so a successor knows the enum "
                        "is inherited, not observed"},
             {"id": "DEF-0202-4", "descriptor": "ibitcount", "field": "form",
              "claim": "the enum {4: reverse, 5: count/scan} is incomplete: our own "
                       "`k_pc_two` compiles to form = 21 (0x15) at its second "
                       "occurrence, a value the enum does not name",
              "evidence": "raw/prefreeze/census_b.json, pc_two occ1 `2715540003005c04`",
              "action": "orchestrator's call"},
           ],
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
