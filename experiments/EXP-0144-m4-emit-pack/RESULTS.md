# RESULTS — EXP-0144: is the Apple9 pack/convert family EMITTABLE?

**Clean-room provenance**

```
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for IEEE-754 and the MSL
  format-conversion definitions, used only to write the host oracle, never to
  source an Apple9 encoding fact)
Inputs inspected: kernels/carriers.metal + kernels/anchors.metal (authored here)
  and the machine code compiled from them; tools/agx-isa/db.json (this project's
  own, read-only)
Apple binary introspection: NONE
Reproduction: README.md "Reproduction"
Evidence: raw/m4_20260828_run03/, raw/m4_20260828_run05/ (append-only JSONL);
  three retained partial captures with their own PARTIAL.md; analysis/*.json
```

**Target: local Apple M4 / G16G only** (10 GPU cores, macOS 26.6.2 build 25G82,
Metal 4). The A18 Pro was not touched. Nothing here is A18/G17P-validated.

**Concurrency (`FIELD-SWEEP-PROTOCOL.md` §7.4).** The promoted evidence
(`m4_20260828_rv01__*`) was captured while **two** other GPU-contending experiments
ran — EXP-0138 (FALU) and EXP-0140 (MOV+CF) — three in total, not ten. Contention was
directly visible and is quantified in §6: **853 `…ErrorInnocentVictim` attempts** were
discarded and re-run, and the host's `MTLCompilerService` collapsed **twice**, the
second time killing the last three shards.

**EVIDENCE BASE — read this before any number below.** Everything promoted here comes
from the **revalidation captures `m4_20260828_rv01__*` only**. The earlier captures
`run01`–`run05` are retained as append-only history and **back no label**: they were
taken across a window in which a GPU test destabilised WindowServer and took
`MTLCompilerService` down machine-wide. Where the revalidation and an original
disagree, **the revalidation wins**, and every field's `note` records the comparison.

---

## 0. Headline

| | |
|---|---|
| Blocking fields at dispatch | **51** |
| **Survived revalidation at emitter grade** | **33** (31 `hardware-run`, 2 `isolated-byte-diff`) |
| Still `untested` | **18** |
| Previously claimed from the contaminated runs | ~~44~~ — **retracted** |
| Instruments revalidated | **6 of 9 complete**, 1 partial, 2 never ran |
| `db.json` defects found | **8**, recorded under `db_defects`, none patched here |

**The 44-of-51 figure in the earlier version of this file is withdrawn.** It rested
on captures taken during the WindowServer/`MTLCompilerService` failure. Re-measuring
every case with a majority vote, and refusing to carry any label forward from those
runs, gives **33**. The 11-field difference is almost entirely *coverage*, not
contradiction: two instruments (`cvt_bf16`, `packed_half2_hi`) and most of a third
(`cvt_f2h_dst`) were never re-measured, so their fields return to `untested` rather
than inherit an inadmissible label. Of the measurements that *were* repeated, only
**92 of 13,783 (0.67 %)** were overturned.

The single most useful outcome is not a label count: **`pack_convert`'s and
`unpack_convert`'s operand structure in `db.json` is wrong**. Both model several
live operand bytes as one opaque raw descriptor (`fmt_word`, `convert_desc`). The
sweeps show those bytes are the destination register, the two per-lane source
registers, and an emittable **format selector** with a decoded code table. An
implementer following `db.json` today cannot emit either instruction; with §2 they
can.

---

## 1. What was actually run

The frozen 22,237-case matrix (`harness/casematrix.py`, sha256 `00529a0a…`) was
**re-measured** case-by-case by `harness/revalidate.py`:

* **majority of 3 repetitions**, escalating to **5** whenever the three disagreed;
* an attempt whose OS fault string is `…ErrorInnocentVictim` is a sibling
  experiment's fault surfacing in our command buffer → **discarded and re-run**;
