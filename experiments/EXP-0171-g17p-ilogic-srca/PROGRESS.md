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

## 2026-08-30 — M2 RESUMED after the session-limit kill
Re-oriented from the committed files at `b44ffbc7` (not from memory): `PROGRESS.md`,
`work/m1_findings.json`, `work/emit-worklist-regen.md`, `harness/{casematrix,isa_helpers}.py`,
`kernels/{probes,carrier_dag}.metal`. What was MISSING and is being authored now:
`PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `README.md`, `harness/{anchors,sweeprun,run}.py`,
`harness/sync.sh`, `analysis/{coverage,emit_verdicts}.py`, `work/frozen/`.

Neo reachable (`26.6`, `Mac17,5`), `~/agxre/tools/{shdump,agxtest,agx-isa}` present,
one sibling `agxrun_persist` running (EXP-0168/0169 sweeping — expected, unlocked).

Worklist REGENERATED from live `tools/agx-isa`: headline is **40 emittable / 126 blocked / 166**
(the copy in `work/emit-worklist-regen.md` says 44/122 and is STALE — superseded, kept as the
record of what the pre-kill session saw). `dst` blocks 35 (EXP-0168's), `srcA` 17, `tail` 15.

Blocking-field re-derivation against live `validation.json` (supersedes M1 finding 1 in one
detail): `ilogic` is **5** fields from emittable — `lut_a_free` (corpus-correlation) + `z6`,
`outmod`, `z8`, `z9` (all `untested`, withdrawn by EXP-0164). Arm B ranked by closure distance:
`ibitcount.tail` (1), `bf_fma_dst.tail` (1), `fspecial_est.{srcA,subop}` (2),
`iadd2.{srcA,b2_fmt}` (2), `bf_alu.{srcA,srcB,tail}` (3), `ibfe.{srcA,sign_ext,b2_bit0}` (3).

## 2026-08-30 — M3 FROZEN. Two descriptor defects found at anchor extraction.
`PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` written. Matrix **35,949 cases**,
`matrix_sha256 bce0b7dee4dcbd4c93d21bc24d52e282a2d37ce348026b0decf712102ee0001b`,
7 arms, 38 owned verdict keys. Step 0 (`harness/anchors.py`) is COMPILE-ONLY and ran
before the freeze so the contract could carry the real case count; it dispatched nothing.

Step 0 produced two first-class findings that changed the design:

**DEF-0171-1 — `ilogic`'s byte0 match is over-fitted to destination r0.** Our own
`out[g]=a[g]&b[g]` compiles on G17P to `2b 03 1f 01 00 00 00 80 00 00`. `ilogic`'s match
is `[[0,8,11]]`, a FULL 8-bit byte0, so it only matches byte0 `0x0b` = dst r0; every other
destination falls through to `b_alu10_lof`/`b_alu10_loe`, whose match is the LOW NIBBLE
only and which model `dst` at byte0's high nibble. Verified on the frozen snapshot:
`0b031f01...` -> `ilogic`, `2b031f01...` -> `b_alu10_lof`. Byte structure is parallel
field-for-field (b1,b3,b4,b5,b6,b7,b8,b9). So EXP-0154's G17P `ilogic` rows are rows about
**dst r0 only**, and one sweep here serves both key sets. The SYNTH carrier sweeps byte0
densely to PROVE the equivalence (H7).

**DEF-0171-2 — no length rule for byte0 == 0x31, so G17P's own bfloat ALU does not
tokenize at all.** `bfloat +`/`*`/fma compile to `31 00 1c 00 11 00 c0 81` (8B),
`31 00 1d ...` (8B), `31 00 1e 00 86 02 10 00 c0 81` (10B) -- all `<unknown>, length None`.
`bf_alu`'s match demands byte0 `0x11` (the SAME dst-nibble over-fit) and byte+1 `0x02`,
but G17P emits byte+1 `0x00`; `bf_fma_dst.fmt`'s enum `{2,4}` lacks the emitted `0x00`.
Lengths PINNED in the matrix from the compiled programs themselves (the following
`mov_imm 0cda` lands at exactly +8/+8/+10); every such case records `anchor_pinned: true`.

Two more Step-0 observations: **`fspecial_est` byte+3 == `0x0f`** on G17P (absent from
db.json's `{9,11,13}` enum), and **the predicate-consumed `ilogic` pole is unreachable from
our own MSL on G17P** -- both `(a&b)!=0?7:9` and the `if` form lower to `isel10` with no
logic op at all, recorded as `instr_absent` rather than dropped.

Also fixed before freezing: `SEED_I` was EXP-0154's bit-disjoint table, under which a
lifted logic op on the compiler's chosen (r1,r0) computes `21 & 10 == 0` -- a baseline that
is itself a silent zero. Replaced with high-popcount seeds; no pair ANDs to 0, asserted at
import.

**Courtesy hazard notice (FIELD-SWEEP-PROTOCOL sect 7):** the FSPECIAL_EST arm sweeps
`fspecial_est` byte+3 densely 0..255, adjacent to the known `fspecial` byte+3 >= 192 hang
region. Arm aborts and reports PARTIAL after 2 genuine hangs.
