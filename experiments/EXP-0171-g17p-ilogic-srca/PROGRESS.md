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

## 2026-08-30 — M4 COORDINATOR CHECK: db pin verified, and it mattered
Answering the stale-`db.json` alert. **Mine is pinned and matches.**

| copy | sha256 | instructions | fields | `falu2` byte+5 | `ilogic` |
|---|---|---|---|---|---|
| repo live `tools/agx-isa/db.json` | `322847609de7…` | 172 | 1062 | `srcA_class`,`srcB_class` | split `lut_a_sel/free/z` |
| **my `work/frozen/db.json`, resolved ON THE DEVICE** | **`322847609de7…`** | **172** | **1062** | `srcA_class`,`srcB_class` | split |
| the neo's shared `~/agxre/tools/agx-isa/db.json` | `f5db942f03c9…` | 171 | 1036 | **`mod_lo`** | **un-split `lut_a`** |

`raw/g17p_20260830_run01/00_env.json` records `isa_dir
/Users/user/agxre/EXP-0171/work/frozen` and `db_sha256 322847609de7…`, i.e. the pin held for
the whole gated run. Had `_find_isadb()` fallen through to the shared copy, **`lut_a_free`
does not exist there at all** (the shared `ilogic` still has the pre-split 9-field layout),
so this experiment's primary target would have been keyed to a nonexistent field. The neo's
shared `tools/` was **read only, never edited** (EXP-0168/0172 are on that machine).

**The `device_load` asynchrony contamination mode does not apply to this design.** SYNTH and
FRAME seed **all 16 registers with `mov_imm`** (int) or `falu2i` from r14 (float) — there is
no `device_load` anywhere in a synthesized program. The NAT carriers use the compiler's own
`device_load`s with the compiler's own scheduling, and their comparator is a **host-computed
oracle**, not a refreshed baseline, so a re-seeded baseline cannot fabricate movement there.
Independently, `analysis/emit_verdicts.py` measures movement against the **anchor
sub-value's own observation on the same carrier in the same run** and then gates on
cross-run agreement — never against a periodically refreshed baseline. `baseline_fail` is 0
in run01, and a refreshed baseline that differs restarts the child rather than being logged
as data.

Coverage keys `values_dispatched`, `distinct_bytes`, `encodable_range`, `start`, `width` are
emitted on **every** row by `analysis/emit_verdicts.py` (both `field_verdicts.json` and
`field_verdicts_flat.json`); `start`/`width` come from the pinned snapshot, so a stale-DB
mismatch surfaces in `merge_verdicts.py` as a loud refusal.

Headline drift noted: the coordinator now reports **41 of 166 emittable, 616 fields**.
`PRE_REGISTRATION.md` §1 cites 40/126/166 and 614 fields, true at freeze and left unedited
because its sha256 is the contract's gate. This entry is the correction of record.

## 2026-08-30 — M5 GATED RUN 01 COMPLETE (35,949/35,949, 0 hangs, 0 baseline failures)
`raw/g17p_20260830_run01/` pulled back (48 MB). 1596 s, 22.5 case/s aggregate.
Counters: ok 9246, wrong_value 18368, silent_zero 7104, fault 1103, **hang 0**,
undecodable 128, victim 595, sentinel_bad 622, invalid_run 128, baseline_fail 0.
`00_env.json` confirms the pinned `db_sha256 322847609de7…`. run02 (reverse order) launched.

### The primary result: H1 CONFIRMED, and the M4↔G17P contradiction is a CARRIER artefact
`ilogic`/`b_alu10_*` byte+7 (`outmod`), dense 0..255, run01:

| carrier | distinct observations | moved | which values moved |
|---|---|---|---|
| **NAT k_and** (store-consumed) | 2 | **128** | **every value with bit 7 CLEAR** |
| **NAT k_or / k_xor / k_andn / k_nand** | 2 each | **128** each | every value with bit 7 clear |
| SYNTH k_and (register dump) | 1 | **0** | — |
| FRAME k_and (register dump + framing probe) | 1 | **0** | — |

EXP-0146's M4 result reproduces **value-for-value on G17P**. EXP-0154's "inert across the
whole range" was the register-dump carrier being blind to it, exactly as EXP-0166 §2.1
hypothesised. **There is no cross-target divergence.** R1a and R1b did not fire.

### …and the MECHANISM in db.json is wrong
db.json calls byte+7 bit7 "an output/store flag". The poisoned buffer says otherwise. With
bit 7 clear, `poison_out == 0` and **both sentinels are intact** — the store DID execute —
and the value written is:

| kernel | bit7 set (anchor 0x80) | bit7 clear |
|---|---|---|
| k_and | `a&b` (correct) | **0** |
| k_or | `a\|b` | **0** |
| k_xor | `a^b` | **0** |
| k_andn | `a&~b` | **0** |
| **k_nand** | `~(a&b)` | **`0xFFFFFFFF`** |

