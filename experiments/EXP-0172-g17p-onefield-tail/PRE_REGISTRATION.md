# EXP-0172 — PRE-REGISTRATION (frozen before any build or device run)

**Experiment:** `EXP-0172-g17p-onefield-tail` — the one-field-away tail of the emitter worklist.
**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6,
Metal family Apple9), host `users-MacBook-Neo.local` / `192.168.10.243`.
**Clean-room category:** OWN-SHADER + HW-PROBE. Every byte spliced, decoded or inspected is the
compiled form of MSL in `kernels/`. No Apple binary is disassembled, at any point, for any reason.
**Governing law:** `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md` (all eight sections, including the four rules added
2026-08-30).

---

## 1. The question

Of the 31 instructions the live worklist reports as **one field away** from emittable, this
experiment owns the remainder after EXP-0168 (`dst` everywhere + 12 instructions), EXP-0171
(`ilogic`, `srcA`, `tail`) and EXP-0169 (the 144 unverifiable fields + `get_sr.dst_hi`) take
theirs. For each field it owns: **can an emitter choose this field's value and get documented
hardware behaviour** — or is the field unsweepable, or inert, or an ordering control this harness
cannot observe?

The headline this is measured against is **41 of 166 emittable, 616 fields**. 125 fields were
withdrawn in the last day; nothing here is promoted on a weaker basis than the gate in §6.

## 2. Ownership reconciliation (against the live worklist, not the dispatch text)

`python3 tools/agx-isa/emit_worklist.py` at pre-registration: **41 emittable / 125 blocked / 166
emitter-relevant**, **31** instructions one field away.

- **Not mine, field name `dst`** (EXP-0168): `frag_color_pack.dst`, `n4_rt_word.dst`,
  `rt_query_traverse.dst`, `uniform_mov.dst`.
- **Not mine, field name `tail`/`srcA`** (EXP-0171): `bf_fma_dst.tail`, `ibitcount.tail`.
- **Not mine, EXP-0168 instructions**: `atomic_mem`, `copysign`, `cvt_f2h`, `falu_acc`, `if_push`,
  `iter_at`, `pack_convert`, `shift_amt_move`.
- **Already settled by EXP-0163, not re-litigated**: `frag_color_store.store_mode`, `iter.b9`
  (both INERT-ROBUST → `single-template-inference` under rule 8).
- **Mine (15 fields, 13 instructions):** the `TARGETS` table in `harness/carriers.py`.
- **Mine but DECLINED without device time (4), with reasons:** the `DECLINED` table in
  `harness/carriers.py`. Both tables are part of the frozen contract.

## 3. Priority, and why (the dispatch asks for this explicitly)

Ruthless, and the ordering is by **oracle strength × probability the field is live**, because
under rule 8 an *inert* field cannot be promoted at all — so device time spent on a field that is
probably inert buys a `single-template-inference` row and no instruction closure.

### TIER 1 — attempt promotion (5 fields, 5 instructions)

| field | w | legal values | carriers, and the dimension they differ in | oracle |
|---|---:|---:|---|---|
| `falu2i.imm_flag` | 1 | 2 | `fimm` (positive immediates spanning the minifloat exponent range, fadd+fmul, **ALU/SR-seeded operand**) vs `fimm2` (negative immediates, fma, **load-sourced** `mods==0xC0` form) — differ in the *decoded immediate* and in *operand provenance* | the observed float result of the dependent output word, adjudicated offline against `isadb.imm_decode` (see H1 below for the corrected model). |
| `get_sr.form` | 1 | 2 | `srwide` (multi-component uint3 position-in-grid SR family only; `form` natively 1) vs `srnarrow` (scalar SRs only; `form` natively 0) — differ in exactly the *SR width* db.json says `form` controls | db.json asserts `form` "does not change the SR select". Prediction: the SR **value** is unchanged or silently zero. A *different non-zero SR value* refutes db.json and is a first-class result. |
| `tex_sample.coord` | 8 | 256 | `texread` (integer `read(uint2)`: no sampler, no derivative, no LOD, no filter) vs `texmix` (explicit-LOD sample + gather + read in one program) — differ in *operation kind and derivative dependence* from EXP-0155's filtered arms | `coord` is op+1, a **register index**. The sampled texture is R32Float with `texel(x,y) = x + 100·y`, so the value observed at a probe pixel **names the coordinate the hardware used**. The claim is the per-value partition, and it must be identical in both runs. |
| `vary_slot.slot` | 8 | 256 | `vmany` (16 scalar varyings → slots past 7), `vhalf` (half/vector widths), `vflat` (flat/no-perspective), `vsrc` (memory/immediate-sourced) — differ in *varying count, width and interpolation class* | db.json: byte+3 *is* the varying slot. Prediction: redirecting the slot descriptor redirects which varying the following `vary_store` writes, so the fragment's read changes. |
| `tex_deriv.dstsrc` | 24 | boundary+PoT+16 interior (protocol §3.3 for w>8) | `deriv` (**new authored carrier**: 8 derivatives of 3 varyings with distinct gradients, both axes 0x92/0x90 plus the `fwidth` form, each result in its own channel) | Every derivative of a linear varying is **constant over the primitive**, so each channel has one host-computable expected value; a dst- or src-register redirect is an exact numeric change. |

