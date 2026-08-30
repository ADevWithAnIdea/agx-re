# EXP-0205 — RESULTS

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, macOS 26.6,
Metal family Apple9), `192.168.170.254`. **Measured SIMD width: 32** — read back
per lane from `threads_per_simdgroup`, in every gated run, never assumed.

**Verdicts are on the six independent axes of
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §2.** A result on one axis never implies a
result on another, and the legacy `docs/evidence-classification.md` label is
**never rounded up from liveness**. Exact numerators and denominators throughout.

Machine-readable: `analysis/field_verdicts.json` (revision B, the one to merge),
`analysis/field_verdicts_revA.json` (revision A, retained and reclassified),
`analysis/report_revA.txt`, `analysis/report_revB.txt`.

---

## 1. Verdict table

| field | start/width | geometry | liveness | semantics | recipe | target | repro | legacy label |
|---|---|---|---|---|---|---|---|---|
| `simd_reduce.op` | 8 / 8 | geometry-mapped | **live** | **semantically-mapped** | not-generated | G17P-direct | independently-confirmed | **`hardware-run`** |
| `simd_reduce.dtype` | 56 / 8 | geometry-mapped | **live** | **semantically-mapped** | not-generated | G17P-direct | independently-confirmed | **`hardware-run`** |
| `simd_shuffle.dir` | 7 / 1 | geometry-mapped | **live** | **semantically-mapped** | not-generated | G17P-direct | independently-confirmed | **`hardware-run`** |
| `simd_shuffle.cache` | 17 / 1 | geometry-mapped | **live (contextual)** | bounded-map | not-generated | G17P-direct | independently-confirmed | `isolated-byte-diff` |
| `simd_ballot.pred` | 12 / 4 | geometry-mapped | accepted-inert | hypothesis | not-generated | G17P-direct | independently-confirmed | `untested` |
| `simd_ballot.cache` | 16 / 8 | geometry-mapped | accepted-inert | bounded-map | not-generated | G17P-direct | independently-confirmed | `untested` |

**`compiler_recipe` is `not-generated` for all six, and that is not a formality.**
Every case in this experiment mutates ONE field of a compiler-emitted program.
Nothing here builds a whole `simd_*` instruction from documented rules, so Gate D
was not attempted and no field here is an emittability proof.

## 2. Exact counts (revision B, both gated runs)

| field | moved / dispatched·arms | arms | with detection power | arms moved | sem match/checked | mismatch | ledger verified | distinct actual bytes | min cross-run agreement | faults+hangs | measurement failures |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `simd_reduce.op` | 896 / 1024 | 4 | 4 | 4 | 8/15 | 7 | 2048/2048 | 1024 | 100.000 % | 0 | 0 |
| `simd_reduce.dtype` | 847 / 1024 | 4 | 4 | 4 | 11/15 | 4 | 2048/2048 | 1024 | 99.609 % | 1 (contaminated, §7) | 0 |
| `simd_shuffle.dir` | 5 / 10 | 5 | 5 | 5 | 6/6 | 0 | 20/20 | 10 | 100.000 % | 0 | 0 |
| `simd_shuffle.cache` | 3 / 10 | 5 | 5 | **3** | 7/10 | 3 | 20/20 | 10 | 100.000 % | 0 | 0 |
| `simd_ballot.pred` | **0** / 96 | 6 | 6 | 0 | 6/6 | 0 | 192/192 | 96 | 100.000 % | 0 | 0 |
| `simd_ballot.cache` | **0** / 1536 | 6 | 6 | 0 | 1536/1536 | 0 | 3072/3072 | 1536 | 100.000 % | 0 | 0 |

Revision A independently reproduced every movement count on its own 11 carriers
(`op` 896, `dtype` 848, `dir` 3/6, `cache` 2/6, both null fields 0).

