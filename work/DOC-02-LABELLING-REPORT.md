# DOC-02 — per-field evidence labelling of the Apple9 ISA database

**Date:** 2026-08-28 · **Spec applied:** `docs/evidence-classification.md`
**Artifacts produced:** `tools/agx-isa/validation.json`, `tools/agx-isa/validate_labels.py`
**Generator (auditable, re-runnable):** `work/gen_validation.py`
**Input pinned:** `tools/agx-isa/db.json` sha256 `eaca7256f0f2dcd79ec01aac9dd825f888ceb23f3b720b755ab384ad686e90af`
**Task type:** DESK. No GPU work, no shader compilation, no dispatch. Everything below is read
out of already-committed evidence.

---

## 1. What was labelled

Every one of the **170** instruction descriptors in `db.json` and every one of their **1025**
fields now carries exactly one of the eight labels from §2 of the spec, plus a `range`
(the interval actually exercised, in the field's own units), a `target` (`M4` / `A18` / `M4+A18`,
never assumed to transfer), and an `evidence` list of experiment ids.

Sources read, in order of yield:

1. **`db.json`'s own `semantics` and per-field `note` text** — the single richest per-field
   evidence index in the repository, and the only place several 2026-08-28 retractions are
   recorded (read in full via `python3 -c` over `db.json`'s `semantics`/`note` fields).
2. `docs/isa/README.md`, `docs/isa/register-move-and-liveness.md`, `docs/isa/memory-model.md`.
3. `experiments/EXP-*/RESULTS.md` for the ISA-bearing experiments: 0003, 0005–0007, 0010,
   0012–0013, 0016, 0018–0020, 0022–0026, 0029–0031, 0033–0038, 0041, 0082–0083, 0086–0087,
   0089–0093, 0099–0106, 0111–0115, 0119, plus `EXP-M4-01/10/12/13/14`, `EXP-O2C/O2D`, and the
   `RT-*` red-team splice passes.
4. `experiments/EXP-M4-14-a18-splice/splice_results.json` — 56 per-field A18 splice sweeps with
   the exact value sets, which is where most of the `hardware-run` labels outside the float ALU
   come from.

### Conventions adopted (also embedded in `validation.json._conventions`)

- **`untested` is the default.** Positional knowledge alone — "we know this byte is the source
  register because the corpus says so" — is *not* a label. 298 fields ended up here.
- **Evidence ids are directory-name prefixes under `experiments/`.** This deliberately includes
  the `RT-*` red-team passes, which are committed experiments with retained raw A18 splice
  evidence; refusing them would have forced real hardware findings to be labelled `untested`.
  All 59 distinct ids used resolve to a real directory (checked).
- **`tokenization-only`** is used where a field's only established role is consuming bytes so the
  length/framing round-trips. Its evidence is the census/round-trip work (`EXP-0036` A18
  consolidation census, `EXP-M4-12` residue closure, `EXP-M4-13` full-corpus convergence) plus
  `roundtrip_test.py`.
- **`corpus-correlation`** is used only where `db.json` or `docs/` attributes the co-variation to a
  named experiment. **`EXP-M4-13` is compile-only** (it never dispatches), so nothing sourced from
  it can exceed this label — that alone accounts for a large share of the 234.
- **A field that WAS exercised on hardware but whose semantics remain unexplained is `untested`**
  (semantics not established), with the observation preserved in `note`. Three fields landed here:
  `device_load.ldform_hi11`, `ibitcount.cache`, and `spill_frame_marker`'s role.

---

## 2. Coverage

| label | fields | % of 1025 |
|---|---:|---:|
| `hardware-run` | 115 | 11.2 % |
| `isolated-byte-diff` | 51 | 5.0 % |
| `corpus-correlation` | 234 | 22.8 % |
| `tokenization-only` | 304 | 29.7 % |
| `single-template-inference` | 23 | 2.2 % |
| `api-accept-reject` | 0 | 0.0 % |
| `host-private` | 0 | 0.0 % |
| **`untested`** | **298** | **29.1 %** |

**Emitter-grade (`hardware-run` + `isolated-byte-diff`): 166 / 1025 fields = 16.2 %.**
**Decode-grade or worse (the other six labels): 859 / 1025 = 83.8 %.**

Per-instruction shape:

- **53 / 170** instructions have at least one emitter-grade field.
- **111 / 170** instructions have fields but **not one** emitter-grade field among them.
- **37 / 170** instructions are labelled entirely `untested` + `tokenization-only` — i.e. we can
  tokenize them and nothing more.
- Whole-instruction labels: 38 `hardware-run`, 28 `isolated-byte-diff`, 86 `corpus-correlation`,
  18 `tokenization-only`. So **66 / 170 instructions have been observed to actually execute** in a
  controlled probe — but that is a claim about the *instruction*, not about its fields, which is
  precisely the distinction this exercise exists to make.

### Emittable instructions: **5 / 170**

Under the spec's rule (*every* field an emitter must fill is `hardware-run` or
`isolated-byte-diff`):

