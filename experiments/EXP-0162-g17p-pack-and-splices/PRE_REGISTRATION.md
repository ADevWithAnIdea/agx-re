# PRE-REGISTRATION — EXP-0162: the PACK coverage gap, and two descriptor defects that need a fragment splice

**Frozen 2026-08-29, before any GPU dispatch in this experiment.**
Repo revision at freeze: `afea465ef67dc713b684a16370cc732d1c5a230c` (working tree dirty
with *other* agents' in-flight experiments; this experiment gates on the **authored blob
hashes** in `CAPTURE_CONTRACT.json`, never on live `HEAD` — `SUBAGENT_BRIEF.md`).

**Target: Apple A18 Pro / G17P** (`users-MacBook-Neo.local`, 192.168.10.243, `applegpu_g17p`,
`AGXAcceleratorG17P`, 5 GPU cores, macOS 26.6). Every result of this experiment is labelled
`target: G17P`. **No result here is carried onto M4/G16G and no M4 label is carried onto a
G17P result.** Where this experiment deliberately re-runs an M4 measurement, the M4 result
being tested against is named and the reproduction outcome stated.

**Clean-room provenance:** OWN-SHADER + HW-PROBE (+ PUBLIC for IEEE-754 / bfloat16 / MSL
format-conversion definitions, used only to write the host oracle — never to source an
Apple9 encoding fact). No Apple binary is disassembled, decompiled, symbol-dumped, or
otherwise introspected.

---

## 0. Why these five questions

Two independent gaps, both stuck for reasons that are *recorded*, not guessed.

**(1) EXP-0144's coverage gap.** EXP-0144 revalidated the PACK family and honestly returned
18 fields to `untested` because their shards never dispatched a case (`cvt_bf16`, 8 fields;
`packed_half2_hi`, 5) or died mid-run when `MTLCompilerService` collapsed (`cvt_f2h_dst`,
5 of 6). It also **withdrew** two findings as inadmissible — `cvt_bf16`'s RNE rounding and
`packed_half2_hi`'s high-lane-only semantics — because each rested on a single contaminated
run. No label was inherited to paper over any of this, so all of it is clean to attack.

Part-II questionnaire items **P2-01/02 (BF16)** are today "hardware YES, emit NO": the `0x11`
group with scalar and packed `bfloat2` forms is real, but **no committed experiment has ever
measured a single bf16 numeric result.** One measurement closes both.

**(2) Two descriptor defects the corpus cannot adjudicate.**
- `pixel_order` declares field `flags` at bits[32:40] **and** a match constant pinning those
  bits to `0x06`. `work/DB-DEFECT-TRIAGE.md` §4 measured two candidate fixes and both are
  wrong: dropping `[32,8,6]` **regresses** (the match then equals `threadgroup_barrier`'s and
  loses the tie-break); a byte+1 discriminator **over-claims** (186 real corpus
  `threadgroup_barrier`s move into `pixel_order`). The corpus has **zero** `pixel_order`
  firings, so it has no power here.
- `vary_store` (`emit_unsafe`): byte0=0x57 in a fragment main is a **6-byte** kill/target-mask
  op, mis-tokenized as the 8-byte vertex `vary_store` (EXP-0091). EXP-0093 corrected the
  companion reading — `07 02 54 01 ..` is the ordinary fragment epilog, not a partner.

**Static work already done at desk, before freezing** (`analysis/corpus_scan.py`,
`analysis/scan57.py`, over the committed own-MSL corpus `EXP-M4-13-full-corpus/hex`, 1080
files). It is recorded here because it *shaped* the hypotheses and must not be presented
later as a result of the run:

| observation (corpus, desk) | value |
|---|---|
| byte0==0x07 tokens | 344 (`threadgroup_barrier` 280, `mem_fence8` 36, `link_save_restore` 28); **`pixel_order` 0** |
| byte0==0x07 byte+3 values seen | `00 01 06 08 09 0a 0c 14 15 16 30 48 61 c0 c4` — **never `0x50`/`0xd0`** |
| byte0==0x07 byte+4 values seen | `00 02 09 80 81` — **never `0x06`** |
| byte0==0x57 tokens | 625, all named `vary_store` |
| 0x57 with byte+1 low-nibble **6** and byte+5 ∈ {0x40,0x41} | **615**, all vertex-stage |
| 0x57 with byte+1 low-nibble **4** and byte+5 == **0x01** | **10**, all fragment-stage |
| 0x57 byte+2 values | `0x54`×554, `0x55`×31, `0x56`×40 — **and 0x54/0x55/0x56 all occur in BOTH populations** |