**Gate A is met by measurement, not assumption.** Every case re-reads the spliced
archive *from the file handed to `newLibraryWithURL:`*, extracts the instruction
bytes at `main_off + off`, decodes the field back out of them, and records
`requested_value`, `requested_bytes`, `actual_bytes`, `decoded_value`,
`program_sha256`, `program_len`, `db_sha256`, `harness_sha256`.
**5300 / 5300 target-arm cases verified; zero `ledger_mismatch`; zero missing.**
Distinct actual encodings equal the dispatched value count on every arm, and
every difference is confined to the field's own span — so no `match`-bit
collision aliased two values onto one encoding.

---

## 3. `simd_reduce.op` — LIVE, and only three bits wide

**Observed.** On `sr_sum` (integer reduce carrier, `opcls=1`, `dtype=3`), with
32 unique per-lane inputs containing one negative word:

| op | observed | host-predicted semantic | match |
|---|---|---|---|
| 0 | `0xFFFFFFFF` | `ior` reduce | ✓ |
| 1 | `0x00000C14` | `isum` reduce (baseline) | ✓ |
| 2 | `0x000000D5` | `smax` reduce | ✓ |
| 3 | `0xFFFFFF00` | `umax` reduce | ✓ |

Four values, four **distinct** predicted 32-word vectors, four matches, zero
mismatches on that arm. Three of the four are non-baseline values.

**Bit structure, measured not assumed.** `analysis/report.py` compares the
observed vector at every value `v` against the vector at `v XOR (1<<b)`, in both
runs. On **all four** reduce carriers: **live bits [2:0], inert-within-field
bits [7:3]**. The observation repeats with period 8 across the whole 256-value
sweep. `op` is a **3-bit opcode occupying an 8-bit byte**.

**Interpretation, and its limits.** `op` selects the reduction operation. The
`{0,1,2,3} → {ior, isum, smax, umax}` map is established **at `opcls=1` with
`dtype=3`**. It does **not** generalise: on `sr_max` (`dtype=7`) `op=0` and
`op=3` returned the *exclusive-scan* shapes of `ior`/`umax`, and on `sr_scan`
(`dtype=9`) the predictions for `op≠1` all failed. **`op` and `dtype` are not
independent** — that is the 7 mismatches in the table above, and it is a result,
not noise. `op` values 4..7 on the integer carriers returned each lane's own
input (identity, indistinguishable on these inputs from a running unsigned max);
no prediction was made for them and none is claimed.

**Ambiguity we could not remove.** With one negative word, `umax` and `smin`
predict the *same* vector (`0xFFFFFF00`). `op=3` is consistent with either. A
future input set needs a large positive value as well as a negative one.

## 4. `simd_reduce.dtype` — LIVE, and it selects the SCAN SHAPE

**Observed.** On `sr_scan` (`op=1`, baseline `dtype=9`), all four predictions
matched with zero mismatches on that arm:

| dtype | observed shape | host-predicted | match |
|---|---|---|---|
| 3 | all 32 lanes `0x00000C14` | `isum` **reduce** | ✓ |
| 7 | all 32 lanes `0x00000C14` | `isum` **reduce** | ✓ |
| 9 | per-lane prefix sums | `isum` **inclusive scan** (baseline) | ✓ |
| 11 | per-lane prefix sums shifted by one | `isum` **exclusive scan** | ✓ |

Reduce, inclusive scan and exclusive scan differ in **31 of 32 lanes**. A
single-word read-back could not have told them apart at all; this is the whole
reason for per-lane read-back.

**Bit structure.** Live bits `[0,3]` on `sr_sum` and `sr_max`, `[0,1,3]` on
`sr_scan`, `[0,1,2,3,5]` on the float carrier. **Bits 4, 6 and 7 are
inert-within-field on all four carriers**; the integer carriers repeat with
period 16. Even values of `dtype` returned each lane's own input on the integer
carriers, i.e. bit 0 behaves as an enable. That last sentence is an
**observation with a plausible reading, not a semantic map**.

## 5. `simd_shuffle.dir` — LIVE, fully mapped, and its own falsifier

**Observed**, on 5 arms carrying **both** compiler-chosen baseline values:

| carrier | baseline | `dir=0` | `dir=1` |
|---|---|---|---|
| `sh_bc` | 0 | every lane reads lane 5 ✓ | lane *t* reads lane *t*^5 ✓ |
| `sh_xor` | 1 | every lane reads lane 5 ✓ | lane *t* reads lane *t*^5 ✓ |
| `sh_reuse` | 0 | ✓ | ✓ |
| `lb_shuffle_ld` / `lb_shuffle_alu` | 0 | ✓ | moved (no prediction registered) |

6/6 semantic checks matched, 0 mismatches. **Each carrier's spliced result is
the other carrier's independently measured baseline vector** — the strongest
cross-check this design can produce, and it was pre-registered as H4's
prediction before any splice was scored. 32 distinct per-lane source values make
`bcast:lane5` and `xor:mask5` completely different vectors.

## 6. `simd_shuffle.cache` — **LIVE. The two previous INERT verdicts were a carrier failure.**

This is the field the dispatch flagged, and the suspicion was correct.

**Observed.** Byte+2 bit 1, both values, on 5 arms:

| carrier | compiler baseline | `cache=1` | `cache=0` |
|---|---|---|---|
| `sh_bc` | **1** | correct broadcast ✓ | **`0x00003039` on every lane** |
| `sh_xor` | **1** | correct xor-shuffle ✓ | **`0x00003039` on every lane** |
| `lb_shuffle_ld` (litmus) | **1** | correct ✓, atomic total correct | **silent zero on every lane; cross-threadgroup atomic total WRONG** |
| `sh_reuse` | **0** | correct ✓ | correct ✓ (baseline) |
| `lb_shuffle_alu` (litmus) | **0** | correct ✓ | correct ✓ (baseline) |

`0x00003039` is **12345 — this experiment's integrity-sentinel constant**. With
the bit cleared, the shuffle's source read returned the contents of an unrelated
register rather than the loaded operand. On the litmus carrier the same
mutation produced a silent zero, and the post sentinel and readback plan 3 (the
operand re-read after two barriers) were **both still correct** — so the program
ran to completion and the operand register itself was intact; only the
instruction's own source read was wrong.

**The separating context, measured by a matched pair.** `lb_shuffle_ld` and
`lb_shuffle_alu` are the *same kernel with the same dispatch*, differing only in
how the operand was produced (device load vs pure ALU on the thread id). Their
compiled instructions have **identical `srctype` (byte+5 = 0x04) and identical
`src` (byte+4 = 0x03)** — and the compiler chose `cache=1` for the load-seeded
one and `cache=0` for the ALU-seeded one. The bit is live in the first and inert
in the second.

**What this licenses, stated conservatively.** The mechanical split in
`analysis/field_verdicts.json` separates the arms exactly by *the compiler's own
chosen value*: the field moved on every arm where the compiler set it to 1 and
on none where it set it to 0. The safe emitter rule from this evidence is
therefore **"1 is safe everywhere we tested; 0 is safe only in the contexts
where the compiler itself chose 0"** — `cache=1` was confirmed correct on
`sh_reuse`, whose own baseline is 0, so 1 is not merely template-copying.

**Why it is `isolated-byte-diff` and NOT `hardware-run`.** The value that
*moved* produced an **unpredicted** result: we had registered no model that
predicts `0x00003039` or the silent zero. Under Gate C, stable movement with no
matching semantic model is *liveness*, not semantics, and may not be rounded up.
`simd_shuffle.cache` is **live with a bounded map and an open semantic role**.

**Why the earlier sweeps missed it.** EXP-0163's four carriers and EXP-0172's
`deadsrc` differ in source *reuse*, not in source *provenance*. Both readings of
the public `cache`/`discard` documentation point at reuse, and both were tested;
the dimension that actually mattered was where the operand came from. EXP-0129
had already found the same provenance split on a different field. This is
`docs/isa/emit-worklist.md`'s rule working exactly as written.

## 7. `simd_ballot.cache` — accepted-inert over the tested envelope; **global role unknown**

**`inert in 0..255 dense × 6 carriers × 2 gated runs on G17P; global role
unknown.`** 1536 semantic checks, all matching the baseline prediction; 0 moved;
100.000 % cross-run agreement; 3072/3072 ledger-verified; every bit of the byte
inert-within-field on every carrier.

