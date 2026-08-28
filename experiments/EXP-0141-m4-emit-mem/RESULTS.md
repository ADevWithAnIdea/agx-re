# RESULTS — EXP-0141 M4 memory / atomic / fence family: emission, not decoding

**Target: local Apple M4 / G16G only** (`Mac16,10`, macOS 26.6.2 / 25G82).
No A18 Pro replication (hands-off). No M5 evidence used anywhere. Everything
below is an M4 claim; nothing is promoted to G17P.

**Concurrency (FIELD-SWEEP-PROTOCOL section 7.4).** This experiment was
dispatched in a GPU batch with **EXP-0139 (IALU)** and **EXP-0146 (integer
misc)**; **EXP-0148** is desk-only and does not contend. The `ps` snapshots
recorded in `raw/<run>/01_progress.json` are the honest per-run answer: **all
four gated runs recorded 0 sibling GPU-runner processes at their start and at
their end**. That is a sample at two instants, not a guarantee for the interval
between them, and it should not be over-read: the earlier smoke and pilot phases
recorded **2** siblings, and run 12 ran markedly slower than run 11 on identical
work (~7 s vs ~2 s per case in the mostly-faulting `attg` arms), which is what
sibling load looks like. Treat run 11 as the quiet run and run 12 as the
possibly-contended one — which is precisely why every claim below is gated on
the two agreeing case-for-case, and why the sentinel and majority machinery in
section 2 exists.

---

## 0. Headline verdicts

### H1 — `device_load`'s destination register IS NOW EMITTABLE. `hardware-run`.

This was the wave's named target: `work/DOC-02-LABELLING-REPORT.md` calls
`device_load.dst_lo`/`dst_ext9` *the largest single synthesis blocker in the
ISA*, because `EXP-0112`'s generator produces 100 correct random DAGs only by
copying those two fields **verbatim** from a compiled shader.

**They carry no register information at all, and the rule is three constrained
bits:**

| field | encodable | accepted | rule |
|---|---|---|---|
| `dst_lo` (bits 70-71) | 4 values | **1** | `v & 0x03 == 0x01` (EXACT mask rule) |
| `dst_ext9` (bits 72-78) | 128 values | **64** (every odd value) | `v & 0x01 == 0x01` (EXACT) — **bit 0 must be 1; bits 1-6 are DON'T CARE** |
| the pair, 2-D | 512 combinations | **64** | `v & 0x181 == 0x81` (EXACT) — the two constraints are independent |
| `extmode` (byte+3) | 256 values | **128** (0..127) | `v & 0x80 == 0x00` (EXACT) — destination register = `extmode >> 1`; **bit 0 is a DON'T CARE**; 128..255 (r64+) silently zero |

Every rule quoted in this document is a **machine-derived, exactness-checked**
mask/pattern (`analysis/bitrules.py`, `analysis/bitrules.json`, and the
`mask_rule` key of every entry in `analysis/field_verdicts.json`); fields whose
accepted set is *not* a mask rule are printed as such rather than described with
a rule that does not hold.

Swept **exhaustively** — all 4 `dst_lo` values and all 128 `dst_ext9` values at
**four independent target registers (r3, r7, r20, r33)**, plus the **full
512-value 2-D product** at r7. The accepted set is *identical at every target
register*: exactly 64 of 512 pairs work and they factorise cleanly as
`{dst_lo == 1} x {dst_ext9 odd}`. That kills "the pair encodes the destination".
The *other* half of `EXP-0101`'s advice — "copy it from a load of the same
`addr_mode`/`ld_format` shape" — is killed separately by the addendum's H8
(section 7), which re-runs the full 512-value product under every `ld_format`
code that works; and `addr_mode` is inert over all 256 values on this shape
(section 4.1), so there is no shape left for the pair to depend on.

**What an emitter must do, complete:**

```
device_load destination register R (0 <= R <= 63):
    extmode  = 2*R          (bit 0 free; 2*R+1 works identically)
    dst_lo   = 1            (byte+8 bit 6 set, bit 7 clear)
    dst_ext9 = 1            (byte+9 bit 0 set)
  R >= 64 is NOT REACHABLE through this field: it silently zeroes.
```

