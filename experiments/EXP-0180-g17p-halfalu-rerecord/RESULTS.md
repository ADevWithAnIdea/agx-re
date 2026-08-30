# EXP-0180 — RESULTS

**Status: COMPLETE.** Two gated runs on the **Apple A18 Pro / G17P**, plus a pilot.
Everything below is a **G17P** claim; nothing is promoted to any other target.

| run | order | cases | fault | hang | `carrier_dead` | `invalid_run` | `measurement_failed` | `sentinel_bad` |
|---|---|---|---|---|---|---|---|---|
| `g17p_run02` | reverse | 16,735 | 400 | **0** | **0** | 0* | **0** | **0** |
| `g17p_run03` | forward | 16,735 | 400 | **0** | **0** | 0* | **0** | **0** |

`matrix_sha256` `bcfcf5260b3cb5ffe2f58be6a061bdad21fec537ba79c4e77a073e2a776219be`, **identical in
both**. \*the 400 `seed_ok=False` records are exactly the 400 `fault` cases, which produce no
observation at all; no case that produced an observation failed the seed check.

> **Cross-run agreement: 100.0000%. All 16,735 cases, zero disagreements**, on the full
> observation digest (16 post-registers + both sentinels + the stray-word map) — instruments
> included. Outcome counters are byte-identical: 11,711 `wrong_value` / 4,396 `ok` /
> 400 `fault` / 228 `silent_zero` in each run.

**Run id `g17p_run01` is BURNED** (§9). `raw/g17p_run01/` is retained containing only its
procsample trace; it also carries the quiet-window measurement for the `run02` window.

---

## 1. The headline: what happens to the 25 row-claims

**25 row-claims over 16 DISTINCT FIELDS.** The nine `EXP-M4-14` rows are a **strict subset** of
the sixteen EXP-0169 held, so nine fields carry two claims and get two verdicts: does the
**field** substantiate, and does the **committed claim** reproduce. *A field can substantiate
while its claim is refuted, and eight of the nine did exactly that.*

### 1a. Set (a) — the 16 HELD rows: **15 substantiated, 1 is not a field**

| # | field | verdict | label | measured range | moved (C_HI / C_LO) | agree |
|---|---|---|---|---|---|---|
| 1 | `half_alu_ext8.dst` | **LIVE-FULL** | `hardware-run` | 256/256 | 254 / 254 | 100% |
| 2 | `half_alu_ext8.srcA` | **LIVE-FULL** | `hardware-run` | 256/256 | 254 / 254 | 100% |
| 3 | `half_alu_ext8.b5` | **LIVE-FULL** | `hardware-run` | 256/256 | 254 / 254 | 100% |
| 4 | `half_alu_ext8.rsv6` | **LIVE-FULL** | `hardware-run` | 256/256 | 252 / 248 | 100% |
| 5 | `half_alu_ext8.opflags` | **LIVE-FULL** | `hardware-run` | 32/32 | 30 / 30 | 100% |
| 6 | `half_alu_ext8.b7_lo` | **LIVE-FULL** | `hardware-run` | 2/2 | 1 / 1 | 100% |
| 7 | `half_alu_ext8.saturate` | **LIVE-FULL** | `hardware-run` | 2/2 | 1 / 1 | 100% |
| 8 | `half_alu_ext8.b7_mid` | **LIVE-FULL** | `hardware-run` | 32/32 | 28 / 28 | 100% |
| 9 | `half_alu_ext8.op_valid_marker` | **INERT-MULTI** | `hardware-run` (inert) | 2/2 | 0 / 0 | 100% |
| 10 | `half_alu_ext8.opsel` | **LIVE-PARTIAL** | `isolated-byte-diff` | **3** of 8 | 2 / 2 | 100% |
| 11 | `half_alu_ext8.srcB_desc` | **LIVE-PARTIAL** | `isolated-byte-diff` | **64** of 256 | 60 / 60 | 100% |
| 12 | `half_alu_fma12.dst` | **LIVE-FULL** | `hardware-run` | 256/256 | 254 / 254 | 100% |
| 13 | `half_alu_fma12.srcA` | **LIVE-FULL** | `hardware-run` | 256/256 | 254 / 254 | 100% |
| 14 | `half_alu_fma12.opflags` | **LIVE-FULL** | `hardware-run` | 32/32 | 30 / 30 | 100% |
| 15 | `half_alu_fma12.opsel` | **NOT-A-FIELD (1 legal value)** | → `match` | **1** of 8 | 0 / 0 | 100% |
| 16 | `half_alu_fma12.ext` | **NOT-A-FIELD** | `untested` + defect | 1856 of 2^64 | — | 100% |

