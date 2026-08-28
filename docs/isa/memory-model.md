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
- Consequently §2 rests on A18-native evidence assumed (not re-validated here) to also
  hold on M4, and §4–§7 rest on M4-native evidence assumed (not re-validated here) to also
  hold on A18. Both assumptions are Apple9-family inferences, not independent
  measurements; neither direction is re-derived in this chapter.

## 1. What this chapter covers and does not cover

**Covers:** the addressing model for `device_load`/`device_store`/atomic-RMW instructions
(§2); the access-unit decomposition and per-unit alignment-rounding rule for device-buffer
accesses (§4); the compiler consequence for unaligned NIR buffer access (§5);
out-of-allocation and boundary-straddling read/write/atomic-exchange behavior (§6); the
constraint this places on synthesizing a Vulkan-style bounded/robust buffer load (§7).

**Does not cover** (see §8 for the open-item list): the numeric offset/scaling questions
MEM-01..MEM-05; the physical mechanism behind the observed bound (MEM-11); load→consumer
and store/atomic dependency interlocking (MEM-13/MEM-14); device-buffer base-slot capacity
and aliasing (MEM-15..MEM-19); dynamic 64-bit / descriptor-array addressing
(MEM-20..MEM-22); threadgroup-memory bounds; texture/sampler descriptor bounds (see
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

The following MEM-* items from `APPLE9_RE_IMPLEMENTATION_GAPS.md` are **open**. None of
them is answered by this chapter or by EXP-0076. Where a successor experiment exists, it
is named for traceability only — **its observations are quarantined non-evidence and are
not cited or relied upon anywhere above.**

| item(s) | question | status | pursuing experiment (non-evidence; named for traceability only) |
|---|---|---|---|
| MEM-01 | Does `device_load/store`'s GPR index scale as an element index by the encoded element size? | `UNKNOWN` (open) | quarantined `EXP-0077`/`EXP-0080`/`EXP-0081` (`m4-mem-offset-semantics`) |
| MEM-02 | Is the in-instruction immediate offset added in element units, not bytes? | `UNKNOWN` (open) | same as above |
| MEM-03 | Is the complete signedness/legal range of the immediate element offset known and HW-validated? | `UNKNOWN` (open) | same as above |
| MEM-04 | Can `device_load/store` directly encode `base + index·stride + offset` for arbitrary vertex strides? | `UNKNOWN` (open) | same as above |
| MEM-05 | Does 32-bit address/index arithmetic wrap the way legal NIR buffer offsets require? | `UNKNOWN` (open) | same as above |
| MEM-11 | Is there no descriptor-level buffer bound available to the memory instruction (i.e. is §6's behavior a bound, a mask, or allocator zero-fill)? | `Partial` / answer `Unknown` per EXP-0076's own required-response block (adjacent observations recorded, mechanism not identified) | none active; needs a separate ISA/descriptor-level splice or native experiment (EXP-0076 RESULTS.md explicitly declines to answer this) |
| MEM-13 | Does the hardware guarantee dependency interlocking from every load/texture/atomic result to a consuming ALU instruction without an explicit wait? | `UNKNOWN` (open) | none active |
| MEM-14 | Does the same interlock hold for stores/atomics whose source was just produced? | `UNKNOWN` (open) | none active |
| MEM-15..17 | Maximum simultaneously usable device-buffer base-slot count; are all encoded slots below it independently selectable with no aliasing/holes; does an unpopulated/out-of-range slot return zero, alias, or fault? | `UNKNOWN` (open) | quarantined `EXP-0078` (`m4-base-slot-census`) |
| MEM-18 | Does `base_slot` index the userspace resource table directly, or an intermediate USC-populated preload file? | `UNKNOWN` (open) | none active |
| MEM-19 | Can the USC constant/uniform program populate every usable base slot, and what happens past capacity? | `UNKNOWN` (open) | none active |
| MEM-20 | Can Apple9 load/store through a 64-bit device address obtained dynamically in a GPR, without a statically encoded base slot? | `UNKNOWN` (open) | none active |
| MEM-21 | Can a non-uniform, per-lane descriptor-array index select different buffer base addresses per SIMD lane? | `UNKNOWN` (open) | none active |
| MEM-22 | When more live buffer resources exist than fit the direct-slot path, does Apple's compiler reject, use a dynamic/descriptor-table path, or split/preload? | `UNKNOWN` (open) | none active |

Additional explicit non-guarantees, restated from §3/§6 so they are not lost by omission:

- The §4–§7 model was validated on **one 64-byte allocation size only**; other allocation
  sizes, and whether the align-down / zero-fill boundary scales with allocation size at
  all, are untested. `STRUCTURAL`, EXP-0076 RESULTS.md "Exact tested range".
- The zero-fill region past the allocation end was probed only at offsets 64..79 and
  1088; the shape of the boundary between those distances is unknown. `STRUCTURAL`,
  EXP-0076 RESULTS.md "MEM-08".
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
- `PROVENANCE.md` (2026-08-27 EXP-0076 row; 2026-07-06 EXP-0012 rows) — the audit trail
  for both experiments underlying this chapter.
- `APPLE9_RE_IMPLEMENTATION_GAPS.md`, "P0 — Memory addressing and robustness" (MEM-01
  through MEM-22) — the open-item list reproduced in §8.
- `docs/P0-P1-CLOSURE.md`, row P1.5 — live closure status for this subsystem (still
  `OPEN`; this chapter documents what EXP-0076 bounded, not a closure).
