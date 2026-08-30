# EXP-0199 — RESULTS

**Target:** A18 Pro / G17P (`192.168.170.254`, T8140, `AGXAcceleratorG17P`, 5 cores,
macOS 26.6, Metal 4). **Every result on this page is `G17P-direct`.**

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected:      only MSL we authored (kernels/*.metal) and the AGX bytes the
                       public Metal runtime produced from it
Apple binary introspection: NONE
Reproduction:          python3 run.py <run_id> <arms>     (discovery)
                       python3 conf.py <run_id> shuffle|reverse   (confirmation)
                       python3 analysis/gates.py && python3 analysis/make_verdicts.py
Evidence:              raw/g17p_conf01, raw/g17p_conf04 (gated confirmation);
                       raw/g17p_run01{a,b,c}, raw/g17p_run02{a,b,c} (discovery);
                       raw/prefreeze/*, raw/smoke01, raw/g17p_confsmoke,
                       raw/g17p_conf02, raw/g17p_conf03 (retained partials)
```

**Process note.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` landed mid-experiment. The
original contract and its captures are **retained unchanged and reclassified as
DISCOVERY**; `AMENDMENT-01.md` + `CAPTURE_CONTRACT-AMENDMENT-01.json` were frozen before
the confirmation captures and add the actual-byte ledger, the per-arm positive control, the
pre-registered competing semantic models, and shuffled/reversed confirmation. Nothing was
discarded or re-run because the bar moved.

---

## 1. Gate results, overall

| Gate | Result |
|---|---|
| **A — actual-byte ledger** | **PASS. 12 932 ledger checks, 0 failures.** Both runners print `ACTUAL <off> <hex>` from the spliced file **re-read off disk**, i.e. the bytes handed to `newLibraryWithURL:`; the driver decodes the swept byte out of them independently (bit extraction *and* `isadb.decode_one`) and asserts equality with the request. There is no assembler in this path — splices are raw byte writes — so the DEF-0166 failure mode cannot occur here; the ledger proves that rather than assuming it. A round trip was not used. |
| **B — positive control per arm** | **PASS in every arm that reports a negative.** See §3 for the vary_slot control (26/32 exact host-predicted, 32/32 cross-run) and §4/§5 for the marker controls (0 of 7 for three independent controls at the same boundaries). |
| **C — independent semantic model** | Pre-registered competing models in `AMENDMENT-01.md`; per-case predictions written to `analysis/predictions_<run>.json` **before** any output was read. Selections in §2–§5. **Arm E declared `semantics: unknown` in advance and is not promoted.** |
| **D — compiler recipe** | Only `generated-point` is claimed, for `sfu_marker` and the 4-byte `0x60` form. No `canonical-recipe-proven` anywhere. |
| **E — clean confirmation** | **NOT MET, and reported as not met.** Two captures were taken, **shuffled** (`g17p_conf01`) and **reversed** (`g17p_conf04`), 6 507 cases each, identical frozen archives and ledgers, **0 hangs, 0 measurement failures, 0 invalid ledgers**. But Gate E requires a **quiet** machine, and this experiment **measured** the machine rather than asserting anything about it: `raw/<run>/concurrency.jsonl` records a **median of 9 and a peak of 17** concurrent foreign GPU processes, and it was never quiet. The orchestrator has since confirmed Gate E is currently unmeetable for the whole fan-out. **Every verdict below is therefore held at `reproducibility: INCOMPLETE — Gate E not met`, awaiting a serialized quiet confirmation run.** See §1a for the adjudication. |

### 1a. Cross-run disagreements, adjudicated

Both captures ran **19:29–19:42 UTC**, entirely **before** EXP-0204's declared
20:00–20:25 UTC hang window, so none of the disagreements below can be attributed to it.

| | |
|---|---|
| raw cross-run outcome agreement | **6 475 / 6 511 = 99.447 %** |
| disagreements with a `fault`/`hang` on exactly one side | **26 of 36** (11 of them carrying `kIOGPUCommandBufferCallbackErrorInnocentVictim`) |
| remaining "soft" disagreements | **10**, and **3 of those are the baseline records themselves** (an artefact of scoring the baseline against a null reference in `conf01` and against itself in `conf04` after the guard was added) |
| **adjudicated agreement** (a fault against a clean observation on a measured-busy machine is a measurement failure — EXP-0160's filter, and the shape EXP-0201 found in 40 156 cases) | **6 501 / 6 511 = 99.846 %** |
| lowest per-group adjudicated agreement | 254/256 = 99.22 % (`frag_depth_store.b5` on `c_depth2`) |

Applying EXP-0201's lens: the disagreements here are **overwhelmingly confined to a hard
outcome class** (`fault` ⟷ a clean observation), not to unstable semantics. The 7 genuinely
soft disagreements out of 6 508 real cases are all single values inside dense 256-value
sweeps whose remaining 255 values agree, and none of them changes a model selection: no
model selection in §2–§5 turns on a single value.

---

## 2. `frag_depth_store` — the descriptor's claim is now OBSERVED, for the first time

### What was directly observed

`db.json` says of itself: *"Not individually splice-validated (agxrender has no depth
attachment to read back)"*, and EXP-0181 records that the earlier dense sweeps of
`b3/b4/b5` were **scored against a colour probe**. This experiment reads the
**Depth32Float attachment back per pixel**.

- **Unmutated**, the depth attachment holds the shader's `[[depth]]` output exactly, at
  three probe pixels with three **distinct** values, on **two independent carriers** with
  **different** depth functions:
  - `c_depth`: DEPTH = 0.395833 / 0.270833 / 0.520833, and the host oracle
    `(PIX0.r − 0.5) × 4` gives the same three numbers;
  - `c_depth2` (adversarial: depth is a **decreasing** function of a **different**
    varying, colour carries a **third**): DEPTH = 0.6125 / 0.6875 / 0.5375, and the host
    oracle `0.9 − (PIX0.g − 0.125)` gives the same three numbers.
- **Clearing byte+5 bit 1** makes the depth attachment receive **0.0 at every covered
  pixel** while the colour value at every covered pixel is unchanged. 128 of 256 `b5`
  values, identically on both carriers and in both captures. The depth histogram collapses
  from a per-pixel gradient to exactly two values (1.0 = clear, 0.0 = written).
- **0 of 2 304** dispatched mutations of this instruction's own bytes moved the **colour**
  surface while leaving the depth surface unchanged, in either capture.
- With the instruction **replaced** (three different 6-byte replacements, both carriers,
  both captures — 12 cases, all agreeing), the tile is discarded entirely and the depth
  attachment keeps the **clear** value 1.0.

### Model selection (pre-registered)

| Model | Verdict |
|---|---|
| **M_A1** — writes the shader depth output to the depth attachment | **SELECTED** |
| M_A2 — the depth attachment is filled by interpolating `position.z` (= 0.0) | **REFUTED**: the baseline depth is the shader's value, not 0.0; and with the store removed the depth is the clear 1.0, not 0.0 |
| M_A3 — a general, selectable tile store | **REFUTED**: 0 of 2 304 mutations produced `color_moved` |
| M_A4 — carrier artefact | **REFUTED**: reproduced exactly on `c_depth2` |

### Exact accepted sets (numerator / denominator, never a bare percentage)

| byte | dispatched | distinct actual encodings | accepted | exact rule | cross-run agreement |
|---|---|---|---|---|---|
| `b3` (byte+3) | 256 ×2 carriers | 256 | 4 | `(v & 0xfc) == 0x00` | 0.99609 / 0.99609 |
| `b4` (byte+4) | 256 | 256 | 8 | `(v & 0x1f) == 0x00` | 1.0 |
| `b5` (byte+5) | 256 ×2 carriers | 256 | 128 | `(v & 0x02) == 0x02` | 0.99609 / 0.98828 |
| byte+1 (declared **match** `0x14`) | 256 ×2 carriers | 256 | 64 | `(v & 0x06) == 0x04` | 0.98828 / 0.99219 |
| byte+2 (declared **match** `0x54`) | 256 ×2 carriers | 256 | **256** | none — every value ok | 0.99219 / 0.99219 |

### db defect candidates (recorded, **not** applied — the orchestrator owns `db.json`)

- **byte+2 is declared a full-byte match (`match [16,8,84]`) and the hardware does not
  enforce it.** All 256 values leave both surfaces byte-identical on both carriers in both
  captures (512 dispatched, 512 `ok`). Bounded wording: *inert over 0..255 in the c_depth
  and c_depth2 fragment carriers with a depth attachment; global role unknown.* The arm's
  detection power is proven on the same instruction by `b5`, `b3`, `b4` and byte+1.
- **byte+1 is declared a full-byte match (`match [8,8,20]` = `0x14`) and only two bits are
  required:** the accepted set is exactly `(v & 0x06) == 0x04`, 64 of 256.

### Proposed label

`_instruction`: **`corpus-correlation` → `isolated-byte-diff`.** Not `hardware-run`: the
*instruction's role* is now semantically checked against an independent host predictor on
two carriers, but the operand map of `b3`/`b4` is unknown and no complete program was
generated from documented rules. Axes: geometry `geometry-mapped`, liveness `live`,
semantics `bounded-map`, recipe `not-generated`, target `G17P-direct`, reproducibility
`INCOMPLETE — Gate E not met`.

---

## 3. `vary_slot` — db.json's stated semantics is REFUTED against a working control

Carrier `c_vary4`: four varyings whose values are the widely separated constants
1000 / 2000 / 3000 / 4000, copied straight into the four colour channels. Any permutation,
duplication or dropout is directly readable and **names the slot that was used**.

**Positive control (Gate B), on the same observable, by a known mechanism.** Changing
`vary_store.out_slot` — byte+4 of a **different** instruction — matched the host-computed
model `out_slot == index << 5` on **26 of 32** cases exactly and agreed on **32 of 32**
across the two captures. All **six downward relocations were predicted and observed
exactly**, channel and value: e.g. store 7 (varying `v3`) with `out_slot = 0x80` puts
**4000.0 into channel 0**; with `0xa0`, into channel 1; with `0xc0`, into channel 2. The
six non-matching cases are all *upward* moves, where two stores then target one slot and
the model did not specify which writer wins — an omission in the model, not a failure of
the observable.

**Against that control, `vary_slot.slot` produced ZERO relocations in 256 values × 2
captures.** Its 256 values split exactly 128 `ok` / 128 `draw_gone` on bit 2.

| Model | Verdict |
|---|---|
| **M_B1** — `byte+3` is the varying slot, monotone, tracks the store slot (**db.json**) | **REFUTED** |
| **M_B2** — bit 2 is an enable; the other seven bits are inert here | **SELECTED**: 255 of 256 values match its per-case prediction exactly (128 `ok` iff `(v & 0x04) == 0`, 127 `draw_gone`; 1 cross-run disagreement) |
| M_B3 — fully inert | **REFUTED** |

This independently reproduces EXP-0172's DEF-0172-3 (*"only bit 2"*) on a **new carrier
with four separately identifiable varyings**, and strengthens it: not merely "bits 5–6 did
nothing", but **no value of the whole byte ever selects a different varying, while the
documented lever demonstrably does.**

Other bytes, exact accepted sets:

| byte | dispatched | accepted | exact rule |
|---|---|---|---|
| `sel` (byte+1) | 256 | 16 | `(v & 0x0f) == 0x0c` — high nibble free; `0x04` and `0x0a`, which `db.json` lists as valid forms, are **not** accepted here |
| byte0 (declared **match** `0x00`) | 256 | 60 | the contiguous range `0x00..0x3b`; not a fixed match byte |
| byte+2 (declared **match** `0x40`) | 256 | 4 | `(v & 0x7e) == 0x40` — bits 0 and 7 free |

**Proposed label: `_instruction` stays `corpus-correlation`.** Promoting it would certify a
slot selector that does not select. Semantics axis: `unknown` — db.json's model is refuted
and no replacement model is established. Reproducibility axis: `INCOMPLETE — Gate E not met`.

**A geometry observation worth passing on:** `c_vary4`'s vertex shader contains four
instructions of the shape `dX 0Y 40 ZZ` at offsets 70/80/90/100 that share `vary_slot`'s
byte+2 `0x40` but whose byte0 is **not** `0x00`, and which `isadb.instr_length` cannot
tokenize (`LEN_UNKNOWN` at offset 70). Together with byte0 accepting 60 values, this
suggests `vary_slot`'s `match [0,8,0]` is over-constrained and the family is wider. Not
resolved here.

---

## 4. `sfu_marker` — independently emitted, and its length CONFIRMED by insertion

**Method.** Insert the instruction, from bytes **we** generate, at an instruction boundary
**the compiler did not choose**, in a straight-line compute carrier that contains no `0x06`
leader of its own, shifting the tail into the container's zero alignment pad. If the
hardware consumes a number of bytes different from what we inserted, the following
instruction loses its leader and the stream desynchronises. The oracle is 32 host-computed
`uint`s, an independent pre-sentinel stored **before** the insertion point through its own
`device_store`, and two never-written 0xDEADBEEF poison regions — so *correct* / *wrong* /
*halted early* / *never ran* are four separable observations.

| payload | width | correct at |
|---|---|---|
| **`06 02`** | 2 bytes | **7 of 7 boundaries** (38, 52, 62, 74, 84, 94, 104), both captures |
| `00 00` | 2 bytes | 0 of 7 |
| `ff ff` | 2 bytes | 0 of 7 |
| *delete 2 bytes* | — | 0 of 7 |

That contrast is the length proof and the detection-power control in one.

**Match-bit correction.** `db.json` declares `(byte0 & 0x07) == 6` — 32 values. Of those
32, **exactly 8 are accepted, and they are exactly `(byte0 & 0x1f) == 0x06`**
(`0x06,0x26,0x46,0x66,0x86,0xa6,0xc6,0xe6`): bits 5–7 free, bits 3–4 must be 0. `byte0 =
0x0e` also satisfies the declared match but is `stop` — it halts the program (poison in the
output, sentinel present). 36 byte0 values are accepted in total at each swept site; the
other 28 have `(byte0 & 0x07) == 4` (the `get_sr`/`mov_imm` low-3-bits-100 family) and are a
**different descriptor**, so they are not evidence about `sfu_marker`.

**byte+1 is unconstrained for framing:** 256 of 256 accepted at boundary 94, 255 of 256 at
boundary 74 (the single exception is a lone fault against a clean observation on a
measured-busy machine). This does **not** contradict EXP-0146/EXP-0157: those measured
byte+1 in a **replacement** context inside an SFU carrier, where a wrong value produced a
wrong `fast::sin`. That is a **semantic** constraint on the SFU control word; this is a
**framing** constraint. Both hold, and the two axes must not be collapsed.

**Proposed label: `_instruction` `tokenization-only` → `isolated-byte-diff`.** Geometry
`geometry-mapped` (length 2 confirmed), liveness `accepted-inert in an integer-only compute
carrier / live in the SFU carriers of EXP-0146+0157`, semantics `bounded-map for framing
only — the micro-operation remains unknown`, recipe **`generated-point`**, target
`G17P-direct`, reproducibility `INCOMPLETE — Gate E not met`.

---

## 5. `frame_marker_compact` — the descriptor's LENGTH is refuted in the tested envelope

Same insertion method, same oracle, same carrier, same seven boundaries.

| payload | width | correct at |
|---|---|---|
| `60 01` | **2 bytes** | **0 of 7 boundaries** |
| `60 XX`, XX over 0..255 minus the two EXP-0172 hang hazards | 2 bytes | **0 of 254** |
| **`60 01 00 00`** | **4 bytes** | **7 of 7 boundaries** |
| `60 XX 00 00`, XX over 254 values | 4 bytes | **253 of 254** at boundary 74, **254 of 254** at boundary 94 |
| `00 00 00 00` (detection-power control) | 4 bytes | only **2 of 7** |

`db.json` models a 2-byte `frame_marker_compact` (byte0 `0x60`, byte+2 ≠ `0x00`) distinct
from the 4-byte `spill_frame_marker`, and `isadb.py`'s length rule chooses between them on
**byte+2 — a byte that lies outside the claimed 2-byte instruction**. On hardware, in this
envelope, the 0x60 leader consumes **four** bytes regardless of byte+1 and regardless of
byte+2. This supports EXP-0148's listing of `frame_marker_compact` as an **unresolved
continuation-word candidate**: the 2-byte reading is most simply explained as a 4-byte
instruction whose byte+2 and byte+3 were being read as the next instruction's leader.

In the 4-byte form: **byte+3 is inert over its full range** (256 of 256 `ok`), and
**byte+2 is constrained to exactly 40 of 256** values (`h0,h1,h2,h3,h7` for even `h`).
byte0 is **not** the declared full-byte match `0x60`: 12 of a 16-value control set are
accepted, including `0x20,0x30,0x40,0x50,0x70,0xa0,0xc0,0xe0`.

**Scope, stated precisely.** This is measured by **insertion into two straight-line compute
carriers at seven boundaries**. The corpus occurrences of `60 00 <nonzero>` are in
threadgroup-atomic and divergent-control-flow contexts that were **not** re-tested here. The
2-byte reading is refuted **in the tested envelope**, not proven impossible everywhere.

**Proposed label: `_instruction` stays `tokenization-only`** — its framing is now measured
and it disagrees with the descriptor, and its role remains unknown. Recipe:
**`generated-point` for the 4-byte form only.** Reproducibility axis:
`INCOMPLETE — Gate E not met`.

---

## 6. `n2_op6` — NOT promoted, and the reason was fixed before the run

Amendment 01 declared this arm `semantics: unknown` **in advance**, because `db.json`'s own
text calls the descriptor *"a genuine catch-all bucket"* whose *"per-sub-op value maps are
mixed"*. A bucket has no single operation to predict, so no independent predictor could be
written; `sem_checked == 0`, which per `RE_EXPERIMENT_PROCESS_CORRECTIONS` §2 can never
yield `hardware-run` or `semantically-mapped`.

What the arm *did* establish, on a **fourth** carrier and on G17P: all three swept bytes
are **live**, with exact accepted sets — byte0 `(v & 0xcb) == 0x02` (8 of 256, with 16
faults and 64 tile discards), `opsel` `(v & 0x1e) == 0x00` (16 of 256), `imm_sel`
`(v & 0x0f) == 0x04` (16 of 256). Replacing the whole instruction with a 6-byte barrier
discards the tile, so it is load-bearing. Every non-accepted value moved the **colour**
surface only, never the depth surface.

**Proposed label: unchanged, `corpus-correlation`.** Reproducibility axis:
`INCOMPLETE — Gate E not met`.

---

## 7. Hazards and negative results (first-class)

- **Inserting the 2-byte word `01 00` at a `k_line` instruction boundary hung the GPU 5
  times out of 5** (`kIOGPUCommandBufferCallbackErrorHang`), in prefreeze pilot 02. The
  device recovered every time; **no `macvdmtool` was needed and none was run**. Excluded
  from the frozen matrix and reported here. `01 00` is `db.json`'s `n1_word`
  (`match [[0,8,1],[8,8,0]]`, length 2) — a descriptor whose independent emission at an
  arbitrary boundary is therefore **hazardous**, not merely wrong.
- `frame_marker_compact` `b1 ∈ {3,7}` (EXP-0172's device-hang hazard) was excluded from the
  2-byte-form subset and not re-tested; the other 254 values were.
- **0 hangs across both gated confirmation captures** (13 014 cases).
- Inserting `0e 02` (which satisfies `sfu_marker`'s declared match) halts the program: the
  output region stays 0xDEADBEEF poison while the pre-sentinel is written. `0x0e` is
  `stop`. This is a **match-bit collision the database currently allows**.

## 8. Limitations — what this experiment does NOT establish

1. Nothing about M4/G16G. Every result is `G17P-direct`.
2. `frag_depth_store`'s `b3`/`b4` operand meaning is unknown; only their accepted sets are
   measured. No compiler recipe is generated for any instruction here.
3. `sfu_marker`'s and `frame_marker_compact`'s **micro-operations** remain unknown. Framing
   is not semantics, and the labels above say so.
4. The marker framing results come from **insertion into straight-line compute carriers**.
   `frame_marker_compact`'s corpus contexts (threadgroup atomics, divergent control flow)
   were not re-tested; `sfu_marker`'s SFU context was tested by EXP-0146/0157 by
   replacement, not here.
5. Inertness findings (`frag_depth_store.byte2`, `frame_marker_compact.byte3_in_4byte`) are
   bounded to their exact tested envelope. They do **not** meet FIELD-SWEEP-PROTOCOL §9's
   four-part criterion for a general inert-field promotion (three structurally different
   carrier classes), and none is proposed for promotion.
6. **Gate E is NOT met and no verdict here is `independently-confirmed`.** Confirmation ran
   on a **measured-busy** machine (median 9, peak 17 concurrent foreign GPU processes); the
   orchestrator has confirmed a quiet window is currently unobtainable for the whole
   fan-out. Adjudication was done offline from the poison and the sentinels, per EXP-0160's
   filter, not by re-running. Every promotion below is **held** pending a serialized quiet
   confirmation pass. Gates A, B, C and D are complete.
7. `raw/g17p_conf02` (13 records) and `raw/g17p_conf03` (2 records) are **retained defective
   partials** — the first crashed on an unguarded baseline comparison, the second aborted
   correctly once the guard was added but before the baseline was scored against itself.
   Neither was topped up or reused; `g17p_conf04` is the replacement.