The last row **refutes the dispatch's own premise** that "byte+2 = 0x54" identifies the
6-byte fragment op: byte+2 does not discriminate. Two candidate discriminators that do
separate the corpus perfectly are pre-registered below.

**Locate-only pilot** (`harness/locate.py`, compile + static tokenize, **no dispatch**;
`work/pilot_locate.json`). All nine compute carriers and all three render carriers compile on
G17P, and every anchor this experiment needs reproduces EXP-0144's / EXP-0147's / EXP-0091's
**M4 bytes exactly**:

| carrier | offset in `_agc.main` | anchor bytes | first recorded by |
|---|---|---|---|
| `c_f2bf` | 156 | `01 01 14 81 05 02 40 00` | EXP-0144 (M4) |
| `c_f2h_dst` | 156 | `c1 01 14 81 04 02` | EXP-0144 (M4) |
| `c_ph2` | 108 | `90 04 05 00 00 20` (`half_alu`, MODE-A splice target) | EXP-0144 (M4) |
| `f_rog` fragment | 248 / 254 | `07 14 54 50 06 00` / `07 04 54 d0 06 00` | EXP-0147 (M4) |
| `f_kill` fragment | 54 | `57 14 54 00 00 01` then `07 02 54 01 00 00` at 60 | EXP-0091 (M4) |
| `f_vary` vertex | 106,114,152,160,168,176,184,192 | `57 46 54 04 00 40 4a 00` etc. | EXP-0037 (A18) |

---

## 1. Hypotheses, expected observations, and refuters

### H1 — `cvt_bf16` rounds float32→bfloat16 round-to-nearest-EVEN

*Independent variable:* the input float value fed to the unmutated `c_f2bf` carrier.
*Controlled:* everything else (same archive, same dispatch shape, same poison).

Three **competing, pre-registered** host models, all scored on every vector:
`RNE` (round half to even) · `TRUNC` (truncate toward zero, i.e. drop the low 16 bits) ·
`RNA` (round half away from zero). The vector set contains **exact bf16 ties**
(`1.00390625`, `1.001953125`, `1.005859375` from EXP-0144's frozen set, plus ties added here
whose correctly-rounded results differ between all three models), subnormals, `±inf`, `NaN`,
and overflow.

*Expected if H1:* every vector matches `RNE` and at least one tie **refutes** `TRUNC` and at
least one **refutes** `RNA`.
*Refuter:* any vector where the hardware result differs from `RNE`. In particular a tie
matching `TRUNC` refutes H1 in favour of truncation — which is the live alternative, because
EXP-0079 found reduced-float **stores** truncate and EXP-0133 found `unorm16` **ties round
DOWN** where `unorm8` rounds up. Ties are where the surprises live, so the tie vectors are
the load-bearing part of this arm and are scored individually in `RESULTS.md`.

*Known confounder:* a host oracle that is itself wrong. Mitigation, carried from EXP-0144's
run01 failure: the oracle is exact integer arithmetic, is evaluated over **every** case vector
in a pre-flight before any dispatch, and is cross-checked against `numpy`-free independent
re-derivation in `analysis/oracle_selftest.json`.

### H2 — `packed_half2_hi` executes when synthesized, and operates on the HIGH lane only

MODE-A splice: the carrier's own 6-byte `half_alu` (`90 04 05 00 00 20`) is **replaced** by
`98 04 24 00 00 20`, an encoding assembled from `db.json` alone (same length, so the stream
stays aligned iff length 6 is right — itself part of what this tests).