### TIER 2 — swept for the record; promoted only if genuinely LIVE (6 fields)

`imageblock_store.src` (4 attachment/sample-count arms — a field win only, see `DECLINED`);
`irotate.b2` (**only 2 legal values**, see §5); `simd_ballot.cache` and `simd_shuffle.cache` on the
**new `deadsrc` carrier**, whose every operand is loaded, used once and dead immediately — the
last-use dimension in which EXP-0163's four carriers were all identical, i.e. one carrier under
rule 2; `frame_marker_compact.b1`; `n4_cf_word.b3`.

### TIER 3 — swept for the record, **promotion declined in advance** (2 fields)

`ret.scoreboard`, `dev_scoreboard_fence.scope_flag`. Both are ordering controls (an
execution/scoreboard-wait mask; a memory-fence scope). This harness reads back after
command-buffer completion, which flushes, so it **has no ordering observable**: a carrier that
moves proves general sensitivity to the byte, not ordering-specific power. Three prior experiments
declined to promote this family for that reason; **we pre-register the same decline, so that a
LIVE result here cannot be converted into a promotion after the fact.**

### DECLINED without device time (4)

Verbatim reasons in `harness/carriers.py::DECLINED`: `cubearray_coord_const.b3` (descriptor fires
0 times in 1080 corpus files — EXP-0148 — because its signature is interior to the
`tex_addr_setup` token; there is no program in which to splice it, and its only exercise is a
round-trip string, which §3b says is not an emitter gate); `half_alu_fma12.ext` (instruction is
`emit_unsafe` for a length that over-consumes the next leader, and `ext` is precisely the disputed
remainder); `mesh_out_src.sel` (no mesh pipeline exists in `gfrun2.m`); and the note that
`imageblock_store.src` does not close its instruction.

## 4. Hypotheses, expected observations, and refuters

**H1 (`falu2i.imm_flag`) — CORRECTED AT PRE-REGISTRATION, before any build; see §9.**
db.json's prose (`flag(bit8)` listed inside `imm_decode(b1, sign)`) suggests the bit is part of the
immediate's mantissa, but **our own decoder disagrees with our own prose**:
`tools/agx-isa/isadb.py::imm_decode` computes `m = (b1 >> 1) & 0x7` — a **3-bit** mantissa at b1
bits 1..3 — and **never reads b1 bit 0 at all**, while `imm_encode` hard-sets it
(`b1 = (e<<4) | (m<<1) | 1`). So the field carries no weight in the decoded value and an emitter
using our encoder can only ever produce `imm_flag = 1`. Writing this experiment around a
mantissa-LSB model would have been an oracle that could not be right.