Rows 10, 11, 15 carry the **measured** encodable range from the arms the LEN map covers
(`E8_FMA`, `E8_ADD`, `F12_FMA`). `analysis/field_verdicts.json` also reports a larger
`measured_encodable_range` for rows 10/11/15, taken as the **max** over arms as the frozen rule
says; the larger figure comes from the lift-control arms, whose exclusions are driven by *our
tokenizer* failing to length the block rather than by the hardware. **The hardware-measured
numbers above are the defensible ones and are what I recommend acting on.** Both are in the
committed JSON; nothing is hidden.

### 1b. Set (b) — the 9 `EXP-M4-14` claims: **1 reproduces, 6 are refuted, 2 are citation defects**

`EXP-M4-14` has **no `raw/` tree at all** (EXP-0164). Each claim was restated as a prediction
and tested value by value with a host-computed oracle.

| row | committed claim (verbatim) | verdict |
|---|---|---|
| `ext8.rsv6` | "0x00..0xc0 swept, every value kept the result — **fully INERT/reserved**" | **REFUTED.** LIVE at 252/256 and 248/256 on two carriers, **13 distinct architectural results**, 100% cross-run |
| `ext8.op_valid_marker` | "every byte+7 value **without bit7 set nulls the op** — a required op-valid marker" | **REFUTED.** 0 of 2 moved, two carriers, three arms, both runs. The op *is* nullable from byte+7 — but by **`b7_mid` bit 2 = instruction bit 60** (`b7_mid` ∈ {4,5,6,7} leaves the destination untouched), not bit 63 |
| `ext8.saturate` | "byte+7 0x82 **clamps** saturate(9) to 1; 0x80 passes 9 unclamped" | **REFUTED as semantics.** The field is LIVE, but it is not a clamp: on `C_HI` (result **7.0586**) it yields **2.84375** — the third operand's value, not 1.0 — and on `C_LO` (result **0.125**, where a clamp *must* be a no-op) it changes the result to **0.46875**, again the third operand. **A clamp cannot change a sub-unit result.** Bit 57 suppresses the multiply term |
| `ext8.srcB_desc` | "**0x01 required** in the add+saturate instance; carries the fma srcA-negate (byte+7 0xc0→0xc8)" | **REFUTED as an operand.** "0x01 required" is a **length** requirement: `byte+4 & 3` is the length selector. Only 64 of 256 values keep the 8-byte framing, and inside that subset the pre-registered same-length step (`byte+4 += 4`, a different half-register at the same length) **does not move on any arm**. byte+4 has no detectable operand role. The cited byte+7 example is a different field |
| `ext8.b5` | "bits3/4 null in this instance; **largely inert**" | **REFUTED where testable.** LIVE at 254/256 on both carriers and on the lifted anchor. The claim is about the add+saturate instance, which **this experiment could not test** — see §4 |
| `ext8.opsel` | "gains 6 = hfma (byte+2 = 0x1e)" | **REPRODUCES, range overstated.** opsel 6 selects the fma form. But opsel is a length input: only 3 of 8 values keep the 8-byte framing |
| `fma12.opsel` | "6 = hfma (byte+2 = 0x1e)" | **REPRODUCES — as a `match` bit.** Exactly **one** of 8 values yields a 12-byte instruction. One legal value ⇒ it belongs in `match`, not `fields` (the `falu2_uni.uni_mode` finding, EXP-0175/EXP-0169 §16b) |
| `ext8.srcA` | "byte+3 0x02 works, 0x04/0x06 break; **byte+6 swept 0x00..0xc0 all inert**" | **Field reproduces; CITATION DEFECT.** byte+3 *is* `srcA` and is LIVE 254/256. The second clause documents **byte+6 = `rsv6`**, a different field — and that clause is the *entire* evidence `rsv6`'s own row rests on. One sentence, one experiment with no raw, two promoted rows |
| `fma12.srcA` | "byte+4 0x83 → fma(\|a\|,b,c); 0x82 → \|a\| alone; 0x80 → 0" | **Field reproduces; CITATION DEFECT.** `fma12.srcA` is bits 24..31 = **byte+3**; the claim documents **byte+4**, which lies inside `ext`. And `0x83/0x82/0x80` differ in `byte+4 & 3`, so they are partly a **length** change (12 / 10 / 6 bytes), not an operand modifier |

