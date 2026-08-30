# EXP-0171 — PROGRESS (append-only; newest last)

Target: **A18 Pro / G17P** (`users-MacBook-Neo.local`, 192.168.10.243).
Scope: (A) close `ilogic` on G17P; (B) the `srcA` / `tail` levers.

## 2026-08-30 — M0 governing documents read
`CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`, `experiments/FIELD-SWEEP-PROTOCOL.md`
read in full. Device work is QUEUED — no SSH, no dispatch, nothing touched on the neo.

## 2026-08-30 — M1 offline evidence review COMPLETE
Read: `EXP-0166/RESULTS.md` + `analysis/`, `EXP-0154/{RESULTS.md,harness/*,raw/*}`,
`tools/agx-isa/{db.json,validation.json}`, `EXP-0168`/`EXP-0169` pre-registrations
(collision check). Findings recorded in `work/m1_findings.md`.

Load-bearing corrections to the dispatch's premises (all verified from committed raw):

1. **`ilogic` is FIVE fields from emittable, not one.** `lut_a_free` (corpus-correlation)
   *and* `z6`, `outmod`, `z8`, `z9` (all `untested`, withdrawn by EXP-0164 for
   single-carrier inertness). EXP-0166 §1.2's "single field" predates that withdrawal.
2. **EXP-0154's G17P `lut_a` arm DID sweep the whole of byte+4** — 256 distinct `bytes`
   strings in both gated runs, contradicting `validation.json`'s note that it "covered
   lut_a 0..15 = bits 32-35 only". It was orphaned by the mid-experiment `lut_a` split,
   never re-keyed. A5-decomposing it offline yields a **G17P** arm for
   `lut_a_sel` (4/4, 3 move), `lut_a_free` (8/8 dense INERT), `lut_a_z` (8/8, 7 move),
   D=0 across the two gated runs. That is carrier #1 for `lut_a_free`, free of charge.
3. **`ilogic` bytes +6,+7,+8,+9 are ALL single-digest inert on EXP-0154's carrier**
   (256 values, 256 distinct encodings, one observed digest) while bytes +1,+3,+4,+5 move
   on the same carrier — so that carrier's detection power is proven and the inertness of
   the tail is a real measurement, not a dead probe.
4. **The M4 "outmod bit7 clear -> silent zero" cannot be a GPR-write-enable on G17P.**
   EXP-0154's baseline seeds r0=10 and the ilogic writes r0=2 (=10&34); with byte+7=0x00
   r0 is still 2. So on G17P the GPR write happens with bit7 clear. Whatever M4 saw was
   either the store path or the target.
5. **`isadb.assemble()` match/field overlap (DEF-0166-1) does not touch my target fields.**
   Static scan: of the 11 candidate descriptors only `funary.op` (3 bits),
   `fspecial_est.subop` (2 bits) and `packed_half2_hi.opsel` (2 bits) overlap a set match
   bit. `fspecial_est.subop` IS a target, so the harness splices raw bytes into the lifted
   block and never routes a swept value through `assemble()`; distinct-`bytes` counting is
   a hard gate in `analysis/coverage.py`.
6. **No verdict collision with the two concurrent device experiments.** EXP-0168 owns
   `dst` + 12 named one-field-away rows + `cvt_f2i.b9`, `vtx_out_pos.slot`; EXP-0169 owns
   `falu2*`, `half_alu*`, `iunary`, `reg_move_*`, `bf_alu.opsel`, `icmp_pred.cond`,
   `get_sr.*`, `device_store.*`. My rows are disjoint from both. `icmp_pred` is *shared as
   an instruction* (disjoint fields) and is ranked last for that reason.