`frame_prologue`, `link_save_restore`, `spill_frame_marker`, `stop`, `tex_addr_setup`

**165 / 170 are "decodable, not yet emittable."** Read that number with four caveats, because it
is easy to misread in either direction:

1. **Four of the five are A18-only** (`EXP-M4-14` splice campaign). Only `stop` has A18 evidence
   that is uncontested and trivially portable. Given the `EXP-0119` A18↔M4 contradiction (§5, D1)
   is unresolved, an M4/G16G backend should not treat the A18 sweeps as transferred.
2. **`spill_frame_marker` is emittable but useless** — every byte was swept on A18 and found inert
   except `b3=0xff` (fault), yet `EXP-0041` found the word absent from all nine retained M4 own
   mains including 208–576 B declared scratch. Its *role* is unresolved. You can emit it; nobody
   knows why you would.
3. **`tg_addr_compute` was mechanically emittable and has been explicitly vetoed.**
   `EXP-M4-14` proved byte0's high nibble and byte+1 are live operand selectors, but neither is
   modelled as a field — `db.json`'s `match` over-fits the r1 form. An emitter must fill bytes the
   descriptor does not expose. The veto is recorded in the `_instruction` note and enforced by the
   validator, so this is not a silent judgement call.
4. **The number is low for a real, specific reason, not out of pedantry.** `falu2`, `falu2i`,
   `device_load`, `device_store`, `iadd2` and `icmp_pred` — the exact set `EXP-0112` used to
   generate 100 correct random dataflow DAGs — all *miss* the bar. They miss it because the
   generator succeeds by copying **verbatim tokens** for the fields it cannot derive
   (`device_load.dst_lo`/`dst_ext9`, `ld_format`, `iadd2`'s whole register-mode operand block).
   That is exactly what "not yet emittable" is defined to mean. `EXP-0112`'s own §4 says the same
   thing in prose; this labelling just makes it countable.

**`matrix_mac` is the closest near-miss:** 10 of its 12 fields are emitter-grade (all A18 splice),
and only `dst_desc` and `b11hi` are `tokenization-only`.

---

## 3. Top 10 highest-impact `untested` fields

Ranked by "an emitter must fill this to emit a common instruction, and nobody has swept it."
Weak-but-not-`untested` entries are included where the weakness is the actual blocker; the label
is given for each.

| # | field | label | why it blocks an emitter |
|---|---|---|---|
| 1 | `device_load.dst_lo` + `device_load.dst_ext9` | `single-template-inference` | The **single biggest synthesis blocker in the ISA.** `EXP-0101` proved they are independently required *and* that deriving them from the target register breaks the load in 4 adversarial cases — so a backend must carry a verbatim token per `addr_mode`/`ld_format` shape, and nobody knows the shape space. Every generated load in `EXP-0112` copies `(1,1)`. |
| 2 | `device_load.ld_format` / `device_store.st_format` | `corpus-correlation` | The data-format descriptor an emitter must pick per element type. Located by compile-only byte-diff (`EXP-M4-13`); **no synthesized format code has ever been executed.** Blocks every non-scalar-f32 load/store. |
| 3 | `falu2.mod_lo` (instruction bits 40–42) | `untested` | The only thing standing between `falu2` — the most-used instruction in the ISA — and emitter grade. Never exercised in isolation by any committed experiment. Its neighbours in the same byte (`srcB_neg` bit43, `mod_hi` bits44–47) are all characterized; this 3-bit hole is not. |
| 4 | `iadd2.dst` / `srcA` / `srcB_reg_hi` / `srcB_ext` / `opc_tail` / `opc_tail2` | `corpus-correlation` | `iadd2` **register-mode** (both operands GPR, independently chosen registers and dst) is an explicit open item in `EXP-0112` §4 and `EXP-0090`. The srcB register number is *scattered* across b1/b5/b6 and the reg-vs-imm type flips three separate tail bytes. Only the one verbatim immediate-mode anchor has ever run. No integer register-register arithmetic can be generated today. |
| 5 | `icmp_pred.srcA` / `icmp_pred.srcB` | `untested` | The compare sources of the only predicate producer. `dst_pred` and `cond` are `hardware-run`, so the *branch* is generable — but only over the one fixed skeleton whose operands were inherited verbatim. Blocks general control-flow synthesis. |
| 6 | `device_load.ldform_hi11` (byte+11 bits 2–7) | `untested` | `EXP-0082` swept 6 raw values: three inert, **`0x48` and `0x50` produce undecodable output**, semantics UNKNOWN and flagged as follow-up. A live byte adjacent to `idx_off` with two known-bad values and no model. |
| 7 | `tex_sample.coord` / `extra_coord` / `result_sel` / `comp_flags` / `tex_type` | `corpus-correlation` / `untested` | The coordinate and result **register** operands of the texture bundle. `EXP-0016`/`EXP-0034` state plainly that the extra index operand (slice/face/z/sample/ref) is byte-diff only, **not splice-validated**. `tex_slot` and `variant` are `hardware-run`; the registers that feed them are not. |
| 8 | `simd_reduce.dst` / `src`, `simd_shuffle.dst` / `src` / `dsthi` | `corpus-correlation` | Subgroup **operand registers**, located by compile-only own-MSL byte-diff (`EXP-M4-13` R10/R9). The op-select and dtype enums are HW-validated; the registers they read and write are not. Any generated subgroup op is a guess about where its data lives. |
| 9 | `atomic_rmw` / `atomic_mem` RMW-operand register | *not a field at all* | `db.json`'s own semantics: "the actual RMW operand register is implicit (supplied by the preceding op / amode)". The same structural gap exists for `device_store`'s data register. The 13 op codes are `hardware-run`; the operand plumbing is undocumented. This is a **missing field**, not a weak one — the worst kind of gap for an emitter. |
| 10 | `jump_cond.offset` | `corpus-correlation` | `EXP-0115` mapped the practical branch reach in 162 splice points — **on `jump`, not on `jump_cond`.** The conditional form's reach, its alias holes, and its non-determinism envelope are all assumed by structural analogy. Since `jump_cond` is the if/else and loop-exit guard, this is the reach every real branch actually uses. |

Honourable mentions that did not make the ten: `falu2i.ctrl_lo` (only the 2 length bits are known
of 7); `matrix_mac`'s **half-datapath** `op_enable`/`acc_en` values (the fp32 values `0x24`/`0x01`
are splice-proven, the half datapath uses `0x8c`/`0x00` and is uncharacterized — RT-10);
`frag_color_store.fmt` (attachment-format code, corpus-only); `vary_store.hint1`/`hint6`/`b7`.