### 1c. What I recommend WITHDRAWING

**Withdrawing what cannot be reproduced was the stated goal, and six things must go.** None of
them is a *field* — every one is a **semantic claim or a range** attached to a field that does
substantiate. That distinction is the main result:

1. **`ext8.rsv6`'s `range`** — "fully INERT/reserved" is false. Withdraw the text; the
   `hardware-run` label survives on new evidence (252/256 moved) with a new range.
2. **`ext8.op_valid_marker`'s `range`** — "a required op-valid marker" is false for bit 63.
   Withdraw and replace with instruction bit 60.
3. **`ext8.saturate`'s `range`** — the clamp semantics are false. Withdraw.
4. **`ext8.srcB_desc`'s `range` and its 256-value range** — withdraw; encodable range is **64**
   and no operand role is detectable.
5. **`fma12.opsel` as a field** — one legal value; fold into `match` (`db_defects`).
6. **`fma12.ext` as a field** — 64 bits, 2^64, byte+4 is the length selector; not a field.

`ext8.srcA` and `fma12.srcA` keep their labels but their **`range` strings must be corrected**:
each documents a byte the field does not cover.

---

## 2. Why this run could answer what two previous attempts could not

### 2a. The carrier repair, measured

Every GPR now carries **two distinct non-zero normal fp16 lanes**. On hardware, `seed_ok=True`
and the frozen adequacy predicate `True` on all 11 (arm, carrier) anchors, in both runs; the
observed pre-dump is **bit-identical to the predicted seed vector**. EXP-0169's carrier had zero
low halves, so only 28 of 256 descriptor values could move anything; here all 256 are
informative. `analysis/field_verdicts.json` shows the consequence directly: `dst`, `srcA`, `b5`
each moved on **254 of 256** values, against EXP-0169's 28.

### 2b. The falsifier EXP-0169 held 16 rows on was never a falsifier

`byte0 → 0x00` does not null this family's op — it **relocates the destination** (§3). `half_alu`
moved anyway because its result happened to be non-zero; `half_alu_ext8`/`half_alu_fma12` could
not because theirs was `0`. The ladder step that failed could not have succeeded for the right
reason. **This experiment removed it from the ladder and put it in its own arm, where relocation
is the thing being measured.**

### 2c. No moving baseline anywhere

The anchor observation is captured **once** per (arm, carrier) per run and never refreshed, and
every case proves its own seeds through a PRE-dump. DEF-0169-1's failure mode — a differently
seeded baseline recording up to 250 cases as *fabricated* movement — is structurally impossible
here, and would have been caught per case if it were not.

---

## 3. DEF-0180-1 CONFIRMED: the destination is byte0's HIGH NIBBLE

`DSTNIB` arm, `byte0 = n<<4`, `n = 0..15`, two carriers, both runs, 100% agreement:

    n=0   r0  40a044a0 -> 40a0470f          n=7   r7  415044f8 -> 4150470f
    n=1   r1  3fc04440 -> 3fc0470f          n=14  r14 00000000 -> 0000470f

**The result is written into `r[n]`'s LOW 16 bits and `r[n]`'s HIGH 16 bits are preserved**, for
every `n`. Two exceptions, both harness artefacts and both explained: `n=15` is the store index
register the harness re-seeds before every store, and on `C_LO` `n=13` is the second-consumer
destination.

**A second, independent confirmation is structural:** the seed program itself writes the low
halves with `byte0 = (j<<4)|0x0` for `j = 0..13`, and all 14 landed in `r_j` in **every program
of every one of the 33,470 gated cases**. The finding does not rest on one arm.

**And a third, arithmetic one:** `E8_FMA@C_HI` computes `r1.lo = 0x470f = 7.0586 =
1.625 × 2.59375 + 2.84375` = **byte+3 × byte+1 + byte+5**. db.json's `dst` (bits 8..15) appears
in the arithmetic as a **source**. byte+4 does not appear at all.

> **HW-VALIDATED, G17P: `db.json` pins all eight bits of byte0 in `match`, so an emitter
> following it can only ever write `r1`, and its `dst` field names a source.** Same class as
> `mov_zext16`/DEF-0161-2, `n3_mov`, `cvt_f2h_dst` — all of which `db.json` already documents
> correctly one family over.