This is **not** promoted, and the wording above is deliberate. What was and was
not exercised:

| dimension | exercised? |
|---|---|
| Full encodable range (256/256), directly on G17P | yes |
| Detection power — generic control on the same instruction and occurrence | yes, `psrc` moved 13/16 on all 6 carriers |
| **In-dimension control** — a `dst` value that changes the operand's post-instruction content, with the later read on the output path | **yes: fired on 3 carriers** (`sec_moved` 2–4 values each) |
| Source **reuse** across the instruction, under register pressure (16 live loads) | yes (`sb_reuse`) |
| **Multi-invocation ordering**: 4 threadgroups × 2 simdgroups, cross-simdgroup threadgroup-memory exchange, cross-threadgroup device atomic checked against a host total, operand re-read after two barriers | **yes (revision B litmus, `lb_ballot_ld` / `lb_ballot_alu`)** |
| Operand **provenance** (device-load vs ALU) | yes (the `_ld` / `_alu` litmus pair) |
| Distinct **compiler-chosen baseline values** | **NO — all six carriers compile to byte+2 = 0x54.** |
| **Retention / occupancy**, whose only observable is timing and power | **NO, and a functional read-back cannot express it.** |

The last two rows are the honest boundary. `GPUTIME_NS` is recorded on every
case and is reported as an observation only: across the 256 `cache` values the
per-arm spread is at or below the timer's own quantisation on the
single-simdgroup carriers (median 1500 ns, σ 27–54 ns), which is nowhere near
enough to resolve a register-cache hint. **This experiment cannot decide whether
byte+2 is a performance hint on `simd_ballot`.**

## 8. `simd_ballot.pred` — inert, and `db.json`'s attribution is REFUTED

**`inert in 0..15 dense × 6 carriers × 2 gated runs on G17P; global role
unknown.`** 0 moved; exactly **one** distinct observed vector across all 16
values on every arm; 100 % agreement; 192/192 ledger-verified.

`db.json` models byte+1's high nibble as `0x0 = active_mask/any/all` vs
`0x1 = ballot(predicate)`. Three independent observations contradict that:

1. **Calibration, before any splice:** our compiler emits byte+1 = `0x07`
   (`pred = 0`) for **both** `simd_ballot(predicate)` and
   `simd_active_threads_mask()`. The forms differ in byte+5 (`psrctype`
   `0x00` vs `0x02`) and the byte+7..9 tail (`58 22 12` vs `08 02 18`).
2. **The gated sweep:** no value of `pred` in 0..15 changes anything, on six
   carriers whose controls all fire — including two carriers that *do* compute
   the two different ballot forms, so the dimension is demonstrably expressible
   and this field is demonstrably not what expresses it.
3. **The adversarial probe** (`raw/adversarial01/`, **single observations, not
   gated — hypothesis-grade**): on the ballot carrier, `psrctype` alone changed
   nothing; the tail alone gave a silent zero; **`psrctype` + tail together
   turned the result from the predicate mask `0x6C8AF35D` into `0xFFFFFFFF`, the
   all-active mask** — and **byte+6 (`form`) alone, `0x00 → 0x14`, did the same**.

**`db_defects` entry** (recorded in `analysis/field_verdicts.json`, **not**
written into `db.json`, which the orchestrator owns): the ballot-form selection
attributed to `simd_ballot.pred` is carried by byte+5 / byte+6 / byte+7..9. The
`pred` field as modelled is inert across its full range on G17P.

## 9. Faults, hangs, contamination, and what is NOT claimed

- **Gated runs, revision B: 1 non-clean case in 10 184.** `sr_scan` `dtype=216`
  in runB01: three attempts, all `CMDBUF_ERROR`, with **seven
  `InnocentVictim`** classifications, one `ErrorHang` and one
  `ImpactingInteractivity`. The reversed-order run recorded **zero** non-clean
  cases at the same value. This is scored as **contamination from a sibling
  experiment, not a hardware fault**, and no fault claim is made for it.
  Gate E requires fault claims to be repeated in isolation; that was not done,
  so none is made.