---

## 4. Retractions carried into the labels

Each of these is recorded in the affected field's `note`, so an implementer reading the sidecar
cannot miss it.

| retraction | where it lands |
|---|---|
| `EXP-M4-13`'s `device_load` destination formula `dst = dst_lo \| (dst_ext9<<2)` is **REFUTED**; the ALU-visible register is `extmode/2` (`EXP-0101`) | `device_load.extmode` (`hardware-run`), `dst_lo`/`dst_ext9` (`single-template-inference`) |
| bit 15 / bit 31 retention attribution **retracted** (commit `88fa4953`); both `falu2` and `falu2i` register-field top bits are HW-tested **INERT** for addressing *and* retention, role UNKNOWN | `falu2.srcA_reg_top`, `falu2.srcB_reg_top`, `falu2i.srcA_reg_top` — all `hardware-run` (the inertness is the result), all carrying the retraction note |
| `tex_sample.tex_slot` is **not** a per-texture binding index — it names a compiler-reused register/uniform slot; 14 of 16 nibble values are a deterministic silent zero (`EXP-0114`) | `tex_sample.tex_slot` |
| `rt_intersect` operand sub-fields are byte-diff correlations, **not** splice-validated; the "`EXP-O2C` `0x8b→0x1b` HW-validated end-to-end" note is retracted (RT-5/RT-10) | every `rt_intersect` field |
| `tex_sample` op+6 is **not** the filter selector — filtering is the sampler's job (RT-5) | `tex_sample.mode` |
| `device_store` byte+8 is **not** the data register and is HW-inert (`EXP-M4-10` ISA-1) | `device_store.st_format` |
| `iadd2` polarity was **inverted**: `0x9f` = ADD, `0x1f` = SUBTRACT (RT-1a-FIX) | `iadd2.addsub` |
| `ibitcount` byte+4 is an op-**enable** gate, not the sub-op selector; the sub-op is (byte0 bit7 + byte+1) (`EXP-M4-14`) | `ibitcount.op_enable`, `ibitcount.form` |
| `op04_len8` renamed from `frag_pos_read`; `[[position]]`/`[[front_facing]]` lower to `get_sr` + `iter` (HW-validated negative) | `op04_len8._instruction` |
| the 0x54/0x56 "cache bit" is **not** confirmed inert anywhere — downgraded to UNKNOWN (`EXP-0086`) | `simd_reduce.cache`, `simd_shuffle.cache`, `fspecial.src_cache`, `ret_luse.tail`, `ibfins.cache`, `cvt_i2f_src.src_cache`, `falu_acc.cache` |

