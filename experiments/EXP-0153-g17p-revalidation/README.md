# EXP-0153 — G17P revalidation of the seven load-bearing M4 findings

**Target: Apple A18 Pro / G17P** (`Mac17,5`, `AGXAcceleratorG17P`, `applegpu_g17p`,
5 GPU cores, macOS 26.6 build 25G5043d, Metal family Apple9). Every result in
this directory is labelled `target: G17P`. No M4 label is carried onto a G17P
record, and no G17P label onto an M4 record.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal -- five verbatim copies of
  kernels already committed by EXP-0138/0139/0141/0146), the AGX bytes those
  compile to on G17P, and the outputs the GPU produced from them; for arm G,
  the own-MSL corpus at experiments/EXP-M4-13-full-corpus/corpus.
  tools/shdump, tools/agxtest and tools/agx-isa were used READ-ONLY and
  unmodified (the one persistrun hazard found was worked around by SUBCLASSING
  it in harness/run.py, not by editing the tool).
Apple binary introspection: NONE
Reproduction: see "Reproduction" below
Evidence: raw/g17p-20260830-run01/, raw/g17p-20260830-run03/,
  raw/g17p-20260830-reval01/, raw/g17p-20260830-run02/ (PARTIAL, retained),
  raw/smoke01/, raw/corpus_build.json
```

## Question

Every load-bearing ISA finding in this repository was measured on **M4 / G16G**
and its G17P status is `INFERRED`. The A18 Pro is now the test target. Which of
the seven highest-value M4 findings reproduce as **direct observation** on
G17P, and which refute? A refutation is the more valuable outcome — one
G16G↔G17P divergence (`tg_addr_compute`) is already open, so transfer is not a
safe default.

This experiment **re-runs** committed experiments rather than re-deriving them:
each arm uses the same carrier MSL, the same input vectors and the same
construction as the M4 experiment it revalidates, so a disagreement can only be
the hardware (or the G17P compiler's carrier layout, which is measured rather
than assumed).

## The seven arms

| arm | claim under test | M4 source | carrier | cases/run |
|---|---|---|---|---|
| A | `device_load` destination rule (`extmode`, `dst_lo`, `dst_ext9`, R ≤ 63) | EXP-0141 | `carrier_synth.metal` (whole-program synthesis) | 1035 |
| B | `falu2` source-class model + the inline 8-bit float immediate | EXP-0138 | `carrier_uni.metal` (MODE-A synthesis, live uniform file) | 195 |
| C | the native single-instruction 64-bit integer ADD (`iadd2.addsub`) | EXP-0146 | `k_u64sub.metal` (one-bit splice) | 7 |
| D | the register-file model: `r(R mod 64)` aliasing, and the fault bound | EXP-0112 + EXP-0139 | `carrier_uni.metal` + `carrier_dag.metal` | 386 |
| E | `ibfe`'s opposite out-of-range rules (`offset` literal, `width` mod 32) | EXP-0139 | `ialu_probes.metal` (two independent lowerings) | 195 |
| F | `mov_imm` is 7-bit; `imm_top = 1` does not write; `imm7 == 12` | EXP-0140 | `carrier_uni.metal`, read back as u32 | 140 |
| G | the four instruction-length-rule corrections, on G17P-compiled code | EXP-0148 | desk-side, over a G17P rebuild of the own-MSL corpus | — |

Full hypotheses, refuters, coverage and confounder handling:
**`PRE_REGISTRATION.md`** (frozen before any device run) and
**`CAPTURE_CONTRACT.json`**.

## Method

Whole-program **synthesis** (`isadb.assemble()` only — never a captured byte
string) for arms A, B, D and F; a **single-field splice** into our own compiled
carrier for arms C and E. Two gated capture runs, plus a revalidation pass over
every non-`ok` case. Arm G is compile-and-tokenize only.

Three things are **discovered on the target rather than assumed**, because
hard-coding an M4 value would have been an automatic stop:

1. every carrier's `_agc.main` length (`run.py :: prepare()`);
2. every splice anchor's offset, length and decoded fields
   (`anchors.find`, with `anchors.check_field_setter` round-tripped against
   `isadb` before the first case);
3. where the G17P container places our bound `constant float4&` — arm B sweeps
   `srcB_reg` 0..63 densely and *finds* the indices.

### Integrity, per FIELD-SWEEP-PROTOCOL §7

- Every output slot is bound as an **input file pre-filled with
  `0xDEADBEEF + i` per word**, so an unwritten word identifies itself;
  `not_written` is a distinct verdict and is retried, never recorded as a
  property of the swept value.
- Every synthesised carrier writes a **sentinel through a path that does not
  involve the instruction under test, before that instruction runs**
  (`out[4] = 8.0` on `synth`; `out[12] = 26.0` on `uni`; `out[4] = 33` on
  `dag`). The `bfe`/`shr`/`u64` splice carriers have no spare independent path;
  there the poison test plus the periodic health check are the integrity check,
  and that is stated as a limitation in `RESULTS.md`.
- The OS `kIOGPUCommandBufferCallbackError*` class is recorded on every non-OK
  case; `InnocentVictim` responses are retried and segregated and never by
  themselves make a case a `fault`; a `fault` verdict requires reproduction in
  ≥ 2 of 3 non-innocent attempts.
- The unmutated carrier is re-run every 120 cases; two consecutive failures
  abort the carrier with `cascade` recorded.
- Every request writes a **unique archive path** and unlinks it afterwards
  (EXP-0141's pilot measured ~7–8 % spurious `CMDBUF_ERROR` when one filename
  is reused).

### Concurrency

Bulk sweeps ran **unlocked and concurrently** with sibling experiments
(EXP-0154/0155/0156 were observed live on the device), per the orchestrator's
2026-08-30 direction that contamination is detectable rather than silent. The
revalidation pass took the GPU lease. `RESULTS.md` §"Concurrency" reports what
was running.

## Reproduction

On the neo (`~/agxre/EXP-0153`), with `AGX_TOOLS=$HOME/agxre/tools`:

```sh
bash harness/build.sh                       # rebuild shdump + agxrun_persist from our sources
python3 -B harness/run.py --run-id <id> --bin-dir bin --work work --raw raw/<id>
python3 -B harness/run.py --run-id <id>-reval --bin-dir bin --work work \
        --raw raw/<id>-reval --revalidate raw/<other>/sweep.jsonl --repeats 5
