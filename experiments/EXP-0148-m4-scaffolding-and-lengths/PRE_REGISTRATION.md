# EXP-0148 — pre-registration (frozen)

**Frozen:** 2026-08-28. **Target:** local Apple M4 / G16G (the only test target).
**Repo revision at freeze:** `f17938ee0105c8f1fb1e1c25be3aa22fa4a77a5c` (clean tree apart from
sibling experiments' untracked dirs — per `SUBAGENT_BRIEF.md` a moving `HEAD` from sibling
commits is NOT contamination; the gate below is on authored blob hashes, not `HEAD`).

**Frozen input hashes (sha256):**

| file | sha256 |
|---|---|
| `tools/agx-isa/db.json` | `6f082cc470c94e345a758cc87e4177e8c706892f12a1db12ab39fa50c94f94e9` |
| `tools/agx-isa/isadb.py` | `aa4791f63bf518aeb81a8ff982429ad2b1a78e5f7b98da53c73338ebe7751041` |
| `tools/agx-isa/roundtrip_test.py` | `783306cba12c1894e4f5b7ce7e5a534c1dc649d94195fe7a70c47019eff731b5` |

Working copies live in `work/isa_copy/` (baseline) and `work/variant_*/`. **The live
`tools/agx-isa/` tree is never written by this experiment.**

**Corpus:** `experiments/EXP-M4-13-full-corpus/hex`, 1080 files, 587 586 bytes, all compiled
from MSL committed under `experiments/EXP-M4-13-full-corpus/corpus/` (OWN-SHADER).

---

## 1. Questions

- **Q1 (Task 1).** For each of the 23 descriptors the dispatch names, is it
  **(a)** a continuation word of a longer parent instruction, **(b)** a genuine standalone
  instruction lacking characterization, or **(c)** a decoder artifact?
- **Q2 (Task 2).** What is the correct, modifier/op-select-aware length rule for the three
  descriptors flagged `emit_unsafe` with `length_rule_gaps.doc02_over_consumers_20260828`
  (`half_alu_fma12`, `falu2_ext8b`, `op04_len8`)?

## 2. Hypotheses (falsifiable, stated before the A/B runs and before any hardware work)

**H1 — the low-nibble-9 op-select class rule.**
For `byte0 & 0x0f == 0x9` (the float-ALU group), the instruction length is selected by the
**op-select field `byte+2 bits[2:0]` FIRST**, and only then by the `byte+4` extension bits:

```
opsel = byte+2 & 0x07
opsel in {0,1}  ->  length 4      (the compact accumulate/move form)
opsel in {4,5,6,7} -> length 6 + 2*(byte+4 & 0x03)
opsel in {2,3}  ->  UNRESOLVED, left at the current rule
```

The current rule applies `6 + 2*(byte+4 & 3)` to opsel 0/1 as well. Because a large fraction of
real AGX op leaders end in low nibble `7`/`f` (`&3 == 3`) or `1`/`5`/`9`/`d` (`&3 == 1`), the
rule then reads the *next instruction's leader byte* as its own length selector and produces a
spurious 8- or 12-byte token. `falu2_ext8b` (match: `opsel bit1 == 0 && bit2 == 0`, i.e. exactly
`opsel in {0,1}`, length 8) is predicted to be **entirely** this artifact.

**H2 — the same class rule holds for `byte0 == 0x10` (native fp16 ALU).**
`byte0 == 0x10` with `opsel in {0,1}` is the 4-byte compact half form. `half_alu_fma12`
(fixed length 12 for `byte0 == 0x10`) is predicted to be this artifact in the corpus, while the
own-MSL `k_hfma_abs` 12-byte instance (`10 02 1e 03 83 ...`, `opsel = 6`) is predicted to remain
12 bytes and keep decoding.

**H3 — `byte0 == 0x10` is an overloaded byte.**
`10 XX` is also a legal low-nibble-0 two-byte trailing-operand/pad word (`pad_operand`
high-nibble 1). Some corpus `half_alu_fma12` firings are that word, not a half-ALU op.

**H4 — the `0x?b` 10-byte modifier/logic class is `(byte+2 & 0x06) == 0x06`.**
The current dispatch enumerates `byte+2` low nibbles `{7, e, f}` (plus `0x17`). The
generalisation `(byte+2 & 0x06) == 0x06` adds exactly low nibble `6`, which is the class of the
external compiler engineer's 10-byte XOR example `4b 85 16 07 02 08 00 00 00 00` that
`EXP-0099` reported as undecodable under every family.