---

## 5. Disagreements between experiments (reported, **not** resolved)

Per the brief these are first-class findings. I have recorded each in the affected field's `note`
and have not picked a winner.

**D1 — `ibitcount.cache`: a direct A18↔M4 contradiction on identical bytes.**
`EXP-M4-14` (A18 Pro) recorded "only 0x54/0x55 (bit1 clear) break the stored result; 0x56
standalone writes back." `EXP-0119` (M4) re-spliced *EXP-M4-14's own literal anchor bytes*
(`27 05 56 00 02 00 5c 04` / `27 05 54 …`) and got the **correct popcount either way**, with the
src operand unconditionally released to two independent later readers regardless of the bit.
`EXP-0119` discloses that a dispatch-shape confound is not ruled out (real multi-thread kernel vs
`grid=1/tg=1`). **This is the `EXP-0119` A18↔M4 contradiction the spec cites, and it is the only
direct cross-target byte-level contradiction I found in the corpus.** I labelled the field
`untested` with both observations in the note, because "two hardware runs disagree" is not a
semantics.

**D2 — `falu2.opflags`: carrier-dependent, two hardware results disagree.**
`EXP-0090` finding_1: a both-real `falu2` **requires** `opflags=3`; `opflags=1` is a silent zero of
the srcB read, falsified over 4 independent kernels. `EXP-0112`: swept all 4 raw values in two
shapes — including a byte-for-byte re-creation of EXP-0090's own falsifying construction — on a
different carrier file, and got the correct sum in **all 8 runs**, i.e. no observable effect at
all. Kept `hardware-run` because the release contract itself is independently established under
two-run gates by `EXP-0086`/`0089`/`0099`/`0119` across six families; the carrier dependence is
not root-caused. Safe policy recorded in the note: emit `opflags=3`, correct under both.