- **Revision A, both runs: 0 non-clean cases in 7630.**
- **A contiguous hazard, found and deliberately not mapped.** `pilot01`
  dispatched `dst = 192` on both reuse carriers and got 3/3
  `CMDBUF_ERROR`/`ErrorHang` — the same `dst[7:6] == 0b11` wall EXP-0168 mapped
  on `frag_color_pack.dst`. Amendment 1 (frozen before any gated run) trimmed
  the two `dst` **control** arms to 0..191. `dst` is not a field under test
  here; mapping that wall on `simd_ballot.dst` / `simd_shuffle.dst` is a
  **named debt**, recorded rather than silently skipped.
- **The machine was NOT quiet.** `env.json` in every run records concurrent
  GPU work (EXP-0199/0200/0201/0202/0204/0206/0207). Gate E's "quiet machine"
  condition was not available to this experiment. What it has instead is
  EXP-0160's filter — two agreeing clean dumps win outright, because
  contamination can destroy an observation but never fabricate a coherent one —
  plus poisoned read-back, pre/post sentinels, majority-of-3 on every non-OK
  case, and `InnocentVictim` retried before anything is concluded.
- **Movement never counts a fault, a hang, `not_written`, an `invalid_run` or a
  measurement failure**, and the tokenized mnemonic of every mutated
  instruction is recorded so "movement" that is really a different instruction —
  or our own disassembler failing to decode — is visible rather than scored.

## 10. Limitations

1. **No compiler recipe.** Gate D untouched; every program here is a mutated
   compiler donor. None of these six fields is an emittability proof.
2. **`simd_ballot.cache`: one baseline value.** All six ballot carriers compile
   to byte+2 = 0x54, so the "compiler chose the other value" contrast that made
   `simd_shuffle.cache` decidable does not exist here.
3. **`op` × `dtype` interaction is unmapped.** They are demonstrably not
   independent; only the pairwise points listed above are established.
4. **`umax` vs `smin` at `op=3`** is unresolved on these inputs.
5. **Timing** cannot be resolved at this dispatch size; the retention reading of
   `cache` is untested, not refuted.
6. **The adversarial probe is single-observation.** Its conclusions about
   byte+5/6/7..9 are hypothesis-grade and need their own gated experiment.
7. **`_alu` litmus provenance is not perfectly isolated**: the ALU codeword is
   computed from `thread_position_in_grid`, so "no memory traffic" and "system
   value in the dependence chain" are not separated.

## 11. Recommended next experiments

1. **Gate D for `simd_reduce`**: generate a complete `simd_reduce` from
   documented rules — `op` and `dtype` now have a semantic map to generate
   from — and check every output word against a host prediction.
2. **`simd_shuffle.cache` semantics**: sweep byte+2 bit 1 against byte+4 (`src`)
   and byte+5 (`srctype`) as a pairwise covering array over several producer
   classes, and register a model that predicts *what* the wrong read returns.
3. **`simd_ballot` form selector**: promote the adversarial probe into a gated
   experiment over byte+5, byte+6 and byte+7..9, with a `db.json` correction.
4. **The `dst[7:6] == 0b11` wall** on `simd_ballot.dst` / `simd_shuffle.dst`, as
   a declared hang-tolerant mapping pass.
5. **`op` × `dtype` cross product** on a reduce carrier, to state the predicate
   under which each `op` value keeps its meaning.

## Clean-room attestation

```
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: only our own MSL in kernels/ and the machine code compiled from
                  it. The public dougallj/applegpu notes in gpu_knowledge/ were
                  the source of HYPOTHESIS H5 only, never of a value or encoding.
Apple binary introspection: NONE
Reproduction: README.md -> Reproduce
Evidence: raw/prefreeze/{calibration,calibration02,calibration06_litmus}.json,
          raw/pilot01/, raw/g17p_20260830_run01, run02, runB01, runB02,
          raw/adversarial01/, CAPTURE_CONTRACT.json, analysis/field_verdicts*.json
```