The structural reading instead: bit 8 is **bit 0 of the srcB operand byte**, and in all three
overloads of this 6-byte form that bit position is an operand **SIZE** bit —
`falu2.srcB_size` ("1: b32, 0: b16"), `falu2_uni.usrc` (documented as `(ureg<<1)|size32`).
*Hypothesis:* in the immediate overload the same bit is the immediate/operand **width** selector.
*Expected:* clearing it changes the observed result (the immediate read at the other width, or a
silent zero) on at least one occurrence, on both carriers, identically in both runs.
*Refuter:* no movement at any occurrence on either carrier whose ladder passes → the size
distinction does not exist in the immediate overload; the bit is inert with an unknown role and,
per rule 8, gets `single-template-inference`, **not** emitter grade.
*Either way* the `imm_decode`/`imm_encode` asymmetry is recorded as a db/tool defect: an encoder
that can only emit one of a field's two legal values does not make that field emittable
(the same class of finding as DEF-0170-1).

**H2 (`get_sr.form`).** `form` is a datapath/width modifier and does not change the SR select.
*Expected:* on at least one of the two width classes the read changes (value or silent zero); the
SR *identity* never changes.
*Refuter:* a flipped `form` yields a different, non-zero SR value — `form` would then be part of
the selector and db.json's semantics line is wrong.

**H3 (`tex_sample.coord`).** `coord` is a coordinate register index, and EXP-0155's 73–93%
cross-run disagreement came from *filtering/derivative/LOD* dependence, not from the field.
*Expected:* on the derivative-free carriers the per-value outcome partition reproduces at ≥99%.
*Refuter:* the same per-value instability appears on `read(uint2)` too — the irreproducibility is
then not attributable to filtering and `coord` stays `corpus-correlation`.

**H4 (`vary_slot.slot`).** The slot descriptor selects the slot the following store writes.
*Expected:* dense movement on the 16-varying carrier, structured by slot.
*Refuter:* movement of the EXP-0155 magnitude (0–3 of 256) or unstructured movement — in which
case the emitter-relevant lever really is `vary_store.out_slot`, as EXP-0155 concluded, and we say
so.

**H5 (`tex_deriv.dstsrc`).** The 24-bit field packs a destination and a source register.
*Expected:* movement, with the changed channel identifying which half was hit.
*Refuter:* no movement at any sampled value on a carrier whose liveness ladder passes → `dstsrc`
is not an operand as modelled, and the 24-bit lump is a db defect to report.

## 5. Confounders, and what is done about each

1. **`assemble()`/`match` overlap (DEF-0170-1).** `python3 tools/agx-isa/match_overlap_report.py`
   was run at pre-registration. Of this experiment's fields exactly **one** overlaps its own
   descriptor's `match`: **`irotate.b2`** (width 8, bits 16 and 18..23 pinned, **1 free bit → 2
   legal values**). Every other field of mine is match-disjoint, so its dense sweep really is
   dense. The harness patches bytes through its own clear-then-set mask (`run.py::isadb_set`), not
   through `assemble()`, and then **re-decodes** every patched instruction: a value that no longer
   decodes as the same mnemonic is recorded `undecodable` and excluded from `encodable_range`. So
   `irotate.b2` is reported honestly as 2 legal values out of 256 dispatched.
2. **Rule 3 — the observable must not co-vary with the field under test.** Checked explicitly for
   every arm: `run.py` splices **only** the instruction under test at a frozen absolute offset, and
   observes fixed surfaces at fixed probe points chosen before the run. No read-back register,
   probe pixel, output index or surface is a function of the swept value. This is the EXP-0140
   failure (`uniform_mov.dst` read back through `device_store(data_reg=D)` where `D` *was* the
   swept dst) and it cannot occur in this shape.
3. **Rule 4 — a round trip is not an emitter gate.** No verdict in this experiment cites `rt_ok`,
   `roundtrip_test.py`, or tokenization. Not once.
4. **Rule 2 — a never-moving field is promotable only if the carriers differ in the dimension the
   field controls.** Every carrier's `why` in `harness/carriers.py` names the dimension. An inert
   verdict on carriers identical in that dimension will be reported as **STILL-UNDERPOWERED →
   `untested`**, not as an inert result.