---

## 4. DEF-0180-2 CONFIRMED, and the length rule is now MEASURED — 4,096 cases, zero ambiguity

`LEN` arm: four 2-byte `mov_imm` markers at byte +6; the surviving-marker count reads the
hardware's instruction length directly (4→6B, 3→8B, 2→10B, 1→12B, 0→14B). Zero point (the chain
with no instruction in front) gave **4 in both runs**.

    MEASURED HARDWARE LENGTH, byte0 == 0x10   (opsel = byte+2 & 7, m = byte+4 & 3)

      opsel          m=0    m=1    m=2    m=3
      0,1,2,3,7       10     10     10      8
      4  (hadd)        6      8     10      6
      5  (hmul)        6      8     10      8
      6  (hfma)        6      8     10     12

**No cell shows more than one length.** `opflags`, byte+4's upper six bits and byte+1/+3/+5 are
all irrelevant to length. *Bound:* bytes +6.. are the marker chain in every case, so a length
dependence on byte +6 or later is **untested**.

Both committed models are wrong, in different cells (`analysis/length_rule.json`):

* `db.json`'s `"6, or 8 if (byte+2 & 0x02)"` — wrong in **25 of 32** cells; it has no byte+4 term.
* `isadb.instr_length`'s implemented rule — wrong in **18 of 32** cells, including
  **(opsel 4, m 3): predicts 12, measured 6** and **(opsel 6, m 0): predicts 8, measured 6**.

**DEF-0180-3 is REFUTED as I stated it, and I withdraw my own claim.** All four of our compiled
instances are lengthed correctly by the measured rule — `k_hadd` (4,0)=6, `k_hsat` (4,1)=8,
`k_hfma` (6,1)=8, `k_hfma_abs` (6,3)=**12**. `half_alu_fma12` **is** a real 12-byte instruction
at (opsel 6, m 3); it is not an over-consumer there. What survives is narrower and still true:
`ext` is 64 bits over a 2^64 space and its byte+4 is the length selector, so it is not a field.

### A second exact wall, in `opflags`

    fault  <=>  (byte+2 >> 3) >= 16  AND  (byte+2 & 7) in {4, 5}

**`opflags` bit 4 (instruction bit 23) set, with `opsel` = hadd or hmul, faults
unconditionally** — 128 LEN-arm cases, zero counterexamples, and independently reproduced in the
field sweeps: the `E8_ADD` (opsel 4) `opflags` sweep faults at exactly 16..31 while `E8_FMA` and
`F12_FMA` (opsel 6) fault at none. Faults were contained: **no hang, no device reset, no
`macvdmtool`.**

---

## 5. The instruments, and the arm this experiment REJECTED

| arm | falsifiers | core ladder | admitted? |
|---|---|---|---|
| `E8_FMA` @ C_HI, C_LO | 3/3 fire | 4/4 move | **yes, two carriers** |
| `F12_FMA` @ C_HI, C_LO | 3/3 fire | 4/4 move | **yes, two carriers** |
| `E8_LIFT`, `F12_LIFT` @ C_HI | 3/3 fire | 4/4 move | **yes** |
| `E8_ADD` @ C_HI, C_LO | **0/3** | **0/4** | **REJECTED — no detection power** |

**`E8_ADD` is reported, not worked around.** Its base (`opsel = 4` in the 8-byte form) writes
nothing at all: every falsifier and every ladder step scored `ok / match=True`, on both carriers
and in both runs. That is the same failure as `iter_at.loc` at one sample and `get_sr` at
grid=1, and it is why the `EXP-M4-14` `b5` and `srcB_desc` claims — which are explicitly about
the **add+saturate instance** — remain untestable in their own instance. `E8_FMA` covers the
same 11 fields on two carriers, so no row is lost; but the instance-specific half of two claims
is an honest **open bound**, not a result.

Two ladder steps deliberately do **not** move, and both were declared diagnostic in
`harness/casematrix.py` **before the run** (that file is hashed in `CAPTURE_CONTRACT.json`):
`L_srcB_desc_samelen` — its non-movement **is** the finding that byte+4 is a pure length
selector — and `L_ext_b9`.