**H5 — `op04_len8` (`byte0 == 0x04`, fixed length 8) is not one instruction.**
Its predicted true length is short (2 or 4), with `byte0 == 0x04` being the `0x0c` `mov_imm`
family's datapath sibling (`byte0 low-3-bits == 0b100`, bit3 clear).

**Refuters (any one of these refutes the corresponding hypothesis):**

- **R-a** `roundtrip_test.py` drops below 302/302 under a candidate rule → the rule is wrong.
- **R-b** the strict-walk clean-file count **falls** below the baseline 803/1080, or the
  strict-walk leftover byte count **rises** above 395 390 → the rule mis-lengths real
  instructions.
- **R-c** the resync-walk gap-byte count **rises** above the baseline 4 902 → the rule creates
  new undecodable bytes.
- **R-d (hardware).** For H1/H2: splicing the bytes that the *current* rule claims are the
  parent's trailing field, but the *new* rule assigns to a following instruction, must change
  the program's output **in the way that following instruction predicts**. If instead the
  spliced byte is inert, or changes the output in a way only the parent could explain, H1/H2
  are refuted for that case.

## 3. Independent / controlled variables

- **Independent:** the `instr_length()` dispatch (one rule change per variant directory).
- **Controlled:** the corpus bytes, `db.json`, the walk algorithm, the metric definitions.
- **Hardware arm independent variable:** one spliced byte per run; everything else (carrier
  shader source, buffers, dispatch shape) held fixed.

## 4. Metrics (frozen, computed by `analysis/tokenize_corpus.py` + `roundtrip_test.py`)

| metric | baseline |
|---|---|
| `roundtrip_test.py` OK / FAIL | 302 / 0 |
| strict-walk clean files (of 1080) | 803 |
| strict-walk leftover bytes (of 587 586) | 395 390 |
| resync-walk gap bytes | 4 902 |
| resync-walk `<gap>` records | 2 451 |

A variant is **accepted as an improvement** only if roundtrip stays 302/0 **and** every
tokenization metric moves in the improving direction or stays equal.

## 5. Hardware arm (only if a splice decides (a) vs (b), per the dispatch)

- **Carrier:** our own MSL, compiled at runtime with `newLibraryWithSource:`; splice with
  `tools/shdump` + `tools/agxtest/persistrun.py` (persistent runner, faults logged and
  continued, per-request watchdog).
- **Case record:** one JSON object per case appended to `raw/<run_id>/sweep.jsonl` and
  `fflush`ed immediately, with the keys required by `experiments/FIELD-SWEEP-PROTOCOL.md` §4.
- **Timeouts:** 20 s per compile, 20 s per dispatch, 600 s per run; hard kill on overrun.
- **Stop rule:** after **two genuine hangs** in one arm, that arm STOPS and is reported PARTIAL.
- **Baseline before mutation:** the unmutated carrier's output is captured and committed first.

## 6. Known confounders

1. The corpus tokenizer's `--resync` mode manufactures instruction boundaries; any statistic
   taken from a token whose predecessor is `<gap>` is not evidence. Strict-walk numbers are
   primary; resync numbers are secondary and always reported as such.
2. Round-trip is blind to over-consumption by construction (the swallowed byte is re-emitted
   verbatim). Round-trip staying at 302/302 is a **non-regression gate, not evidence for** a
   length rule.
3. `EXP-M4-13` is compile-only; nothing inherited from it can exceed `corpus-correlation`.
4. A corpus-derived length rule is `STRUCTURAL` at best. Only the hardware arm can raise it.
5. The compiler may never emit some legal encodings, so "absent from the corpus" is not
   "impossible in hardware".

## 7. Deliverables

`analysis/scaffolding_classification.md`, `analysis/proposed_db_changes.json`,
`analysis/field_verdicts.json`, `RESULTS.md`, `PROGRESS.md`, plus this file.
**No `git commit`. No edit to `tools/agx-isa/*`, `docs/`, `PROVENANCE.md`, or `validation.json`.**

## 8. Clean-room statement

```
Clean-room provenance: OWN-SHADER (corpus + carrier) / HW-PROBE (splice arm)
Inputs inspected: our own MSL sources and the AGX bytes compiled from them;
                  our own tools/agx-isa database and tokenizer.
Apple binary introspection: NONE
Reproduction: analysis/*.py (commands in README.md)
Evidence: raw/
```
