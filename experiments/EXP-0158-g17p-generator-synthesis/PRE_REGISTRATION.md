# PRE-REGISTRATION — EXP-0158, G17P generator synthesis

**Target: A18 Pro / G17P** (`users-MacBook-Neo.local`, `192.168.10.243`,
`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS 26.6, Metal family Apple9).
**Frozen before any gated capture.** Sections 1–5 and 7–10 were written before a single
program was generated; section 6 records a **disclosed pre-freeze pilot** whose results
are frozen into `frozen_pilot.py` *before* run01, exactly as CODEX §5 permits and
`EXP-0101`/`EXP-0112` did before it.

---

## 1. The question, and why it is the one worth asking

`CLAUDE.md`'s Definition of Done has six closure rules. Rules **1** and **6** are:

> value/behavior **generated**, not merely decoded from a captured template
> …the relevant userspace object **independently generated and consumed without a
> captured Apple template**

`EXP-0112` is this repository's strongest generation result: 140/140 gated cases and 100
independently generated dataflow DAGs, bit-exact, twice, on the M4. But its own DOC-02
labelling pass showed **how** it succeeded: several field values were **lifted verbatim
from a compiled shader** because at the time no rule for them existed. A generator that
copies a token is replaying a template in that field, however good its arithmetic is
elsewhere.

That excuse is now gone. `EXP-0141` established `device_load`'s destination rule
exhaustively, `EXP-0139`/`EXP-0128` established `iadd2`'s register mode,
`EXP-0138` established `falu2`'s operand-source classes **and an inline 8-bit float
immediate nobody knew about**, `EXP-0140` established `mov_imm`'s immediate and the
length rule, and `EXP-0148` corrected four length rules.

**Question.** With those rules in hand, how many of EXP-0112's programs can be rebuilt with
**every field computed** — zero verbatim tokens — and still run bit-exactly correct; and,
for the ones that cannot, exactly which token is still missing a rule?

**And, for the first time, on G17P.** EXP-0112 ran on the M4. Every rule this experiment
composes was established on the M4. This is the first time the generator runs on the
documentation target at all. **A G16G↔G17P divergence is a first-class finding**, not a bug.

---

## 2. Deliverable 1 — the token inventory

*What EXP-0112 copies rather than computes.* Compiled by reading
`experiments/EXP-0112-m4-program-generator/{isa_helpers,generator,families,cf}.py`
field by field. "COPIED" below means EXP-0112 wrote a literal whose value it took from an
observed compiled instruction; "RULE" means it computed the value from a cited rule.

### 2.1 `device_load` — 14 fields

| field | EXP-0112 | class | EXP-0158 | rule now available |
|---|---|---|---|---|
| `space` | `0x10` | **COPIED** | FREE, off-natural | EXP-0141: exact rule `v & 0x03 == 0` |
| `addr_mode` | `0x44` | **COPIED** | FREE, off-natural | EXP-0141: INERT 256/256 on this shape |
| `extmode` | `2*R` | RULE | RULE + **bit0 deliberately set** | EXP-0101 H1 + EXP-0141 (bit0 don't-care) |
| `base_slot` | carrier | CARRIER | CARRIER | re-derived per carrier by `baseline.py` |
| `index_reg` | `R_IDX` | RULE | RULE | EXP-0141 |
| `access_desc` | `0x20` | **COPIED** | FREE, off-natural | EXP-0141: INERT 256/256 |
| `reserved7` | `0` | **COPIED** | FREE, off-natural | EXP-0141: INERT 256/256 |
| `ld_format` | `0x11` | **COPIED** | RULE, off-natural | EXP-0141: 21 of 64 codes deliver the 32-bit scalar |
| `dst_lo` | `1` | **COPIED VERBATIM** — `DST_TOKEN_KNOWNGOOD`, the single most load-bearing copy in EXP-0112 | RULE | EXP-0141: **exact** rule `dst_lo & 0x03 == 0x01` |
| `dst_ext9` | `1` | **COPIED VERBATIM** — same token | RULE, off-natural | EXP-0141: **exact** rule `dst_ext9 & 0x01 == 0x01` |
| `idx_off` | computed | RULE | RULE | EXP-0082 address formula |
| `ldform_hi11` | `0x10` | **COPIED** | FREE, off-natural | EXP-0141: exact rule `v & 0x07 == 0` |
| `elem_size` | `0x40\|(code<<1)` | RULE | RULE | EXP-0082 |
| `reserved13` | `0` | **COPIED** | FREE, off-natural | EXP-0141: INERT 256/256 |

EXP-0112's own docstring is explicit about the worst of these:

> `dst_lo`/`dst_ext9` default to the ONE HW-CONFIRMED-valid verbatim token for this
> addr_mode/ld_format shape … copied verbatim, per EXP-0101's own explicit finding that
> this pair must NEVER be derived from the target register.

**9 of 14 fields copied.**

### 2.2 `device_store` — 14 fields

| field | EXP-0112 | class | EXP-0158 | rule now available |
|---|---|---|---|---|
| `space` | `0x00` | **COPIED** | FREE | EXP-0141: `v & 0x02 == 0` |
| `addr_mode` | `0x54` | **COPIED** | FREE | EXP-0141: INERT when the stored data is ALU-computed |
| `extmode` | `2*data_reg` | RULE | RULE | EXP-0090 finding_5 / EXP-0141 H10 |
| `base_slot` | carrier | CARRIER | CARRIER | — |
| `index_reg` | `R_IDX` | RULE | RULE | EXP-0092 |
| `access_desc` | `0x21` | **COPIED** | FREE | EXP-0141: INERT |
| `reserved7` | `0` | **COPIED** | FREE | EXP-0141: INERT |
| `st_format` | `0x11` | **COPIED** | RULE | EXP-0141: 84 of 256 store the 32-bit scalar |
| `st_format_ext` | `0` | **COPIED** | FREE | EXP-0141: `v & 0x60 == 0` |
| `idx_off` | computed | RULE | RULE | EXP-0082 |
| `st_desc_hi` | `0x24` | **COPIED** | FREE | EXP-0141: `v & 0x11 == 0` |
| `elem_size` | `0x11` | **COPIED** | FREE | EXP-0141: 96 of 256 store correctly |
| `reserved13` | `0` | **COPIED** | FREE | EXP-0141: INERT |

**9 of 14 fields copied.**

### 2.3 `falu2` (register–register) — 15 fields

| field | EXP-0112 | class | EXP-0158 |
|---|---|---|---|
| `dst`, `srcA_reg`, `srcB_reg`, `opsel`, `opflags`, `srcA_size`, `srcB_size`, `srcB_imm` | computed | RULE | RULE |
| `ctrl` | `0` | **COPIED** (framing) | RULE — EXP-0119: bits 0/1 are the length selector, 0 selects the 6-byte form |
| `mod_lo` | `0` | **COPIED**, `validation.json` labelled it `untested` | RULE — EXP-0138: this is not one field but two, `srcA_class` (bit 40) and `srcB_class` (bits 41-42), an **operand-source-class** selector. 0/0 = "both operands GPR". |
| `srcB_neg` | `0` | RULE | RULE — EXP-M4-10 |
| `mod_hi` | **`0xC` COPIED VERBATIM** — EXP-0112's own words: *"the natural value observed in every own-compiled falu2 reg-reg instance … reused as the default"* | **COPIED** | **PILOT** — measured on G17P by this experiment's arms P1/P2 (§6) |
| `srcA_reg_top`, `srcB_reg_top` | absent (EXP-0112's db modelled a 7-bit register field) | — | RULE — EXP-0099: HW-tested inert |

**`mod_hi` is the one falu2 token this experiment cannot promote to RULE from published
work, and the reason is a genuine contradiction in the record — see §6.**

### 2.4 `falu2i` — 13 fields

All RULE in EXP-0112 already, including `mods = 0xC0 if load_sourced else 0x00`
(EXP-0101 H1) — **except** `ctrl_lo = 0`, which was framing-only and is now RULE
(EXP-0119, the 6-byte-form length selector).

### 2.5 `iadd2` — 14 fields, and the worst case in EXP-0112

EXP-0112's `iadd2_anchor` docstring:

> every field EXCEPT `srcB_imm` … iadd2's OWN register-mode operand encoding is
> explicitly NOT independently re-derived anywhere in this project … so this generator
> treats the whole anchor pattern as a **single documented-constant copy**.

**13 of 14 fields copied**, and the instruction could not be used with an
independently chosen destination or second operand at all.

EXP-0158 replaces it with a fully synthesised **register-mode** `iadd2`
(`families.build_iadd_synth_program`): `srcA` is a format byte that always reads r0
(EXP-0128 §1.2); `srcB_imm = 4*N` selects r_N; `addsub=0` gives `r_N − r0`
(EXP-0128 §1.4); `dst = (reg<<1)|size` with reg < 96 (EXP-0139 §1.3); and
`lenbit`/`srcB_imm_hi`/`opmode`/`srcA`/`opc_tail`/`opc_tail2`/`srcB_ext` all have
EXP-0139 masks. **0 of 14 copied.**

The **immediate-mode** anchor is *retained* as its own family, still tagged COPIED,
because EXP-0139's masks were established on the register-mode carrier and demonstrably
do not describe the immediate-mode tail (the anchor's `opc_tail2 = 4` violates
EXP-0139's `v & 0x05 == 0x05` yet executes). Keeping it is how the "still needs a donor"
count stays honest.

### 2.6 `get_sr` — 6 fields, all copied — **eliminated by construction**

EXP-0112: *"EXP-0090 P3 anchor byte pattern, verbatim … not independently re-derived."*
EXP-0158's DAG programs contain **no `get_sr` at all**: the dispatch is grid=1/tg=1, so
`thread_position_in_grid` is identically 0 and the index register is set with
`mov_imm(r15, 0)` — a `hardware-run` instruction (EXP-0140). The copy is removed by not
needing it, which is a legitimate elimination and is reported as such, not as a rule.

### 2.7 `mov_imm` — 3 fields

EXP-0112's helper took an **8-bit** `imm8`. The current model is `imm7` (7 bits) plus
`imm_top`, and EXP-0140 showed `imm_top=1` means the instruction **does not write at all**
and, unpadded, consumes the next 2-byte instruction. EXP-0158 computes `imm7` in 0..127
with `imm_top = 0`, and refuses `imm7 == 12` (does not tokenize, EXP-0140).

### 2.8 `stop` — 1 field

EXP-0112: `reserved = 0`, copied. EXP-0158: FREE — EXP-0003/EXP-0010 corrupted the full
24-bit body with no effect, so the generator deliberately writes a non-zero body.

### 2.9 The control-flow skeleton — **every field copied, and it stays that way**

`cf.py` reuses EXP-0090's P3 loop+if/else→select skeleton byte-for-byte:
`get_sr`, 2× `device_load`, 2× `icmp_pred`, `if_push_pred`, `jump_cond`, `reg_move_c0`,
`if_push`, `iadd2`, `scoreboard_fence`, `ret`, `jump`, 2× `pop_reconverge`, `isel10`.
**No rule exists for any of their operand fields.** EXP-0158 keeps the family and tags
every one of those fields COPIED, so the headline count has an honest denominator. Only
the falu2i immediates inside the skeleton and its final `device_store` are computed.

### 2.10 Summary of the inventory

| instruction | fields | copied by EXP-0112 | copied by EXP-0158 |
|---|---|---|---|
| `device_load` | 14 | 9 | **0** |
| `device_store` | 14 | 9 | **0** |
| `falu2` | 15 | 3 (`ctrl`, `mod_lo`, `mod_hi`) | **0 RULE + 1 PILOT** (`mod_hi`) |
| `falu2i` | 13 | 1 (`ctrl_lo`) | **0** |
| `iadd2` register mode | 14 | n/a (could not be built) | **0** |
| `iadd2` immediate anchor | 14 | 13 | **13 (deliberately retained)** |
| `get_sr` | 6 | 6 | **0 (eliminated: not emitted)** |
| `mov_imm` | 3 | 0 (but under-modelled as 8-bit) | **0** |
| `stop` | 1 | 1 | **0** |
| CF skeleton (16 instrs) | ~90 | ~90 | **~90 (deliberately retained)** |

---

## 3. Hypotheses, and what would refute each

**H1 (headline).** Every `MAIN_DAG`, `DAG_INLINE`, `REGBOUNDARY` (R ≤ 63), `INLINEIMM`
and `IADD_SYNTH` case — built with **zero COPIED fields** — returns its host-computed
oracle bit-exactly on G17P.
*Refuter:* any such case returning a wrong value, a silent zero, or a `no_write` while its
integrity sentinel is correct. A single one refutes H1 for that field's rule.

**H2 (destination rule, EXP-0141, on G17P).** `device_load` into register R delivers the
loaded value for **R = 0..63 only**, with `dst_lo = 1` exactly, `dst_ext9` bit0 = 1, and
`extmode = 2*R` whose **bit 0 is a don't-care**. **R = 64 must silently fail** (extmode
bit 7 is then set, which EXP-0141 says zeroes the write, and the consuming ALU's 6-bit
`srcA_reg` independently aliases to `r(R mod 64)`).
*Pre-registered prediction, not a bug.* R = 63 must WORK; R = 64 must NOT.
*Refuter:* R = 64 delivering the loaded value, or R = 63 failing.
*Discriminator:* the poison arm. For R ≥ 64 a poisoned `r(R mod 64)` returning the poison
value proves consumer-side aliasing; returning `0.0` proves a pure silent zero. R = 63 is
a control — 63 mod 64 = 63, so the poison and the load target are the same register and
the load must overwrite the poison.

**H3 (inline float immediate, EXP-0138, on G17P).** `falu2` with `srcB_class = 1` and a
7-bit srcB index of 64+k supplies an inline 8-bit float immediate of magnitude
`m·2^-5` (e = 0) or `(8+m)·2^(e-6)` (e > 0), where `e = k>>3`, `m = k&7` — with **no
`mov_imm` and no separate seed instruction**.
*Refuter:* any code k whose delivered magnitude differs from the model.
*Already partly observed in the pilot (§6): the magnitude model reproduces exactly and
the **sign is inverted** relative to EXP-0138's stated table. The sign convention is
therefore measured, frozen, and reported as a divergence — it is not assumed.*

**H4 (`iadd2` register mode, EXP-0128/EXP-0139, on G17P).** `r_dst = r0 + r_N` for
`addsub=1` and `r_N − r0` for `addsub=0`, with `srcB_imm = 4*N`, for dst register < 96.
*Refuter:* a wrong sum, the wrong subtraction polarity, or a fault below reg 96.

**H5 (the adversarials must fail).** Each of the 10 `expect_match = False` cases violates
exactly one newly computed rule and must NOT produce the correct value.
*Refuter:* an adversarial case producing the correct value — which would mean the rule it
violates is not load-bearing, i.e. the rule is wrong.

**H6 (target).** Every M4-established rule above reproduces on G17P.
*Refuter:* any systematic disagreement. **This is a first-class finding either way** and
will be reported as such, not smoothed over.

---

## 4. Variables

- **Independent:** field provenance (computed vs copied); the field values themselves
  (deliberately off-natural where a don't-care range is documented); DAG shape (seeded,
  identical to EXP-0112's); R; inline-immediate code k; iadd2 (A, B, N, dst, addsub); K.
- **Controlled:** the two carrier kernels (our own MSL, unchanged from EXP-0112 so the
  carrier is not a variable); dispatch shape grid=1/tg=1; the pinned ISA snapshot; input
  buffers; one fresh process per case.
- **Dependent:** the read-back word, its outcome class, and the integrity sentinel.
- **Known confounders, and the mitigation for each:**
  1. *Sibling-agent GPU cascade.* ~11 other GPU experiments are on this machine and one
     unleased pilot sweep was already destroyed by it. Mitigations: the OS fault class is
     recorded on every non-OK case and `InnocentVictim` rows are excluded from evidence; a
     **cascade witness** case is re-run every 40 cases into `03_cascade.jsonl`; every
     fault/hang/victim/invalid case is re-run to **majority of 3** into
     `04_revalidate.jsonl`; the whole gated run is taken under `gpulease.sh`.
  2. *Carrier-dependent splice behaviour* (EXP-0099, and EXP-0112's own unresolved
     `opflags` discrepancy). Mitigation: the carriers are unchanged from EXP-0112, so any
     difference is target or provenance, not carrier.
  3. *A dead dispatch masquerading as a silent zero.* Mitigation: the integrity sentinel
     and the poisoned read-back buffer, which separate `no_write` from `silent_zero`.
  4. *`db.json` moving under the experiment.* Mitigation: the pinned snapshot (§5).
  5. *Float rounding in the oracle.* Mitigation: every oracle value is computed with the
     hardware's own documented codecs (`isadb.imm_encode/imm_decode`, the inline codec)
     and compared with exact IEEE-754 `==`; inline-immediate constants are drawn only
     from exactly representable values.

---

## 5. Frozen inputs

- **Pinned ISA snapshot** `work/isadb_pinned/`:
  `db.json` sha256 `418d780ca2920a7235deb55878b4e5e82563f2370c6ce6f9fea7d05643e7c91f`,
  `isadb.py` sha256 `1d60d36d2da7b681028c201013a510603d8fb7909bb59186e7534296e3b6e0d1`.
  `synth.py` asserts at import that it loaded this copy and not `tools/agx-isa`.
  Rationale: `tools/agx-isa/db.json` is orchestrator-owned and changed **under this agent
  mid-read**; a two-run byte-identity gate must not depend on a moving file. `tools/` is
  not modified.
- **Authored source hashes** for `synth.py`, `generator.py`, `families.py`, `cf.py`,
  `casematrix.py`, `frozen_pilot.py`, `harness/build.sh`, `harness/case_exec.py`,
  `run.py`, `verify.py`, `make_manifest.py`, `baseline.py`, both carrier kernels and the
  three doc files: recorded in `CAPTURE_CONTRACT.json` and re-checked by
  `verify.py --between-runs`.
- **Repo revision is recorded, never gated on** (SUBAGENT_BRIEF.md standing instruction:
  the orchestrator commits sibling experiments continuously).
- **Run ids (append-only, never reused):** `g17p-20260830-run01`, `g17p-20260830-run02`.
- **Timeouts:** 20 s per `agxrun` dispatch, 45 s per `agxtest` invocation, 60 s per
  `case_exec` subprocess, 900 s per gate.
- **Raw schema:** `raw/<run-id>/00_env.json`, `01_results.jsonl` (one gated record per
  case), `01_timing.jsonl` (non-gated), `02_dispatch.json`, `03_cascade.jsonl`,
  `04_revalidate.jsonl`. `01_results.jsonl` must be **byte-identical** across the two runs.

---

## 6. Disclosed pre-freeze pilot

*Filled in from `work/pilot/` before the contract was frozen. Its raw output is retained
in full, including the run destroyed by the sibling cascade, which is superseded but never
overwritten.*

### 6.1 Why a pilot is needed at all — a real contradiction in the record

`validation.json` records `falu2.mod_hi` (evidence EXP-0105/EXP-0099) as:

> bit44 at {0,1} (silent corrupt-to-zero…); bits45-47 at all 8 values (**no observable
> effect**)

But EXP-0101 H1 requires `falu2i.mods = 0xC0` when the operand is load-sourced — and
`falu2i`'s `mods` field (bits 40..47) **is** `falu2`'s `{srcA_class, srcB_class, srcB_neg,
mod_hi}`, so `0xC0` is exactly `mod_hi = 0xC`. EXP-0112's own adversarial case confirmed
that `mods = 0` silently zeroes a **load-sourced** operand. The two records are only
compatible if `mod_hi` bits 1–3 are **inert for an ALU-sourced operand and live for a
load-sourced one**. Arms P1/P2 test exactly that, on G17P, so the generator chooses
`mod_hi` from a **measured** set rather than copying EXP-0112's `0xC`. Values that rest on
this pilot are tagged `PILOT`, never `RULE`, and are counted separately from the headline.

### 6.2 Arms

| arm | what it measures |
|---|---|
| P1 | `falu2.mod_hi` 0..15, both operands ALU-sourced |
| P2 | `falu2.mod_hi` 0..15, srcA sourced by a `device_load` bridge |
| P3 | `falu2i.mods` ∈ {0x00, 0x40, 0x80, 0xC0} × {ALU-sourced, load-sourced} — EXP-0101 H1 on G17P |
| P4 | the inline float immediate, **all 64 codes dense** |
| P5 | the same immediate with `srcB_neg = 1` — an **extrapolation**: does the documented negate bit negate an *immediate*? |
| P6 | `srcB_class` ∈ {0,1,2,3} at a fixed index — the source-class model on G17P |
| P7 | `device_load`, one field at a time, at the off-natural values the frozen chooser will pick |
| P8 | `device_store`, same |
| P9 | `iadd2` register mode |
| P10 | unmutated carrier + a sentinel-only program |

### 6.3 Results (see `analysis/pilot_summary.json` and `frozen_pilot.py`)

**Recorded before the freeze, verbatim, in `PROGRESS.md` M2–M4:**

- The **integrity sentinel and the poisoned read-back both work** on G17P: a sentinel-only
  program leaves out[0] at the poison word and sets out[252] to bits `0x55`.
- `srcB_class = 2` produced a **real GPU hang** on the first attempt. It is therefore
  known-hang-prone, is excluded from unleased work, and is not in the gated corpus.
- **The inline immediate's magnitude model reproduces exactly on G17P and its sign is
  inverted** relative to EXP-0138's stated table. Frozen as `INLINE_NEG0_SIGN`.

The frozen values themselves are in `frozen_pilot.py`, which is generated by
`analysis/freeze_from_pilot.py` from the retained JSONL and carries that JSONL's sha256.
`run.py` refuses to start while `frozen_pilot.FROZEN` is False.

---

## 7. Corpus and pass criterion

~250 programs in eight groups (`casematrix.py`): `MAIN_DAG` (100, the exact DAG shapes
EXP-0112 ran), `DAG_INLINE` (24, the same shapes with constants moved into the inline
immediate), `REGBOUNDARY` (R sweep including **63 and 64**, plus poison controls and the
extmode bit-0 don't-care), `INLINEIMM` (all 64 codes dense, plus fmul and negate arms),
`IADD_SYNTH` (16), `IADD_ANCHOR_COPIED` (12, honest denominator), `CF` (12, honest
denominator), `ADVERSARIAL` (10, all pre-registered to FAIL).

**Pass criterion, stated before the run:**

1. every `expect_match = True` case matches its oracle bit-exactly, in **both** runs;
2. every `expect_match = False` case does **not** match, in both runs;
3. `01_results.jsonl` is byte-identical across the two runs;
4. every case's integrity sentinel is correct (except CF, which has none — §7 note);
5. no `fault` verdict rests on a single observation.

**Headline number, defined before the run so it cannot be redefined afterwards:**

> **N = the number of cases that (a) contain ZERO `COPIED` fields, (b) were predicted to
> match, and (c) matched bit-exactly in both runs.**

A second number is reported alongside it and is never merged into it: **N₀ = the subset of
N whose fields are additionally all `RULE`/`FREE`/`CARRIER`, i.e. that rest on no value
measured by this experiment's own pilot.** And a third: the cases that still need a donor,
named by which token.

**CF is the one family with no integrity sentinel.** The 152-byte CF carrier cannot hold
the extra 16 bytes, and lengthening a carrier is not semantically neutral (EXP-0140). This
is stated, not silently skipped.

---

## 8. Safety and stop rules

- Every remote call is hard-timeout wrapped. `macvdmtool` is **forbidden** to this agent.
- The gated runs are taken under `~/agxre/gpulease.sh` because the machine is demonstrably
  in a multi-agent cascade and because the corpus contains known fault-prone arms
  (R ∈ {126,127}, `iadd2` dst ≥ 96).
- **After two genuine (non-victim, reproduced) hangs in one arm, that arm STOPS** and is
  reported PARTIAL.
- If the unmutated-carrier witness starts failing, the run is in a cascade: it is recorded
  in `03_cascade.jsonl` and the affected stretch is named in `RESULTS.md`.
- If the neo stops answering: **STOP and report BLOCKED**.
- A partial capture is **retained, never reused**; a replacement takes a new run id.

## 9. What this experiment does NOT claim

- It does not claim to synthesise control flow. The CF family is a parameterised copy and
  is labelled COPIED in every operand field.
- It does not claim the immediate-mode `iadd2` tail. That family is retained as a copy.
- It does not claim `reg_move` as a dataflow primitive (EXP-0101 Blocker 2, unresolved).
- It does not claim `device_load` forwarded directly to `device_store` without an ALU
  consumer (EXP-0112 §4, still out of envelope).
- It does not claim anything about G16G from a G17P observation, or vice versa.

## 10. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code
  (synth.py, generator.py, families.py, cf.py, casematrix.py, work/pilot/pilot.py --
  every instruction built via a PINNED, hash-recorded snapshot of this repository's own
  isadb.assemble()), our own carrier MSL (kernels/carrier_dag.metal,
  kernels/carrier_cf.metal), our own splice+run harness (harness/case_exec.py over
  tools/agxtest, tools/shdump).
Apple binary introspection: NONE.
Reproduction: README.md's command sequence.
Evidence: raw/g17p-20260830-run01/, raw/g17p-20260830-run02/, work/pilot/
```

---

## AMENDMENT 1 — 2026-08-30, after `g17p-20260830-run01`

**Disclosed in full because the capture that forced it is retained and committed.**

`run01` ran the frozen corpus and returned **139/289 matched, 167/289 as predicted**. That is
not noise; it exposed **two real defects in this generator's inherited assumptions**, both of
which are first-class hardware findings in their own right. `run01` is **retained, append-only,
and never re-run**. The corrected generator captures the contracted gated pair under **new run
ids `g17p-20260830-run03` / `g17p-20260830-run04`** (ids are never reused; `run02` was never
started).

### Defect 1 — `device_load.ld_format` is a load WIDTH, and the non-17 codes write extra registers

`work/diag/diag01.jsonl` and `diag02.jsonl` isolate it by disabling exactly one off-natural
choice at a time: with `ld_format` forced to 17, every previously failing DAG is bit-exact;
with any other code from EXP-0141's "delivers the 32-bit scalar" set, DAGs corrupt.

`work/diag/diag_ldformat.jsonl` then measures the mechanism directly — six witness registers
seeded with distinct constants, one load into r7, all six read back:

| `ld_format` | loads the target | ALSO writes |
|---|---|---|
| 17, 49 | yes | *(nothing)* |
| 25, 27, 31 | yes | r8 |
| 19, 21, 29, 51 | yes | r8, r9 |
| 23 | yes | r8, r9, r10 |
| 18, 20 | **no** | r8 (and r9) |
| 16, 33, 35 | **no** | *(nothing)* |

The extra registers receive the **following consecutive memory words**. `ld_format` is a
vector-width / component-mask field: EXP-0141's claim that 21 of 64 codes "deliver the 32-bit
scalar" is true of the *addressed* word and **dangerously incomplete for an emitter** — the
codes are not interchangeable, and the corruption is invisible in a single-load probe (this
experiment's own pilot arm P7 marked all six `ok`) and silent in a register-allocated program.

**Correction:** the generator now draws `ld_format` only from
`frozen_pilot.DL_LDFORMAT_ONE_REGISTER = [17, 49]`, still off-natural (49 is not what the
compiler emits) but measured to write exactly one register.

### Defect 2 — `iadd2.srcA` is NOT inert on G17P

Six `IADD_SYNTH` cases returned the **second operand alone** instead of the sum, while the
pilot's P9 arm — same operands, natural values for every non-operand field — returned the sum.
New pilot arm **P11** (`work/pilot/pilot_iadd01.jsonl`) sweeps every field EXP-0139 recorded as
inert, one at a time, on G17P. Result: `opc_tail`, `opc_tail2`, `opmode`, `b2_fmt`, `srcB_ext`,
`store_en`, `b2_bit0`, `srcB_reg_hi` are inert here too — but **`srcA` is not**:

- 44 of 64 sampled values (step 4) deliver the sum;
- `(v & 0x18) == 0` places the sum in the **upper half-word** (17 read back as `0x00110000`);
- `(v & 0x7C) == 0x50` **silently zeroes**.

That mask model reproduces all 64 observations exactly. EXP-0139's "only bits 0,1 decide
(must be 0)" is **refuted on G17P**; `srcA` carries a live size/half-select.

**Correction:** every `iadd2` register-mode field is now chosen from the set **P11 measured
`ok` on this target**, and is tagged `PILOT` rather than inheriting an M4 inertness claim.

### What this changes about the headline

Nothing about its definition, which was fixed in §7 before any run. It does move fields from
`FREE` (inherited M4 don't-care) to `PILOT` (measured on target), which *lowers* N₀ — the
strict subset resting only on previously published rules. That is the honest direction: two
published inertness claims turned out not to hold here, and the corpus now says so.