5. **Asynchronous `device_load` (EXP-0169) — the contamination mode that can FABRICATE a positive.**
   On G17P a load with no wait landed 0..8 of 8 seed registers depending only on filler length; a
   diff-based movement oracle then reads a differently-seeded case as *movement*. Two defences:
   (a) **prevention** — every TIER 1 carrier except `fimm2` was rewritten for this experiment to be
   **device-load-free**: `k_fimm`, `k_srwide`, `k_srnarrow` seed from special registers through ALU
   only, and `k_texread`/`k_texmix`/`k_deriv` derive everything from the interpolated `[[position]]`
   and declare no buffer at all; (b) **detection** — the ≥99% per-value cross-run gate is exactly a
   nondeterminism detector, and a load that lands intermittently cannot produce the same per-value
   partition twice. `fimm2` keeps the load-sourced form deliberately (it is the `mods==0xC0` arm)
   and is flagged as carrying the hazard knowingly.
6. **The baseline is captured once per arm and never replaced.** `run.py` compares every case
   against that first baseline; `baseline_holds()` *checks* the unmutated program still reproduces
   it and stops the arm if it does not. A refreshed baseline can therefore not silently redefine
   what "moved" means.
7. **A stale shared `db.json` on the device.** EXP-0169 found the neo's shared `tools/agx-isa/db.json`
   has **1036 fields against the repo's 1060**, with `falu2.srcA_class`/`srcB_class` replaced by
   `mod_lo` — a silent mis-keying. This experiment therefore **pins its own snapshot**:
   `db.json` + `isadb.py` are copied into `~/agxre/EXP-0172/tools/agx-isa/`, `AGXRE_REPO` points at
   that tree so resolution is explicit rather than a search, and the sha256 of both files is
   recorded in `CAPTURE_CONTRACT.json`. The neo's shared `tools/` is **not** touched (EXP-0168,
   EXP-0169 and EXP-0171 are on that machine).
8. **Concurrent siblings.** Sweeps run **unlocked** (§7). Mitigations on every case: read-back
   poisoned with `0xDEADBEEF` (distinguishes "wrote 0" from "never ran"), an integrity sentinel
   through a path independent of the instruction under test, the OS fault-classification string
   recorded per trial, `InnocentVictim` retried and segregated as `foreign`, majority-of-3 before
   any `fault`, and periodic + end-of-arm baseline re-validation. **No `fault` is concluded from a
   single observation.**
9. **Contamination cannot fabricate a coherent observation, only destroy one** (EXP-0160). Where a
   case disagrees across runs it is excluded from the promoted range and counted in the
   disagreement total that the ≥2× movement rule is measured against.
10. **Hang courtesy (§7).** `ret.scoreboard` is an execution-wait mask and `n4_cf_word.b3` sits
    before reconvergence points; both are plausible hang regions. Declared in `PROGRESS.md` before
    the run. `MAX_HANGS_PER_FIELD=2` stops an arm, `MAX_HANGS_PER_ARM=6` stops the carrier.

## 6. The promotion gate (frozen; no verdict may be written any other way)

A field is promoted only if **all** hold:

1. **Two gated runs**, `run01` and `run02`, byte-identical programs, same frozen `arms.py`.
2. **≥99% per-value cross-run agreement** on the outcome partition, **and movement ≥ 2× the
   disagreement count.**
3. The arm's **detection profile** showed at least one status-OK, **same-mnemonic** control that
   moved the observation. An arm with no detection power is recorded and **barred** from supporting
   any verdict — inert *or* live.
4. The end-of-arm baseline re-validation passed.
5. For a never-moving field, rule 2 is satisfied by the carrier set.

**Label policy** (inherited from EXP-0163, restated so a reviewer can disagree explicitly):

- **LIVE** → `hardware-run`. The full encodable range executed on hardware and the value→behaviour
  partition is exact and reproduced. Where a TIER 1 host oracle exists (`falu2i.imm_flag`), the
  predicted value must also match.
- **INERT-ROBUST** → **`single-template-inference`, NOT `hardware-run`** (rule 8). Emitter-grade
  asserts the implementer may *choose* the value; "emit what the compiler emitted" is a
  captured-template dependency. The measurement is not downgraded — its full strength lives in
  `note`/`range`/`inert_arms` — only the claim about what an emitter may do.
- **STILL-UNDERPOWERED** → `untested`. Protocol §5: do not round up.
- **DECLINED** → the field keeps its current label and the reason is recorded.

