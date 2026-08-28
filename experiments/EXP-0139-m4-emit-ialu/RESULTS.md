# RESULTS — EXP-0139: making the integer-ALU family *emittable*, not merely decodable

**Status: PARTIAL / SUBSTANTIAL PROGRESS.** Of the **137 blocking fields** across the
16 integer-ALU instructions, **73 reached emitter grade** (39 `hardware-run`,
34 `isolated-byte-diff`) and **64 remain blocked**. **Two instructions became emittable:
`ibitcount` (8/8 fields) and `iunary` (3/3)** — precisely the two single-field blockers the
dispatch prioritised. **129,839 GPU dispatches**, four captures, **0 hangs**, 0 reboots.

**Target: local Apple M4 / G16G only** (macOS 26.6.2 / 25G82, Metal 4). No A18 Pro claim
anywhere; the A18 is hands-off. No M5 evidence used or produced.

**Concurrency (`FIELD-SWEEP-PROTOCOL` §7.4): this experiment did NOT run alone.** It was
scheduled in a batch with **two other GPU-contending experiments — EXP-0141 (MEM) and
EXP-0146 (integer misc)** — and the contamination that §7 warns about is visible in the raw
data and was measured, not assumed (§3).

---

## 0. Headline

| | count |
|---|---|
| blocking fields at dispatch (validation.json vs db.json) | **137** |
| → `hardware-run` after this experiment | **39** |
| → `isolated-byte-diff` after this experiment | **34** |
| → still blocked | **64** |
| instructions that became **emittable** | **2** (`ibitcount`, `iunary`) |
| distinct field values executed on hardware | 29,685 cases × 2 in-run repeats × 2 gated launches |
| total GPU dispatches | **129,839** |
| genuine GPU hangs | **0** |

**The 64 that remain blocked are not random.** **32** of them are **operand-selector** fields
(`cmpA`, `cmpB`, `selTrue`, `selFalse`, `srcA`, `srcB`, `dst`, `dst_full`, `sel_operand`,
`opB`, `srcC_lo`) and a further **12** are compare/condition selectors (`cc`, `cmp_mode`,
`cmpmode`, `cond`) — 44 of 64, concentrated in the `isel*`/`icmpsel`/`imad`/`iminmax`
families. A single-carrier splice sweep can prove such a field is live and
enumerate which values keep the program correct, but it cannot establish the
**value → register-number mapping**, because every wrong value points at a register the
carrier never seeded. Closing them needs a seeded-register carrier per family, the way the
`iadd2` and `ibitcount` arms here were built. That is the single highest-value follow-up.

---

## 1. What was directly OBSERVED (per priority, as dispatched)

### 1.1 `ibitcount.tail` — CLOSED. The only field blocking `ibitcount`.

**Observed.** On a **fully synthesized** program (16 `mov_imm` seeds → `ibitcount` →
`device_store` → `stop`; nothing copied from a compiler template), `tail` swept **densely
over all 256 values**, twice per launch and in two launches:

- all **128** values with **bit 2 (0x04) set** return the correct `popcount(r3=91) = 5`;
- all **128** values with bit 2 clear return a wrong, constant, **non-zero** value (1);
- deterministic in every one of the four observations of every value.

**Interpreted.** `tail` is not a `0x04` marker: **only bit 2 is load-bearing**, and bits
0,1,3,4,5,6,7 are free. An emitter must set bit 2 and may choose the other seven bits
arbitrarily. This supersedes the `single-template-inference` / "0x04 marker in every observed
instance" label.

The pre-registered falsifier fired correctly: `tail = 2`, which EXP-0129 had observed
degrading the GPR read, is `predict = mismatch` and did mismatch.

**With `tail` closed, every one of `ibitcount`'s 8 fields is `hardware-run` → `ibitcount` is
EMITTABLE.**

### 1.2 `iunary.operand` — CLOSED, and db.json's descriptor is wrong. (`db_defects` DEF-0139-1)

`db.json` models `operand` as **one 40-bit `raw` field** holding a "MIXED" popcount source /
SFU-interp / format-conversion coefficient word. No `iunary`-tokenizing instruction exists
anywhere in 30 authored MSL probe kernels, so the field looked unreachable.

**Method.** The pilot (`PROGRESS.md` M1, `work/pilot/p8_iunary.py`) searched the 8-byte
`byte0 == 0x27` encoding space for members that tokenize as **`iunary` and not `ibitcount`**
(the tighter descriptor otherwise wins) and still compute. `byte+1 = 0x2d` with
`byte+2 ∈ {0x22,0x26,0x07,0x66,0x46,0x76}` is such a member. The arm then swept all five
`operand` bytes on a synthesized program built around it.