**D3 — `device_load` byte+8/+9: two experiments agree it is live, disagree on what it means.**
`EXP-M4-10` ISA-1 spliced byte+8 `0x51→0x11` and concluded "the load writes a different GPR."
`EXP-0101` proved that byte is **not** the destination register (the destination is `extmode/2`)
and that `dst_lo`/`dst_ext9` must be copied verbatim. Both observed a real effect from the same
byte. Labelled `single-template-inference` with the "never derive it" warning; the
"different GPR" reading is not carried forward.

**D4 — `falu2.ctrl` bits 0/1: same bits, two descriptions.**
`EXP-0105` classified them as "general silent corruptors"; `EXP-0119` identified them as the
0x09-group **instruction-length selector** (flipping one in place therefore re-lengths the
instruction and produces garbage). The readings are compatible, but they are different claims and
only the second is actionable. Both are in the `range` and `note`.

**D5 — the literal bit-17 / `0x54`↔`0x56` position has at least four behaviours.**
RT-1a-FIX/`EXP-0025`: inert scheduling hint (a same-instruction self-check, structurally incapable
of detecting a liveness bug). `EXP-0089`: in `unpack_convert`/`cvt_i2f` it corrupts the
instruction's **own** result *and* a later reader. `EXP-0086`/`0099`: in the `falu2` `opflags`
family (a different absolute bit) it corrupts **only** a later reader. `EXP-0119`: in `ibitcount`
it is causally **null** (corruption is unconditional), and in `device_store.addr_mode` it is
**inert**. `EXP-0119` §3.3's verdict — "at least three distinct behavioral signatures that happen
to share a bit position, not one mechanism" — is the one I encoded.

**D6 — mod-64 register aliasing vs "96 distinct registers".**
`EXP-0020`/RT-7 (A18): r0..r95 are 96 distinct entries, `r64 ≠ r0`, explicitly **no** mod-64
aliasing; r96+ reads 0 as an ALU source and faults as a memory index.
`EXP-0112`/`0099`/`0105`/`0119` (M4): a `falu2`/`falu2i` **source register field** value R in
[64,112] silently aliases to `r(R mod 64)` (proven with poison-register controls), and R in
{126,127} faults. These concern different paths — `get_sr`'s write side and the memory index
register vs the packed ALU source field — but the A18-era blanket "no mod-64 aliasing" statement
and the M4 ALU-source aliasing finding sit in tension and should not be read together.
Recorded on every affected register field.

**D7 — `device_store.index_reg` / `get_sr.dst` at R=112.**
`EXP-M4-10` reports the r95/r96 boundary as a clean uniform fault. `EXP-0092` found R=112
**genuinely nondeterministic** — fault in one gated run, `STATUS OK` with the write silently
discarded in the other, plus 8 informal repeats splitting 5 faults / 3 silent successes on
byte-identical splices. Not a contradiction, but "uniformly faults above 95" is too strong.

**D8 — the `iminmax` family is unvalidated and nondeterministic.**
`EXP-0105` found that splicing a real, in-range register field of this family produced **zero**
effect, and could not read back even a `mov_imm`-seeded low register. `EXP-0113` then found the
family's spliced results **nondeterministic across runs** (4/46 cases, identical bytes, different
outcomes), refuting the pilot impression that it could address r96–127. Every `iminmax` operand
field is `untested` with this flag; `db.json` carries the same provenance flag.

**D9 — `fast::` vs `precise::` sin/cos across targets.**
`EXP-0026` (A18): "fast and precise are byte-identical." `EXP-0103` (M4): 552/1294 (cos) and
554/1294 (sin) FP32 outputs differ, and the compiled AGX byte lengths differ (136 B vs 456 B for
sin). Not a field label — recorded here because it is a second A18↔M4 divergence in the corpus,
and because `EXP-0103` itself flags it as a refinement of the A18 claim rather than a conflict.

---

## 6. Defects surfaced by the labelling pass (not part of the brief, but load-bearing)

- **`half_alu_fma12.ext` and `falu2_ext8b.exttail` over-consume.** 121/126 and 193/250 corpus
  instances embed a real op-leader byte inside the "field". `db.json` flags both; a fixed 12-byte
  length for `byte0==0x10` is wrong and the length rule must be modifier/opsel-aware.