*Expected if H2:* the dispatch executes (integrity sentinel `clean`) and the output half2's
**high lane** carries `v0.y * v1.y` while the **low lane** is left at whatever the carrier's
register held (poison-discriminated: the low lane is *unwritten*, not *zeroed*).
*Refuters:* (a) the splice does not execute / sentinel absent → `packed_half2_hi` is not
reachable at this length and the claim stays withdrawn; (b) both lanes are computed → the
"hi" reading is wrong and the descriptor's name is misleading; (c) the low lane comes back
**zero** rather than poison → the instruction writes the whole register, and EXP-0144's
withdrawn "leaving the low lane untouched" reading is refuted.

### H3 — `dst` of all three instruments is byte0's HIGH NIBBLE, densely emittable

EXP-0144 gave byte0 only a bounded 24-value probe and therefore reported all three `dst`
fields `untested`. Here byte0's **high nibble is swept dense 0..15 with the low nibble held at
the anchor's value**, which cannot change the instruction length, so the field is covered
exhaustively at no extra risk. The low nibble gets a separate bounded off-match probe,
recorded as match evidence, never as `dst` evidence.

*Expected:* the conversion result appears in a *different* output slot per high-nibble value,
a monotone map like the one EXP-0144 measured for `cvt_i2f.dst`.
*Refuter:* the result stays in slot 0 for every value → byte0's high nibble is not `dst`.

### H4 — `pixel_order` and the 0x07 barrier family are ONE instruction, and byte+4 is a field

*Sub-claims, each separately falsifiable:*

- **H4a (detection power / liveness — run FIRST, and the whole arm is void without it).**
  Corrupting the acquire member's byte+4 to `0x01` loses raster-order updates: with 8
  instances over one texel the read-back texel falls from `8·src` to `1·src` and the
  programmable-blend pixel from `clear + 36·src` to `clear + 8·src`. This is the proof that
  the spliced value is **live on the rendered-pixel path**. *Refuter:* the texel does not
  move → this litmus cannot see what it is being used to exclude, and every "inert" verdict in
  this arm is reported `untested`, exactly as EXP-0147 did for its fence arms and as EXP-0129
  failed to do.
- **H4b.** byte+4 is a genuine field: a dense 0..255 sweep of the acquire member reproduces
  the *pixel-exact* result at many values (M4 measured 112), and of the release member at many
  (M4: 224). *Refuter:* only `0x06` works → the match constant is right and the field
  declaration is what must be deleted.
- **H4c (the cross-form probe — the new evidence the corpus cannot supply).** Replacing the
  acquire/release pair with `07 14 54 51 0e 00` / `07 04 54 d1 0e 00` — the
  `threadgroup_barrier(mem_texture)` acquire/release pair our own MSL compiles to (EXP-M4-13
  R8) — **preserves ordering** (texel `8·src`, pixel `clear + 36·src`).
  *Expected if H4c:* the two descriptors name one instruction and the fix is a
  merge/relabel, not a discriminator.
  *Refuter:* ordering is lost → byte+3/byte+4 are semantically load-bearing across the family,
  the two are genuinely different operations, and a **match narrowing** is the right fix.
- **H4d (the theft probe).** Replacing the pair with corpus `threadgroup_barrier` forms
  (`07 04 54 61 09 00` compute, `07 02 54 0c 02 00` fragment tile-ordering) **loses** ordering.
  *Expected if H4d:* those encodings are not raster-order markers, so a match that stole them
  would be wrong — which is exactly what candidate C1b did.

### H5 — the byte0=0x57 length is selected by byte+1 bit1 (equivalently byte+5 bit6), not byte+2

*Corpus-side (already frozen above):* byte+1 bit1 set ⇔ byte+5 bit6 set ⇔ the 8-byte
vertex form, across all 625 corpus tokens with **zero** exceptions; byte+2 splits 0x54/0x55/0x56
across **both** populations and therefore cannot be the discriminator.

*Hardware-side, pre-registered:*
- **H5a (detection power / liveness — run FIRST).** In `f_kill`, splicing the op's byte+4 from
  `0x00` to `0x01` kills the fragment: the pixel falls from `(0.75,0.5,0.25,1)` to the clear
  colour, with `mask=1` bound. *Refuter:* no change → the arm has no power and promotes nothing.