**Observed.** The 40-bit blob is **five one-byte sub-fields with exactly `ibitcount`'s
meanings**:

| operand byte | is | evidence |
|---|---|---|
| +3 | `dst`, reg<<1 | corrected relocation oracle matched **15/16** over r0..r15 |
| +4 | `op_enable` | dense 0..255: **bit 1 alone** decides, 128 work / 128 do not |
| +5 | `src`, reg<<2 | model matched **16/16** over 16 distinct `mov_imm`-seeded registers |
| +6 | `srcdesc` | dense 0..255, deterministic |
| +7 | `tail` | dense 0..255, **identical bit-2 rule** to `ibitcount.tail` |

**Interpreted.** For the `byte0==0x27` / length-8 space the loose `iunary` descriptor and the
tight `ibitcount` descriptor describe the **same five operand bytes**. The `operand` raw field
should be split. (The RT/interp siblings — `opsel 0x22` with `byte+1 == 0x81` — are a
*different length class* and this finding does not cover them; that is stated in the defect
record.) **`iunary` is now 3/3 `hardware-run` → EMITTABLE.**

Note the `op_enable` result is *stronger* than the prior EXP-M4-14 datum: EXP-M4-14 sampled
`0x00..0x0a`; this arm swept all 256 and the bit-1 rule holds without a single counterexample.

### 1.3 `iadd2` — 8 of 12 blocking fields closed; two cross-experiment corrections

Built directly on EXP-0128's HW-VALIDATED register-mode rule (`srcA = 0xA8` reads r0,
`srcB_imm = 4N` selects r*N*, subtract polarity `rN − r0`, `dst` a full 7-bit field) — not
re-derived. The carrier seeds **all 16 registers with distinct values**, so a field that
re-selects a register *decodes which one* from the observed sum.

**`dst` (dense 0..255, relocation oracle):** the sum reaches the store's register r6 at
**exactly `dst = 12/13` and nowhere else below reg 96**. Two hardware facts follow:

1. **Fault bound, sharper than the prior claim.** `reg ≥ 96` (`dst ≥ 192`) faults
   **reproducibly** — 60 dense values, each 5/5 attempts in a fresh process with healthy
   baselines before and after. EXP-0112's "faults at 126/127" is too narrow; this is
   consistent with EXP-0020's "up to 96 regs".
2. **EXP-0112's `r(R mod 64)` aliasing rule does NOT hold for `iadd2.dst`.** `dst = 140/141`
   is reg 70, which would alias r6; r6 kept its sentinel. The sweep tests aliasing at exactly
   one point, and at that point it is refuted. (`db_defects` DEF-0139-4.)
   `dst = 30/31` (reg 15) is a carrier artefact, not a field property: r15 is this program's
   store index register, so writing the sum there moves the store.

**`srcB_reg_hi` — EXP-0128's disclosed failed refuter is now explained.** EXP-0128 forced
`srcB_reg_hi = 8` expecting corruption and got the correct answer, and left the field
`UNKNOWN`. Sweeping **all 128 values** here: every one reproduces `r0 + r2 = 32`. The field is
**INERT across its entire encodable range** in this construction — not merely inert at 8.

Also closed: `lenbit` (bit 0 alone; the pre-registered falsifier `lenbit = 0` selects the
12-byte form and over-consumes the following `device_store` — it mismatched as predicted),
`b2_bit0`, `store_en`, `b2_fmt`, `opmode`, `srcB_imm_hi`.
`srcA`, `opc_tail`, `opc_tail2` reached `isolated-byte-diff` (a 2–4-bit rule fully decides
correct execution). `srcB_ext` remains blocked: only values 0–3 work and no ≤4-bit rule
explains the partition.

### 1.4 `ibfe` — the bare-instruction answer EXP-0102 asked for (`db_defects` DEF-0139-2)

EXP-0102 could only characterise Metal's **compiled sequence** for `extract_bits` with runtime
operands and explicitly recommended "independently assemble a bare `ibfe` with an explicit
width field and splice-execute it". Done here, on the single-`ibfe` carrier
`o = extract_bits(a, 4, 8)`.

**`offset` and `width` of the same instruction use OPPOSITE out-of-range rules:**

- **`offset` is LITERAL.** Dense 0..63: values 0–31 shift normally; values 32–63 shift the
  field out entirely (result 0). The literal model fits **64/64** stable values; a mod-32
  model fits only 32/64. **The hardware does not implement NIR's "mask offset mod 32."**
- **`width` is TAKEN MOD 32 — and this REFUTES the model this experiment pre-registered.**
  The pre-registered "literal, clamp at 32" model fits only **37/64**; `width mod 32` fits
  **64/64**. `width ≡ 0 (mod 32)` is the no-mask (extract-to-MSB) case, so `width = 32`
  behaves exactly like `width = 0`.

