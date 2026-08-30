#!/usr/bin/env python3
"""EXP-0156: emit `analysis/field_verdicts.json` in FIELD-SWEEP-PROTOCOL §5 shape.

Consumes `analysis/gate_report.json` (produced by `verdicts.py` over ALL frozen run
pairs). Promotion to `hardware-run` requires ALL of:

  * the arm swept its field densely (all 2^w values for w<=8, or the protocol's
    wide-field sample for the 16-bit fields);
  * the two gated runs produced the IDENTICAL accepted-value set;
  * the arm's own liveness gate / falsifier fired exactly as pre-registered;
  * neither run recorded a baseline-check failure (no cascade).

Anything short of that is reported at the weaker label. Labels come from the eight
in `docs/evidence-classification.md` and nothing else. `target` is G17P throughout;
no M4 result is carried onto a G17P verdict.
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
G = json.load((EXP / "analysis" / "gate_report.json").open())

# arm -> the control group(s) whose falsifier/liveness gate must have fired
GATE = {
    "jump.branch_ctrl": ["cf.baseline.cfN", "cf.falsifier.cfN"],
    "pop_reconverge.reserved@a": ["cf.baseline.cfN", "cf.falsifier.cfN"],
    "pop_reconverge.reserved@b": ["cf.baseline.cfN", "cf.falsifier.cfN"],
    "ret.linkmode": ["cf.baseline.cfN", "cf.falsifier.cfN"],
    "ret.scoreboard": ["cf.baseline.cfN", "cf.falsifier.cfN"],
    "ret_luse.linkmode": ["ret_luse.control"],
    "ret_luse.tail": ["ret_luse.control"],
    "if_push_pred.level": ["cf.baseline.cfN", "cf.falsifier.cfN"],
    "jump_cond.offset": ["jc.live.cf0.P1", "jc.live.cfN.P1", "jc.live.cf0.P2", "jc.live.cfN.P2",
                          "jc.live.cf0.NAT", "jc.live.cfN.NAT"],
    "jump_cond.cf_scope@P1": ["jc.live.cf0.P1", "jc.live.cfN.P1", "jc.live.cf0.P2", "jc.live.cfN.P2",
                          "jc.live.cf0.NAT", "jc.live.cfN.NAT"], "jump_cond.cf_scope@P2": ["jc.live.cf0.P1", "jc.live.cfN.P1", "jc.live.cf0.P2", "jc.live.cfN.P2",
                          "jc.live.cf0.NAT", "jc.live.cfN.NAT"],
    "jump_cond.reserved@P1": ["jc.live.cf0.P1", "jc.live.cfN.P1", "jc.live.cf0.P2", "jc.live.cfN.P2",
                          "jc.live.cf0.NAT", "jc.live.cfN.NAT"], "jump_cond.reserved@P2": ["jc.live.cf0.P1", "jc.live.cfN.P1", "jc.live.cf0.P2", "jc.live.cfN.P2",
                          "jc.live.cf0.NAT", "jc.live.cfN.NAT"],
    "mask_op.mask_bank": ["mask_op.liveness"], "mask_op.scope_kind": ["mask_op.liveness"],
    "atdev_atomic_mem_b12": ["atdev.baseline", "atdev.falsifier"],
    "atdevimm_atomic_mem_b12": ["atdevimm.baseline", "atdevimm.falsifier"],
    "atdev_atomic_rmw_b12": ["atdev_rmw.control"],
    "attg_atomic_tg_b5": ["attg.baseline", "attg.falsifier"],
    "attg_atomic_tg_b10": ["attg.baseline", "attg.falsifier"],
    "attg_atomic_tg_b11": ["attg.baseline", "attg.falsifier"],
}
for b in range(6):
    GATE["tgac.b%d" % b] = ["tgac.baseline", "tgac.falsifier"]
for a in ("bf.byte0_dst", "bf.fmt", "bf.opsel", "bf.srcA", "bf.srcB",
          "bf.tail5", "bf.tail6", "bf.tail7"):
    GATE[a] = ["bfadd.baseline", "bfadd.falsifier"]
for a in ("bffma.byte0_dst", "bffma.fmt", "bffma.srcA", "bffma.srcB", "bffma.srcC"):
    GATE[a] = ["bffma.baseline", "bffma.falsifier"]
for a in ("h.byte0_dst", "h.dst_full", "h.srcA", "h.sel", "h.srcB"):
    GATE[a] = ["hmax.baseline", "hmax.falsifier"]
for op, nb in (("half_alu_lo", 8), ("h_alu_hi", 4)):
    for i in range(nb):
        GATE["h2.%s.b%d" % (op, i)] = ["h2fma.baseline", "h2fma.falsifier",
                                       "h2.halfprobe"]

DB_DEFECTS = {
    "decoder_mistokenizes_the_0x11_native_bfloat_group": {
        "evidence": "EXP-0156 compile-only pilot, work/pilot_loc.json",
        "observed": "Our own tools/agx-isa decoder tokenizes bf_add.metal's +32 as "
                    "`operand_word` (2 B) + `mov_imm` (2 B) + `cvt_f2h` (6 B), but the "
                    "bytes are one 8-byte `bf_add_dst` (`21 00 1c 00 11 00 c0 81`): "
                    "byte0 low nibble 1, byte+2 = 0x1c, and the tail byte+6 = 0xc0 / "
                    "byte+7 = 0x81 db.json's own semantics text predicts. The same "
                    "happens to `hminmax` (`22 00 1c 00 10 c0` decoded as a 10-byte "
                    "`n2_op10`) and to `bf_fma_dst`.",
        "impact": "The five bf16/half splice sites had to be pinned by EXACT BYTES at an "
                  "EXACT offset instead of by mnemonic. It is a DECODER defect only: the "
                  "hardware executed all three instructions correctly and every operand "
                  "sweep below ran against them.",
    },
    "h_alu_hi_is_4_bytes_in_the_half2_form_not_6": {
        "evidence": "EXP-0156 pilot + the h2fma arms",
        "observed": "A half2 fma emits `20 00 1e 04 81 08 00 c0` (8 B, low half) "
                    "immediately followed by `28 01 1b 09` (4 B, high half) and then the "
                    "carrier's own `0c a5` / `02 a4` sentinel-constant pair, which also "
                    "appear after the 8-byte bf_add and the 6-byte hminmax. db.json "
                    "models h_alu_hi as 6 bytes and its `match` requires byte+2 bits 2..4 "
                    "== 7, but the observed byte+2 is 0x1b (bits 2..4 = 6), so this form "
                    "does not match the descriptor at all.",
        "impact": "`h_alu_hi.ctrl` and `h_alu_hi.mods` (byte+4/+5 in the 6-byte model) "
                  "were NOT swept — they are not part of this form — so h_alu_hi is NOT "
                  "reported emittable despite four of its fields reaching hardware-run.",
    },
    "bf_add_dst_fmt_scalar_value_is_0x00_not_0x02": {
        "evidence": "EXP-0156 bf.fmt arm + the pilot",
        "observed": "db.json's semantics say byte+1 = 0x02 scalar bfloat / 0x04 bfloat2. "
                    "The compiler emits 0x00 for a scalar `bfloat + bfloat`, and the dense "
                    "sweep accepts exactly {0x00, 0x80}; 0x02/0x03/0x82/0x83 produce "
                    "garbage and every value >= 0x04 makes one addend vanish (the output "
                    "becomes exactly `b`).",
    },
    "bf_add_dst_byte5_carries_a_NEGATE_source_modifier": {
        "evidence": "EXP-0156 bf.tail5 arm, gated, 100.0% cross-run agreement",
        "observed": "byte+5 accepts {0x00,0x20,0x40,0x60,0x80,0xA0,0xC0,0xE0} "
                    "(`v & 0x1F == 0x00`) for a+b. Its low bits are a SOURCE MODIFIER, "
                    "proven by value: `0x08` turns a+b into **a-b** exactly "
                    "([0.5,1.75,2,0,-1,0.375,4,4] for our inputs), `0x09` gives **-b**, "
                    "`0x01` gives **b**. db.json models byte+5..+7 as one opaque 24-bit "
                    "`tail`; it is at least (modifier, cache, marker).",
        "impact": "A bf16 SUBTRACT is directly emittable; no separate opcode is needed.",
    },
    "tg_addr_compute_byte0_and_byte1_are_live_and_unmodelled": {
        "evidence": "EXP-0156 tgac.b0/b1 and tgac141.b0/b1, both gated, 100.0% agreement",
        "observed": "byte0 accepts 104/256 values on k_thr.metal and 102/256 on "
                    "EXP-0141's carrier; byte+1 accepts 96/256 on BOTH. db.json models "
                    "neither as a field (both are pinned in `match`), so an emitter "
                    "cannot fill them from the tables.",
        "impact": "The instruction-level `emit_unsafe` veto STANDS on G17P. bytes +2..+5 "
                  "are 256/256 inert in both carriers and both runs.",
    },
}

INSUFFICIENT = {
    "dev_scoreboard_fence.scope_flag": "NOT SWEPT. No carrier in this experiment has a "
        "memory-ORDERING observable, so a pass would bound acceptance only. EXP-0141 swept "
        "all 256 values densely and refused promotion for exactly this reason; EXP-0147 "
        "reached the same INSUFFICIENT verdict; EXP-0152 pre-registered the same refusal. "
        "Stays `untested`. dev_scoreboard_fence therefore remains ONE FIELD SHORT.",
    "mem_fence.sub": "NOT SWEPT — same insufficiency.",
    "mem_fence.memclass": "NOT SWEPT — same insufficiency.",
    "mem_fence.b5": "NOT SWEPT — same insufficiency.",
    "mem_fence8.mask": "NOT DISPATCHABLE. Emitted only by intersection_query traversal; "
        "agxrun_persist cannot bind an acceleration structure.",
    "mem_fence8.tail": "NOT DISPATCHABLE — same reason.",
    "call.*": "NOT ATTEMPTED. `call` (14 B) does not appear in the frozen CF skeleton and "
        "the only same-length splice sites would transfer control to an address computed "
        "from uninitialised state — the construction that hung the GPU in EXP-0128.",
    "call_indirect.*": "NOT ATTEMPTED — same reason (6 B, only pop_reconverge is the same "
        "length).",
    "mask_op.mask_bank / mask_op.scope_kind": "SWEPT AND DELIBERATELY NOT PROMOTED. The "
        "pre-registered liveness gate (the compiler-natural mask_op spliced over if_push) "
        "did NOT reproduce the baseline — it HUNG in the smoke run and FAULTED in the "
        "gated run — so the site is demonstrably live, but every swept value either faults "
        "or suppresses the output store, which leaves no classification. Reported "
        "`untested` per PRE_REGISTRATION.md §11.",
    "bf_mul_dst.*": "The op-select is proven BY VALUE (byte+2 0x1c->0x1d turns a+b into "
        "a*b, matching a host-computed MUL oracle and failing the ADD oracle), but the "
        "operand fields were swept in the 0x1c form, not the 0x1d form. A full operand "
        "sweep in the mul form is a successor's job.",
    "bf_fma_dst.tail": "NOT SWEPT. bf_fma_dst's tail is byte+6..+9 and only bytes 0..5 "
        "were dispatched, so bf_fma_dst is NOT reported emittable.",
    "h_alu_hi.ctrl / h_alu_hi.mods": "NOT SWEPT — see db_defects: the observed high-half "
        "op is 4 bytes in this form, so those two modelled bytes are not part of it.",
}

import verdicts_map  # noqa: E402  (ARM_FIELDS lives next to verdicts.py)


def controls_fired(groups):
    seen = {}
    for c in G["controls"]:
        seen.setdefault(c["group"], []).append(c["fired_as_registered"])
    out = {}
    for g in groups:
        v = seen.get(g)
        out[g] = (bool(v) and all(v)) if v is not None else None
    return out


def main():
    fv, unresolved = {}, {}
    for arm, e in sorted(G["arms"].items()):
        mf = verdicts_map.ARM_FIELDS.get(arm)
        if not mf:
            continue
        instr, fields = mf
        gates = controls_fired(GATE.get(arm, []))
        gate_ok = bool(gates) and all(v is True for v in gates.values())
        dense = e["dense_full_byte"] or e["swept"] >= 30
        clean = e["accepted_set_identical"] and e["swept"] > 0
        gate_failed = any(v is False for v in gates.values())
        label = ("hardware-run" if (gate_ok and dense and clean)
                 else ("untested" if gate_failed or not clean
                       else ("corpus-correlation" if dense else "untested")))
        rng = ("0..255 dense (all 256 values)" if e["dense_full_byte"]
               else "%d values sampled" % e["swept"])
        note = []
        if e.get("reclassified_no_store"):
            note.append("%d values reclassified `no_store` (EXP-0140 §8 rule: "
                        "invalid_run in BOTH gated runs with every trial STATUS OK)"
                        % e["reclassified_no_store"])
        if e["hangs_a"]:
            note.append("%d reproduced GPU hang(s) in this arm" % e["hangs_a"])
        if e["skipped"]:
            note.append("%d values skipped as known-hang exclusions" % e["skipped"])
        if not gate_ok:
            note.append("NOT PROMOTED: liveness/falsifier gate %s" % gates)
        if e.get("half_class_a"):
            note.append("half classification %s (cross-run agree=%s)"
                        % (e["half_class_a"], e["half_class_agree"]))
        for f in fields:
            k = "%s.%s" % (instr, f)
            ent = {"label": label, "range": rng, "target": "G17P",
                   "evidence": ["EXP-0156"],
                   "accepted": e["accepted_values"],
                   "accepted_count": e["accepted_a"],
                   "mask_rule": e["mask_rule"],
                   "cross_run_accept_agreement_pct":
                       e["cross_run_accept_agreement_pct"],
                   "cross_run_exact_agreement_pct":
                       e["cross_run_exact_agreement_pct"],
                   "arm": arm, "note": "; ".join(note)}
            if k in fv and fv[k]["label"] == "hardware-run" and label != "hardware-run":
                continue          # keep the stronger of two arms for one field
            fv[k] = ent
    fv["_meta"] = {
        "experiment": "EXP-0156", "target": "G17P (Apple A18 Pro, applegpu_g17p)",
        "labels_from": "docs/evidence-classification.md §2 (the eight labels only)",
        "gate": "both gated runs dispatched the same case set for the arm AND produced "
                "the identical accepted-value set AND the arm's liveness/falsifier gate "
                "fired as pre-registered AND neither run had a baseline-check failure",
        "target_discipline": "Every entry here is G17P. Fields NOT listed keep whatever "
                             "label validation.json already carries, which for these "
                             "instructions is M4/G16G evidence; an instruction that "
                             "becomes emittable by combining the two is emittable across "
                             "MIXED targets and analysis/emittability.json says so "
                             "per-instruction under `target_mixing`.",
    }
    fv["db_defects"] = DB_DEFECTS
    fv["insufficient"] = INSUFFICIENT
    Path(EXP / "analysis" / "field_verdicts.json").write_text(
        json.dumps(fv, indent=1, sort_keys=True))
    print(json.dumps({k: v["label"] for k, v in sorted(fv.items())
                      if isinstance(v, dict) and "label" in v}, indent=1))


if __name__ == "__main__":
    main()