`dst_ext9 = 1` is valid under **every one of the 21 `ld_format` codes that
work** (addendum H8, section 7). How many of `dst_ext9`'s *upper* bits are
additionally don't-cares is `ld_format`-dependent — free for 16 of the 21 codes,
narrower for `ld_format` 3/7/9/13 and 39 — so an emitter should just write 1.

No captured token, no per-shape table, no compiled-shader donor. **Answer to the
dispatch question: yes — `device_load`'s destination is emittable.**

Three facts here are new relative to `EXP-0101`, which established
`extmode = 2*R` but never swept the pair: (a) `dst_lo`/`dst_ext9` are a fixed
3-bit enable pattern, not a per-`addr_mode`/`ld_format` token; (b) `extmode`
bit 0 is a don't-care; (c) `extmode` cannot address r64+.

### H3 — the atomic RMW operand register IS encoded in the instruction. `db_defects`.

`db.json`'s own semantics say *"the actual RMW operand register is implicit
(supplied by the preceding op / amode)"*, and DOC-02 section 3 ranks this a
**missing field** — *"the worst kind of gap for an emitter."*

It is not implicit. `kernels/atomic_dev.metal` keeps `a[0..3]` = 7 / 1007 /
2007 / 3007 live across `atomic_fetch_add(o, a[0])`, and the dense byte sweep
finds the selector:

| splice | counter becomes | side effect |
|---|---|---|
| baseline `byte+5 = 0x00, byte+6 = 0x00` | **7** = `a[0]` | — |
| `byte+5 = 0x80` | **1007** = `a[1]` | `a[1]`'s later reader now reads **0** |
| `byte+6 = 0x01` (also `0x41/0x81/0xC1`) | **2007** = `a[2]` | `a[2]`'s later reader now reads **0** |

Model: `operand_register_index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1)`,
relative to the register the compiler's own encoding selects. The redirected
register is **consumed** — its later reader gets 0 — which is the same
register-release contract `EXP-0086`/`0089`/`0099` document for the ALU
families, and is independent corroboration that the byte really moved the data
operand rather than the address.