This is a *refuted* pre-registration, reported as such, with the competing model scored on the
same data (`analysis/verdicts.py :: oracle_corrections`).

10 of `ibfe`'s 16 fields are now `hardware-run`, 4 more `isolated-byte-diff`.
A second, independent `ibfe` carrier (`k_shr`, a different lowering of the same instruction)
was swept as an adversarial cross-check and is reported per field in `field_verdicts.json`.

### 1.5 `ishift.shamt`, `iminmax.sel` — two db.json corpus maps confirmed on hardware

- **`ishift.shamt`**: `shamt = n << 2`, `o = a >> n` arithmetic — matched **32/32** at every
  multiple of 4 from 0 to 124 (n = 0..31), against a host computation over 8 operands
  including `0x80000000` and `0xFFFFFFFF`.
- **`iminmax.sel`**: db.json's corpus-derived map is **confirmed on hardware for the four
  integer members** — `4=umax, 5=umin, 6=imax, 7=imin`, each matching an independent host
  oracle over 8 asymmetric/boundary pairs. `sel = 0/1` (fmax/fmin) execute and behave as float
  max/min but disagree with a naive IEEE oracle **exactly on the NaN and denormal operands**
  in this carrier's integer input vector, i.e. the hardware **flushes denormals to zero and
  suppresses NaN** in min/max. A normal-float carrier is the named follow-up. This arm was
  under the dispatch's special instruction (EXP-0113 nondeterminism): every `iminmax` case ran
  4× across two launches and **all four observations agreed for every one of its 858 cases**.

### 1.6 `isel_reg8` — extrapolate-and-test succeeded (`db_defects` DEF-0139-5)

`isel_reg8` occurs **nowhere** in our own compiled corpus; db.json only *infers* that it
"adopts the isel8 field layout". Constructing it by rewriting the `isel8` anchor's `byte+2`
from `0x0f` to `0x25` produced an instruction the hardware **accepts and executes
deterministically** (it changes the result rather than faulting), and all seven of its fields
respond to a dense 0..255 sweep. The instruction is real and reachable even though the
compiler never emits it.

---

## 2. What did NOT close, and why (named, not dropped)

- **`ibfe_mesh_attr` (3 fields).** No anchor: it is the fragment/mesh-stage packed
  per-primitive-attribute source mode (`byte+2 == 0x66`); 30 authored compute kernels produced
  none and this harness is compute-only. Declared out of scope in `PRE_REGISTRATION.md` §7.
  Follow-up: a mesh/fragment carrier on `tools/agxtest/agxrender.m`.
- **44 operand- and condition-selector fields** (32 operand selectors + 12 compare/condition
  selectors) across `isel8/isel10/isel10_c/isel_reg/isel_reg8/icmpsel/imad/iminmax/ishift/
  icmp_pred`. They were swept densely and deterministically; the raw log
  enumerates the outcome of every value; but the value → register mapping is not established,
  so they are labelled **`untested` with the full enumeration in `note`**, per
  `validation.json`'s own `tested-but-unexplained` convention. **They are not rounded up.**
- **`iadd2.srcB_ext`, `ibfe.dst`, `ibfe.b5`, `ibfins.{dst,mask_imm,b6hi,b7,srcdesc,b10}`,
  `icmpsel.tail`** — same reason.

### The labelling rule actually applied (so a reader can audit it)

A dense sweep **alone never promotes a field**. Promotion required a rule an emitter can apply:

| label | requires |
|---|---|
| `hardware-run` | a pre-registered model matched over its domain, **or** the field is inert across its whole encodable range, **or** a **≤1-bit** rule fully decides correct execution |
| `isolated-byte-diff` | a **2–4-bit** rule fully decides correct execution ("fix these bits, the rest are free") |
| `untested` | everything else — exercised on hardware, deterministic, fully enumerated in `raw/`, semantics **not** established |

