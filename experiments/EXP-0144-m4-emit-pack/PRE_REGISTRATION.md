# EXP-0144 — PRE-REGISTRATION (frozen before any recorded capture)

**Frozen:** 2026-08-28. Repository revision recorded in `CAPTURE_CONTRACT.json`
(`git_rev`), pinned here and NOT re-gated on live `HEAD` (CODEX: sibling experiments
land continuously; a capture is valid if the *authored blob hashes* match).

**Target:** local Apple M4 / G16G, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4.
The A18 Pro is hands-off. No SSH anywhere. Nothing here is A18/G17P-validated.

**Batch:** this experiment runs in orchestrator batch 2 together with EXP-0140
(MOV+CF) and EXP-0147 (pipeline misc) — **three** GPU-contending experiments, per
`FIELD-SWEEP-PROTOCOL.md` §7.

---

## 1. Question

`pack_convert`, `unpack_convert` and the seven `cvt_*`/`packed_half2_hi` family
members gate every format conversion a driver performs. Across the nine, **51
fields** are below emitter grade in `tools/agx-isa/validation.json` (`untested`,
`tokenization-only`, `corpus-correlation`, or `single-template-inference`).

> For each of those 51 fields: **can an emitter choose an arbitrary value and get
> documented behaviour** — and if not, what does the hardware actually do?

The bar is `docs/evidence-classification.md` §2 `hardware-run`: arbitrary operands
*executed*, boundaries and holes included, silent zeros recorded.

## 2. Falsifiable hypotheses

- **H1 (operand fields are register selectors).** `pack_convert.src`,
  `unpack_convert.reg_sel`, and the `cvt_*` `dst`/`src` bytes select GPRs under a
  fixed scale. *Refuter:* sweeping the byte over 0..255 with six distinct
  host-known values live in distinct registers produces **no** value that yields
  the conversion of a different live value — i.e. the byte is not a register
  selector at all.
- **H2 (`unpack_convert` byte+2 is open).** Commit `2b1cbc50` relaxed the match so
  only bit1 was ever pinned by evidence. *Refuter:* a dense 0..255 sweep of byte+2
  shows behaviour depending on bits other than bit1, or shows bit1 inert here.
- **H3 (the 0x54/0x56 bit position is NOT one mechanism).** EXP-0089/0119 found ≥4
  distinct behaviours across families. *Prediction:* `pack_convert` byte+2 and
  `unpack_convert` byte+2 will each show their own behaviour, not a shared one.
  *Refuter:* both behave identically to `falu2`'s later-reader-only corruption.
- **H4 (format is selected by a field we can find).** The pilot showed
  `pack_convert` byte+9 `0x82`→`0x42` converts unorm2x16 into snorm2x16, and
  byte+8 `0x45`→`0x00` disables conversion. *Prediction:* the byte+8/byte+9 sweep
  crossed with semantic vectors yields an emittable format table. *Refuter:* no
  value of either byte reproduces a second, host-predictable format exactly.
- **H5 (rounding).** `pack_float_to_unorm2x16` ties round-to-nearest-**even**
  (EXP-0102). **Competing pre-registered model:** ties round **DOWN**, as EXP-0133
  found for the unorm16 *storage* path. Exactly one must fail.
- **H6 (bfloat rounding).** `cvt_bf16` float→bfloat rounds RNE. **Competing model:**
  truncate toward zero, as EXP-0079 found for reduced-float *stores*. Exactly one
  must fail.

## 3. Independent / controlled variables

Independent: one byte of the instruction under test, or one whole wide field, or the
input vector. Controlled: carrier, buffer bindings, grid/threadgroup (1/1), input
vector (fixed for the field arms), every other byte of the instruction, compiler
flags (`--no-fast-math`), tool binaries.

## 4. Method — five arms (`harness/casematrix.py`, frozen; 22,237 cases)

| arm | n | what |
|---|---|---|
| `C` | 19 | baselines, positive controls, pre-registered FALSIFIERS |
| `S` | 70 | unspliced carrier over semantic vectors; full host oracle (rounding/ties) |
| `F` | 15,829 | every byte of the instruction, all 256 values (byte 0 bounded — see §6) |
| `W` | 175 | whole-field values for `fmt_word` (40b) and `convert_desc` (32b) |
| `X` | 6,144 | the format-selector bytes × 8 semantic vectors, so a discovered format code gets emittable semantics |

**Carriers** (`kernels/carriers.metal`, our own MSL): one per instruction, each
holding six distinct host-known values live in distinct registers *across* the
instruction and storing several registers after it, so an operand-field sweep can
identify which register a value selects and a destination-field sweep can be seen
redirecting the result.