**Limits, stated plainly:** index 3 (`byte+5 = 0x80` *and* `byte+6 = 0x01`
simultaneously) was **not constructed** — this experiment sweeps one byte at a
time — so the `<< 1` multiplier on `byte+6` is interpolated from two points, not
proven. `db.json` calls `byte+5` `index_reg` ("per-lane index GPR, zeroed for a
uniform address") and `byte+6` `addr_desc` ("framing only"); our
`atomic_dev_imm` carrier uses a **uniform** address yet the compiler emits
`byte+5/+6 = 0x80/0x02`, which the per-lane reading does not explain. The
address role is not excluded for the per-lane form; the **data** role is now
proven for the uniform form.

### H2 — `device_store.addr_mode` bit 1 is a live data-source selector, not inert.

`validation.json` currently records `device_store.addr_mode` as `hardware-run`
with the range *"bit1 at {0,1} (the literal 0x54/0x56 position): INERT here"*
(`EXP-0119`). Both halves swept densely, in both source shapes:

| stored data comes from | accepted `addr_mode` values |
|---|---|
| an ALU result | **256 / 256** — genuinely inert |
| a **live `device_load` result** | **128 / 256** — exactly the values with **bit 1 SET**; the 128 with bit 1 clear store **0** |

So `EXP-0119` was right about the configuration it measured and wrong as a
general statement: bit 1 selects *ALU-computed* vs *direct live load-result*
data, exactly as `db.json`'s `addr_mode` enum text says, and it is unobservable
whenever the source is ALU-computed. This is a refinement, not a contradiction,
and it is load-bearing: a synthesised load-to-store forward with `0x54` silently
stores zero.

### H4 — `threadgroup_barrier.flags` and `.b5` do not carry the fence. Confirmed.

All 256 values of each leave the 256-lane litmus **exact**. This is a real
negative, not an insensitive carrier: the same carrier's falsifier makes
**224 of 256 lanes** read stale zeros when the barrier is neutralised (224 =
256 - 32 is precisely the set of lanes outside the writer's own SIMD group).

`mem_scope` (byte+3), swept densely for the first time, shows **only bit 0
matters** for a threadgroup-memory litmus: all 128 odd values pass, all 128 even
values fail with the same 224 stale lanes. That is dense confirmation of
`EXP-0093`'s "byte+3 bit 0 is the execution-convergence enable, independent of
the requested memory-fence class" — the memory-class bits are don't-cares here.

### H5 — `tg_addr_compute`: the EMITTABLE VETO must STAND, and an A18<->M4 divergence.

`EXP-M4-14` (A18) found byte0's high nibble live, with `0x1c` **and `0xfc`**
reproducing the baseline. On M4, of all 256 values **only `0x1c`** — the
compiler's own — leaves the tile dataflow correct; `0xfc` does **not**
reproduce. Byte+1 is likewise live, with 32 of 256 values accepted, the set
being exactly `{v : v & 0x03 == 2 and v & 0x10 == 0}`. Bytes +2, +3, +4, +5 are
**inert over all 256 values each** (M4 confirmation of `EXP-M4-14`'s A18
result, and confirmation that byte+2 is a *decoder* length discriminator, not a
hardware one).

Because byte0 admits exactly one value on M4 and neither byte0 nor byte+1 is
modelled as a field, **`tg_addr_compute` is still not emittable** and I am not
reporting it as such, exactly as the dispatch required.

### H6 — `dev_scoreboard_fence` and `mem_fence`: swept, deliberately NOT promoted.

`dev_scoreboard_fence` was **synthesised from scratch** into the validated
load->ALU->store program (no own-MSL kernel we could compile emits
`80 02 00 xx`), and all 256 `scope_flag` values execute and leave the
surrounding dataflow exact. `mem_fence`'s `sub`/`memclass`/`b5` were swept
densely in a device-atomic carrier, with `memclass` and `b5` inert over all 256
values.

**Neither carrier has a memory-ORDERING observable**, so these sweeps bound
*acceptance and dataflow-inertness only*. Promoting them to `hardware-run` would
claim the tables' documented semantics were tested when they were not, so they
stay at `corpus-correlation` with the observation attached. This is the
pre-registered limitation (`PRE_REGISTRATION.md` H6), not a post-hoc excuse.

`mem_fence8` is **untested**: it is emitted only by `intersection_query`
traversal, and `agxrun_persist` cannot bind an acceleration structure. One new
fact was obtained by compiling our own ray-query kernel and disassembling it: a
`mask` (byte+3) value of **`0x11`**, which `db.json` does not list (it records
`0x14` / `0x0c`). That is `corpus-correlation` and is recorded as such.

---

## 1. What was actually run

| | |
|---|---|
| main matrix | 93 arms, **20 529 cases**, frozen in `sweepdefs.py` before any capture; captured twice (**20 615** and **20 744** records including interleaved health checks) |
| addendum | 39 arms, **14 853 cases**, captured twice (**15 005** records each) |
| total dispatched | **~71 000 GPU measurements** across four gated runs, plus the retained partial `run01` |
| coverage rule | every field of width <= 8 swept **densely over all 2^w values**; `dst_lo` x `dst_ext9` over its full 512-value product |
| carriers | 6, all our own MSL; every oracle host-computed and checked against the unspliced kernel first |
| falsifiers | 6 pre-registered to FAIL; all 6 failed in every run |

## 2. Robustness — and three ways this hardware lies to a sweep

`FIELD-SWEEP-PROTOCOL.md` section 7 landed between this experiment's first
freeze and its first capture. Implementing it surfaced three distinct
contamination modes, all of which forge *field results*, and all of which are
now mitigated in `harness/sweeprun.py`:

1. **Archive-path reuse.** Reusing one splice-archive filename across
   persistent-runner requests — the pattern in
   `RT-1a-FIX/harness/mem_index.py` — produced **28 / 360 spurious
   `CMDBUF_ERROR`** on byte-identical, known-good archives. A unique path per
   request, unlinked afterwards, gave **0 / 360**. Any experiment that sweeps
   through `agxrun_persist` and overwrites one archive path is at risk of
   phantom faults.
2. **Innocent-victim cascades.** A GPU fault poisons subsequent command buffers,
   which return `kIOGPUCommandBufferCallbackErrorInnocentVictim /
   "Discarded (victim of GPU error/recovery)"`. Every record carries
   `fault_classes` and `innocent_retries`; these failures are retried (bounded,
   6) and never by themselves make a case a fault.
3. **`STATUS OK` with nothing executed.** The nastiest one, and the reason the
   integrity sentinel exists: under sibling GPU load a command buffer can report
   success while the output buffer stays at its zero-initialised contents. On
   this ISA an all-zero readback is the *expected* signature of a wrongly
   encoded field, so the artifact forges a real-looking negative. It corrupted
   the **pre-registered baseline itself** during smoke (`synth/_baseline`, i.e.
   `EXP-0101`'s HW-VALIDATED construction, read back wrong with `STATUS OK`).
   Every carrier now writes a fixed sentinel through a path independent of the
   instruction under test; a measurement without its sentinel is `invalid_run`
   and is repeated, never recorded.

On top of that, **no non-`ok` verdict is taken from one observation**: a case is
re-measured until two observations agree or three have been made, and
`fault`/`hang` additionally require >= 2 of 3 non-innocent failures. The
unmutated carrier is re-measured at every carrier's start and end and every 100
cases; a failure restarts the runner and re-checks, and a second failure would
declare a cascade and stop that carrier.

**Health across all four gated runs: 214/214, 215/215, 152/152 and 152/152
baseline checks passed; 0 cascades; 0 aborted carriers.**

**Cross-run acceptance agreement: 0 disagreements out of 20 611 common main-matrix
cases, and 2 out of 15 005 addendum cases** (both `atdev_operand_pair`
byte+6 = 0x30/0x31, excluded from every claim).

## 3. Safety

Two **reproduced** GPU hangs in run 11, both in `attg_atomic_tg_b5`
(`atomic_tg` byte+5), at exactly **0x7E** (`HANG`, `HANG`, `HANG`) and **0x7F** (`HANG`,
`CMDBUF_ERROR`, `CMDBUF_ERROR`) — bytes `67 03 54 00 00 7E 00 00 20 00 00 04`
and `...7F...`. **Do not emit `atomic_tg` byte+5 in 0x7E..0x7F.** The arm was
aborted at case 129 of 257 per the 2-hang budget, so run 11 is **PARTIAL** there.

**Run 12 did not hang on those values** — it returned a reproduced
`CMDBUF_ERROR` (3/3) for both and completed the whole 0..255 sweep. So the two
encodings are reproducibly bad in both runs, but their *severity* varies between
a contained command-buffer fault and a real hang. Because only one gated run has
a dense sweep of that byte, `atomic_tg.op_desc` is the one field the automatic
gate refuses to promote, and it stays **PARTIAL**. No other hang occurred
anywhere in ~71 000 measurements. The host survived; every later baseline health
check passed. `macvdmtool` was never used; the A18 was never touched.

## 4. Per-field outcome, main matrix

Full machine-readable detail in `analysis/field_verdicts.json`; per-arm tables in
`analysis/summary.json`.

### 4.1 `device_load` — 6 blocking fields, all closed

| field | was | accepted / swept | rule |
|---|---|---|---|
| `dst_lo` | `single-template-inference` | 1 / 4 (x4 registers) | must be 1 |
| `dst_ext9` | `single-template-inference` | 64 / 128 (x4 registers) | bit 0 must be 1, bits 1-6 free |
| `ld_format` | `corpus-correlation` | 21 / 64 | same 21 in both program shapes |
| `ldform_hi11` | **`untested`, range `none`** | 8 / 64 | bits 0-2 must be 0, bits 3-5 free |
| `reserved7` | `tokenization-only` | 256 / 256 | genuinely INERT |
| `reserved13` | `tokenization-only` | 256 / 256 | genuinely INERT |

Also upgraded on the same carrier: `extmode` (128/256, rule above), `space`
(64/256 — bits 0-1 must be 0, bits 2-7 free), `access_desc` (256/256 inert,
first M4 evidence; was A18-only), `elem_size` (48/256), `index_reg` (190/256 —
r0..r95 work, **bit 7 is ignored so 128..255 mirror 0..127**, and r96..r127
fault reproducibly), and `addr_mode` — **256/256 inert** for a terminal scalar
32-bit indexed load, i.e. none of `db.json`'s addressing-mode enum is
observable on this shape (see `db_defects`).

### 4.2 `device_store` — 5 blocking fields, all closed

`st_format` 84/256 (same set with an ALU and a load-forwarded source),
`st_format_ext` 32/128 (bits 5-6 must be 0), `st_desc_hi` 16/64 (`v & 0x11 == 0x00`: bits 0 and 4
must be 0, bits 1-3 and 5 free), `reserved7` and `reserved13` 256/256 **inert**. Plus
`addr_mode` (H2 above), `space` 128/256, `access_desc` 256/256 inert,
`elem_size` 96/256, and `extmode` — the store's SOURCE-register selector, where
exactly two values work per source register, `2*R` and `2*R | 0xC0`, proven by
re-sweeping with the value in r4, r8 and r12 (addendum H10, section 7). Unlike
the load side, **bit 0 is live** here.

### 4.3 `atomic_mem` — 14 blocking fields, all swept densely

`amode`, `rsv3` and `base_slot` are **inert** (256/256 each) on this carrier;
`index_reg` and `addr_desc` are the **operand-register selector** (H3);
`ret_flag` (1/256), `rsv11` (1/256) and `rsv10` (4/256) are heavily constrained
**live** bytes despite two of them being named "reserved"; `ret_desc` 2/256,
`idx_off` 32/256, `amode_hi` 32/256 (register-operand carrier) vs 96/256
(immediate-operand carrier). Byte+12 — which carries `op_lsb`, `op`, `per_lane`
and `op_msb` — was swept over all 256 values, i.e. **every combination of those
four sub-fields**; `0x36` (op 27 = `sub`) yields `0xFFFFFFF9` = -7 exactly, an
independent confirmation of the op enum.

### 4.4 `atomic_tg` — 11 blocking fields, 10 swept densely, 1 PARTIAL

`amode` and `ret_desc` **inert** (256/256 each — the returned old value is never
consumed in this carrier, which is why `ret_desc` is unobservable here);
`rsv4` 4/256, `rsv6` 2/256, `xop_desc` 2/256, `data_desc` 128/256,
`rsv9` 1/256, byte+10 1/256, byte+11 24/256 — again, three "reserved" bytes
that are live. **`op_desc` (byte+5) is PARTIAL**: aborted after 2 reproduced
hangs at case 129/257.

Caveat: `atomic_tg`'s `op` field straddles byte+10 and byte+11, and this
experiment sweeps one byte at a time, so the two bytes' **joint** space is not
covered — each byte is dense with the other at its compiler-emitted value.

### 4.5 `threadgroup_barrier` — 2 blocking fields, both closed

`flags` 256/256 inert, `b5` 256/256 inert (H4). `sub` 64/256 (`sub & 0x06 ==
0x04`), `mem_scope` 128/256 (bit 0 only), and byte+2 — a `match`-pinned byte
`db.json` does not model as a field — **inert over all 256 values**.

## 4.6 The cross-run gate, and where the two runs disagree

`analysis/verdicts.py` promotes a field to `hardware-run` only if the two
independent gated runs agree **case for case on ACCEPTANCE** (`ok` vs not-`ok`)
**and** produce the identical accepted-value set — not if they agree on the
exact outcome label. The distinction is load-bearing and it is reported both
ways in `field_verdicts.json` (`cross_run_accept_agreement_pct` is the gate,
`cross_run_agreement_pct` is the raw number).

The one place they come apart is `device_store.extmode`: 11 of its 256 cases are
`nondeterministic` in one run and `wrong_value` in the other. **Both runs agree
those values fail**, and both produce the same accepted set `{16, 208}`; they
disagree only on how *stably* the value failed. Gating on exact outcomes would
have downgraded a claim neither run contradicts. Gating on acceptance is the
honest reading of what the label asserts, and the raw disagreement is published
next to it so a reader can apply the stricter rule if they want to.

## 5. Alternative explanations not excluded

1. **One carrier shape per instruction.** `device_load` results are for the
   terminal scalar 32-bit indexed shape; `addr_mode`'s inertness may not hold for
   the base-sharing, CF or RT forms its enum names. More specifically: this
   program's index register holds **0** and `idx_off` is **1**, so several of the
   addressing modes the enum names could resolve to the *same* address and be
   indistinguishable here — "inert" is a statement about the value loaded, not a
   proof that the modes are the same mode. `atomic_mem.base_slot`'s inertness is
   likewise measured with **one** bound atomic target, where a slot index cannot
   be observed at all.
2. **The operand-register model is two points and an interpolation.** Indices 0,
   1 and 2 were constructed; index 3 (both bytes at once) was not.
3. **Fence semantics are untested, not disproven.** `mem_fence` and
   `dev_scoreboard_fence` sweeps show acceptance and dataflow-inertness in
   carriers with no ordering observable.
4. **"Inert" always means "inert on this observable".** A byte that does not
   change a scalar load's value may still change scheduling, latency, or
   behaviour under contention.
5. **`device_store.extmode`'s `| 0xC0` alternative form** is now characterised
   over three source registers (addendum H10) but its MEANING is unknown — only
   that it is accepted. Likewise `atomic_mem` byte+6 = `0x30`/`0x31`, which
   restore the baseline operand and are the addendum's only cross-run acceptance
   disagreement.
6. **Single target.** M4/G16G only. The `tg_addr_compute` byte0 result actively
   disagrees with `EXP-M4-14`'s A18 measurement, which is a reason to treat
   cross-target transfer in this family with suspicion rather than to assume it.

## 5.1 Verdict counts

`analysis/field_verdicts.json` carries **77** labelled entries (the 58 blocking
fields plus the non-blocking fields this experiment also swept, plus seven
`match`-pinned bytes `db.json` does not model as fields at all):
**69 `hardware-run`, 1 `isolated-byte-diff`, 6 `corpus-correlation`,
1 `untested`.** Every one carries its swept range, its accepted-value set, its
machine-derived mask rule, both cross-run agreement numbers, whether both runs
covered the same case count, and the arms it came from.

## 6. The honest field ledger

Machine-generated by `analysis/ledger.py` from `tools/agx-isa/validation.json`
(read-only — this experiment does not edit it) and
`analysis/field_verdicts.json`.

**51 of the 58 blocking fields moved to emitter grade
(`hardware-run` / `isolated-byte-diff`).**

| instruction | fields | blocking before | moved to emitter grade | still blocking |
|---|---:|---:|---:|---:|
| `atomic_mem` | 15 | 14 | **14** | 0 |
| `atomic_rmw` | 15 | 14 | **14** | 0 |
| `atomic_tg` | 11 | 11 | **10** | 1 |
| `dev_scoreboard_fence` | 1 | 1 | **0** | 1 |
| `device_load` | 14 | 6 | **6** | 0 |
| `device_store` | 13 | 5 | **5** | 0 |
| `mem_fence` | 3 | 3 | **0** | 3 |
| `mem_fence8` | 2 | 2 | **0** | 2 |
| `tg_addr_compute` | 3 | 0 | **0** | 0 |
| `threadgroup_barrier` | 4 | 2 | **2** | 0 |
| **TOTAL** | | **58** | **51** | **7** |

The **7** that did NOT move, and exactly why:

- `atomic_tg.op_desc` — **PARTIAL.** Run 11 aborted this arm at case 129/257 after two reproduced GPU hangs; run 12 completed all 257 without hanging. The two runs therefore do not have a common dense sweep, so the automatic gate downgrades it. Values 129..255 have one run's evidence only.
- `dev_scoreboard_fence.scope_flag` — All 256 values execute and leave a synthesised dataflow exact, but the carrier has **no ordering observable**, so the field's documented scope semantics were not tested. Deliberately not promoted.
- `mem_fence.sub` — Same reason: swept densely, no ordering observable.
- `mem_fence.memclass` — Same reason: inert over all 256 values w.r.t. the carrier output, no ordering observable.
- `mem_fence.b5` — Same reason: inert over all 256 values, no ordering observable.
- `mem_fence8.mask` — **Not dispatchable.** Emitted only by `intersection_query` traversal; `agxrun_persist` cannot bind an acceleration structure. One new corpus fact only: our own compiled ray-query kernel emits `mask = 0x11`, which `db.json` does not list (`analysis/memfence8_locate.json`).
- `mem_fence8.tail` — Same reason: no dispatchable carrier.

## 7. Addendum captures (runs 21 / 22)

Two independent gated runs, **15 005 records each, 0 cases present in only one
run, 0 cascades, 0 hangs, 152/152 health checks, 0 control violations**, and
**2** acceptance disagreements out of 15 005 (both `atdev_operand_pair`
byte+6 = 0x30/0x31, excluded from the claim).

**H7 — `atomic_rmw` shares `atomic_mem`'s field layout. CONFIRMED.**
With byte+1 pinned to `0x11`, each of bytes +2..+13 swept densely yields an
accepted-value set **identical to the corresponding `atomic_mem` arm** — all
twelve bytes, exactly. `atomic_rmw`'s 14 blocking fields are now swept in the
0x11 form itself rather than inherited from a correlation.

**H9 — the atomic operand-register model is PROVEN, not interpolated.**
Arm `atdev_operand_pair` pins byte+5 = `0x80` and sweeps byte+6 densely, which
builds **index 3** for the first time:

| byte+5 | byte+6 | index | counter becomes | consumed register |
|---|---|---|---|---|
| 0x00 | 0x00 | 0 | 7 = `a[0]` | — |
| 0x80 | 0x00 | 1 | 1007 = `a[1]` | `a[1]`'s reader -> 0 |
| 0x00 | 0x01 | 2 | 2007 = `a[2]` | `a[2]`'s reader -> 0 |
| **0x80** | **0x01** | **3** | **3007 = `a[3]`** | **`a[3]`'s reader -> 0** |

`0x41`/`0x81`/`0xC1` behave as `0x01`, so byte+6 bits 6-7 are don't-cares.
**Unexplained residue:** with byte+5 = 0x80, byte+6 = `0x30`/`0x31` restore the
*baseline* operand rather than selecting a high index, and they are the only two
cases in the addendum whose acceptance differed between run 21 and run 22. Those
two values are enough to make the automatic gate label the *joint* byte+5|byte+6
entry `isolated-byte-diff` rather than `hardware-run` — even though the four
index constructions above reproduce byte-identically in both runs. The gate is
left to say that rather than being hand-waved past; the index model is
`hardware-run`-strength at indices 0-3 and the byte pair as a whole is not.

**H10 — `device_store.extmode` is the source register. CONFIRMED as predicted.**
Re-sweeping densely with the stored value in three different registers moves the
accepted set exactly as `extmode >> 1` predicts:

| source register | accepted `extmode` |
|---|---|
| r4 | `{8, 200}` = `{2*4, 2*4 \| 0xC0}` |
| r8 | `{16, 208}` |
| r12 | `{24, 216}` |

So bit 0 is live on the store side (unlike the load side), and bits 6+7
**together** are an accepted alternative form — a modifier, not register bits
(neither bit alone works). The meaning of the `0xC0` form remains unknown; that
it is accepted is now established over three registers.

**H8 — the `dst_lo`/`dst_ext9` rule is *mostly* `ld_format`-independent, and the
pre-registered refuter PARTIALLY FIRED.** The full 512-value 2-D product was
re-run under each of the 21 accepted `ld_format` codes:

| `ld_format` codes | accepted pairs | exact rule |
|---|---:|---|
| 17, 19, 21, 23, 25, 27, 29, 31, 49, 51, 53, 55, 57, 59, 61, 63 (16 codes) | 64 / 512 | `v & 0x181 == 0x081` |
| 3, 7, 9, 13 | 32 / 512 | `v & 0x1C1 == 0x081` — `dst_ext9` bit 6 must also be 0 |
| 39 | 16 / 512 | `v & 0x1E1 == 0x081` — `dst_ext9` bits 5 and 6 must also be 0 |

`dst_lo == 1` holds under **every** one of the 21 formats, and `dst_ext9` bit 0
must be 1 under every one of them. What varies is only **how many of
`dst_ext9`'s upper bits are additionally don't-cares** — the constraint tightens
for the narrow formats. **`dst_lo = 1, dst_ext9 = 1` is valid under all 21**, so
the emitter rule in section 0 stands unchanged; but the claim "bits 1-6 are
don't-care" is true only for the 16-code majority, and this document says so
rather than quietly generalising the r7/`ld_format=17` measurement.

## 8. Appendix — what an emitter can now write, verbatim

Every value below is `hardware-run` on **M4** within the stated range, and each
line's rule is the machine-derived exact mask from `analysis/bitrules.json`.
This is the whole point of the exercise: none of it requires a donor shader.

```text
device_load  (byte0 = 0x67), terminal scalar 32-bit indexed load
  byte+1  space        v & 0x03 == 0x00      device space; bits 2..7 free
  byte+2  addr_mode    ANY                   inert on this shape (256/256)
  byte+3  extmode      2*R, R in 0..63       destination register; bit 0 free
  byte+4  base_slot    per EXP-0083
  byte+5  index_reg    r0..r95; bit 7 IGNORED (128..255 mirror 0..127)
                                             r96..r127 FAULT
  byte+6  access_desc  ANY                   inert (256/256)
  byte+7  reserved7    ANY                   inert (256/256)
  byte+8  ld_format    one of the 21 accepted codes (not a mask rule)
          dst_lo       v & 0x03 == 0x01      MUST be 1
  byte+9  dst_ext9     bit 0 MUST be 1  -- WRITE 1. Upper bits free for 16 of the
                       21 ld_format codes, narrower for 3/7/9/13 and 39
          idx_off      0..2047 (EXP-0082)
  byte+11 ldform_hi11  v & 0x07 == 0x00      bits 0..2 must be 0; 3..5 free
  byte+12 elem_size    one of 48 accepted values
  byte+13 reserved13   ANY                   inert (256/256)

device_store (byte0 = 0xE7)
  byte+1  space        v & 0x02 == 0x00      device space
  byte+2  addr_mode    ALU-sourced data:  ANY (inert)
                       load-forwarded data: v & 0x02 == 0x02   (REQUIRED)
  byte+3  extmode      2*R or (2*R)|0xC0     R = source GPR; bit 0 LIVE, unlike the load
  byte+6  access_desc  ANY                   inert (256/256)
  byte+7  reserved7    ANY                   inert (256/256)
  byte+8  st_format    one of the 84 accepted codes
  byte+9  st_format_ext v & 0x60 == 0x00     bits 5,6 must be 0
  byte+11 st_desc_hi   v & 0x11 == 0x00      bits 0 and 4 must be 0
  byte+12 elem_size    one of 96 accepted values
  byte+13 reserved13   ANY                   inert (256/256)

atomic_mem / atomic_rmw (byte0 = 0x67, byte+1 v & 0x03 == 0x01)
  byte+2  amode        ANY                   inert (256/256)
  byte+3  rsv3         ANY                   inert (256/256)
  byte+4  base_slot    ANY                   inert with one bound target
  byte+5  operand-register index bit 0 (0x80 = +1)
  byte+6  operand-register index bits 1.. (byte bits 6,7 free)
          index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1); proven for 0,1,2,3
  byte+7  ret_flag     0 only
  byte+8  ret_desc     0 or 128
  byte+9  idx_off      v & 0x0E == 0x00
  byte+10 rsv10        0..3 only             LIVE, despite the name
  byte+11 rsv11        0 only                LIVE, despite the name
  byte+12 op word      the op enum; 0x36 = sub verified by value
  byte+13 amode_hi     v & 0x07 == 0x00      (register-operand form)

threadgroup_barrier (0x07 04 54 ...)
  byte+1  sub          v & 0x06 == 0x04
  byte+2               ANY                   inert (256/256)
  byte+3  mem_scope    v & 0x01 == 0x01      bit 0 = execution convergence
  byte+4  flags        ANY                   inert (256/256)
  byte+5  b5           ANY                   inert (256/256)

DO NOT EMIT: atomic_tg byte+5 in 0x7E..0x7F -- reproducible GPU HANG.
```

## 9. Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal), our own hand-assembled AGX
  programs built only through tools/agx-isa isadb.assemble(), and the compiled
  bytes of our own shaders
Apple binary introspection: NONE
Reproduction: README.md section "Reproduction"
Evidence: raw/m4-20260828-run11/sweep.jsonl, raw/m4-20260828-run12/sweep.jsonl,
  raw/m4-20260828-run21/sweep.jsonl, raw/m4-20260828-run22/sweep.jsonl
  (all append-only), plus each run's 00_manifest.json / 00_env.json /
  01_progress.json. raw/m4-20260828-run01 is a RETAINED superseded partial
  capture (see its PARTIAL.md); it is cited by no verdict.
```