**Merge policy:** evidence accumulates, so each field takes the **stronger** of (the label
already in `validation.json`, this experiment's verdict). EXP-0139 never demotes a field a
prior experiment established; a sweep that cannot re-derive a rule on *its* carrier is not a
refutation. The one place this experiment does contradict a prior claim (EXP-0112's aliasing
rule, §1.3) is called out explicitly rather than merged away.

---

## 3. Fault discipline — and what concurrency actually cost (FIELD-SWEEP-PROTOCOL §7)

§7 became binding **after** this contract was frozen and after gated run01 had completed; the
disclosed amendment is `CAPTURE_CONTRACT.json :: amendment_01` (the **case matrix is
byte-identical**, so `matrix_sha256` is unchanged and run01/run02 stay comparable).

**Measured, not assumed.** Two revalidation passes re-ran every suspect case in a fresh
process with a baseline check before and after:

| pass | cases | attempts | outcome |
|---|---|---|---|
| `reval01` — every non-OK case, 5× | 1,580 | 7,900 | **811 reproducible_fault, 692 transient (did not reproduce at all), 66 intermittent, 11 baseline-unhealthy** |
| `reval02` — every OK-but-unstable case, 7× | 457 | 3,199 | **388 transient, 52 intermittent, 14 baseline-unhealthy, 3 genuinely nondeterministic** |

**44 % of the faults in the gated runs did not reproduce.** The OS's own classification string
names the cause: **1,552 of the revalidation attempts carried
`kIOGPUCommandBufferCallbackErrorInnocentVictim` ("Discarded (victim of GPU error/recovery)")**
against 2,656 genuine `…ErrorHang` and 50 `…ErrorPageFault`. Without §7's re-validation rule,
**692 legal field values would have been labelled `fault`** in `validation.json` and shipped to
a compiler. This is the single most important process finding of the run.

Only **3 cases out of 29,685** are genuinely nondeterministic after re-validation. In
particular the `iminmax` family — flagged UNVALIDATED and nondeterministic by EXP-0113 — was
**perfectly reproducible here** across 4 observations of all 858 of its cases.

**Baseline health.** run02 re-validated the current arm's unmutated carrier every 250 cases
(144 checks). Two arms reported failures — and both were **false alarms that the check
correctly surfaced as a harness defect rather than a cascade**: `ISEL_REG8`'s baseline is an
*extrapolated* construction whose baseline is pre-registered `mismatch`, and `ICMPSEL`'s arm
was being fed the integer input vector while its host oracle used the float vector
(`db_defects` DEF-0139-6). No GPU error cascade occurred. The ICMPSEL captures are sound — the
recorded bytes are exactly `(a<b)?1:0` over `A_IN`/`B_IN` reinterpreted as float32 with
denormals flushed — and that arm is scored against its own gated baseline.

---

## 4. Limitations

1. **M4 only.** Nothing here is an A18/G17P claim.
2. **Concurrency.** Two sibling GPU experiments ran throughout. Mitigated and *measured*
   (§3), not eliminated. 2,037 of 29,685 cases needed re-validation.
3. **Single carrier per family** (except `ibfe` and `ibitcount`, which have two). A field that
   is inert *in this carrier's operand configuration* may not be inert in another; every
   `range`/`semantics` string is scoped to the carrier named in `field_verdicts.json`.
4. **Operand-selector mappings are not established** (§2) — the biggest remaining gap.
5. **`iminmax` float members** are untested on normal float operands.
6. **Wide fields** (`iunary.operand` as a whole, `icmpsel.tail`) were sampled per
   FIELD-SWEEP-PROTOCOL §3.3, not exhausted; the `operand` result is per-byte-dense.
7. **One pre-registered model was refuted** (`ibfe.width`) and three host oracle *expressions*
   were corrected in analysis. All are disclosed in `analysis/verdicts.py`'s header with the
   competing model scored on the same data. No raw capture was edited.

---

## 5. Reproduction

```sh
sh harness/build.sh work/bin
python3 harness/verify.py --selftest                      # 457 checks, no device needed
python3 harness/run.py --run m4_20260828_run01
python3 harness/run.py --run m4_20260828_run02
python3 harness/revalidate.py --runs m4_20260828_run01,m4_20260828_run02 \
        --out raw/m4_20260828_reval01 --repeats 5
python3 harness/revalidate.py --runs m4_20260828_run01,m4_20260828_run02 \
        --indices work/unstable_indices.json --out raw/m4_20260828_reval02 --repeats 7
python3 analysis/emit_verdicts.py                         # -> analysis/field_verdicts.json
```

## 6. Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: kernels/ialu_probes.metal and kernels/carrier_dag.metal (authored by us)
  and the AGX machine code the public runtime API compiled from them; tools/agx-isa/db.json
  (our own DB); tools/{shdump,agxtest} (our own tools, used READ-ONLY and unmodified).
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled, symbol-dumped,
  strings-scanned or debugged. The only machine code inspected or spliced is the compiled form
  of our own MSL.
Reproduction: see §5.
Evidence: raw/m4_20260828_run01/{00_env,01_anchors,02_summary}.json + sweep.jsonl
          raw/m4_20260828_run02/{00_env,01_anchors,02_summary}.json + sweep.jsonl + 03_baseline.jsonl
          raw/m4_20260828_reval01/{00_env.json,revalidate.jsonl}
          raw/m4_20260828_reval02/{00_env.json,revalidate.jsonl}
          analysis/field_verdicts.json, analysis/field_stats.json
```