### Geometry was measured, not asserted
Every falsifier and ladder step, in every arm and carrier, gave **identical outcomes at
`grid=1/tg=1` and `grid=32/tg=32`** (`raw/pilot01`). EXP-0178 root-caused EXP-0169's `get_sr`
failure as geometry; this family is not geometry-sensitive, and that is now a measurement.

---

## 6. Instrument integrity

* **Poison + `carrier_dead`:** 0 cases in 33,470. EXP-0179 lost 1,395 cases to a frozen-but-dead
  carrier; the detector was armed here and never fired.
* **DEF-0178-1:** `harness/saferunner.py` (one reader thread per child) was used throughout;
  `tools/agxtest/persistrun.py` was **not modified**. `measurement_failed`: **0 cases**.
* **Hangs: 0.** 400 faults, all contained, all in the two mapped walls.
* **Victims:** 48 in `run02`, all `E8_ADD` `fault` cases whose three attempts were all
  `kIOGPUCommandBufferCallbackErrorInnocentVictim`; they are inside the opflags wall, which the
  LEN arm maps independently, so no verdict rests on them.
* **`sentinel_bad`: 0.** **`rt_ok` was recorded on every case and is cited nowhere.**
* **Remote verification:** `harness/verify_remote.py` reported **18/18 blobs matching on the
  neo** immediately before each capture. The pinned `db.json` (`a77f8cfa…`) travelled with the
  experiment and `isadb` resolves **only** to `work/frozen/` — `00_env.json` records the
  resolved path.
* **Quiet window: measured, and there was none.** 100 of 100 procsample samples across both
  gated windows recorded foreign GPU activity — EXP-0178's `agxrun_persist` and `rendersweep`,
  plus `MTLCompilerService`. The pair nevertheless produced **byte-identical counters and
  100.0000% per-case agreement**, which extends EXP-0169 §12: for a `mov_imm`-seeded carrier
  with per-case seed proof, concurrency cost this pair nothing measurable.

## 7. Coverage keys

**16 of 16 rows carry every required key** — `values_dispatched`, `distinct_bytes`,
`encodable_range`, `start`, `width`, `coverage_pct`, `thin`, `under_covered`, plus
`measured_encodable_range`, `measured_encodable_range_lenmap` and `expressiveness`.
**0 spans moved** — `analysis/merge_check.py` re-asserts that and refuses the merge otherwise
(16 rows checked, 0 refusals).

**One row is flagged `under_covered`, and the flag is correct**: `half_alu_fma12.ext` dispatched
2,048 values but produced **2,041 distinct encodings**. `ext` is 64 bits swept byte-wise, so in
each of its eight byte sweeps the value that equals the anchor's own byte re-encodes the anchor;
seven of those eight collide (the eighth byte's anchor value is unique). That is the
`distinct_bytes` instrument doing exactly what it exists for — counting **encodings**, never
dispatched values — and it is a further reason the row cannot be promoted. Every other row has
`distinct_bytes == values_dispatched`.

## 8. Limitations

* The **add+saturate instance** of `half_alu_ext8` has no working carrier here, so two
  `EXP-M4-14` claims are refuted only in the fma instance (§5).
* The length rule is exact **within bytes 0..5**; a dependence on byte +6 or later is untested
  (§4).
* `gate_expressiveness` never had to fire: `rsv6`, `b7_lo` and `b7_mid` all turned out **LIVE**,
  so the rule that would have blocked promoting their *inertness* was not needed. It remains the
  right rule, and it is the reason the `rsv6` result is a refutation rather than a re-promotion.
* `half_alu.*` was swept only as an instrument control; **no verdict is emitted for it**, though
  §3 bears directly on `half_alu.dst`.
* Everything here is **G17P**. The committed rows being corrected are labelled A18 or M4.

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/{carrier_dag,carrier_uni,probes}.metal (authored by us in this
  project) and the AGX machine code the PUBLIC runtime API (`newLibraryWithSource:`, via
  tools/shdump) compiled from that source; the committed raw/ trees of EXP-0169, re-read
  offline; tools/{shdump,agxtest,agx-isa} READ-ONLY and unmodified.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. The only machine code inspected or spliced is
  the compiled form of our own MSL.
Reproduction: README.md
Evidence: raw/pilot01, raw/g17p_run02, raw/g17p_run03 (and raw/g17p_run01, burned),
  analysis/{field_verdicts,reproduction,length_rule,db_defects}.json, work/target_rows.json,
  work/remote_verify.json, work/selftest.json
```