**MODE A vs MODE B.** Eight instructions are reached by splicing bytes of the
compiler's own encoding in place (MODE B). `packed_half2_hi` **cannot be provoked
from any MSL shape tried** — every packed-half2 form yields `half_alu` plus a
4-byte `0x18`-leader companion, never `byte+2 == 0x24` — so it is tested MODE A:
a synthesised `98 04 24 00 00 20` replaces the carrier's own 6-byte `half_alu`.

**Oracle** (`harness/oracle.py`, self-test must PASS): host-computed, GPU-
independent, exact `Fraction` arithmetic at every tie. Nothing in it consults the
device.

## 5. Contamination guards (`FIELD-SWEEP-PROTOCOL.md` §7 + EXP-0141)

1. **Integrity sentinel.** Every carrier writes buffer 2 through a path sharing
   nothing with the instruction under test: word0 a constant, word1 derived from an
   input load. Three-way classification — `clean` / `perturbed` (ran, but the splice
   desynchronised the downstream stream) / `absent` (**nothing executed**). Only
   `absent` under `STATUS OK` is `invalid_run`; it is retried up to 3× and never
   scored. This is EXP-0141's contamination mode, whose signature — a zero-filled
   output buffer — is on this ISA indistinguishable from a genuine wrong-field value.
2. **Unique splice-archive path per request** (EXP-0141 measured ~8% phantom
   `CMDBUF_ERROR` from a shared path: 28/360 vs 0/360).
3. **No `fault`/`hang` from one observation.** Every faulting case triggers a carrier
   **baseline re-validation** and then a re-run; it is recorded `fault` only if it
   reproduces. A failed baseline marks the case `invalid_run` (cascade), not a result.
4. **The OS fault-classification string is recorded verbatim** (`err`), so
   `...ErrorInnocentVictim` (machine evidence) is separable from
   `...ErrorHang` (encoding evidence). InnocentVictim responses are retried.
5. **Periodic baseline re-validation** every 250 cases, logged in `01_summary.json`.
6. **Concurrency is reported** in `RESULTS.md`.

## 6. Deliberate deviation from "sweep all 2^w", and why

Byte 0 is the **opcode leader**, not an operand field; changing it changes the
instruction's *length* and desynchronises the whole downstream stream. The smoke run
produced a genuine `kIOGPUCommandBufferCallbackErrorHang` from `cvt_bf16` byte0=0xFF,
and this host has **no out-of-band recovery**. Byte 0 therefore gets a bounded
24-value probe: all 16 values of its high nibble with the match-forced low nibble
preserved (that high nibble *is* the `dst` field in `cvt_f2h_dst`, `cvt_bf16`,
`packed_half2_hi`), plus 8 off-match values testing whether the low nibble is
load-bearing. **Every operand byte still gets the full dense 0..255.**

## 7. Stopping rules

- Genuine hangs: **area = (instruction, swept byte)**. Two genuine hangs in one area
  stop that area; its remaining cases are recorded `skipped_after_hangs`. A hang while
  sweeping the opcode leader says nothing about an operand byte five positions along,
  so stopping the whole instruction would discard good coverage; stopping the byte
  stops the actually-wedging configuration.
- **Global cap of 10 genuine hangs** stops the entire run and it is reported PARTIAL.
- Per-request watchdog 8 s (`persistrun`), child killed and restarted on a wedge.
- Append + `flush` + `fsync` per case; `PROGRESS.md` entry per milestone.

## 8. Gate

Two runs under different run ids (`run01`, `run02`), never reusing an id. The gated
comparison is over `(i, name, instr, field, value, bytes, observed, oracle, match,
outcome, validity, decode)`. Records whose `validity != valid`, and every `err`
containing `InnocentVictim`, are **excluded from the gate** (machine evidence, not
encoding evidence) and reported separately, exactly as EXP-0136 had to.

## 9. Known confounders

- Register allocation is the compiler's; a field value that selects a register the
  carrier never wrote is indistinguishable from an inert field. Mitigated by six
  distinct live values plus a never-written register as a negative control.
- A splice that changes the instruction length desynchronises everything after it;
  the `perturbed` sentinel state detects exactly this and it is reported separately
  from a clean silent zero.
- `pack_convert.fmt_word` (40b) and `unpack_convert.convert_desc` (32b) are swept
  per-byte-dense plus a whole-field value set — **not** 2^40 / 2^32 coverage. The
  range is reported as what it is.
- Two `db.json` self-consistency issues are already visible from the pilot and are
  recorded under `db_defects`, not fixed here (the orchestrator owns `db.json`).

## 10. Not in scope

Editing `db.json` / `validation.json` / `docs/` / `PROVENANCE.md`; committing; the
A18; render/fragment-stage forms of these instructions (compute only).
