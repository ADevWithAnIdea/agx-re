# Apple9 Device Memory Access Model — Alignment, Bounds, and Robustness

Normative chapter on **device-buffer memory access behavior**: what byte address an
`device`/`constant`-space load, store, or atomic actually touches once its nominal
(requested) byte address is computed, and what happens at and past the end of an
allocation. This is the load/store/SSBO cluster the user has marked top priority
(`docs/P0-P1-CLOSURE.md` P1.5, `APPLE9_RE_IMPLEMENTATION_GAPS.md` MEM-01..MEM-22); it had
no consolidated normative chapter before this one.

Every normative sentence below carries an inline evidence label
(`HW-VALIDATED` / `DATA-TRACE-VALIDATED` / `OWN-SHADER-DIFF` / `STRUCTURAL` / `INFERRED` /
`UNKNOWN`, per `CODEX.md` §9) and cites the exact experiment/artifact it comes from.
**No fact in this chapter is stated without one of these labels and a citation.**

## 0. Scope and target labels — read this before anything else

This chapter draws on two experiments that were run on **two different chips**, and the
labels below are asymmetric. Do not average them into a single "Apple9" claim.

- **§2 (instruction-level addressing recap)** is `HW-VALIDATED` **on Apple A18 Pro / G17P**
  (EXP-0012, corrected by RT-1a-FIX — both A18-native; see `docs/isa/README.md`,
  `### ✅ Memory access family (EXP-0012)`). It is reproduced here as already-published
  baseline documentation; this chapter does not re-derive it or re-run it on M4.
