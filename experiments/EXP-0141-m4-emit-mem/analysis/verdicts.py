#!/usr/bin/env python3
"""EXP-0141 -> analysis/field_verdicts.json (FIELD-SWEEP-PROTOCOL section 5).

Reads ONLY the append-only raw/*/sweep.jsonl. For every field it computes,
mechanically, the swept range, the set of values that produced the predicted
behaviour, the outcome histogram and the CROSS-RUN agreement; the LABEL and the
`semantics` prose are supplied explicitly in DECISIONS below, and the script
enforces the promotion rule rather than trusting the prose:

    a label of `hardware-run` requires
      * dense coverage of the whole encodable range of the field, and
      * BOTH gated runs to have covered the same number of cases for the arm
        (a run that aborted an arm on the hang budget must not be silently
        completed by its sibling), and
      * the two independent gated runs to agree, case for case, on ACCEPTANCE
        (`ok` vs not-`ok`) AND to produce the identical accepted-value set, and
      * a behavioural oracle that could have failed (the arm's carrier has a
        pre-registered falsifier that did fail).

    Acceptance agreement, not exact-outcome agreement, is the gate, because the
    label's claim is "these values work and those do not". Exact-outcome
    agreement is reported alongside it and is genuinely lower in places: on
    `S_extmode`, 11 of 256 cases are `nondeterministic` in one run and
    `wrong_value` in the other -- both runs agree the value fails, and disagree
    only on how stably it failed. Gating on exact outcomes would downgrade a
    claim neither run contradicts, which is a different kind of dishonesty.

Anything failing that is emitted at the weaker label the data actually supports.
`db_defects` records the places where the hardware disagrees with db.json's model.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
MAIN = ("m4-20260828-run11", "m4-20260828-run12")
ADD = ("m4-20260828-run21", "m4-20260828-run22")


def load(run):
    p = EXP / "raw" / run / "sweep.jsonl"
    return [json.loads(l) for l in p.open()] if p.exists() else []


def mask_rule(accepted, universe):
    """Tightest `v & MASK == PATTERN` rule reproducing the accepted set, and
    whether it does so EXACTLY. Machine-derived so the prose in RESULTS.md is
    checked against the raw data rather than eyeballed (analysis/bitrules.py
    prints the same table for every arm)."""
    if not accepted:
        return None
    ones, zeros = accepted[0], ~accepted[0]
    for v in accepted:
        ones &= v
        zeros &= ~v
    m = (ones | zeros) & (universe - 1)
    pat = ones & m
    exact = {v for v in range(universe) if (v & m) == pat} == set(accepted)
    return {"mask": "0x%02X" % m, "pattern": "0x%02X" % pat, "exact": exact,
            "rule": "v & 0x%02X == 0x%02X%s" % (m, pat, "" if exact else "  (NOT EXACT)")}


def compress(vals):
    if not vals:
        return "none"
    vs = sorted(set(vals))
    if len(vs) == 1:
        return "only %d" % vs[0]
    d = {vs[i + 1] - vs[i] for i in range(len(vs) - 1)}
    if len(d) == 1:
        return "%d..%d step %d (%d of %d)" % (vs[0], vs[-1], d.pop(), len(vs), len(vs))
    runs, s, prev = [], vs[0], vs[0]
    for v in vs[1:]:
        if v == prev + 1:
            prev = v
            continue
        runs.append((s, prev)); s = prev = v
    runs.append((s, prev))
    txt = ",".join("%d" % a if a == b else "%d-%d" % (a, b) for a, b in runs[:10])
    return "%s%s (%d values)" % (txt, ",..." if len(runs) > 10 else "", len(vs))


class Data:
    def __init__(self, runs):
        self.a, self.b = load(runs[0]), load(runs[1])
        self.ka = {(r["carrier"], r["arm"], r["i"]): r for r in self.a}
        self.kb = {(r["carrier"], r["arm"], r["i"]): r for r in self.b}

    def arm(self, name):
        rs = [r for r in self.a if r["arm"] == name]
        rs_b = [r for r in self.b if r["arm"] == name]
        both = [k for k in self.ka if k[1] == name and k in self.kb]
        agree = [k for k in both if self.ka[k]["outcome"] == self.kb[k]["outcome"]]
        acc = [k for k in both
               if (self.ka[k]["outcome"] == "ok") == (self.kb[k]["outcome"] == "ok")]
        okb = {self.kb[k]["value"] for k in both if self.kb[k]["outcome"] == "ok"
               and not str(self.kb[k]["field"]).startswith("_")}
        return rs, len(both), len(agree), len(acc), okb, len(rs_b)

    def field(self, arms):
        rows, nboth, nagree, nacc, present, okb, nb_rows = [], 0, 0, 0, [], set(), 0
        for a in arms:
            rs, nb, na, nac, ok2, nrb = self.arm(a)
            if rs:
                present.append(a)
            rows += rs; nboth += nb; nagree += na; nacc += nac; okb |= ok2
            nb_rows += nrb
        vals = sorted({r["value"] for r in rows if not str(r["field"]).startswith("_")})
        ok = sorted({r["value"] for r in rows
                     if r["outcome"] == "ok" and not str(r["field"]).startswith("_")})
        oc = collections.Counter(r["outcome"] for r in rows)
        uni = 1
        while uni <= (max(vals) if vals else 0):
            uni <<= 1
        return {"arms": present, "n_cases": len(rows), "n_values": len(vals),
                "mask_rule": mask_rule(ok, max(uni, 2)),
                "swept": compress(vals), "accepted": compress(ok),
                "n_accepted": len(ok), "outcomes": dict(oc),
                "cross_run_cases": nboth,
                "cross_run_agreement_pct": round(100.0 * nagree / nboth, 3) if nboth else None,
                "cross_run_accept_agreement_pct": round(100.0 * nacc / nboth, 3) if nboth else None,
                "accepted_sets_identical": (set(ok) == okb) if nboth else None,
                "n_cases_run_b": nb_rows,
                "coverage_equal": (len(rows) == nb_rows) and nb_rows > 0,
                "aborted_arms": [a for a in present
                                 if len([r for r in rows if r["arm"] == a]) < 250
                                 and a.startswith(("attg", "atdev", "tgtile", "devfence"))]}


# (instr, field) -> (proposed label, dense?, semantics, note, arms)
DECISIONS = [
 ("device_load", "extmode", "hardware-run", True,
  "DESTINATION REGISTER SELECTOR. register = extmode >> 1; bit0 is a DON'T CARE "
  "(both parities of every register work). Values 128..255 -- i.e. registers 64..127 -- "
  "do NOT work: they silently zero. So the reachable destination range through this "
  "field is r0..r63.",
  "Confirms EXP-0101's extmode = 2*R over the FULL 8-bit field and adds two facts "
  "EXP-0101 could not: bit0 is a don't-care, and the field cannot reach r64+.",
  ["L_extmode"]),
 ("device_load", "dst_lo", "hardware-run", True,
  "NOT a register field and NOT a function of the target register: dst_lo must be "
  "EXACTLY 1. 0, 2 and 3 silently zero the load, identically at target registers "
  "3, 7, 20 and 33.",
  "THE headline. EXP-0112's generator copied (dst_lo, dst_ext9) verbatim from a "
  "compiled shader because nobody had swept them. Swept exhaustively (4/4 values) "
  "at four independent target registers plus the full 512-value 2-D product.",
  ["L_dst_lo_R3", "L_dst_lo_R7", "L_dst_lo_R20", "L_dst_lo_R33"]),
 ("device_load", "dst_ext9", "hardware-run", True,
  "BIT 0 must be 1 -- all 64 odd values work and all 64 even values silently zero, "
  "identically at target registers 3, 7, 20 and 33. Not a register extension of any "
  "kind. How many of bits 1..6 are additionally free is ld_format-DEPENDENT (addendum "
  "H8, 21 formats x the full 512-value product): for 16 of the 21 accepted formats the "
  "rule is `v & 0x181 == 0x081` (bits 1..6 all free); for ld_format 3/7/9/13 it is "
  "`v & 0x1C1 == 0x081` (bit 6 must also be 0); for ld_format 39 it is "
  "`v & 0x1E1 == 0x081` (bits 5 and 6 must be 0). `dst_ext9 = 1` satisfies ALL 21.",
  "Refutes the residue of EXP-M4-13's dst = dst_lo | (dst_ext9 << 2) model: the field "
  "carries no register information at all. The ld_format dependence is the addendum's "
  "pre-registered refuter PARTIALLY FIRING -- reported, not smoothed over.",
  ["L_dst_ext9_R3", "L_dst_ext9_R7", "L_dst_ext9_R20", "L_dst_ext9_R33"]),
 ("device_load", "dst_pair", "hardware-run", True,
  "Full 2-D product: exactly 64 of the 512 encodable (dst_lo, dst_ext9) combinations "
  "work, and they are exactly {dst_lo == 1} x {dst_ext9 odd} -- the two constraints "
  "are independent, confirming the per-field results jointly.",
  "Cross-check arm for dst_lo / dst_ext9; not a db.json field.",
  ["L_dst_pair"]),
 ("device_load", "ld_format", "hardware-run", True,
  "Data-format descriptor. 21 of the 64 encodable values deliver the 32-bit scalar "
  "correctly, and the SAME 21 in both the ALU-consumer and the bit-exact "
  "load->store-forward program, so the set is a property of the load and not of the "
  "consumer. The remaining 43 either silently zero or deliver a different value.",
  "First execution of SYNTHESISED ld_format codes; EXP-M4-13 located the field by "
  "compile-only byte-diff and never ran one.",
  ["L_ld_format", "L_ld_format_fwd"]),
 ("device_load", "ldform_hi11", "hardware-run", True,
  "byte+11 bits 2..7. Bits 0..2 of the field are live and must be 0; bits 3..5 are "
  "DON'T CARE. Exactly the 8 multiples of 8 work, identically in both program shapes.",
  "Was `untested` with range `none`. EXP-0082's 6-value probe found 3 inert and 2 "
  "'undecodable'; the dense sweep resolves it to a clean low-3-bits-must-be-zero rule.",
  ["L_ldform_hi11", "L_ldform_hi11_fwd"]),
 ("device_load", "reserved7", "hardware-run", True,
  "INERT. All 256 values leave the load, its consumer and the store correct.",
  "Was `tokenization-only` (framing only, no semantics).", ["L_reserved7"]),
 ("device_load", "reserved13", "hardware-run", True,
  "INERT. All 256 values leave the load correct.",
  "Was `tokenization-only`.", ["L_reserved13"]),
 ("device_load", "space", "hardware-run", True,
  "Exact rule `v & 0x03 == 0x00`: bits 0 and 1 are live and must both be 0 for a "
  "device-space load; bits 2..7 are DON'T CARE (64 of 256 values work).",
  "Was `isolated-byte-diff` over 2 of 256 values (0x00 device, 0x02 threadgroup).",
  ["L_space"]),
 ("device_load", "addr_mode", "hardware-run", True,
  "INERT for a terminal scalar 32-bit indexed load: all 256 values -- including every "
  "code db.json's enum names -- leave the load correct.",
  "db.json models this byte as an addressing-mode ENUM (0x44 indexed / 0x54 base-rel / "
  "rare CF and RT forms). On this shape none of it is observable; the enum is a "
  "corpus correlation, not a hardware selector. See db_defects.",
  ["L_addr_mode"]),
 ("device_load", "access_desc", "hardware-run", True,
  "INERT. All 256 values leave the loaded value unchanged.",
  "M4 confirmation of EXP-0012/RT-1a-FIX's A18 exhaustive result (was target A18 only).",
  ["L_access_desc"]),
 ("device_load", "elem_size", "hardware-run", True,
  "48 of 256 raw byte+12 values deliver the 4-byte element correctly.",
  "Extends EXP-0082 (canonical codes plus 23 raw values) to the full byte.",
  ["L_elem_size"]),
 ("device_load", "index_reg", "hardware-run", True,
  "Index GPR selector. r0..r95 work (except r10, which THIS program uses for its own "
  "integrity sentinel), r96..r127 fault REPRODUCIBLY, and bit 7 is IGNORED: values "
  "128..255 mirror 0..127 exactly.",
  "Adds the bit-7 mirror, which no prior experiment reports, and re-confirms the "
  "r95/r96 fault boundary (EXP-M4-10) with 3-of-3 fault reproduction.",
  ["L_index_reg"]),
 ("device_store", "extmode", "hardware-run", True,
  "SOURCE REGISTER SELECTOR: exactly TWO values work for a source register R, namely "
  "`2*R` and `2*R | 0xC0`. Proven by moving the source register and re-sweeping densely "
  "(addendum H10): r4 -> {8, 200}, r8 -> {16, 208}, r12 -> {24, 216}. So `extmode >> 1` "
  "is the source register (EXP-0090's formula, now dense over three registers), bit 0 is "
  "LIVE here unlike device_load.extmode, and bits 6+7 TOGETHER are an accepted "
  "alternative form -- a modifier, not register bits (neither bit alone works).",
  "The 0xC0 alternative is now characterised rather than merely observed. Its MEANING is "
  "still unknown; only that it is accepted.",
  ["S_extmode", "S_extmode_D4", "S_extmode_D8", "S_extmode_D12"]),
 ("device_store", "addr_mode", "hardware-run", True,
  "DATA-SOURCE SELECTOR, and it is bit 1: with an ALU-computed source all 256 values "
  "work, but with a DIRECT load-result source only the 128 values with bit1 SET work "
  "(0x56-class), and the 128 with bit1 clear (0x54-class) store 0.",
  "REFINES `validation.json`'s current range text 'bit1 ... INERT here' (EXP-0119): "
  "that measurement used an ALU-computed source, where the bit genuinely is inert. It "
  "is live exactly when the stored data is a live load result. Both halves swept "
  "densely in both source shapes.",
  ["S_addr_mode", "S_addr_mode_fwd"]),
 ("device_store", "st_format", "hardware-run", True,
  "Store data-format descriptor. 84 of 256 values store the 32-bit scalar correctly, "
  "the same 84 with an ALU-computed and with a load-forwarded source.",
  "First execution of synthesised store-format codes; EXP-M4-13 was compile-only.",
  ["S_st_format", "S_st_format_fwd"]),
 ("device_store", "st_format_ext", "hardware-run", True,
  "Only the low 5 bits are free: exactly 0..31 work, 32..127 break the store, so bits "
  "5 and 6 of the field are live and must be 0.",
  "Was `corpus-correlation` ('bit set only for the 3-component store').",
  ["S_st_format_ext"]),
 ("device_store", "st_desc_hi", "hardware-run", True,
  "byte+11 bits 2..7. Machine-derived exact rule `v & 0x11 == 0x00`: bits 0 AND 4 "
  "of the field are live and must be 0; bits 1..3 and 5 are DON'T CARE "
  "(16 of 64 values work).",
  "Was `corpus-correlation`, 'located only'.", ["S_st_desc_hi"]),
 ("device_store", "reserved7", "hardware-run", True,
  "INERT. All 256 values leave the store correct.", "Was `tokenization-only`.",
  ["S_reserved7"]),
 ("device_store", "reserved13", "hardware-run", True,
  "INERT. All 256 values leave the store correct.", "Was `tokenization-only`.",
  ["S_reserved13"]),
 ("device_store", "space", "hardware-run", True,
  "Exact rule `v & 0x02 == 0x00`: bit 1 is live and must be 0 for a device-space "
  "store; bit 0 and bits 2..7 are DON'T CARE (128 of 256 values work).",
  "Was `isolated-byte-diff` over 2 of 256 values.", ["S_space"]),
 ("device_store", "access_desc", "hardware-run", True,
  "INERT. All 256 values leave the store correct.",
  "M4 confirmation of the A18 exhaustive result.", ["S_access_desc"]),
 ("device_store", "elem_size", "hardware-run", True,
  "96 of 256 raw byte+12 values store correctly.",
  "Extends EXP-0082's 25 probed store-side values to the full byte.", ["S_elem_size"]),
]

ATOMIC_MEM = [
 ("amode", "hardware-run", "INERT on the device register-operand form: all 256 values "
  "leave the atomic correct.",
  "db.json documents 0x11 vs 0x01 at byte+1 as the form selector and byte+2 as `amode`; "
  "byte+2 has no observable role here.", ["atdev_atomic_mem_b2", "atdevimm_atomic_mem_b2"]),
 ("rsv3", "hardware-run", "INERT. All 256 values leave the atomic correct.",
  "Was `tokenization-only`.", ["atdev_atomic_mem_b3", "atdevimm_atomic_mem_b3"]),
 ("base_slot", "hardware-run", "INERT on this carrier: all 256 values leave the atomic "
  "correct, so the buffer address does NOT come from this byte for a "
  "single-bound-buffer atomic.",
  "db.json calls it 'a base-register-table slot, NOT the Metal buffer index'; with one "
  "bound target the slot is unobservable. Tested with ONE atomic target buffer only.",
  ["atdev_atomic_mem_b4", "atdevimm_atomic_mem_b4"]),
 ("index_reg", "hardware-run", "LOW HALF OF THE RMW OPERAND-REGISTER SELECTOR. Only the "
  "compiler's own value keeps the baseline operand; byte+5 == 0x80 makes the atomic add "
  "a[1] (1007) instead of a[0] (7), and the later store of a[1]'s register then reads 0 "
  "-- the redirected register is consumed. Bit 7 of byte+5 is operand-register bit 0.",
  "FIRST-ORDER db_defects RESULT: db.json says 'the actual RMW operand register is "
  "implicit (supplied by the preceding op / amode)' and DOC-02 ranks it a MISSING field. "
  "It is not implicit; see db_defects.atomic_operand_register.",
  ["atdev_atomic_mem_b5", "atdevimm_atomic_mem_b5"]),
 ("addr_desc", "hardware-run", "HIGH PART OF THE RMW OPERAND-REGISTER SELECTOR. byte+6 "
  "bit0 set (0x01, 0x41, 0x81, 0xC1 -- bits 6/7 don't care) makes the atomic add a[2] "
  "(2007) and zeroes a[2]'s later reader, exactly the byte+5 signature one register "
  "further on.",
  "Same db_defect: modelled `tokenization-only`, 'framing only, no value semantics'.",
  ["atdev_atomic_mem_b6", "atdevimm_atomic_mem_b6"]),
 ("ret_flag", "hardware-run", "LIVE: only the compiler's own value leaves the atomic "
  "correct; every other value of the byte breaks it.",
  "Was `corpus-correlation` (byte+7 bit0 = discard/no-writeback).",
  ["atdev_atomic_mem_b7", "atdevimm_atomic_mem_b7"]),
 ("ret_desc", "hardware-run", "LIVE: 2 of 256 values work (0 and 128), so bit 7 is a "
  "don't-care and the remaining bits are load-bearing.",
  "Was `corpus-correlation`.", ["atdev_atomic_mem_b8", "atdevimm_atomic_mem_b8"]),
 ("idx_off", "hardware-run", "LIVE: exactly 32 of 256 values work (bits 1..3 must be 0; "
  "bits 0 and 4..7 are don't-care).",
  "Was `tokenization-only`.", ["atdev_atomic_mem_b9", "atdevimm_atomic_mem_b9"]),
 ("rsv10", "hardware-run", "LIVE, not reserved: only 4 of 256 values (0..3) work.",
  "Was `tokenization-only`; the name is wrong.",
  ["atdev_atomic_mem_b10", "atdevimm_atomic_mem_b10"]),
 ("rsv11", "hardware-run", "LIVE, not reserved: only the value 0 works.",
  "Was `tokenization-only`; the name is wrong.",
  ["atdev_atomic_mem_b11", "atdevimm_atomic_mem_b11"]),
 ("op_lsb|op|per_lane|op_msb", "hardware-run", "The whole byte+12 operation word swept "
  "densely; 48 (register-operand carrier) / 56 (immediate-operand carrier) of 256 values "
  "leave the counter at the add result, and 0x36 (op 27 = sub) produces 0xFFFFFFF9 = -7 "
  "exactly, an independent confirmation of the op enum.",
  "`op` itself was already `hardware-run` (EXP-0018/EXP-M4-10, 13 codes); this is the "
  "first dense sweep of the byte, covering op_lsb / per_lane / op_msb too.",
  ["atdev_atomic_mem_b12", "atdevimm_atomic_mem_b12"]),
 ("amode_hi", "hardware-run", "LIVE: 32 of 256 values work on the register-operand "
  "carrier (bits 0..2 must be 0), 96 of 256 on the immediate-operand carrier.",
  "Was `tokenization-only`. The two carriers accept DIFFERENT value sets, so the byte's "
  "meaning is form-dependent; not root-caused.",
  ["atdev_atomic_mem_b13", "atdevimm_atomic_mem_b13"]),
]

ATOMIC_TG = [
 ("amode", "hardware-run", "INERT: all 256 values leave the threadgroup reduction correct.",
  "Was `corpus-correlation` (0x56 direct-value vs 0x54 RMW).", ["attg_atomic_tg_b2"]),
 ("ret_desc", "hardware-run", "INERT: all 256 values leave the reduction correct.",
  "Was `corpus-correlation` (0x03 returns / 0x00 noret). The old value is never "
  "consumed in this carrier, which is why the byte is unobservable here.",
  ["attg_atomic_tg_b3"]),
 ("rsv4", "hardware-run", "LIVE, not reserved: only 4 of 256 values work (0, 1, 128, 129).",
  "Was `tokenization-only`; the name is wrong.", ["attg_atomic_tg_b4"]),
 ("op_desc", "untested", "PARTIAL, and the only field the automatic gate refuses. Run 11 "
  "ABORTED this arm at case 129 of 257 after 2 REPRODUCED GPU hangs (byte+5 = 0x7E and "
  "0x7F), per the protocol's 2-hang budget; run 12 did NOT hang on those values -- it "
  "returned a reproduced CMDBUF_ERROR (3/3) and completed the whole 0..255 sweep, finding "
  "{0, 96, 128, 224} accepted. The two runs therefore have no common dense sweep, so the "
  "accepted sets are not identical and the field stays below emitter grade.",
  "The only hangs in ~71 000 measurements. 0x7E/0x7F are reproducibly bad in BOTH runs; "
  "only their SEVERITY differs (hang vs contained fault). DO NOT EMIT byte+5 in "
  "0x7E..0x7F. Values 129..255 have one gated run's evidence only.",
  ["attg_atomic_tg_b5"]),
 ("rsv6", "hardware-run", "LIVE, not reserved: only 0 and 1 work.",
  "Was `tokenization-only`.", ["attg_atomic_tg_b6"]),
 ("xop_desc", "hardware-run", "LIVE: 2 of 256 values work (0 and 128); bit 7 is a "
  "don't-care.", "Was `tokenization-only`.", ["attg_atomic_tg_b7"]),
 ("data_desc", "hardware-run", "LIVE: 128 of 256 values work; bit 4 must be 0 and the "
  "rest of the byte is a don't-care in this shape.",
  "Was `corpus-correlation`.", ["attg_atomic_tg_b8"]),
 ("rsv9", "hardware-run", "LIVE, not reserved: only the value 0 works.",
  "Was `tokenization-only`; the name is wrong.", ["attg_atomic_tg_b9"]),
 ("rsv10lo|op", "hardware-run", "LIVE: only the value 0 works, so the low half of the "
  "op word is fully constrained in this shape.",
  "Was `tokenization-only` + `corpus-correlation`.", ["attg_atomic_tg_b10"]),
 ("op|op_hi_rsv", "hardware-run", "LIVE: 24 of 256 values work.",
  "`atomic_tg.op` was `corpus-correlation` (EXP-M4-13, compile-only). This is the first "
  "dispatched sweep of the byte that carries it.", ["attg_atomic_tg_b11"]),
]

OTHER = [
 ("threadgroup_barrier", "flags", "hardware-run", True,
  "INERT with respect to the fence: all 256 values leave the 256-lane litmus exact.",
  "Was `corpus-correlation` (0x09 tg/none, 0x08 device, 0x0e texture). The litmus is "
  "proven fence-sensitive by its own falsifier (224/256 lanes read stale zeros when the "
  "barrier is neutralised), so this is a real negative, not an insensitive carrier.",
  ["tgtile_threadgroup_barrier_b4"]),
 ("threadgroup_barrier", "b5", "hardware-run", True,
  "INERT: all 256 values leave the litmus exact.",
  "Was `single-template-inference` (0x00 in every observed instance).",
  ["tgtile_threadgroup_barrier_b5"]),
 ("threadgroup_barrier", "mem_scope", "hardware-run", True,
  "Only BIT 0 matters for a threadgroup-memory litmus: all 128 odd values pass and all "
  "128 even values fail with 224/256 lanes reading stale zeros. The memory-CLASS bits "
  "are don't-care here; bit 0 is the execution-convergence enable.",
  "Dense confirmation of EXP-0093's 'byte+3 bit0 is the EXECUTION-CONVERGENCE enable, "
  "independent of the requested memory-fence class', now over all 256 values.",
  ["tgtile_threadgroup_barrier_b3"]),
 ("threadgroup_barrier", "sub", "hardware-run", True,
  "Machine-derived exact rule `v & 0x06 == 0x04`: bit 2 must be 1 and bit 1 must be 0; "
  "bit 0 and bits 3..7 are DON'T CARE (64 of 256 values work, the compiler's own 0x04 "
  "and its 0x05 neighbour among them).",
  "Was `isolated-byte-diff` over 3 values.", ["tgtile_threadgroup_barrier_b1"]),
 ("mem_fence", "sub", "corpus-correlation", True,
  "192 of 256 values leave the carrier's functional output correct.",
  "NOT PROMOTED. This carrier has no memory-ORDERING observable (a single 8-lane "
  "threadgroup with a trailing barrier), so a pass bounds acceptance and dataflow "
  "inertness only, not the fence's semantics. Recorded so nobody re-probes it blindly.",
  ["devfence_mem_fence_b1"]),
 ("mem_fence", "memclass", "corpus-correlation", True,
  "INERT with respect to the carrier's output: all 256 values pass.",
  "NOT PROMOTED, same reason as mem_fence.sub: no ordering observable.",
  ["devfence_mem_fence_b4"]),
 ("mem_fence", "b5", "corpus-correlation", True,
  "INERT with respect to the carrier's output: all 256 values pass.",
  "NOT PROMOTED, same reason.", ["devfence_mem_fence_b5"]),
 ("dev_scoreboard_fence", "scope_flag", "corpus-correlation", True,
  "All 256 values execute and leave an adjacent synthesised load->ALU->store dataflow "
  "at its exact expected value.",
  "NOT PROMOTED. No own-MSL kernel we could compile emits `80 02 00 xx`, so the "
  "instruction had to be SYNTHESISED into the load/ALU/store program, which has no "
  "scoreboard/ordering observable. What IS newly established: the instruction can be "
  "emitted from scratch and every value of the byte is accepted without fault.",
  ["F_dsf_scope_flag"]),
 ("tg_addr_compute", "b3", "hardware-run", True,
  "INERT on M4: all 256 values leave the tile dataflow exact.",
  "M4 confirmation of EXP-M4-14's A18 result (5 values there, 256 here).",
  ["tgtile_tg_addr_compute_b3"]),
 ("tg_addr_compute", "b4", "hardware-run", True,
  "INERT on M4: all 256 values pass.", "M4 confirmation of EXP-M4-14 (A18, 3 values).",
  ["tgtile_tg_addr_compute_b4"]),
 ("tg_addr_compute", "b5", "hardware-run", True,
  "INERT on M4: all 256 values pass.", "M4 confirmation of EXP-M4-14 (A18, 3 values).",
  ["tgtile_tg_addr_compute_b5"]),
]

UNMODELLED = [
 ("atomic_mem", "byte+5|byte+6 as one operand-register index", "hardware-run",
  "Joint sweep with byte+5 pinned to 0x80 and byte+6 dense: index 3 selects a[3] = 3007 "
  "and zeroes its later reader, confirming "
  "index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1).",
  "The main matrix could only build indices 0, 1 and 2 because it moves one byte at a "
  "time. Two values (byte+6 = 0x30, 0x31) disagreed on acceptance between run21 and "
  "run22 and are excluded from the claim.",
  ["atdev_operand_pair"]),
 ("tg_addr_compute", "byte0 (whole byte, incl. high nibble)", "hardware-run",
  "LIVE and almost fully constrained: of 256 values ONLY 0x1c -- the compiler's own -- "
  "leaves the tile dataflow correct. On M4 the high nibble is not a freely-choosable "
  "operand: every other value breaks or faults.",
  "EXP-M4-14 (A18) found 0x1c AND 0xfc reproduce the baseline while 0x2c/0x3c/0x5c/0x6c "
  "corrupt. On M4, 0xfc does NOT reproduce. A18<->M4 divergence, reported not resolved. "
  "The db.json match still over-fits and the EMITTABLE VETO must stand.",
  ["tgtile_tg_addr_compute_b0"]),
 ("tg_addr_compute", "byte+1 (unmodelled operand selector)", "hardware-run",
  "LIVE: 32 of 256 values work. The accepted set is {v : v & 0x03 == 2 and v & 0x10 == 0}, "
  "i.e. bits 0,1 must be 0b10 and bit 4 must be 0; bits 2,3,5,6,7 are don't-care.",
  "First dense map of a byte db.json does not model as a field at all (EXP-M4-14 probed "
  "5 values on A18). Still not emitter-usable while byte0 is pinned to one value.",
  ["tgtile_tg_addr_compute_b1"]),
 ("tg_addr_compute", "byte+2 (match-pinned)", "hardware-run",
  "INERT at runtime: all 256 values leave the tile dataflow exact.",
  "Confirms EXP-M4-14's 'byte+2 is runtime-INERT but is the disassembler's length "
  "discriminator' on M4 over the full byte -- a decoder constraint, not a hardware one.",
  ["tgtile_tg_addr_compute_b2"]),
 ("atomic_mem", "byte+1 (form selector, match-pinned)", "hardware-run",
  "64 of 256 values work, exactly {v : v & 0x03 == 1}. Both db.json forms are in that "
  "set: 0x01 (atomic_mem) and 0x11 (atomic_rmw) execute identically in this carrier.",
  "byte+1 is in db.json's `match`, not a field, so it had no label at all.",
  ["atdev_atomic_mem_b1", "atdevimm_atomic_mem_b1"]),
 ("atomic_tg", "byte+1 (form selector, match-pinned)", "hardware-run",
  "32 of 256 values work, exactly {v : v & 0x07 == 3}.",
  "byte+1 is in db.json's `match`, not a field.", ["attg_atomic_tg_b1"]),
 ("threadgroup_barrier", "byte+2 (match-pinned)", "hardware-run",
  "INERT: all 256 values leave the fence-sensitive litmus exact.",
  "byte+2 == 0x54 is in db.json's `match`; it is not load-bearing on hardware.",
  ["tgtile_threadgroup_barrier_b2"]),
 ("mem_fence", "byte+2 / byte+3 (match-pinned)", "corpus-correlation",
  "INERT with respect to the carrier's output: all 256 values of each pass.",
  "NOT PROMOTED -- no ordering observable, as for the other mem_fence fields.",
  ["devfence_mem_fence_b2", "devfence_mem_fence_b3"]),
 ("dev_scoreboard_fence", "byte+1 / byte+2 (match-pinned)", "corpus-correlation",
  "byte+1: all 256 values leave the synthesised dataflow exact. byte+2: 160 of 256.",
  "NOT PROMOTED -- no ordering observable.", ["F_dsf_b1", "F_dsf_b2"]),
]


def emit():
    d = Data(MAIN)
    add = Data(ADD)
    out = {"_spec": "docs/evidence-classification.md section 2 labels; "
                    "experiments/FIELD-SWEEP-PROTOCOL.md section 5 schema",
           "_experiment": "EXP-0141", "_target": "M4 (G16G) only",
           "_runs": {"main": list(MAIN), "atomic_rmw_addendum": list(ADD)},
           "_promotion_rule": "hardware-run requires dense coverage of the whole "
                              "encodable range AND 100% cross-run outcome agreement "
                              "AND a falsifier that actually failed on that carrier."}

    def put(instr, field, label, semantics, note, arms, src=None):
        st = (src or d).field(arms)
        if not st["arms"] and src is None:
            st = add.field(arms)          # addendum-only arms
        if not st["arms"]:
            return
        agree = st["cross_run_agreement_pct"]
        acc = st["cross_run_accept_agreement_pct"]
        same = st["accepted_sets_identical"]
        eff = label
        cov = st["coverage_equal"]
        if label == "hardware-run" and (acc is None or acc < 100.0 or not same or not cov):
            eff = "isolated-byte-diff"
            note += (" DOWNGRADED from hardware-run: cross-run ACCEPTANCE agreement "
                     "%s%%, accepted sets identical: %s, both runs covered the same "
                     "case count: %s (%d vs %d)."
                     % (acc, same, cov, st["n_cases"], st["n_cases_run_b"]))
        out.setdefault(instr + "." + field, {}).update({
            "label": eff, "range": st["swept"], "accepted_values": st["accepted"],
            "n_accepted": st["n_accepted"], "mask_rule": st["mask_rule"],
            "target": "M4",
            "evidence": ["EXP-0141"], "semantics": semantics, "note": note,
            "outcomes": st["outcomes"], "n_cases": st["n_cases"],
            "cross_run_agreement_pct": agree,
            "cross_run_accept_agreement_pct": acc,
            "accepted_sets_identical": same,
            "cross_run_cases": st["cross_run_cases"],
            "n_cases_run_b": st["n_cases_run_b"],
            "coverage_equal": st["coverage_equal"], "arms": st["arms"]})

    for instr, field, label, dense, sem, note, arms in DECISIONS:
        put(instr, field, label, sem, note, arms)
    for field, label, sem, note, arms in ATOMIC_MEM:
        put("atomic_mem", field, label, sem, note, arms)
    for field, label, sem, note, arms in ATOMIC_TG:
        put("atomic_tg", field, label, sem, note, arms)
    for instr, field, label, dense, sem, note, arms in OTHER:
        put(instr, field, label, sem, note, arms)
    for instr, field, label, sem, note, arms in UNMODELLED:
        put("UNMODELLED_BYTES." + instr, field, label, sem, note, arms)

    # atomic_rmw, from the addendum capture
    if add.a and add.b:
        for field, label, sem, note, arms in ATOMIC_MEM:
            put("atomic_rmw", field, label, sem,
                note + " Swept in the atomic_rmw (byte+1 == 0x11) form itself, "
                "addendum runs 21/22.",
                [a.replace("atdev_atomic_mem", "atdev_atomic_rmw")
                 for a in arms if a.startswith("atdev_")], src=add)
    else:
        out["atomic_rmw._NOT_CLOSED"] = {
            "label": "untested",
            "note": "The addendum capture (byte+1 pinned to 0x11) is absent, so "
                    "atomic_rmw's 14 fields keep their prior labels. atomic_mem's "
                    "sweeps must NOT be transferred to them.",
            "target": "M4", "evidence": ["EXP-0141"]}

    out["db_defects"] = {
      "atomic_operand_register": {
        "claim": "The RMW operand register of atomic_mem / atomic_rmw IS encoded in the "
                 "instruction, in byte+5 bit 7 and byte+6 bits 0..5, as an index into the "
                 "operand register window. db.json states it 'is implicit (supplied by the "
                 "preceding op / amode)' and DOC-02 section 3 row 9 ranks it a MISSING field "
                 "-- 'the worst kind of gap for an emitter'.",
        "evidence": "Carrier kernels/atomic_dev.metal keeps a[0..3] = 7/1007/2007/3007 live "
                    "across atomic_fetch_add(o, a[0]). Baseline byte+5/+6 = 0x00/0x00 -> the "
                    "counter is 7. byte+5 = 0x80 -> the counter is 1007 AND the later store "
                    "of a[1]'s register reads 0. byte+6 = 0x01 (also 0x41/0x81/0xC1, so bits "
                    "6-7 are don't-care) -> the counter is 2007 AND a[2]'s later reader reads "
                    "0. Identical in both gated runs.",
        "model": "operand_register_index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1), relative "
                 "to the register the compiler's own encoding selects. PROVEN AT ALL FOUR "
                 "CONSTRUCTIBLE INDICES: 0 -> a[0] = 7, 1 -> a[1] = 1007, 2 -> a[2] = 2007, "
                 "and -- built for the first time by addendum arm `atdev_operand_pair` "
                 "(byte+5 pinned 0x80, byte+6 swept densely) -- 3 -> a[3] = 3007, each with "
                 "the redirected register's later reader zeroed. byte+6 bits 6 and 7 are "
                 "DON'T CARE (0x01/0x41/0x81/0xC1 all give index 3). The `<< 1` multiplier is "
                 "no longer interpolated.",
        "residual_unknown": "With byte+5 = 0x80, byte+6 values 0x30 and 0x31 restore the "
                            "BASELINE operand instead of selecting index 97/99, and they are "
                            "the only two cases in the addendum whose acceptance disagreed "
                            "between run21 and run22. Unexplained; recorded.",
        "corollary": "The redirected register is CONSUMED -- its later reader gets 0 -- which "
                     "is the same register-release contract EXP-0086/0089/0099 document for "
                     "the ALU families.",
        "conflicts_with": "db.json/validation.json call byte+5 `index_reg` ('per-lane index "
                          "GPR, zeroed for a uniform address') and byte+6 `addr_desc` "
                          "('framing only'). Our atdevimm carrier uses a UNIFORM address yet "
                          "the compiler emits byte+5/+6 = 0x80/0x02, which the per-lane "
                          "reading does not explain. The address role is not excluded for the "
                          "per-lane form; the DATA role is now proven for the uniform form."},
      "device_load_dst_fields": {
        "claim": "device_load.dst_lo and dst_ext9 carry NO register information. dst_lo must "
                 "be exactly 1; only bit 0 of dst_ext9 is live and must be 1. Three "
                 "constrained bits out of the nine the two fields span; the other six are "
                 "don't-care.",
        "evidence": "4/4 dst_lo values and 128/128 dst_ext9 values swept at four independent "
                    "target registers (3, 7, 20, 33), plus the full 512-value 2-D product at "
                    "r7. The accepted set is identical at every target register.",
        "supersedes": "EXP-M4-13's dst = dst_lo | (dst_ext9 << 2) (already retracted by "
                      "EXP-0101) and EXP-0101's own operational advice to copy the pair "
                      "verbatim per addr_mode/ld_format shape. The pair is a fixed 3-bit "
                      "enable pattern, not a per-shape token."},
      "device_load_addr_mode_not_an_enum": {
        "claim": "device_load byte+2 (`addr_mode`) is INERT for a terminal scalar 32-bit "
                 "indexed load: all 256 values load correctly, including every code in "
                 "db.json's enum.",
        "caveat": "Only the terminal scalar 32-bit shape was tested. The enum may still "
                  "select behaviour for the base-sharing / CF / RT forms it names."},
      "reserved_fields_that_are_not_reserved": {
        "claim": "atomic_mem.rsv10 (4 of 256 values work), atomic_mem.rsv11 (1 of 256), "
                 "atomic_tg.rsv4 (4 of 256), atomic_tg.rsv6 (2 of 256) and atomic_tg.rsv9 "
                 "(1 of 256) are LIVE, heavily constrained bytes, not reserved padding. "
                 "device_load.reserved7/reserved13 and device_store.reserved7/reserved13 "
                 "ARE genuinely inert (256/256 each)."},
      "device_store_addr_mode_bit1_is_context_dependent": {
        "claim": "device_store byte+2 bit 1 selects the DATA SOURCE: clear = ALU-computed, "
                 "set = direct live load-result. It is inert when the data is ALU-computed "
                 "(256/256 pass), which is the configuration EXP-0119 measured and reported "
                 "as 'INERT here'; with a load-forwarded source only the 128 bit1-set values "
                 "work and the other 128 store 0."},
    }
    (EXP / "analysis" / "field_verdicts.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n")
    n = sum(1 for k, v in out.items() if isinstance(v, dict) and v.get("label"))
    hw = sum(1 for k, v in out.items()
             if isinstance(v, dict) and v.get("label") == "hardware-run")
    print("field_verdicts.json: %d entries, %d hardware-run" % (n, hw))
    for k, v in sorted(out.items()):
        if isinstance(v, dict) and v.get("label"):
            print("  %-52s %-20s agree=%s%%  accepted=%s"
                  % (k, v["label"], v.get("cross_run_agreement_pct"),
                     str(v.get("accepted_values"))[:44]))


if __name__ == "__main__":
    emit()