python3 -B harness/corpus_build.py --corpus work/corpus --names work/corpus_names.txt \
        --bin-dir bin --out work/hex_g17p --report raw/corpus_build.json --jobs 3
```

Analysis, in this repository:

```sh
python3 analysis/verdicts.py raw/g17p-20260830-run01 raw/g17p-20260830-run03 --out analysis
python3 analysis/tokenize_corpus.py ../../tools/agx-isa work/hex_g17p - work/g17p_corpus_summary.json
python3 analysis/tokenize_corpus.py ../../tools/agx-isa ../EXP-M4-13-full-corpus/hex - work/m4_corpus_summary.json
python3 analysis/tokenize_corpus.py --compare work/hex_m4_subset work/hex_g17p work/byte_identity.json
python3 analysis/make_field_verdicts.py
```

## Layout

```
PRE_REGISTRATION.md   frozen contract + its two numbered amendments
CAPTURE_CONTRACT.json machine-readable freeze (hashes, timeouts, budgets)
RESULTS.md            observations vs interpretation, per-arm verdicts, limits
PROGRESS.md           append-only milestone log
manifest.json         target/tool/revision metadata and artifact hashes
kernels/              our own MSL (verbatim copies of the M4 carriers)
harness/              case matrix, instruction builders, executor, corpus builder
analysis/             verdict scorer, corpus tokenizer, the side-by-side report
raw/                  immutable captures, including the retained PARTIAL run02
```

## What this experiment does NOT do

It does not edit `tools/agx-isa/db.json`, `validation.json`, `docs/` or
`PROVENANCE.md`, and it commits nothing. `analysis/field_verdicts.json` is a
proposal for the orchestrator to merge.