- **H5b.** Setting byte+1 bit1 on the fragment op (`0x14 → 0x16`) makes the hardware consume 8
  bytes, swallowing the `07 02` leader of the following fragment epilog barrier and decoding
  `54 01 00 00` as an instruction → a *catastrophic* outcome (fault, no-draw, or a pixel
  unrelated to either the survive or the kill value), qualitatively unlike the benign outcomes
  of the byte+1 values that leave bit1 clear.
- **H5c (control).** `0x14 → 0x1c` (bit1 still clear) leaves the pixel at the baseline —
  EXP-0091 measured exactly this splice as null on M4. *Refuter:* if it also breaks
  catastrophically, byte+1 is broadly load-bearing and bit1 is not a length selector.
- **H5d.** The mirror on the vertex side: clearing byte+1 bit1 of an `f_vary` `vary_store`
  (`0x46 → 0x44`) or clearing byte+5 bit6 (`0x40 → 0x00`) desynchronises the vertex stream →
  no draw / garbage geometry, whereas a bit-preserving perturbation does not.

*Confounder, stated up front:* changing byte+1 changes both the hypothesised length selector
and whatever else that byte encodes, so no single splice isolates "length". The evidence is
the **pattern** across a dense 0..255 sweep of byte+1 and byte+5 on both stages — a clean
split by one bit is the signature of a length selector; a scattered map is not. This is
reported as `STRUCTURAL` + corroborating HW behaviour, and **not** as a proven length rule if
the map is scattered.

---

## 2. Method, in the order it will be run

Per `FIELD-SWEEP-PROTOCOL.md` §3, and its **§7 + §7A** concurrency rules.