- **§4–§7 (the access-unit / alignment / out-of-allocation / boundary model — the new
  content of this chapter)** is `HW-VALIDATED` **on Apple M4 / G16G only**
  (EXP-0076, promoted commit `446a5f28`). It was **not** run on A18 Pro/G17P: per
  `CLAUDE.md`, the A18 Pro is hands-off for this workstream (never SSH'd, probed, or
  rebooted) and A18 replication is suspended, not a closure gate. Per `CLAUDE.md`'s target
  discipline ("no cross-target promotion without a recorded validation or an explicit
  `INFERRED` label"), **treat every §4–§7 claim as `INFERRED`-by-family for A18 Pro/G17P**
  — plausible because A18/M4 are the same Apple9 generation and every other
  driver-emittable subsystem checked so far is byte-identical across them
  (`CLAUDE.md` "M4 validation... complete"), but **not independently validated** by this
  chapter's evidence, and not a promotion of EXP-0076's M4-only observations to an A18
  fact.
- **§2A (the operand/destination ENCODING rules — added 2026-08-28)** is `HW-VALIDATED`
  **on Apple M4 / G16G only** (EXP-0141), and is labelled **`target: G16G`** throughout. It is
  **not** relabelled G17P and it does not transfer by assumption.
- Consequently §2 rests on A18-native evidence assumed (not re-validated here) to also
  hold on M4, and §2A and §4–§7 rest on M4-native evidence assumed (not re-validated here) to
  also hold on A18. Both assumptions are Apple9-family inferences, not independent
  measurements; neither direction is re-derived in this chapter. **§2A.5 records a live
  counterexample to blanket family equality** (`tg_addr_compute`: M4 accepts byte0 `0x1c`,
  A18's `0xfc` does not reproduce), so treat cross-target transfer as a hypothesis, not a
  default.

### 0.1 Current target rule (updated 2026-08-28)

All live testing has moved to the **A18 Pro / G17P**, which is now both the documentation target
and the test target, and **closure is measured against full G17P** (`CODEX.md`, "Target
discipline"; user directive 2026-08-28). Local M4 GPU testing is retired. Every fact in this
chapter that is labelled `target: G16G` was measured on the M4 and **remains valid on its own
target** — nothing here is retracted by the pivot. **G17P revalidation is under way
(`EXP-0153`).** Cross-target promotion requires a recorded validation or an explicit `INFERRED`
label; a silent relabel is a defect.

## 1. What this chapter covers and does not cover

**Covers:** the addressing model for `device_load`/`device_store`/atomic-RMW instructions
(§2); the **operand and destination register encoding rules an emitter must fill** for those
same instructions (§2A — `target: G16G`); the access-unit decomposition and per-unit alignment-rounding rule for device-buffer
accesses (§4); the compiler consequence for unaligned NIR buffer access (§5);
out-of-allocation and boundary-straddling read/write/atomic-exchange behavior (§6); **the bounds
of that zero-fill model, the exact `2^43` address wraparound, and the VM/allocator conventions
(§6A — `target: G16G`)**; the constraint this places on synthesizing a Vulkan-style
bounded/robust buffer load (§7).

**Does not cover** (see §8 for the open-item list *and* for the rows that have since been
ANSWERED elsewhere and are summarized there): the numeric offset/scaling questions
MEM-01..MEM-04; the physical mechanism behind the observed bound (MEM-11); the USC
preload-file question (MEM-19). *(MEM-05 is now `PARTIAL`; MEM-13/14, MEM-15..17 and
MEM-20..22 are ANSWERED — see §8. MEM-18 is `PARTIAL`.)* Also not covered: threadgroup-memory
bounds; texture/sampler descriptor bounds (see
`docs/descriptors/README.md`, a separate subsystem); vertex/fragment-stage memory access;
allocation sizes other than 64 bytes; offsets beyond 1088 bytes past the allocation; and any
Linux/UAPI-side behavior.

## 2. Addressing-model recap (instruction level) — A18/G17P, HW-VALIDATED (EXP-0012, RT-1a-FIX)

Reproduced from `docs/isa/README.md` (`### ✅ Memory access family (EXP-0012)`) for
context; this chapter adds nothing to this section and does not re-validate it.

Device, threadgroup, and constant loads/stores share one 14-byte opcode pair: `0x67`
(load) / `0xe7` (store). `HW-VALIDATED`, EXP-0012 (splice-and-observe, 6 HW validations)
+ RT-1a-FIX (HW-re-validated correction of the index-register and offset-field bytes).

- **Effective element address = `(index_GPR + idx_off) × element_size`.** `index_GPR` is
  the GPR at byte+5 (RT-1a-corrected — an earlier reading placed it at byte+1); `idx_off`
  is an in-instruction additive immediate element-offset at byte+9 bit7 / byte+10 /
  byte+11; `element_size` is decoded from byte+12 (`0x42`=1 B, `0x44`=2 B, `0x46`=4 B,
  `0x48`=8 B). `HW-VALIDATED`, docs/isa/README.md memory-access-family table + RT-1a-FIX
  note.
- **The compiler observed by EXP-0012 leaves `idx_off` = 0** and instead computes
  `a[i+k]`/`a[i*s]` with a prior integer ALU op on the index register, in element units —
  so `a[gid+1]`, `a[gid+2]`, `a[gid+4]` all share a byte-identical `0x67` load in the
  corpus EXP-0012 examined. The hardware offset field itself exists and is
  independently HW-validated to work (RT-1a-FIX splice), but Apple's compiler was not
  observed to use it in this corpus. `HW-VALIDATED` (field exists and works) /
  `OWN-SHADER-DIFF` (compiler's observed non-use is a corpus observation, not a
  hardware limit) — EXP-0012 §"Addressing model", docs/isa/README.md.
- **base_slot (byte+4)** selects the preloaded buffer-base uniform slot (0 = buf0, 1 =
  buf1, …); the same mechanism serves `device` and `constant` address spaces — a
  `constant T*` array index compiles to a byte-identical `0x67` load, splice-confirmed by
  zeroing base_slot. `HW-VALIDATED`, EXP-0012 (M6). Threadgroup memory uses the same
  opcodes with byte+1 bit1 set and base_slot `0x08` (a local descriptor, not a buffer
  base). `HW-VALIDATED`, EXP-0012 (M5).
- **Vector width (word count) is byte+5's low bits** (RT-1a: byte+5 is actually the index
  register, not count — see docs/isa/README.md for the corrected byte map); a `float4`
  access moves 4 words with one instruction. `HW-VALIDATED`, EXP-0012 (M4).
- **Sign extension for signed sub-32-bit loads is a following ALU shift, not an in-load
  flag**; unsigned sub-32-bit loads use a zero-extend load variant (byte+3 bit1).
  `HW-VALIDATED`, EXP-0012 (M3).

This section establishes **where** the effective byte address comes from (which GPR,
which immediate offset, which buffer-base slot, which element size) and confirms it is
the same encoding across device/constant space. It says nothing about what happens once
that byte address is unaligned or falls outside the bound allocation — that is §4–§7,
established on a different chip by a different experiment, and the two are not yet
correlated to each other (see MEM-11 in §8: whether the §4–§7 behavior is enforced by
this instruction's own hardware, a separate descriptor bound, or allocator zero-fill is
**not established**).

## 2A. Operand and destination ENCODING rules — `target: G16G`, `HW-VALIDATED` (EXP-0141)

§2 says **where the effective address comes from**. This section says **which register fields an
emitter must fill, and with what**, so that a `device_load` / `device_store` / atomic can be
*generated* rather than copied out of a compiled template. It is the section that took
`device_load`, `device_store` and `threadgroup_barrier` from "decodable" to **emittable**
(emitter-grade fields 246 → 288 at that point in the wave).

**Evidence:** `HW-VALIDATED` — exhaustive splice sweeps, ~71,000 GPU measurements, four gated
runs, `experiments/EXP-0141-m4-emit-mem/` (`RESULTS.md`, `analysis/field_verdicts.json`,
`raw/m4-20260828-run11`, `run12`, `run21`, `run22`). The `extmode` boundary and the
`dst_lo`/`dst_ext9` constraints were re-verified by the orchestrator directly from
`raw/m4-20260828-run11/sweep.jsonl`.
**Target:** **M4 / G16G** — `target: G16G`. Not measured on G17P; see §0.

### 2A.1 `device_load` destination register — the rule

> **`dst_lo` and `dst_ext9` carry NO register information.**
>
> ```
> to land a load in register R:
>     extmode        = 2 * R      # byte+3; bit 0 is a DON'T CARE
>     dst_lo         = 1          # exact
>     dst_ext9 bit 0 = 1          # upper bits ld_format-dependent, see below
> ```
>
> That is **three constrained bits** out of the nine those two fields span.

- **Exact tested range and the bound it establishes:** `extmode` values **0..127 all match and
  128..255 all fail**. Therefore **`R` is reachable only for `R = 0..63`; `R ≥ 64` silently
  zeroes through this field** and must be reached by another mechanism. This is a *silent*
  failure — no fault, no status change.
- Identical at target registers **r3, r7, r20, r33**, and under **all 21 working `ld_format`
  codes**.
- **Pre-registered refuter partially fired, and the result is stated rather than smoothed:** how
  many of `dst_ext9`'s **upper** bits are additionally don't-cares is **`ld_format`-dependent**
  (free for 16 codes, tighter for codes 3, 7, 9, 13 and 39). **`dst_ext9 = 1` is valid under all
  21**, so emit that.
- **Safe driver fallback:** emit `extmode = 2·R`, `dst_lo = 1`, `dst_ext9 = 1`, and allocate
  load destinations only in `r0..r63`.

**Retraction chain this supersedes — preserved so a reader can audit it:**

| claim | status |
|---|---|
| `EXP-M4-13`: `dst = dst_lo \| (dst_ext9 << 2)` | **RETRACTED by EXP-0101.** A byte-pattern correlation promoted as if executed; it predicts the wrong register. It was used by every prior experiment and by `tools/agx-isa/db.json`. |
| `EXP-0101`: `extmode = 2 × target_register`, with `dst_lo`/`dst_ext9` "copied verbatim from a compiler-observed value" | **SUPERSEDED (not refuted) by EXP-0141**, which turns the copy-verbatim instruction into a rule and adds two facts EXP-0101 could not reach: `extmode` bit 0 is free, and `R ≥ 64` is unreachable. |
| `EXP-0112`: target register aliases `r(R mod 64)` for `R ∈ [64,112]` | **Does not generalize.** EXP-0139 tested the same aliasing on `iadd2.dst` and it **did not transfer** (at `dst = 140/141`, register 70, the sum never appeared in r6). Treat `r(R mod 64)` as a `device_load`-specific observation only. |

### 2A.2 The atomic RMW operand register is ENCODED, not implicit

`tools/agx-isa/db.json` described the operand as "implicit (supplied by the preceding op /
amode)", and `DOC-02` ranked it a **MISSING** field. It is neither.

> **`index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1)`** — the RMW operand register is carried in
> **byte+5 bit 7** plus **byte+6 bits 0..5**.

- **Tested range:** all four constructible indices, each with the redirected register actually
  consumed (`0 → a[0] = 7`, `1 → a[1] = 1007`, `2 → a[2] = 2007`, `3 → a[3] = 3007`),
  byte-identical in both gated runs.
- The carrier used a **uniform address**, which the old per-lane `index_reg` reading of
  byte+5/+6 cannot explain — that is what makes the data role, rather than an address role, the
  supported interpretation.
- **The redirected register is RELEASED** — a later reader gets **0** — the same
  register-lifetime contract EXP-0086 / EXP-0089 / EXP-0099 document for the ALU families (see
  [`register-move-and-liveness.md`](register-move-and-liveness.md)).
- **Scope limit:** the **address** role of byte+5/+6 is **not excluded** for the per-lane form;
  the **data** role is proven for the uniform form.

Applies to both `atomic_rmw` (byte+1 == `0x11`) and `atomic_mem` (byte+1 == `0x01`).

### 2A.3 `device_store` byte+2 bit 1 is a DATA-SOURCE SELECTOR

> **clear = ALU-computed data · set = direct live load-result.**

- It is **inert when the data is ALU-computed** — 256/256 pass — which is exactly the
  configuration EXP-0119 measured and correctly reported as inert at the time.
- It is **REQUIRED when the source is a forwarded load.** An emitter that copies the
  ALU-computed encoding into a load-forwarding store gets the wrong data with no fault.
- `extmode` on the store side is `2*R` or `2*R | 0xC0`, proven over three registers.

### 2A.4 `rsv*` bytes that are not reserved

**Five `rsv*` bytes in `atomic_mem` / `atomic_tg` are live and heavily constrained, not
padding** — only a handful of the 256 values work in each. **An emitter must not write arbitrary
values there.**

### 2A.5 What EXP-0141 did NOT move, and why — `UNKNOWN`

Stated so silence is not read as a guarantee:

| field(s) | reason it stays `untested` |
|---|---|
| `mem_fence` ×3, `dev_scoreboard_fence.scope_flag` | the carriers have **no ordering observable**, so a pass proves nothing |
| `mem_fence8` ×2 | no dispatchable carrier |
| `atomic_tg.op_desc` | stopped by the hang budget |

> **⚠️ A fresh G17P↔G16G divergence, reported and not resolved.** `tg_addr_compute`'s emittable
> veto **stands on new grounds**: on **M4/G16G only byte0 `0x1c` works**, and **EXP-M4-14's
> A18/G17P `0xfc` does NOT reproduce**. Do not assume Apple9 family equality for this
> instruction; it is a live counterexample to blanket cross-target promotion.

### 2A.6 Reproduction hazards (relevant to anyone re-running this)

- **A third contamination mode exists: `STATUS OK` with nothing executed.** Its output is
  zero-initialised — which on this ISA is *also* the expected signature of a wrong field value,
  so the two are indistinguishable without a control. It corrupted EXP-0141's own baseline
  during smoke and was mitigated with an integrity sentinel written through a path independent
  of the instruction under test.
- **Reusing one splice-archive path across persistent-runner requests gives ~8 % phantom
  `CMDBUF_ERROR`** (28/360, versus 0/360 with a unique path per request).

## 3. Test configuration for §4–§7 (EXP-0076)

All of §4–§7 comes from one experiment, `experiments/EXP-0076-m4-buffer-robustness-matrix/`
(promoted, commit `446a5f28`), two independent runs (`raw/m4-20260827-run01`,
`raw/m4-20260827-run02`) whose `04_results.jsonl` are byte-identical:

- Target: one Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4, runtime
  `newLibraryWithSource:` compile, `fastMathEnabled = NO`, `mathMode = MTLMathModeSafe`.
- Subject: a 64-byte **owned**, exact-length `MTLBuffer` (shared storage), CPU-filled with
  `F(i) = (0xA5 + 0x1B·i) mod 256`, bracketed by 256-byte guard allocations (`0x5A` before,
  `0xC3` after), plus a guarded 32-byte result buffer; guards checked after every case.
- Access idioms: frozen MSL pointer casts (`*(device uint *)p`-style loads/stores) and one
  32-bit relaxed atomic exchange, with the byte offset read at runtime from a device `uint`
  uniform so the compiler cannot specialize/constant-fold the address.
- Matrix: widths 8/16/32/64/128 bits; offset classes `align_in`, `mis1` (misaligned by 1
  byte, offset 33), `mishalf` (misaligned by `width_bytes/2 − 1` bytes — offset 35 at
  64-bit, offset 39 at 128-bit; only defined where this differs from `mis1`), `last`
  (last full in-bounds element), `oob1` (first fully
  out-of-allocation element, offset 64), `far` (offset 1088, +1 KiB past the end),
  `straddle_c` (read/write starts in-bounds and crosses the end by `c = 1..W-1` bytes).
  106 cases/run (52 loads, 52 stores, 2 atomic-exchange stretch cases). Every case:
  status `ok`, no `cb_error`, no `watchdog`, no `proc_fail`/`proc_timeout`, in both runs.
- `HW-VALIDATED`, EXP-0076 RESULTS.md "OBSERVED" + "Exact tested range".

**Explicitly not tested by EXP-0076** (do not extrapolate past this): any offset beyond
1088; negative offsets; offsets ≥ 2^32; allocation sizes other than 64 bytes; buffers
placed adjacent to the guard allocations by explicit control (the guards' relative
placement was chosen by the driver, not by the test); `fastMathEnabled = YES`; 64-bit
atomics; vertex/fragment stages; concurrent accesses; any Linux/UAPI path; any A18
hardware. `STRUCTURAL` (scope statement), EXP-0076 RESULTS.md "Not tested (explicitly)".

## 4. The access-unit model (M4/G16G) — `HW-VALIDATED`, EXP-0076

### 4.1 The rule

Every device-buffer load, store, or atomic access through the tested idioms executes as
one or more independent, naturally-aligned **units**, and **each unit's effective address
is the requested address rounded DOWN to that unit's natural alignment** — not the
requested address itself:

| access width | # units | unit size | per-unit effective address |
|---|---|---|---|
| 8-bit | 1 | 1 byte | `addr` (1-byte alignment is unconditional — see note below) |
| 16-bit | 1 | 2 bytes | `⌊addr / 2⌋ × 2` |
| 32-bit | 1 | 4 bytes | `⌊addr / 4⌋ × 4` |
| 64-bit | 2 | 4 bytes each | unit `i` (i=0,1): `⌊(addr + 4·i) / 4⌋ × 4` |
| 128-bit | 4 | 4 bytes each | unit `i` (i=0..3): `⌊(addr + 4·i) / 4⌋ × 4` |

64-bit and 128-bit accesses are **not** rounded down as one wide block; each constituent
32-bit unit is rounded down **independently**. `HW-VALIDATED` — this single model was
validated against **108/108 load-side and 108/108 store-side observations across both
runs (212 case records), zero exceptions**, including all 26 boundary-straddling reads and
all 26 straddling stores (EXP-0076 RESULTS.md "INTERPRETED"). Nothing faulted anywhere in
the matrix; no load mutated the buffer; no store touched a byte outside its own aligned-down
window (EXP-0076 RESULTS.md "OBSERVED").

At **8-bit width the unit is 1 byte, so `⌊addr/1⌋×1 = addr` always** — misalignment is not
a meaningful state at 1-byte granularity, and accordingly the tested matrix contains no
8-bit "misaligned" case (only `align_in`/`last`, both byte-exact). This is a direct
arithmetic consequence of the validated model, not a separately probed case.
`HW-VALIDATED` (model) / `STRUCTURAL` (this specific corollary), EXP-0076.

A load unit whose rounded-down window lies entirely inside the allocation returns exactly
those bytes; a unit whose rounded-down window begins at or past the allocation end returns
zero (§6.1). A store unit whose window lies entirely inside the allocation writes exactly
the given bits; a unit at or past the end is discarded (§6.2). `HW-VALIDATED`, EXP-0076
RESULTS.md "INTERPRETED".

### 4.2 Worked examples (verbatim observations, `HW-VALIDATED`, EXP-0076 RESULTS.md "MEM-06"/"MEM-07")

Fill pattern in the 64-byte allocation: `F(i) = (0xA5 + 0x1B·i) mod 256`; e.g.
`F(32..39) = 05 20 3b 56 71 8c a7 c2`, `F(60..63) = f9 14 2f 4a`.

| case | width | requested offset | per-unit effective address(es) | bytes actually returned | equals bytes at |
|---|---:|---:|---|---|---|
| `load_w16_mis1` | 16-bit | 33 | `⌊33/2⌋×2 = 32` | `0520` | 32..33 |
| `load_w32_mis1` | 32-bit | 33 | `⌊33/4⌋×4 = 32` | `05203b56` | 32..35 |
| `load_w64_mis1` | 64-bit | 33 | unit0 `⌊33/4⌋×4=32`, unit1 `⌊37/4⌋×4=36` | `05203b56718ca7c2` | 32..39 |
| `load_w64_mishalf` | 64-bit | 35 | unit0 `⌊35/4⌋×4=32`, unit1 `⌊39/4⌋×4=36` | `05203b56718ca7c2` (identical to `mis1`) | 32..39 |
| `load_w128_mis1` | 128-bit | 33 | units at `⌊33/4⌋,⌊37/4⌋,⌊41/4⌋,⌊45/4⌋ ×4 = 32,36,40,44` | `05203b56718ca7c2ddf8132e49647f9a` | 32..47 |
| **`load_w128_mishalf`** | **128-bit** | **39** | units at `⌊39/4⌋,⌊43/4⌋,⌊47/4⌋,⌊51/4⌋ ×4 = 36,40,44,48` | `718ca7c2ddf8132e49647f9ab5d0eb06` | **36..51** |

The `load_w128_mishalf@39` row is the **decisive case**: a single 128-bit-granularity
align-down of the whole access would round the *start* address down to 32 and return
bytes 32..47. That is not what was observed. What was observed — bytes **36..51** — is
exactly what four *independent* 32-bit units at nominal offsets 39/43/47/51, each rounded
down to its own 4-byte boundary (36/40/44/48), produce. This single case rules out a
monolithic wide-access align-down model and requires the per-32-bit-unit model of §4.1.
`HW-VALIDATED`, EXP-0076 RESULTS.md "MEM-06" (row and surrounding text explicitly labeled
"decisive").

Stores mirror loads exactly: `store_w128_mishalf@39` writes bytes 36..51 and no others,
and every other in-bounds store case's changed-byte set matches the load-side effective
address(es) in the table above (EXP-0076 RESULTS.md "MEM-07"). The stored *bit values*
were separately verified byte-for-byte against the exact 32-bit words the harness
uploaded (not against the originally-intended byte image — a harness value-encoding slip
documented in EXP-0076 RESULTS.md "Errata", which the source explicitly states "does not
affect any conclusion" about width, addressing, or adjacency). `HW-VALIDATED`, EXP-0076
RESULTS.md "MEM-07".

All **aligned** and **last-element** cases at every tested width (10/10) were byte-exact
against the fill-derived expectation, in both runs. `HW-VALIDATED`, EXP-0076 RESULTS.md
"MEM-06"/"OBSERVED".

## 5. Alignment rules and the NIR/compiler consequence

**Unaligned device accesses through this path never fault and never corrupt a
neighboring byte, but they are not byte-exact: the bytes returned/written are those of the
aligned-down unit window(s), not the bytes at the requested offset**, for every tested
width (16/32/64/128-bit; see the 8-bit note in §4.1) and every tested misalignment
(1 byte, and `width_bytes/2 − 1` bytes). `HW-VALIDATED`, EXP-0076 RESULTS.md
"MEM-06"/"MEM-07" required-response blocks.

**Compiler consequence (stated directly in the source, reproduced here as the load-bearing
negative result for a compiler):** treat unaligned `nir_load_global`/`nir_store_global` as
**NOT byte-exact** on this path. Either the frontend must guarantee alignment, or the
compiler must **lower unaligned device accesses to a decomposition** (e.g. per-byte loads,
or an explicitly masked/shifted access sequence) rather than emitting a monolithic
unaligned device load/store and expecting the bytes at the given offset. This holds for
both loads and stores; the compiler must handle misalignment uniformly for both.
`HW-VALIDATED` (direct restatement of the RESULTS.md "Driver/compiler consequence" text,
itself a direct logical corollary of the access-unit model above — no new empirical claim),
EXP-0076 RESULTS.md "MEM-06"/"MEM-07" required-response blocks.

Note what this does **not** say: it does not identify *why* the hardware behaves this
way (compiler-emitted address masking upstream of the memory unit vs. a genuine
hardware/TLU alignment-rounding behavior is not distinguished by this evidence — see
MEM-11 in §8), and it does not bound the misalignment amounts beyond what was tested
(1 byte and `width_bytes/2 − 1` bytes, on a 64-byte allocation). `STRUCTURAL` (scope
caveat), EXP-0076 RESULTS.md "INTERPRETED".

## 6. Out-of-allocation and boundary-crossing behavior — `HW-VALIDATED`, EXP-0076

### 6.1 Out-of-allocation reads (MEM-08 = Yes)

Every read whose (aligned-down) unit window starts at or past the end of the 64-byte
allocation returns **all-zero bytes**, at every tested width and at both tested distances
— the first fully out-of-allocation element (offset 64) and +1 KiB past the end (offset
1088): `load_w8_oob1`→`00`, `load_w16_oob1`→`0000`, `load_w32_oob1`→`00000000`,
`load_w64_oob1`→`0000000000000000`,
`load_w128_oob1`→`00000000000000000000000000000000`, and identically for all five `*_far`
cases at offset 1088. 10/10 cases, no fault, no command-buffer error, byte-identical in
both runs. `HW-VALIDATED`, EXP-0076 RESULTS.md "MEM-08" + `analysis.json`
`hypotheses.H3_MEM08_oob_reads_zero`.

Tested distances only span offsets 64..79 (via the five widths) and offset 1088;
distances between roughly 80 and 1088, distances beyond 1088, and negative offsets are
untested — do not assume the zero-fill region is unbounded. `STRUCTURAL` (scope caveat),
EXP-0076 RESULTS.md "MEM-08" required-response block.

### 6.2 Out-of-allocation stores (MEM-10 = Yes)

Every store whose (aligned-down) unit window lies entirely at or past the allocation end
is **discarded**: the 64-byte allocation is byte-identical to its pre-store state, both
256-byte guard allocations are unchanged, both result-buffer guards are unchanged,
command-buffer status is `ok`, and there is no fault — at every tested width and both
tested distances (offset 64, +1 KiB). 10/10 cases. `HW-VALIDATED`, EXP-0076 RESULTS.md
"MEM-10" + `analysis.json` `hypotheses.H5_MEM10_oob_stores_discarded`.

Guard non-corruption is **placement-dependent evidence, not proof of allocation
isolation**: the guard allocations are separate `MTLBuffer`s whose placement relative to
the case buffer was chosen by the driver and was not directly observable through the
public API. `STRUCTURAL` (explicit caveat carried from the source), EXP-0076 RESULTS.md
"MEM-10" required-response block.

### 6.3 Out-of-allocation atomic exchange

A 32-bit relaxed atomic exchange at the first fully out-of-allocation offset
(`axch_w32_oob1@64`) reads the pre-exchange value as `00000000`; the allocation and both
guard allocations are unchanged; no fault. The in-bounds control
(`axch_w32_align_in@32`) exchanges out exactly the fill bytes at 32..35 as a little-endian
word and writes the new word to exactly bytes 32..35, no other byte changed.
`HW-VALIDATED`, EXP-0076 RESULTS.md "Atomic exchange stretch". This is a 2-case stretch
addition (one in-bounds control, one OOB case, 32-bit width only) — not a swept matrix;
64-bit atomics, other widths, and other offsets are untested. `STRUCTURAL` (scope
caveat), EXP-0076 RESULTS.md "Exact tested range".

### 6.4 Boundary-straddling accesses (MEM-09 = No — the pre-registered mix model is refuted)

For a read/write that **starts in-bounds and crosses the allocation end** (26 cases per
run, every crossing amount `c = 1..W-1` bytes at 16/32/64/128-bit): the result is **not**
"in-bounds bytes at the start offset, plus a zero tail from the crossing point" (the
pre-registered per-component mix model, `H4`, **refuted**, 22/26 cases divergent from it).
The actual rule is simply §4.1's per-unit align-down rule applied first, with each
resulting unit then independently classified in- or out-of-allocation: a unit whose
rounded-down window lies fully inside `[0, 64)` reads/writes its exact bytes; a unit whose
rounded-down window starts at or past byte 64 reads zero (for loads) or is discarded (for
stores). Because both the 4-byte unit windows and the 64-byte allocation boundary are
4-byte-aligned, no unit's window ever straddles the boundary itself — every unit is wholly
in-bounds or wholly out-of-bounds. `HW-VALIDATED`, EXP-0076 RESULTS.md "MEM-09"/"MEM-10".

Worked examples (fill: `F(60)=f9, F(61)=14, F(62)=2f, F(63)=4a`; allocation is bytes
`[0,64)`):

| case | offset | units (nominal → aligned-down) | in/out per unit | observed |
|---|---:|---|---|---|
| `load_w32_straddle_1` | 61 | 61→60 | in (60+4=64≤64) | `f9142f4a` |
| `load_w64_straddle_5` | 61 | 61→60, 65→64 | in, **out** (64≥64) | `f9142f4a` + `00000000` = `f9142f4a00000000` |
| `load_w128_straddle_5` | 53 | 53→52, 57→56, 61→60, 65→64 | in, in, in, **out** | `213c57728da8c3def9142f4a` + `00000000` |
| `load_w64_straddle_4` | 60 | 60→60, 64→64 | in, **out** | `f9142f4a` + `00000000` — start is already 4-aligned, so the aligned-down window equals the requested window and the mix model happens to coincide here (this is the source of the 4/26 non-divergent cases) |

26/26 straddling reads and 26/26 straddling stores match this compound rule in both runs,
zero exceptions. Store-side example: `store_w32_straddle_3@63` writes bytes 60..63 only
(the single in-bounds unit); `store_w128_straddle_15@63` likewise writes bytes 60..63 only
(three of its four units are out-of-bounds and discarded). `HW-VALIDATED`, EXP-0076
RESULTS.md "MEM-09"/"MEM-10".

### 6.5 Determinism

Every result in §6 is deterministic: the two independent runs' 106-case result files
(`raw/m4-20260827-run01/04_results.jsonl`, `raw/m4-20260827-run02/04_results.jsonl`) are
byte-identical, including every out-of-allocation and straddling value. `HW-VALIDATED`,
EXP-0076 RESULTS.md "OBSERVED".

### 6.6 What §6 does not establish

The zero-read / discard-write behavior is **consistent with** a hardware bound/clamp
mechanism, zero-filled slack in the driver's sub-allocation, or per-access address
masking — public-Metal behavioral evidence **cannot distinguish these**, and this chapter
does not claim any of them specifically (see MEM-11, §8). `STRUCTURAL` (explicit
non-claim), EXP-0076 RESULTS.md "INTERPRETED".

## 6A. Address wraparound, and the LIMITS of the zero-fill model — `target: G16G`, `HW-VALIDATED` (EXP-0122)

§6 establishes that out-of-allocation accesses in the tested window read zero. **§6A bounds that
statement, and it bounds it in a way a robustness implementation must respect.** Evidence:
`HW-VALIDATED`, public-API only (no private VM interface inspected),
`experiments/EXP-0122-m4-sparse-vm-conventions/RESULTS.md`, commit `f2b8ef66`; two runs with
**0 mismatches across all 87 `ok` cases** in 11 domains; 74 guard cases with **0 hangs, 0 faults,
0 command-buffer errors**, and **no OOB store corrupted an adjacent allocation** in the tested
offset set. `target: G16G` (local Apple M4, macOS 26.6.2/25G82).

### 6A.1 "OOB reads zero" is NOT page-wide — the zero region is bounded

EXP-0076's near-boundary results replicate exactly under an independently authored harness
(offset 32 → `05203b56`; 60 → `f9142f4a`; 64 → `00000000`; 1088 → `00000000`). But sweeping
further **falsifies both a "guard page around the allocation" model and an "everything unmapped
reads zero" model**:

| offset past a 64-byte allocation | observed (32-bit LE) | zero? |
|---|---|---|
| 4096 | `00000000` | yes |
| 16384 − 256 | `d166d8b1` | **no** |
| 16384 − 4 | `09000000` | **no** |
| **16384** (one sparse tile / platform quantum) | `0cda71aa` | **no** |
| 16384 + 4 | `09000000` | **no** |
| 16384 + 256 | `39ada2a3` | **no** |
| 32768 | `00000000` | yes |
| 1 MiB · 16 MiB · 256 MiB · 4 GiB · 64 GiB · 1 TiB · 4 TiB | `00000000` (all) | yes |

At exactly one platform quantum (**16384 B**, also this device's default sparse tile size) and
its immediate ±256 B neighbourhood, reads return **live, non-zero data** — and demonstrably not
our own fill bytes (`0x5A`/`0xC3`), so not the harness's guard buffers. The reading: most address
space near a small, lightly loaded process's live allocations *happens* to be unmapped
(soft-fault-to-zero, as EXP-0076 found), **but this is not a guarantee** — some nearby addresses
are genuinely backed by other live, driver-owned data whose owner this experiment cannot identify.

> **Driver implication:** never assume address space adjacent to (but outside) an owned
> allocation is safe or zero without an explicit bounds check. The zero-fill behaviour is real
> and reproducible at the tested small and very-large distances; it is **not** a property of
> "outside the allocation" in general. This directly constrains §7's robustness synthesis.

### 6A.2 The address space wraps with period EXACTLY `2^43` bytes

For the idiom `(device uchar*)base + (uint64_t)off` — a `device`-space pointer plus a
runtime-uniform byte offset, compiled from our own MSL — the effective address **wraps with
period exactly `2^43` bytes (8192 GiB)**, after which the 32-bit access is aligned down to the
nearest 4-byte boundary (consistent with §4's per-unit align-down model).

**All 12 discriminating cases matched the `(base + off) mod 2^43`, align-down-4 model exactly, in
both runs**, including the two designed to exclude competing periods:

| case | offset | observed | model prediction |
|---|---|---|---|
| `p43_minus_4` | `2^43 − 4` | `5a5a5a5a` | `base − 4` → inside `guard1` (all `0x5A`) ✓ |
| `p43_exact` | `2^43` | `a5c0dbf6` | `base + 0` → `main[0..3]` ✓ |
| `p43_plus_60` | `2^43 + 60` | `f9142f4a` | `base + 60` → matches the in-bounds control ✓ |
| `p43_plus_64` | `2^43 + 64` | `00000000` | `base + 64` → matches the OOB control ✓ |
| `p43x1p5` | `1.5 × 2^43` | `00000000` (far) | **rules out period `2^42`** ✓ |
| `p43x5_plus_4` | `5 × 2^43 + 4` | `112c4762` | **rules out any period larger than `2^43`** ✓ |
| `p45_plus_32` | `2^45 + 32` | `05203b56` | `base + 32` ✓ |
| `neg256` | `2^64 − 256` | `5a5a5a5a` | `guard1`'s first byte ✓ |
| `neg257` | `2^64 − 257` | `00000000` | 1 B before `guard1` → unmapped ✓ |
| `neg2p43` | `2^64 − 2^43` | `a5c0dbf6` | `base + 0` ✓ |

The model correctly predicts landing **inside a real, independently verifiable allocation**
(`guard1`) three separate times from three different large offsets — so this is not a
coincidence fit.

**Alternatives explicitly NOT excluded** (pre-registered as confounders): the `2^43` period could
reflect (a) the GPU's actual hardware VA bus width, (b) a 43-bit-wide addressing-instruction
operand specific to this load encoding, or (c) a firmware/driver-level address-space window. This
experiment establishes the **observed effective behaviour of this addressing idiom** and nothing
more. **Untested:** whether other access widths (8/16/64/128-bit) or other idioms (texture
addressing, argument-buffer-indirect pointers) share the same period.

### 6A.3 VM/allocator conventions a driver must respect — `target: G16G`

| fact | value | scope actually tested |
|---|---|---|
| **Minimum buffer placement alignment** | **256 bytes, uniformly** — *not* the 16 KiB sparse-tile/page granularity one might guess | `heapBufferSizeAndAlignWithLength:` over 31 lengths `1..65537` × {shared, private} = 62 rows, **all returning 256**; a real allocation succeeded for all 62. Untested above 65537 B. |
| **`maxBufferLength` is an EXACT, off-by-one-tested ceiling** | `9534832640` B (≈8.882 GiB) on this M4 — identical for shared and private | `max − 1` OK, `max` **OK**, `max + 1` **fails**, `max + 256` fails, `1 << 40` fails. **No slack.** |
| **Address assignment within one process** | a deterministic **bump allocator with immediate address reuse on free** — allocating, releasing and re-allocating the identical 6-buffer sequence returns byte-identical GPU addresses on all 3 passes. Consecutive same-size allocations pack back-to-back with no slack beyond the 256 B alignment. | one process, one ordered sequence, 3 passes. **Not** tested across processes or under concurrent allocation pressure, and **not** an architectural guarantee — an observed allocator behaviour. |

> ⚠️ **`maxBufferLength` is device-capacity-specific — query it, never hard-code it.** The A18/G17P
> value is unqueried (the device was hands-off for this experiment).

**`vm_start` and the kernel-reserved-region boundaries remain `UNKNOWN`.** The lowest address
observed across all domains was `0x10000018000` (= `2^40 + 0x18000`), suggestively close to a
round `2^40` base, but this experiment never drove allocation volume high enough — nor probed low
enough — to bound where the userspace-visible window actually starts or ends. That is an
allocator property, and it is **distinct from** the addressing-instruction wraparound at `2^43`
in §6A.2, which is much better evidenced.

## 7. Robust-buffer-access synthesis constraint (MEM-12 input)

The observed native behavior already matches the Vulkan `robustBufferAccess` /
NIR `load_global_bounded` requirement for **fully out-of-bounds** components: zero on
read, discard on write, no fault (§6.1, §6.2). It does **not** hand an implementer
byte-exact robust semantics for free, because of two gaps both rooted in §4's per-unit
align-down:

1. **Misaligned in-bounds starts are not byte-exact** (§4, §5): the plain native path
   returns/writes the aligned-down window's bytes, not the requested bytes, even though
   every touched byte is fully in-bounds.
2. **Boundary-straddling in-bounds units are not byte-exact either** (§6.4): a straddling
   access's in-bounds portion is also subject to the align-down rule, not returned as the
   literal bytes at the requested start offset.

**Synthesis constraint (stated directly in the source):** a `load_global_bounded`-style
lowering must **clamp/select the intended BYTE address per vector component before the
compiler's (or hardware's) unit decomposition acts on it** — not rely on the native
OOB=zero/discard behavior alone and not clamp after decomposition. Clamping only at the
whole-access level, or relying on the native path's zero-fill for anything other than
fully-out-of-bounds units, will reproduce the align-down artifacts of §4/§6.4 instead of
exact robust-buffer semantics. `HW-VALIDATED` (the underlying per-unit facts) /
direct compiler-consequence restatement of EXP-0076 RESULTS.md "MEM-09"/"MEM-11-adjacent"
required-response blocks ("the clamp must be computed on the byte address before any unit
decomposition the compiler performs" / "the clamp must operate on byte addresses per
component before the compiler's unit decomposition").

This is a **constraint on the synthesis**, not a synthesis itself: EXP-0076 supplies the
per-unit alignment/OOB facts a `load_global_bounded` lowering must satisfy; it does not
implement or hardware-validate a complete lowering. `STRUCTURAL` (scope statement),
EXP-0076 RESULTS.md "MEM-11-adjacent / MEM-12-input" required-response block.

## 8. What is NOT yet established — do not read silence as a guarantee

The following MEM-* items from `APPLE9_RE_IMPLEMENTATION_GAPS.md` were open when this
chapter was written. **Several have since been ANSWERED and are marked so inline (2026-08-28
update) — those rows now carry real, citable evidence and are no longer gaps.** The remaining
rows stay open; where the named successor experiment is *quarantined*, its observations are
non-evidence and are not relied upon anywhere above.

**Every answered row below is `target: G16G`** and is not promoted to G17P (see §0.1).

| item(s) | question | status | pursuing experiment (non-evidence; named for traceability only) |
|---|---|---|---|
| MEM-01 | Does `device_load/store`'s GPR index scale as an element index by the encoded element size? | `UNKNOWN` (open) | quarantined `EXP-0077`/`EXP-0080`/`EXP-0081` (`m4-mem-offset-semantics`) |
| MEM-02 | Is the in-instruction immediate offset added in element units, not bytes? | `UNKNOWN` (open) | same as above |
| MEM-03 | Is the complete signedness/legal range of the immediate element offset known and HW-validated? | `UNKNOWN` (open) | same as above |
| MEM-04 | Can `device_load/store` directly encode `base + index·stride + offset` for arbitrary vertex strides? | `UNKNOWN` (open) | same as above |
| MEM-05 | Does 32-bit address/index arithmetic wrap the way legal NIR buffer offsets require? | **`PARTIAL`** — EXP-0122 §6A.2 establishes that `base + (uint64_t)off` wraps with period **exactly `2^43`** for this one idiom (`HW-VALIDATED`, `target: G16G`, 12/12 discriminating cases in both runs), with align-down-4 on the 32-bit access. Whether other access widths or other addressing idioms share that period is **untested**, and the mechanism (VA bus width vs a 43-bit instruction operand vs a firmware window) is **not distinguished**. | EXP-0122 (evidence); the numeric-offset questions themselves remain with the quarantined successors |
| MEM-11 | Is there no descriptor-level buffer bound available to the memory instruction (i.e. is §6's behavior a bound, a mask, or allocator zero-fill)? | `Partial` / answer `Unknown` per EXP-0076's own required-response block (adjacent observations recorded, mechanism not identified) | none active; needs a separate ISA/descriptor-level splice or native experiment (EXP-0076 RESULTS.md explicitly declines to answer this) |
| MEM-13 | Does the hardware guarantee dependency interlocking from every load/texture/atomic result to a consuming ALU instruction without an explicit wait? | **`ANSWERED: YES`** — `HW-VALIDATED`, `target: G16G`. Load, dependent-load, **texture-read** and **atomic-result** each feed a consuming ALU with **zero authored slack and no software wait**, to N=65536 plus a 48-loads-per-thread adversarial case; corroborated by structural tokenization of our own compiled bytes showing **zero wait/scoreboard instructions** between producer and consumer. Re-validates EXP-0025's A18 register-interlock claim on M4 silicon and **extends it to texture-read and atomic sources**. | **EXP-0085** (56 cases ×2, 56/56 PASS, gates PASS, no faults) |
| MEM-14 | Does the same interlock hold for stores/atomics whose source was just produced? | **`ANSWERED: YES`** — same experiment, same construction. | **EXP-0085** |
| MEM-15..17 | Maximum simultaneously usable device-buffer base-slot count; are all encoded slots below it independently selectable with no aliasing/holes; does an unpopulated/out-of-range slot return zero, alias, or fault? | **`ANSWERED`** — `HW-VALIDATED`, `target: G16G`, full 0..255 sweep across load/store/atomic (351 cases ×2, byte-identical, zero faults in 702 executions). **The selector is effectively 7-bit: slots 128..255 MIRROR 0..127 on every op path**, with no third behaviour anywhere (buffer 1 held by slots [1,129], buffer 10 by [10,138], …). **No aliasing or holes among populated slots 1..30**; boundaries 7/8 and 15/16 clean. **31 slots simultaneously usable via direct binding** — recorded as a *direct-binding-population edge* (MSL `[[buffer(N)]]` caps at N=30), **NOT** a demonstrated architectural ceiling. **Out-of-range behaviour is fault-contained but SILENTLY WRONG:** LOAD zero-or-mirror; STORE discard-or-redirect-to-binding-0; ATOMIC returns 0 and discards, or redirects and discards. `byte+4` is live but is **not** the selector — the selector is **`byte+5`**. | **EXP-0083** (supersedes the quarantined `EXP-0078`) |
| MEM-18 | Does `base_slot` index the userspace resource table directly, or an intermediate USC-populated preload file? | **`PARTIAL`** — not resolved as a mechanism, but two constraints are now measured (`target: G16G`): **slot 0 is a reservation candidate whose content is pipeline-configuration dependent** (constant-program hoisting gives `P(5,0)` versus plain binding 0), and **each dynamically-loaded pointer receives its own compiler-populated `base_slot` table entry** — refuting a shared-slot model. | EXP-0083; EXP-0084 |
| MEM-19 | Can the USC constant/uniform program populate every usable base slot, and what happens past capacity? | `UNKNOWN` (open) — see MEM-18's partial constraints | none active |
| MEM-20 | Can Apple9 load/store through a 64-bit device address obtained dynamically in a GPR, without a statically encoded base slot? | **`ANSWERED: YES`** — `HW-VALIDATED`, `target: G16G`, both runs' results SHA-256 identical. **Four independent constructions, all byte-exact.** | **EXP-0084** |
| MEM-21 | Can a non-uniform, per-lane descriptor-array index select different buffer base addresses per SIMD lane? | **`ANSWERED: YES`** — a non-uniform per-lane selector computed from `thread_position_in_grid` gives **32 lanes 32 distinct buffers**, proven **divergent rather than broadcast**, with uniform and single-lane-outlier controls. | **EXP-0084** |
| MEM-22 | When more live buffer resources exist than fit the direct-slot path, does Apple's compiler reject, use a dynamic/descriptor-table path, or split/preload? | **`ANSWERED`, with two evidence levels kept separate** — MSL **rejects** a 32nd direct `[[buffer(31)]]` argument **at compile time** (0..30 ceiling), while the **dynamic-address mechanism independently executed correctly at N=64 and N=256, i.e. 2–8× past that ceiling**. **Compiler consequence: the bindless / descriptor-array fallback exists and is hardware-validated; direct slots are bounded (MEM-15/16) and dynamic addressing scales past them.** | **EXP-0084** |

Additional explicit non-guarantees, restated from §3/§6 so they are not lost by omission:

- The §4–§7 model was validated on **one 64-byte allocation size only**; other allocation
  sizes, and whether the align-down / zero-fill boundary scales with allocation size at
  all, are untested. `STRUCTURAL`, EXP-0076 RESULTS.md "Exact tested range".
- ~~The zero-fill region past the allocation end was probed only at offsets 64..79 and
  1088; the shape of the boundary between those distances is unknown.~~ **REFINED by EXP-0122
  (§6A.1, `target: G16G`): the zero region is NOT page-wide.** At exactly 16384 B past the
  allocation (the platform/sparse-tile quantum) and its ±256 B neighbourhood, reads return live
  non-zero data, while 4096 B and 32768 B and beyond read zero. Treat "outside the allocation
  reads zero" as an observation at the tested distances, **never as a guarantee**.
  `HW-VALIDATED`, EXP-0122 RESULTS.md §2.2; original bound EXP-0076 RESULTS.md "MEM-08".
- Vertex-stage and fragment-stage device memory access were not exercised by EXP-0076
  (compute stage only); do not assume this chapter's model applies unmodified there.
  `STRUCTURAL`, EXP-0076 RESULTS.md "Exact tested range".
- `fastMathEnabled = YES` was not tested; this chapter's config is `fastMathEnabled = NO`,
  `mathMode = MTLMathModeSafe` throughout. `STRUCTURAL`, EXP-0076 RESULTS.md "Exact tested
  range".
- No claim is made anywhere in this chapter about the **native instruction encoding**
  that produces the §4–§7 behavior (i.e., §2 and §4–§7 are not yet correlated) — that
  correlation is exactly what MEM-11 (above) would need to establish. `STRUCTURAL`,
  EXP-0076 RESULTS.md "Target and scope label".

## 9. Evidence index

- `experiments/EXP-0012-memory/RESULTS.md` — instruction-level addressing model (§2),
  A18 Pro/G17P, `HW-VALIDATED`.
- `experiments/EXP-0141-m4-emit-mem/RESULTS.md`,
  `experiments/EXP-0141-m4-emit-mem/analysis/field_verdicts.json`,
  `experiments/EXP-0141-m4-emit-mem/raw/m4-20260828-run11/`, `…/run12/`, `…/run21/`, `…/run22/`
  — the operand/destination encoding rules (§2A), M4/G16G, `HW-VALIDATED`, commit `5a9df52b`.
- `experiments/EXP-0101-*/RESULTS.md` — retraction of EXP-M4-13's `device_load` destination
  formula, superseded in turn by EXP-0141 (§2A.1).
- `docs/isa/register-move-and-liveness.md` — the register-lifetime / release-on-read contract
  §2A.2 depends on, and the same EXP-0141 destination rule stated from the liveness side.
- `docs/isa/README.md`, `### ✅ Memory access family (EXP-0012)` — current
  (RT-1a-FIX-corrected) byte map for §2; also cross-linked from that section back to
  this chapter.
- `experiments/EXP-0076-m4-buffer-robustness-matrix/RESULTS.md`,
  `experiments/EXP-0076-m4-buffer-robustness-matrix/analysis.json`,
  `experiments/EXP-0076-m4-buffer-robustness-matrix/manifest.json`,
  `experiments/EXP-0076-m4-buffer-robustness-matrix/raw/m4-20260827-run01/`,
  `experiments/EXP-0076-m4-buffer-robustness-matrix/raw/m4-20260827-run02/` — the
  access-unit / alignment / OOB / boundary model (§3–§7), M4/G16G,
  `HW-VALIDATED`, promoted commit `446a5f28`.
- `experiments/EXP-0122-m4-sparse-vm-conventions/RESULTS.md`,
  `experiments/EXP-0122-m4-sparse-vm-conventions/analysis/summary.json`,
  `experiments/EXP-0122-m4-sparse-vm-conventions/raw/m4-20260828-run01/`, `…/run02/` — the
  zero-fill bounds, the `2^43` wraparound, and the VM/allocator conventions (§6A), M4/G16G,
  `HW-VALIDATED`, commit `f2b8ef66`.
- `experiments/EXP-0083-*/RESULTS.md` — the device-buffer base-slot census answering
  MEM-15/16/17 (§8), M4/G16G, `HW-VALIDATED`.
- `experiments/EXP-0084-*/RESULTS.md` — dynamic 64-bit addressing and per-lane divergent buffer
  selection, answering MEM-20/21/22 (§8), M4/G16G, `HW-VALIDATED`.
- `experiments/EXP-0085-*/RESULTS.md` — the hardware-interlock result answering MEM-13/14 (§8),
  M4/G16G, `HW-VALIDATED`. **Auditability caveat on record:** a harness `--init` byte-order bug
  found during analysis led to a recapture under the SAME run ids, so the flawed first pair is
  unrecoverable. Nothing had been promoted at that point; the promoted pair is internally
  consistent and double-corroborated, but the deviation from append-only discipline is stated
  rather than hidden.
- `PROVENANCE.md` (2026-08-27 EXP-0076 row; 2026-07-06 EXP-0012 rows; 2026-08-28 EXP-0083,
  EXP-0084, EXP-0085, EXP-0122 and EXP-0141 rows) — the audit trail for the experiments
  underlying this chapter.
- `APPLE9_RE_IMPLEMENTATION_GAPS.md`, "P0 — Memory addressing and robustness" (MEM-01
  through MEM-22) — the open-item list reproduced in §8.
- `docs/P0-P1-CLOSURE.md`, row P1.5 — live closure status for this subsystem (still
  `OPEN`; this chapter documents what EXP-0076 bounded, not a closure).