* an attempt returning `STATUS OK` with the integrity sentinel **absent** executed
  nothing (EXP-0141's mode) → **discarded and re-run**;
* a `fault`/`hang` verdict is only accepted if the unmutated carrier baseline passes
  immediately afterwards;
* the carrier baseline is re-validated **every 100 cases** (EXP-0141's cadence).

**Schema fix carried into the revalidation.** A case that is never dispatched now
records `outcome: null, validity: "not_run"`. The original runs recorded skipped
cases as `outcome:"hang"`, which is why an outcome-only cross-run comparison of
run03/run04 reported 58.2 % divergence (§6.1).

| shard | cases | baselines | status |
|---|---|---|---|
| `rv01__pack_convert` | 6,540 | 65/65 | complete |
| `rv01__unpack_convert` | 3,956 | 39/39 | complete |
| `rv01__cvt_i2f` | 1,825 | 18/18 | complete |
| `rv01__cvt_i2f_src` | 1,824 | 18/18 | complete |
| `rv01__cvt_f2i` | 2,338 | 23/23 | complete |
| `rv01__cvt_f2h` | 1,311 | 13/13 | complete |
| `rv01__cvt_f2h_dst` | 294 | — | **PARTIAL** — killed mid-shard by the second `MTLCompilerService` collapse |
| `rv01__cvt_bf16` | 0 | — | **NEVER RAN** — carrier compile failed, same collapse |
| `rv01__packed_half2_hi` | 0 | — | **NEVER RAN** — same |
| **total** | **18,088** | **176/176** | |

**Quality of the revalidated set:** 18,082 measured, **17,876 unanimous at 3
repetitions (99.4 %)**, 106 escalated to 5, **0 indeterminate**, 176/176 baseline
checks passed, **4 genuine hangs in 18,088 records (0.02 %)**. 853 InnocentVictim
attempts and 312 sentinel-absent attempts were discarded and re-run. Observed OS
fault classes, kept separate: `…Caused GPU Hang Error` (1,447 attempts),
`…Discarded (victim of GPU error/recovery)` (853), `…Caused GPU Address Fault Error`
(24), watchdog `no response within 8.0s` (21), `…Impacting Interactivity` (7).

### Controls — all passed, in the revalidated data

* **All carrier baselines reproduced the host oracle**, 176/176 across every shard.
* **Every pre-registered falsifier failed the anchor oracle, as pre-registered.**
  Each instrument therefore demonstrably *can* show a difference.
* Semantic vectors matched the host oracle exactly for every revalidated instrument.

## 2. `pack_convert` — the model in `db.json` is wrong, and the real one is emittable

`db.json`: `src_desc`(+1) `fmt_class`(+2) `src`(+3) `mode`(+4) `fmt_word`(+5..+9, 40 bits raw).

**Measured** in the revalidation (dense 0..255 per byte, majority-of-3→5; 6,540 cases,
65/65 baseline checks passed, 0 indeterminate):

| byte | db name | what it actually is | emission rule |
|---|---|---|---|
| +1 | `src_desc` | operand descriptor | `v & 0x05 == 0x04` — bits 1,3,4,5,6,7 **don't care** |
| +2 | `fmt_class` | **1-bit enable** | reproduces the result **iff bit 1 is set**; bits 0,2–7 inert |
| +3 | `src` | **DESTINATION register** | `reg << 1`, bit 0 don't care — result redirected into **6 distinct** observed registers |
| +4 | `mode` | 1-bit enable | iff bit 1 set; all other bits inert |
| +5 | *(fmt_word)* | **lane-0 SOURCE register** | `reg << 2`, bits 0–1 don't care |
| +6 | *(fmt_word)* | **lane-1 SOURCE register** | `reg << 3`, bits 1–2 don't care, bit 0 must be 0 |
| +7 | *(fmt_word)* | descriptor (the original run lost this byte to hangs at 8 values; the revalidation completed all 256) | `v & 0xfb == 0x50` — bit 2 don't care |
| +8 | *(fmt_word)* | conversion enable | `bits 2 and 6 both set` (exact over 256) |
| +9 | *(fmt_word)* | **FORMAT SELECTOR** | see the code table below |

**Format code table (byte +9), each code confirmed against 8 independent semantic
vectors — a code is only listed if ONE host model explains EVERY vector:**

| byte+9 | format produced |
|---|---|
| `0x42 0x46 0x4a 0x4e` | **snorm2x16** (scale 32767) |
| `0x82 0x86 0x8a 0x8e` | **unorm2x16** (scale 65535) |
| `0xc2 0xc6 0xca 0xce` | **unorm 8-bit lanes** (scale 255) into bits [7:0] and [15:8], bits 31:16 zero — consistent with the low half of a `unorm4x8` pack, since this carrier supplies only two lanes |

Bits 2 and 3 are don't-care (hence the four codes per format); bits 6:7 select the
format. **This is a third pack format reachable from the same instruction**, which
our corpus never showed because the compiler emitted only the two 16-bit forms here.
Spot-checks against the raw records: `0x42`, `(0.25, 0.75)` → `0x5fff2000` = snorm
`(8192, 24575)`; `-1` clamps to `0x8001` = `-32767`, the symmetric scale of EXP-0079;
`0x82`, same input → `0xbfff4000` = unorm `(16384, 49151)`; `0xc2`, same input →
`0x0000bf40` = `(64, 191)` = `round(0.25*255), round(0.75*255)`. Every code was
confirmed on all 8 vectors, NaN and out-of-range inputs included.

The per-lane source registers were read off directly: byte+5 values `{0,1,2,3}`
select the register holding `v1`, `{8..11}` the one holding `v0`, `{20..23}` `v5`,
and so on for six distinct registers; byte+6 does the same one bit-shift up.

---

## 3. `unpack_convert` — byte +2 characterised exactly, and `reg_sel` is not a register

The dispatch flagged byte +2 as newly open after commit `2b1cbc50` relaxed the
match. Dense 0..255:

> **`unpack_convert` byte+2 reproduces the conversion iff `(byte & 0x03) != 0`.**
> Bits 2–7 are completely inert. Exact over all 256 values.

This **reconciles two prior results that looked inconsistent**. EXP-0089 found
`0x56 → 0x54` breaks the instruction: `0x54 & 3 == 0`, so it does. EXP-0119's 7-bit
re-sweep flipped single bits of `0x56` and found all seven inert: every such flip
except bit 1 leaves `(byte & 3) != 0`, so it is. Neither observation was wrong;
both are the same two-bit OR-enable seen through a one-bit window. `db.json`'s
relaxed match (bit 1 only) is still not the hardware rule.

Rest of the instruction (`db.json` models bytes +3..+6 as one 32-bit `convert_desc`):

| byte | db name | what it actually is | emission rule |
|---|---|---|---|
| +1 | `src_class` | descriptor | `bits 0,2 == 0,1` (exact over 256) |
| +2 | `cache` | **2-bit OR enable** | `(v & 0x03) != 0`; bits 2–7 inert |
| +3 | *(convert_desc)* | **DESTINATION register** | result redirected into 3 distinct observed registers |
| +4 | *(convert_desc)* | **completely INERT** | all 256 values reproduce the result |
| +5 | *(convert_desc)* | **SOURCE register** | `reg << 3`, bits 0–2 don't care |
| +6 | *(convert_desc)* | opcode/descriptor | `bits 0,2 == 0,1` (exact over 256) |
| +7 | `size` + `reg_sel` | **FORMAT + a source-register bit** | see below |

**`reg_sel` is not a register selector.** `db.json` calls byte+7's high nibble "most
likely the unpack RESULT destination (role INFERRED)". Measured, with the source
identified by which live value came back:

| byte+7 | result |
|---|---|
| `0x0a 0x8a` | **unorm8** unpack of the low byte |
| `0x2a 0xaa` | **snorm16** unpack |
| `0x4a 0xca` | **unorm16** unpack (the anchor's format) |
| `0x6a 0xea` | **unorm8** |

so bits 6:5 select the format and bit 7 is don't-care, while **bit 3 changes which
register is read** (`0x_2` reads a different source than `0x_a`). This also explains
the pilot observation that our own compiler emits `…1cca` for unorm2x16 and `…1caa`
for snorm2x16 — a *format* difference that `db.json` attributes to a register.

---

## 4. The `cvt_*` cluster shares one operand layout — exploited with one sweep design

`cvt_i2f`, `cvt_i2f_src` and `cvt_f2i` share a byte layout, and the sweeps confirm it
byte for byte. `cvt_f2h` and `cvt_f2h_dst` turn out to be **the same encoding**.

| byte | `cvt_i2f` | `cvt_i2f_src` | `cvt_f2i` |
|---|---|---|---|
| +1 | `bits 1,2 set` | `bits 1,2 set` | `bits 0,1,2 set` |
| +2 (`mode`) | `(v & 3) != 0` | **INERT, all 256** | `(v & 3) != 0` |
| +3 (`dst`) | **`reg << 1`**, 6 registers observed | same | same |
| +4 (`src_class`) | bit 1 | bit 1 | bit 1 |
| +5 (`src`) | **`reg << 2`** | **`reg << 4`** | **`reg << 2`** |
| +6 (`cvtop`) | `bits 0,2,7 == 0,1,1` | same | `bits 1,2,6 don't care` |
| +7 (`signflag`) | bit 5 | bit 5 | `bits 3,5 == 1,0` |
| +8 (`dst_class`) | — | — | bit 1 |
| +9 (`b9`) | — | — | **INERT, all 256** |

The destination map is the strongest single result in the cluster: sweeping byte +3
moves the conversion result into **six different output slots**, each at a
predictable field value (`slot6←{0,1}`, `slot5←{6,7}`, `slot4←{10,11}`,
`slot3←{14,15}`, `slot2←{18,19}`, `slot1←{22,23}`, anchor `slot0←{24,25}`), i.e.
`field = register << 1` with bit 0 free. `pack_convert` byte +3 produces the
**identical** map, which is why §2 reclassifies it from `src` to `dst`.

**Rounding (both pre-registered hypotheses resolved):**

* **H5 — `pack_float_to_unorm2x16` ties round to NEAREST-EVEN** (revalidated). All 16
  pack semantic vectors matched an RTE oracle exactly, including three exact ties
  built with `Fraction` arithmetic. The competing pre-registered model (ties round **down**,
  as EXP-0133 measured for the unorm16 **storage** path) is **refuted for this
  instruction**. The ALU pack path and the PBE store path round differently — an
  implementer must not reuse one rule for the other.
* **H6 — `cvt_bf16` rounding: NOT ESTABLISHED, claim withdrawn.** The contaminated
  run03 showed every bfloat semantic vector (including three exact bf16 ties) matching
  an RNE oracle and refuting the "truncate toward zero" model. That capture is
  inadmissible and the `cvt_bf16` shard **never ran**, so this is reported as an open
  question with a strong prior, not a result. It is the single cheapest thing for a
  successor to close: one shard, 2,048 cases, ~2 minutes.
* fp16 narrowing matched IEEE round-to-nearest-even throughout, including the
  65520.0 overflow tie that must carry to `+inf`, subnormals, and NaN/Inf.

**`packed_half2_hi` — NOT ESTABLISHED, claim withdrawn.** It could not be provoked
from any MSL shape tried, so it is only reachable by an encoding assembled from
`db.json` and spliced over the carrier's own `half_alu`. In the contaminated run03
that synthesis executed and computed the packed-half2 multiply **for the high lane
only**, leaving the low lane at zero across all four semantic vectors — which would
match the instruction's name and explain why the compiler emits `half_alu` (low half)
plus a 4-byte `0x18`-leader companion as a pair. **The revalidation shard never ran**,
so this is recorded as a promising, specific hypothesis for a successor, not a
finding. All five of its fields are `untested`.

---

## 5. The 0x54/0x56 bit position: three more distinct behaviours

The dispatch warned this position has ≥4 distinct behaviours across families. This
experiment adds three more, each now stated exactly rather than as a bit-flip:

| family | byte+2 behaviour, measured over all 256 values |
|---|---|
| `pack_convert` | enable = **bit 1 alone**; bits 0,2–7 inert |
| `cvt_i2f`, `cvt_f2i`, `unpack_convert` | enable = **bit 0 OR bit 1**; bits 2–7 inert |
| `cvt_i2f_src` | **completely inert** — all 256 values reproduce the result (revalidated, unanimous) |

`cvt_i2f_src` is the notable one: it is the sibling that EXP-0089 identified as
carrying the load-bearing "source-consumed-by-a-following-ALU" routing, and in this
carrier — which *does* feed a following ALU add — the byte has no effect at any
value. This is reported as an unresolved tension with EXP-0089, not as a
refutation: the two carriers differ, and this experiment did not reproduce
EXP-0089's exact construction.

---

## 6. Contamination, faults, and what that cost — `FIELD-SWEEP-PROTOCOL.md` §7

### 6.1 The originals were contaminated — and my own schema made it look worse

The orchestrator measured run03 vs run04 at **12,943 of 22,237 outcomes differing
(58.2 %)** and run03 vs run05 at 43.8 %. Decomposed:

| comparison | raw outcome-diff | of which exactly one side was a **never-dispatched skip placeholder** | **both sides actually measured** |
|---|---|---|---|
| run03 vs run04 | 12,943 (58.2 %) | 12,861 (99.4 %) | **14 of 3,751 (0.37 %)** |
| run03 vs run05 | 2,057 (24.5 %) | 2,046 | **4 of 6,292 (0.06 %)** |
| run04 vs run05 | 8,345 (99.2 %) | 8,338 | **0 shared measurements at all** |

Two separate problems, and I own both:

1. **My record schema was misleading.** Skipped cases were written with
   `outcome:"hang"`, so an outcome-only comparison sees catastrophic divergence.
   Fixed in the revalidation (`outcome: null`, `validity:"not_run"`).
2. **run04 really was contaminated** — it cascaded 57 s in and skipped 18,486 of
   22,237 cases; 83 % of its records are placeholders. It is retained and unused.

The 18 genuinely-disagreeing measurements were **all** fault/hang boundary cases —
precisely what majority-of-N exists to settle. Root cause is now known and is not a
defect of this method: a GPU test was destabilising **WindowServer**, taking
`MTLCompilerService` down machine-wide.

### 6.2 What the revalidation changed

Comparing every revalidated measurement against the corresponding original:
**13,783 measurements compared, 92 overturned (0.67 %)**, touching 16 of 53 swept
bytes. The direction is always the same class of change — a `fault` or `hang`
recorded once, re-measured as `silent_zero`/`wrong_value`/`ok` by majority, or the
reverse. Per-byte counts are in `analysis/reval_vs_original.json` and are quoted in
every field's `note`.

The revalidation also **recovered coverage the originals lost**: `pack_convert`
byte +7 stopped at 8 values in run03 after two hangs; in the revalidation it
completed all 256 and yields an exact rule (`v & 0xfb == 0x50`, bit 2 don't-care).

### 6.3 Silent zeros: can we tell "wrote zero" from "wrote nothing"?

`silent_zero` dominates the outcome mix (8,524 of 18,082, against 5,368
`wrong_value` and 3,636 `ok`). On this ISA that is the *expected* signature of a
wrong field value — but only if a zero read-back cannot also mean "nothing was
stored". **These carriers separate the two without assuming anything.** Besides the
instruction's own result, each stores **six other live values through the same
`device_store` path**. If those companion slots still carry their host-predicted
values, the store path demonstrably ran, so the zero in the result slot is a real
read of a register holding zero.

Measured across the revalidated byte sweeps: **4,079 silent zeros DISCRIMINATED**
(companions intact) versus **757 ambiguous**. The ambiguous ones are concentrated in
the byte-0 (opcode-leader) sweeps, where a length desync destroys the whole
downstream stream — exactly what the three-way integrity sentinel flags as
`perturbed`. Every field's `semantics` string carries its own discriminated/ambiguous
split, so no reader has to take "silent zero" on trust. This is the
EXP-0140-overturns-EXP-0128 trap, and it is closed per field rather than assumed.

### 6.4 Retained, unused captures

Per CODEX each is retained unmodified with its own `PARTIAL.md` / `SCOPE.md` /
`NOT_RUN.md`, and **none backs a promoted label**:

* **`run01`** (3,137/22,237) — killed by **our own oracle**: Python's
  `struct.pack('<e')` raises on fp16 overflow instead of producing `±inf`, and the
  boundary vector deliberately contains 65520.0. Replaced with an exact integer fp16
  RNE encoder cross-checked against Python over 20,000 random bit patterns, plus a
  mandatory pre-flight that evaluates the oracle over *every* case vector before a
  single dispatch.
* **`run02`** (5,219/22,237) — baseline check failed inside this sweep's own GPU
  error-recovery window and was recorded rather than retried. Stopped by hand.
* **`run03`** (22,237), **`run04`** (22,237), **`run05`** (8,412) — captured in the
  WindowServer/`MTLCompilerService` failure window. run04 is 83 % placeholders.
* **`rv01__cvt_f2h_dst`** (294/1,311), **`rv01__cvt_bf16`** (0),
  **`rv01__packed_half2_hi`** (0) — killed by the second collapse.

### 6.5 Reproducibility status of the promoted labels

Every promoted label rests on **within-run majority-of-3 (escalated to 5)**, not on a
cross-run gate. That is the right control here: the thing being suppressed is
per-attempt machine noise, not per-run drift, and the originals cannot serve as a gate
partner because they are inadmissible. 99.4 % of cases were unanimous at 3
repetitions and none was indeterminate.

**Not covered at all**, and therefore `untested` with a note recording exactly what
was tried (coordinator rule 3 — no label is carried forward from the contaminated
runs to fill these gaps):

| instrument | fields | why |
|---|---|---|
| `cvt_bf16` | 8 | shard never dispatched a case; `MTLCompilerService` collapse |
| `packed_half2_hi` | 5 | same; also only reachable by a synthesised encoding |
| `cvt_f2h_dst` | 5 of 6 | shard killed after 294 cases; only byte +1 (`srcfmt`) completed |

## 7. Deliberate deviation from "sweep all 2^w"

Byte 0 is the **opcode leader**, not an operand field: changing it changes the
instruction's length and desynchronises the downstream stream. A smoke run produced
a genuine `kIOGPUCommandBufferCallbackErrorHang` from `cvt_bf16` byte0 = 0xFF, and
this host has no out-of-band recovery. Byte 0 therefore got a bounded 24-value probe
(all 16 values of the high nibble, which *is* the `dst` field in `cvt_f2h_dst`,
`cvt_bf16` and `packed_half2_hi`, plus 8 off-match values). **Every operand byte
still got the full dense 0..255.** The two `dst`-nibble fields are reported
`untested` rather than claimed from that bounded probe.

`pack_convert.fmt_word` (40 bits) and `unpack_convert.convert_desc` (32 bits) were
swept **per constituent byte, densely**, plus 175 whole-field values (0, all-ones,
every single-bit value, single-bit-cleared, anchor⊕bit). That exceeds the protocol's
`w>8` requirement but is **not** 2^40 / 2^32 coverage, and the `range` field of every
verdict says so.

---

## 8. `db.json` defects found (recorded, NOT patched — the orchestrator owns `db.json`)

Full detail with evidence in `analysis/field_verdicts.json → db_defects`.

1. **`pack_convert.fmt_word` is not one 40-bit field.** Bytes +5 and +6 are the two
   per-lane **source registers**, +8 a conversion enable, +9 the **format selector**.
2. **`pack_convert.src` (byte +3) is the DESTINATION**, not a source — it produces the
   same register-redirection map as `cvt_i2f`/`cvt_f2i`'s `dst`.
3. **`unpack_convert.convert_desc` is not one 32-bit field.** +3 destination register,
   +4 wholly inert, +5 source register, +6 opcode/descriptor.
4. **`unpack_convert.reg_sel` is a FORMAT selector**, not the result destination.
5. **`unpack_convert`'s byte+2 rule is still wrong after the relaxation**: the
   hardware enable is `(byte & 3) != 0`, not bit 1.
6. **`cvt_f2h` and `cvt_f2h_dst` are the same instruction** — identical bit rules on
   every byte; the two db entries differ only in the byte-0 dst nibble. Related:
   `cvt_f2h_dst` with dst nibble 0 (byte0 = `0x01`) has **no length rule**, so a whole
   class of the instruction fails to tokenize; and `byte0 = 0x18` (the
   `packed_half2_hi` family) has no length rule either.

Also recorded: `cvt_bf16`'s match pins byte+4 to `0x01`, but our own compiler emits
`0x05` there, so the descriptor fails to decode its own compiler's output. (That is a
compile-time tokenization observation from `work/pilot/anchors2.log`, independent of
any GPU capture, so it stands despite the `cvt_bf16` shard not running.)

---

## 9. Limitations

* **Three instruments are not covered.** `cvt_bf16` (8 fields) and `packed_half2_hi`
  (5) were never dispatched, and `cvt_f2h_dst` completed only byte +1 of 6, because
  the host's `MTLCompilerService` collapsed for a second time. Their fields are
  `untested`; nothing was inherited from the contaminated runs to paper over the gap.
* **Reproducibility is within-run, not cross-run.** Majority-of-3→5 in one process
  per instrument, with periodic baseline re-validation. 99.4 % unanimous, 0
  indeterminate. A second independent capture would still be worth having.
* The `signflag` sweeps used a **positive** fixed operand, so they separate "converts"
  from "silently zero" but **not signed from unsigned**. The sign semantics rest on
  the semantic arm's signed/unsigned vectors, not on the byte sweep.
* Absolute register *numbers* in the operand maps are inferred from the carrier's own
  compiler allocation; what is directly measured is the **scale** (`reg<<1`, `reg<<2`,
  `reg<<3`, `reg<<4`) and that six distinct registers are reachable.
* `pack_convert.fmt_word` (40 bits) and `unpack_convert.convert_desc` (32 bits) were
  swept **per constituent byte, densely**, plus 175 whole-field values. That exceeds
  the protocol's `w>8` requirement but is **not** 2^40 / 2^32 coverage, and every
  verdict's `range` says so.
* 757 of 4,836 silent zeros remain **ambiguous** (§6.3), concentrated in the byte-0
  opcode-leader sweeps where a length desync destroys the downstream stream.
* Compute only. No fragment/render-stage form of any of these instructions was tested.
* An arm-C harness defect means the MODE-A "baseline" case measured the *unspliced*
  carrier rather than the synthesised instruction; it is documented rather than
  patched, because patching `casematrix.py` would change the frozen matrix hash.