- **`op04_len8`'s fixed 8-byte length is a candidate over-consumer** of a following instruction
  leader (823 corpus firings, byte+2 spanning real op leaders).
- **`vary_store` mis-tokenizes the fragment kill/target-mask op** (`byte0=0x57`, `byte+2=0x54`,
  6 bytes) as an 8-byte vertex `vary_store` — an opcode collision `EXP-0091` identified and
  `db.json` flags as a pending split.
- **`tg_addr_compute`'s match over-fits the r1 form** (see §2 caveat 3).
- **`unpack_convert`'s match table forces every bit of the `cache` byte except bit1**, so
  `EXP-0119`'s 7-bit resweep constructed bytes that do not re-decode as `unpack_convert` even
  though the hardware ran them and reproduced the baseline exactly. An open self-consistency
  question between our own decoder and the silicon.
- **`falu_srcmod12b.opsel` value 4 is an out-of-spec encoding with a blast radius wider than the
  instruction's own operands** — it corrupts an unrelated, independently seeded register
  (`EXP-0119` §2.4). A field the tooling modelled as an innocuous `mod` byte.

---

## 7. Limitations of this pass, stated plainly

1. **This is a desk labelling of committed evidence, not new evidence.** Where an experiment's
   `RESULTS.md` and `db.json`'s note disagreed about a range, I took the experiment.
2. **Ranges for `EXP-M4-14`'s A18 sweeps are transcribed from
   `experiments/EXP-M4-14-a18-splice/splice_results.json`'s `evidence` strings.** They are exact
   value sets, but they are 5–12 values out of 256 for most 8-bit fields. `hardware-run` here means
   "boundaries plus interior samples, with the observed outcome for each", not exhaustive.
   Two fields *are* exhaustive: `get_sr.sr_sel` (256/256) and `device_load.base_slot` (256/256).
3. **`tokenization-only`'s evidence is the census experiments as a set**, not a per-field pointer.
   That is the honest granularity available — `roundtrip_test.py` validates framing for the whole
   DB at once. If a stricter per-field pointer is wanted, those 304 fields would have to drop to
   `untested`, which would take the `untested` share from 29 % to about 59 %.
4. **No `api-accept-reject` and no `host-private` labels were assigned.** Both are real categories
   for this ISA (e.g. "integer `simdgroup_matrix` is rejected by MSL", "64-bit atomics are absent
   from MSL") but those are *capability* facts about instructions that do not exist in `db.json`,
   not labels on fields that do. Flagging in case the orchestrator expects otherwise.
5. **The `emittable` rule was implemented as "every field in the descriptor"**, with one explicit,
   documented veto (`tg_addr_compute`) where a load-bearing byte is proven live but is not modelled
   as a field. The spec's wording is "every field an emitter must fill"; the veto mechanism exists
   so that reading is not quietly lost.
6. **Nothing here was committed.** The orchestrator commits.

## 8. Reproduction

```
python3 work/gen_validation.py            # regenerates tools/agx-isa/validation.json
python3 tools/agx-isa/validate_labels.py  # exits 0 on success, 1 on any violation
```

Validator output on the committed artifact:

```
OK: 170 instructions, 1025 fields, all labels valid.
  hardware-run                115  (11.2%)
  isolated-byte-diff           51  ( 5.0%)
  corpus-correlation          234  (22.8%)
  tokenization-only           304  (29.7%)
  single-template-inference    23  ( 2.2%)
  api-accept-reject             0  ( 0.0%)
  host-private                  0  ( 0.0%)
  untested                    298  (29.1%)
  emittable instructions: 5 / 170
```

Ten mutation tests were run against the validator (missing field, missing mnemonic, invalid label,
empty evidence on a non-`untested` label, `range: "tested"` on a `hardware-run` entry, evidence on
an `untested` entry, invalid target, extra field, wrong coverage count, wrong emittable list).
All ten exit **1** with a specific `FAIL:` line.