**Machine-readable coverage on every verdict row** (the bar the orchestrator set):
`values_dispatched`, **`distinct_bytes` counted from DISTINCT `bytes` strings in `raw/`** — never
the dispatched-value count — `encodable_range` (the values that re-decode as the same mnemonic),
`start`, `width`. `start`/`width` are re-read from the **pinned** `db.json`, which converts the
stale-DB hazard of §5.7 into a loud merge failure instead of a silent mis-attribution.

## 7. Frozen procedure

1. Freeze this file + `CAPTURE_CONTRACT.json` (source sha256 of every kernel, harness file,
   analysis script, `run.py`, and the **pinned** `db.json`/`isadb.py`). **Done before any build.**
2. Stage `~/agxre/EXP-0172/` on the neo; build `work/{gfrun2,shdump,agxrun_persist}` with
   `clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation`.
3. **Pre-freeze census** (`analysis/census.py`) — calibration, lands in `raw/prefreeze/`, **no
   verdict may cite it**: does each carrier compile with the exact pipeline descriptor the sweep
   will use, does it emit the target instruction, and does the occurrence carry a *different* field
   context from the prior experiment's arm?
4. `analysis/gen_arms.py` → `harness/arms.py`, then **frozen**. Selection rule, frozen here: for
   each target field take carriers that differ structurally in the dimension the field controls, and
   inside a carrier prefer occurrences whose *other* field values differ. `run.py` asserts the
   located instruction still has the census's exact bytes at the census's offset, so a shifted
   occurrence index is a recorded error, never a silently different arm.
5. `run01`, then `run02`, into `raw/<run_id>/sweep.jsonl`, one JSON object per case,
   `flush`+`fsync` per line. Run ids are never reused; a partial run is retained, never topped up.
6. `analysis/verdicts.py` → `analysis/field_verdicts.json` (flat `<mnemonic>.<field>`) +
   `db_defects`. Then `RESULTS.md`.

**Environment / timeouts (frozen):** per-request watchdog `REQ_TIMEOUT = 15.0 s`; `CONFIRM_N = 3`;
`FOREIGN_CASCADE_N = 8`; `BASELINE_EVERY = 250` cases; `BASELINE_RETRIES = 4`;
`MAX_HANGS_PER_FIELD = 2`; `MAX_HANGS_PER_ARM = 6`. Compute carriers: grid 32, threadgroup 32,
2048-byte output. Render carriers: 16×16, `--color-format 125` (RGBA32Float) unless the carrier
says otherwise, probe pixels `(8,8) (5,10) (11,5) (5,9) (3,10) (11,6) (7,10)`, probe lanes
`0 1 5 17 31`.

**Raw record schema, frozen** (protocol §4), one object per case:
`instr, field, value, bytes, observed, oracle?, match, outcome, carrier, note` with
`outcome ∈ {ok, silent_zero, wrong_value, fault, hang, undecodable, moved, inert, foreign,
unreproduced, not_run}`. `observed` carries `status`, a sha256 per surface, the readable probes, the
poison list, the sentinel, and on any non-OK case the OS fault-classification string.

## 9. Amendment log (pre-registration is append-only once frozen)

- **2026-08-30, before any build or device run.** H1 for `falu2i.imm_flag` was drafted from
  db.json's *prose* (`flag(bit8)` named inside `imm_decode`) and predicted the bit to be the LSB of
  a 4-bit mantissa. Reading `tools/agx-isa/isadb.py::imm_decode` showed the implementation uses a
  **3-bit** mantissa and ignores b1 bit 0 entirely, so that prediction was unsatisfiable by
  construction — the same defect class as rule 3 (an oracle that cannot return a negative). H1, and
  the TIER 1 oracle cell for that field, were rewritten to the operand-**size**-bit hypothesis
  before anything was built. `CAPTURE_CONTRACT.json` was re-frozen after the edit; no build, no
  census and no device run had occurred. Recorded here rather than silently corrected.

## 8. What this experiment will NOT do

No `git commit`. No edit to `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/`,
`PROVENANCE.md`, `CLAUDE.md` or `CODEX.md`. No edit to the neo's shared `tools/`. No `macvdmtool`,
ever — if the host stops answering, this experiment STOPS and reports BLOCKED. Nothing outside
`experiments/EXP-0172-g17p-onefield-tail/` on the repo host and `~/agxre/EXP-0172/` on the neo.