`nand` is the discriminator. An output-zeroing flag would give 0 for nand too. `0xFFFFFFFF`
is `~(0 & 0)` — i.e. **the LUT still evaluates and the destination is still written; it is
both SOURCES that read as ZERO.** So byte+7 bit7 is a **source-read / operand-delivery**
control, not an output/store flag. And the SYNTH carrier — where the operands are
`mov_imm`-seeded GPRs written long before — is unaffected, which points at
*pending-load delivery*: in NAT the operands arrive from an asynchronous `device_load`
issued immediately before. (Alternative not excluded: a scoreboard/forwarding bit whose
absence only matters when the consumer is adjacent. A successor discriminates it by putting
the dump store immediately after the block.)

### H7 CONFIRMED — DEF-0171-1 is now HARDWARE-PROVEN, not structural
SYNTH byte0 dense sweep: **every one of the 15 observable values with low nibble `0xb` puts
the AND result (73 = 93 & 107) in register `v>>4`** — `0x0b`→r0, `0x1b`→r1, … `0xeb`→r14.
(`0xfb`→r15 is not observable: r15 is the harness's own `device_store` index register and is
re-seeded before every dump store. 15 of 15 observable, 0 misses.) `ilogic`'s
`match [[0,8,11]]` therefore hides 15 of 16 destinations behind `b_alu10_lof`/`loe`.
Also observed: byte0 `0x23` reproduces the anchor's full register state exactly — a second
low nibble reaching the same datapath, worth a successor's attention.

### F3 POSITIVE CONTROL: 20 of 20 transplants reproduced the transplanted function
Splicing kernel Y's selector bytes (+2,+4,+5) into kernel X's logic op made X compute **Y's
boolean function**, host-computed, for all 20 ordered pairs over
{and, or, xor, andn, nand}. The four `k_andn`-sourced transplants matched **only with the
operands swapped** — its compiler anchor has byte+1/+3 = `01`/`03` where the others have
`03`/`01`. That is DEF-0154-5's operand swap, reproduced as a *prediction* rather than
found by accident. This is synthesis, not tokenization: any of the five functions can be
GENERATED into any of the five kernels.

### Arm B, run01 (single-run, not yet gated)
* **`ibitcount.tail` MOVED 128/256 on all four carriers, and the accept-set is EXACTLY the
  128 values with bit 2 set** — G17P reproduces M4's EXP-0139 DEF-0139-3 value-for-value.
  `ibitcount` was ONE field from emittable.
* **`fspecial_est.srcA` (254/256) and `.subop` (255/256) MOVED on SYNTH and FRAME**, and the
  **NAT `k_rsqrt` carrier FAILED its own falsifier (byte0:=0 came back `ok`) and was
  DISCARDED** — the Newton-Raphson refinement masks everything, which is EXP-0161's failure
  mode, now *diagnosed by the falsifier instead of mistaken for inertness*. H5 confirmed.
* **`bf_alu.srcA` 254/256, `.srcB` 248-254/256, `.tail` moves on all three spanned bytes**
  (b+5 240-248, b+6 128-224, b+7 192-224) — `bf_alu` was 3 fields from emittable.
* **`bf_fma_dst.tail` moves on all four spanned bytes on NAT** (252/248/224/224); SYNTH and
  FRAME see b+8/b+9 as inert. `bf_fma_dst` was ONE field from emittable.
* **`iadd2.srcA` MOVED 208-252/256** with a 48-value accept-set on SYNTH — refutes H6's
  "inert or tiny accept-set". `iadd2.b2_fmt` is dense-INERT (0/64) on all three carriers
  while byte+2 itself moves 128/256 on NAT (that movement is bits 0-1, i.e. `b2_bit0` /
  `store_en`), so the detection power is proven and `b2_fmt` really is inert.
* **`ibfe.srcA` MOVED 192/256 on all three carriers. `ibfe.sign_ext` (byte+6 bit1) is
  INERT on BOTH `k_bfe` (unsigned) and `k_bfe_s` (signed)** — flipping it does not change
  signedness in either direction. Our two compiler anchors differ in byte+6 bit1 *and* in
  `srcC_flags` byte+9 bit0 (`0x11` unsigned vs `0x10` signed); the sweep shows byte+6 bit1
  is not the cause. db.json's "signed sets sign_ext (b6 bit1)" is a CORRELATION across the
  two compiler forms, not a control. (Byte+9 was not swept here — the attribution to
  `srcC_flags` bit0 is INFERRED and needs its own arm.)
* `ilogic.z6 / z8 / z9` (= `b_alu10_*.z6 / ext8 / ext9`): dense-INERT, 0/256 each, on all
  three carrier STYLES — but only ONE probe anchor, so they are held at
  `single-template-inference`, not promoted.
