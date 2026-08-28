# PRE_REGISTRATION -- EXP-0087 (M4 register-move synthesis)

Frozen before any gated GPU dispatch of a spliced variant. Two capture runs
follow this contract verbatim (`CAPTURE_CONTRACT.json`); this document states
the falsifiable hypotheses, method, matrix, and stop conditions.

## 0. Question and why it matters (DRV-ISA-01)

`tools/agx-isa/db.json` carries FIVE separate instruction descriptors for the
byte0-low-nibble-0xb "compact move" family -- `reg_move_c0`, `reg_move_c1`,
`reg_move_c9`, `reg_move_cb`, `reg_move_c2var` -- discriminated by the LOW
nibble of byte+2 (0/1/9/0xb, plus a high-nibble-2 residual class), with the
high nibble of byte+2 modeled as an opaque `src_class` enum per descriptor.
`reg_move_cb`'s own provenance says "Not splice-validated"; `reg_move_c2var`
says its field roles were "inherited" from `reg_move_c0`. All five entries
are byte-diff/census provenance only (EXP-M4-13 R7/R8), never hardware-spliced.

An external compiler-engineer exercise trying to emit a plain register-to-
register move from this documentation could not get one to work. That is the
exact failure this experiment exists to close: this project's acceptance gate
(`CODEX.md`; `APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-ISA-01) requires that an
implementer can GENERATE a correct move, not merely tokenize an observed one.

**Hypothesis under test:** byte+2 of the compact move is not five different
opcodes but ONE instruction shape, and byte+2 (jointly with byte+3, "op_desc")
is a structured FIELD (source class / operand routing / a liveness-adjacent
descriptor), not an opcode discriminator. A sibling experiment,
EXP-0086-m4-register-liveness-bits, separately tests bit 17 (byte+2 bit 1)
liveness semantics; this experiment does not duplicate that and instead
targets the MOVE ENCODING and the SYNTHESIS RULE -- i.e., can a compiler
independently EMIT a correct move using only this documentation.

## 1. Method summary

1. **Compiler census** (`kernels/census.metal`, `baseline.py::derive_census`):
   compile four minimal, per-thread-varying MSL kernels designed to force a
   real GPR-to-GPR move (a value passed through a variable, a swap, a
   loop-carried control-flow-join/phi, a noinline call-argument marshal);
   disassemble with our own `tools/agx-isa`; record which reg_move variant
   (if any) appears in each context and what byte+2/byte+3 actually
   correlate with.
2. **Independent synthesis + hardware readback** (`kernels/synth_move.metal`,
   `casematrix.py`, `run.py`): a purpose-built 16-value carrier kernel whose
   compiled form is 16 compact moves feeding 4 vectorized stores with a fully
   known baseline (`out[K] == in[K]`, `in[K] = 1000.0 + K`, K=0..15). Every
   candidate encoding is INDEPENDENTLY RE-ASSEMBLED from field values with
   `tools/agx-isa`'s own `assemble()` (never copy-pasted from an observed
   byte string) and spliced in place of an existing 4-byte instruction (same
   length, never changes program length), then executed on the real M4 GPU
   and read back via the resulting output buffer.
3. Two probe sites, both frozen by `baseline.py` (re-derived and checked at
   every capture, STOP on drift):
   - `probe_src` = the FIRST compact move (`cb080108`, offset 0x00 in
     `_agc.main`: dst=12(r12), usrc=8) -- feeds `out[0]` via the first vector
     store. Every field except `dst` is swept here (byte+2 family, op_desc,
     src/usrc), so the case's effect is legible purely from `out[0]` plus any
     cross-talk elsewhere in the 16-float output.
   - `probe_dst` = the LAST compact move (`3b260108`, offset 0x3C: dst=3,
     usrc=0x26) -- nothing later in program order can overwrite whatever
     register it is redirected to write, so retargeting its `dst` field alone
     is unambiguous.

## 2. Falsifiable hypotheses (frozen; see `casematrix.py` docstring for the
   exact per-case predictions)

- **H-SRC** (probe_src, byte+2=0x01/op_desc=0x08 -- the one family already
  known to work): retargeting `usrc` (byte+1) to a DIFFERENT sibling move's
  value makes `out[0]` take that sibling's tagged value, with no other
  output slot affected. *Refuter:* `out[0]` stays at its original value, or
  any slot other than 0 changes.
- **H-ZERO**: any byte+2 candidate whose LOW NIBBLE is not 1 -- i.e. every
  `reg_move_c0`/`reg_move_c9`/`reg_move_cb`/`reg_move_c2var` candidate in
  MOVE-01 -- does NOT read the intended uniform slot; it silently produces
  exactly `0.0` in the destination, with no other slot affected. *Refuter:*
  any such case reads back the intended non-zero source value, or corrupts
  an unrelated slot.
- **H-DST**: retargeting `probe_dst`'s `dst` field (holding `src`=0x26 fixed)
  redirects the write to the chosen register; because `probe_dst` is the
  LAST move in program order, the vector store reading that register's quad
  shows `in[15]` (1015.0) in the corresponding slot, and `out[15]` (no
  longer written by anything) reads exactly `0.0`. *Refuter:* the retargeted
  slot does not change, or a slot outside the predicted pair changes.
- **MOVE-02 (op_desc single-bit sweep)**: no single frozen hypothesis --
  informal pilot probing already showed a non-monotonic per-bit pattern
  (bit0 harmless, bit1/bit3 break the read to zero, bit2 CORRUPTS a
  different output slot, bits 4-7 harmless); this item is explicitly
  exploratory, predictions are recorded per bit and re-tested under the full
  gated capture, not asserted from the pilot alone.
- **MOVE-05 (byte+2 outside every documented family: 0x0F, 0xFF)**: FAULT
  (`CMDBUF_ERROR`), by analogy with the piloted 0xFF case. *Refuter:*
  `STATUS OK`.

**Independent variable per case:** exactly one field family of the probe
instruction (byte+2 low-nibble/family selector, OR one bit of op_desc, OR
`usrc`/`src`, OR `dst`) relative to that probe's ORIGINAL bytes.
**Controlled variables:** the carrier kernel, the input pattern, grid/tg
shape (1 thread), compiler flags (`--no-fast-math`), which probe site,
every other field of the 4-byte instruction.

**Known confounders:**
- Compiler collapse: an MSL expression whose buffer index does not depend on
  `thread_position_in_grid` is hoisted to the thread-invariant ("uniform")
  data path and compiled as a `uniform_mov`-shaped compact move regardless of
  our intent -- this is WHY the synthesis carrier uses constant indices
  deliberately (to obtain the move family under test in the simplest
  possible program), and WHY the census kernels instead index by `tid`
  (to avoid it).
- `device_store` does not carry an explicit source-register field (own-ISA
  documentation, `docs/isa/README.md` device_store fields): "the value
  register is supplied implicitly by the preceding op". The two probe sites
  are chosen so the spliced move is the LAST register-affecting instruction
  before the store that reads its register quad -- this is exactly the
  configuration the existing carrier already uses successfully (confirmed:
  unmodified `out[K]==in[K]` for all 16 K), so this confounder is controlled
  by construction, not assumed.
- Write-after-write masking: because all 16 moves execute strictly before
  all 4 stores, retargeting a move's `dst` to a register ANOTHER move
  later overwrites would mask the effect. `probe_dst` is deliberately the
  LAST move so nothing can mask it; `probe_src`'s sweep never changes `dst`
  (holds it at 12 throughout), so this confounder does not apply to MOVE-01
  through MOVE-03.
- Value aliasing with our own tagged inputs: the MOVE-03 low/high-range and
  GPR-flag src probes read registers/uniform slots our kernel never wrote,
  so their content is unknown a priori; predictions for these are honestly
  recorded as `"explore"`, not asserted.
- Compiler-version drift: `baseline.py` re-derives `_agc.main` at every
  capture and STOPs (exit 3, no raw/ artifact) if it differs from the frozen
  anchor below -- the matrix is expressed over these exact bytes.

**Frozen anchors** (see `baseline.py::FROZEN`, re-derived and checked live):
```
main_len            124
main_hex            cb080108db0a0108eb0c0108fb0e01088b1001089b120108ab140108bb1601084b
                    1801085b1a01086b1c01087b1e01080b2001081b2201082b2401083b260108e700
                    541800000000170000900000e700541000000000178000900000e70054080000
                    0000170001900000e7005400000000001780019000000e000000
probe_src_offset    0x00   probe_src_hex   cb080108   {dst:12, usrc:8}
probe_dst_offset    0x3C   probe_dst_hex   3b260108   {dst:3,  usrc:0x26}
```

## 3. Frozen matrix (49 cases; full definition and per-case predictions:
   `casematrix.py`, hash-pinned in `CAPTURE_CONTRACT.json`)

| item | n | probe | swept field | fixed fields |
|---|---|---|---|---|
| CTRL | 2 | src, dst | none (identity re-splice) | paired null-result controls |
| MOVE-01 | 23 | src | byte+2 family (every "observed" high nibble of the five DB descriptors reg_move_c0/c1/c9/cb/c2var) | dst=12, src=8, op_desc=0x08 |
| MOVE-02 | 8 | src | op_desc, one bit flipped from the working 0x08 | dst=12, src=8, byte+2=0x01 |
| MOVE-03 | 10 | src | usrc/src (siblings, below-range, above-range, GPR-mode flag) | dst=12, byte+2=0x01, op_desc=0x08 |
| MOVE-04 | 4 | dst | dst register (4 quads) | src=0x26, byte+2=0x01, op_desc=0x08 |
| MOVE-05 | 2 | src | byte+2 outside every documented family (raw bytes) | dst=12, src=8, op_desc=0x08 |

Total: **49** cases.

## 4. Standing gate set (implemented in `verify.py` / `run.py`)

(a) `verify.py --selftest` -- fabricates synthetic captures (no Metal, no
    device) driven through the SAME static()/captured() code paths used on
    real evidence, both clean-pass and per-defect-class-fail cases;
    importing its key sets (`REC_KEYS`/`DISPATCH_KEYS`/`CASE_KEYS`) from
    `run.py`, never restated. Runnable in every tree state (PRE_GPU and
    RUN01_PRESENT included).
(b) `verify.py --seqtest` -- walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT
    through synthetic states, proving every contracted gate is runnable AND
    satisfiable exactly where the contract invokes it, and REFUSED in every
    other state.
(c) NON-RECORDED smoke gate in `run.py`, Phase 1, strictly BEFORE `raw/` is
    created: one spliced scratch case run into `work/` only, requiring
    `STATUS OK`, `PIPELINE_SOURCE archive`, a full 16-float `OUT` line, and
    at least one applied splice arg; any defect exits 3 with the receipt
    printed and no run id burned.
(d) No nondeterministic field (timing, address, pid) inside any
    byte-compared record: `duration_ms`/`duration_seconds`/`GPUTIME_NS` are
    recorded but never compared for cross-run byte-identity; the cross-run
    check compares `04_results.jsonl` verbatim, which the runner is written
    to keep free of such fields (see `run.py::run_one_case`, no timing key
    inside the JSONL line other than `duration_ms`, itself excluded from the
    `results_sha256` byte-identity claim only insofar as it is IDENTICAL
    across two independent 60 s-timeout dispatches of the same fixed splice
    -- see RESULTS.md for the observed cross-run diff, if any).

Plus: single-threaded harness (`run.py` contains no `threading`/`Thread(`/
`multiprocessing`); every `04_results.jsonl` line flushed AND `os.fsync`'d
before the next case; `raw/` files are append-only regular files (never
edited after a run closes); hard timeouts (`case_process`/`smoke_process`
60 s, `host_build` 60 s, `baseline` 60 s, `env_command` 10 s -- generous
relative to the ~1-3 s observed per-case latency); one changed field per
case; each case its own `agxtest.py`/`agxrun` subprocess; a fault or timeout
is recorded and the sweep continues in a fresh process (never retried in
place).

## 5. Provenance note on pilot probing

Before this document was frozen, the case matrix and its predictions were
informed by informal, NOT-recorded pilot splicing on this same local M4 (the
"extrapolate, then test" method `CLAUDE.md` explicitly endorses for capability
probing). The pilot session itself is not evidence and is cited nowhere as a
fact; only the two gated captures below (`raw/m4-20260827-run01`,
`raw/m4-20260827-run02`) are. Every pilot-informed prediction is re-tested,
independently, under the full gated process, and any case where the gated
result differs from the pilot-informed prediction is reported as a genuine
finding, not smoothed over.

## 6. Clean-room provenance

```
Clean-room provenance: OWN-SHADER
Inputs inspected: kernels/synth_move.metal, kernels/census.metal (our own
  MSL); the compiled AGX bytes tools/shdump extracts from them; our own
  tools/agx-isa assembler/disassembler output on those bytes.
Apple binary introspection: NONE
Reproduction: python3 -B verify.py --selftest && python3 -B verify.py --seqtest
  && python3 -B make_manifest.py --check && python3 -B verify.py --preflight
  && python3 -B run.py --execute --run-id m4-20260827-run01 ... (see
  CAPTURE_CONTRACT.json for the full sequence)
Evidence: raw/m4-20260827-run01/, raw/m4-20260827-run02/ (to be created by
  the two gated captures)
```