1. **Pre-flight (host, no GPU):** evaluate every oracle over every case vector; abort if any
   raises or is `None`. (EXP-0144's run01 was lost to exactly this.)
2. **Baseline before mutation**, per arm, and re-validated every 100 cases.
3. **Detection-power control first** (H4a, H5a). An arm whose control fails promotes nothing.
4. **Bulk sweeps run concurrently and unlocked** (§7). Every non-`ok` case records the OS
   fault-classification string. `…ErrorInnocentVictim` attempts are discarded and re-run.
5. **Majority of 3, escalating to 5** on disagreement.
6. **§7A:** every surviving `fault`/`hang` verdict is re-confirmed **under
   `~/agxre/gpulease.sh`, 5×**, before it is written into `field_verdicts.json`. A fault that
   does not reproduce under the lease is recorded as its re-measured class, and the original
   observation is retained in `raw/`.
7. **Poisoned read-back** (`0xDEADBEEF + i` per word, EXP-0153/0157 convention): the compute
   output buffer is bound as an *input* pre-filled with poison, so `agxrun_persist` reuses it
   and an unwritten word is distinguishable from a genuine silent zero. This also lets suspect
   faults be adjudicated offline from the committed digest.
8. **Sixteen-GPR seeding is NOT used** here: these carriers already keep six mutually
   distinguishable host-known values live across the instruction under test (EXP-0144's
   design), which serves the same purpose — identifying *which* register a field selects —
   and keeps this experiment byte-comparable to the M4 measurement it is converting.
9. `raw/<run_id>/sweep.jsonl` gets one JSON object per case, appended and flushed
   immediately; `PROGRESS.md` after every milestone; `raw/` pulled back to the repo as it is
   produced.

### Case matrix (frozen)

| arm | instrument | cases |
|---|---|---|
| A | `cvt_bf16` @156 in `c_f2bf` | byte0 high nibble dense 0..15 (dst) · bytes +1..+7 dense 0..255 · byte0 low nibble 8 off-match values · ≥10 semantic vectors |
| B | `packed_half2_hi` synthesized over `c_ph2` @108 | synthesis execute/semantics · byte0 high nibble dense · bytes +1..+5 dense 0..255 · 4 semantic vectors |
| C | `cvt_f2h_dst` @156 in `c_f2h_dst` | byte0 high nibble dense 0..15 · bytes +2..+5 dense 0..255 (byte+1 already complete in EXP-0144, re-run here for the G17P label) · 5 semantic vectors |
| D | `pixel_order` @248/@254 in `f_rog` | H4a control · bytes +1,+3,+4,+5 dense 0..255 × both members · H4c/H4d cross-form probes |
| E | `vary_store` @54 in `f_kill`, @106.. in `f_vary` | H5a control · fragment bytes +1,+4,+5 dense 0..255 · vertex bytes +1,+5 dense 0..255 · H5b/H5c/H5d probes |

### Verdict rules (frozen)

- Labels come only from `docs/evidence-classification.md`'s eight.
- A field is `hardware-run` only if arbitrary operands executed **and** its arm's
  detection-power control passed.
- `silent_zero` is a result. `not_written` (poison intact) is a *different* result and is
  recorded separately.
- Anything inconclusive is `corpus-correlation` or `untested`. **No label is rounded up to
  reach a count.**
- `db.json` is **not edited**. Proposed changes go to `analysis/proposed_db_changes.json`
  with their evidence, and any match/length change is A/B-validated against a **COPY** of
  `tools/agx-isa/` with the full `roundtrip_test.py` (must stay ALL PASS) plus the frozen
  corpus metrics (832 clean files / 389 368 strict leftover bytes, EXP-0148).

## 3. Stop rules

- Two genuine hangs in one arm → **stop that arm**, report PARTIAL (§8).
- Baseline fails mid-run → cascade; stop, note the case, resume in a fresh process.
- Neo unresponsive → **STOP and report BLOCKED**. `macvdmtool` is forbidden to this agent.

---

## AMENDMENT 1 — made 2026-08-29, after two **smoke** runs, BEFORE any gated capture

Recorded here rather than silently folded in, because amending a frozen contract is exactly
the thing that must be auditable. Both smoke runs live in `work/smoke/` (retained, and they
back no label). Nothing in `raw/` existed when this amendment was written.

1. **The poisoned read-back exposed a carrier property, not a hardware one.** `c_f2bf` and
   `c_f2h_dst` store **seven 16-bit** values, so the last output word has only its low half
   written and its high half legitimately keeps the poison. EXP-0144's zero-initialised buffer
   hid this (the word read back 0, which its oracle expected). A per-word compare mask
   (`cases162.EXPECT_MASK`, `{3: 0xFFFF}`) is added. This is a harness fix; the discovery is
   itself a small argument for poisoning.

2. **Only `v0` is converted by `c_f2bf`.** The remaining five lanes are `as_type` bit copies.
   EXP-0144's semantic rows put their interesting values in `v1`/`v2`, where the instruction
   never sees them — so the original set could refute `RNA` but could **not** separate `RNE`
   from a ties-toward-zero rule. The `c_f2bf` semantic set is therefore rebuilt with **31
   rows, each carrying its discriminating value at `v0`**: exact bf16 ties at **both mantissa
   parities** and both signs, a tie that carries into the exponent, the two overflow ties at
   the top finite bf16, values one ULP either side of a tie, f32 subnormals, ±0, ±inf, a
   signalling NaN, and a quiet NaN.

3. **A fourth competing model is added: `TIES_DOWN`** — round to nearest, ties toward zero.
   This is the model EXP-0133 measured for the `unorm16` **store** path (where ties round DOWN
   while `unorm8` ties round up), and it is indistinguishable from `RNE` on every even-lsb tie.
   Separating them requires an **odd**-mantissa-lsb tie, which is why the amended vector set
   exists. Frozen predictions, all host-computed:

   | v0 | RNE | TRUNC | RNA | TIES_DOWN |
   |---|---|---|---|---|
   | `1.00390625` (tie, lsb even) | `3f80` | `3f80` | `3f81` | `3f80` |
   | `1.01171875` (tie, lsb **odd**) | **`3f82`** | `3f81` | `3f82` | **`3f81`** |
   | `0.998046875` (tie, carry into exponent) | **`3f80`** | `3f7f` | `3f80` | **`3f7f`** |
   | `3.3961775e38` (tie at the top finite) | **`7f80`=+inf** | `7f7f` | `7f80` | **`7f7f`** |

   H1 is now: **RNE fits all 31 rows, and `TIES_DOWN`, `TRUNC` and `RNA` are each refuted by at
   least one row.** The refuters are named above; if `TIES_DOWN` fits and `RNE` does not, H1 is
   false and the bf16 convert rounds ties toward zero like the `unorm16` store path.
