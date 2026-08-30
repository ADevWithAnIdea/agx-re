# PRE-REGISTRATION — EXP-0157 (Apple A18 Pro / G17P)
## The MISC family: ray-query, SFU-adjacent, half-coordinate, mesh, fence and `op04` descriptors

**FROZEN before any gated capture.** Nothing below is edited after the first gated run;
deviations are recorded in `RESULTS.md` § Deviations, never by rewriting this file.

**Target: Apple A18 Pro / G17P** (`users-MacBook-Neo`, `Mac17,5`, `AGXAcceleratorG17P`,
arch `applegpu_g17p`, 5 GPU cores, macOS 26.6 build 25G5043d, Metal family Apple9).
Every result this experiment produces is labelled **`target: G17P`**. No M4/G16G label is
carried onto a G17P record and no G17P label onto an M4 record.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal), the AGX bytes those compile to on
  G17P, and the outputs the GPU produced from them. tools/shdump, tools/agx-isa and
  tools/agxtest are used READ-ONLY and UNMODIFIED; harness/agxrun_persist_as.m is a
  DERIVED COPY of tools/agxtest/agxrun_persist.m carrying this experiment's additions.
Apple binary introspection: NONE
Reproduction: harness/build.sh ; harness/run.py --run-id <id> ... ; analysis/verdicts.py
Evidence: raw/<run_id>/{00_env.json,00_build.json,00_manifest.json,sweep.jsonl}
```

Repository revision at freeze: `d1b0042278a5c1419736cc24f8c7485e60b34bc0` (53 dirty files in the working tree, all
belonging to sibling experiments; per `SUBAGENT_BRIEF.md` a capture is valid if the
**authored blob hashes** match, and `HEAD` moving because a sibling lands is not
contamination). Frozen source hashes: `CAPTURE_CONTRACT.json`.

---

## 0. Provenance of the harness and the carriers

This experiment authors two new things and reuses everything else with citation.

**Authored here:**

* `harness/agxrun_persist_as.m` — `tools/agxtest/agxrun_persist.m` (EXP-0005) **plus an
  `MTLAccelerationStructure` binding path**. The upstream tool is deliberately NOT edited:
  four sibling G17P experiments (EXP-0153/0154/0155/0156) rebuild it from `tools/`
  concurrently, and rewriting a shared source mid-wave would break their builds. The
  addition is fenced by `EXP-0157 ADDITION` comments so it can be upstreamed verbatim.
* `kernels/k_rq_prim.metal`, `kernels/k_rq_inst.metal`, `kernels/k_rq_getters.metal`,
  `kernels/k_provoke.metal` — our own MSL.

**Reused verbatim, with citation:** `harness/{anchors,isa_helpers}.py` and the shape of
`harness/run.py` from **EXP-0153** (itself from EXP-0139/0141 → EXP-0112 → EXP-0090);
`kernels/k_sfu_sin.metal`, `k_roundmodes.metal`, `k_u64eq.metal`, `k_zext16.metal`,
`k_sfu_mix.metal` from **EXP-0146**; `kernels/c_hcoord.metal` from **EXP-0145**.

## 1. Question

Twenty `db.json` descriptors in the "MISC" cluster have no emitter-grade field on the
**documentation target**. For each, can an emitter choose arbitrary values and get the
documented behaviour on G17P — and where it cannot, is the blocker the hardware, the
descriptor, or our testbed?

The load-bearing sub-question, named by the dispatch: **`sr_read_wide` and the whole
`rtq_*`/`ray_move*` cluster were unsweepable because `agxrun_persist` binds `MTLBuffer`s
only and cannot bind an `MTLAccelerationStructure`** (EXP-0146 §3.7). That is a testbed
gap, not a hardware fact. Closing it is hypothesis H0.

## 2. Hypotheses, each with its refuter

**H0 (testbed).** Adding a `setAccelerationStructure:` path makes our own
`intersection_query` kernels actually traverse, so every ray-query getter reaches the
output and the cluster becomes sweepable.
*Predicted:* each single-getter carrier returns its host-computed oracle exactly.
*Refuter:* the getters still return zero (or the poison word) with an AS bound — then the
blocker was never the binding.

**H1 (`ray_move*` are one instruction).** `ray_move`, `ray_move_copy6`, `ray_move_zero6`,
`ray_move_zinit` and `rtq_state_move` are five `byte+2` values of ONE `0x?b` 4-byte
compact move, the family EXP-0140 showed `reg_move_c0/c1/c2var/c9/cb/uniform_mov` to be.
*Predicted:* in the RT carriers their `dst`/`src` fields behave like the family's, and
`byte+2` accepts a masked subset that does NOT match EXP-0140's `(v & 0xCB) == 0x01`
(none of 0x81/0x41/0x40/0x80/0x09 satisfies it), i.e. the accepted set is context-dependent.
*Refuter:* `byte+2` in the RT carrier accepts exactly EXP-0140's set — then the RT forms
are not reachable there and the five descriptors are unexplained.

**H2 (`sr_read_wide` is the ray-query property read).** Its `sel`/`width`/`phase` fields
select WHICH property (primitive id / geometry id / distance / type) and whether the read
is of the CANDIDATE or the COMMITTED hit.
*Predicted:* a single-getter carrier's output changes to another property's value for some
swept value — i.e. at least one value produces a *different but predictable* number.
*Refuter:* every value either reproduces the baseline or silently zeroes, with no value
producing another getter's oracle.

**H3 (G17P reproduces EXP-0146's M4 bit-rules).** For `n2_op6`, `n2_op10`, `n3_mov`,
`sfu_marker` the accepted-value masks measured on M4/G16G reproduce on G17P.
*Predicted:* the same exact rule (same mask, same free bits) in the same carrier.
*Refuter:* a different accepted set — a first-class G16G↔G17P divergence, reported as such.

**H4 (`op04_len8` is 8 bytes).** The descriptor's fixed length 8 is the true hardware
length of the `byte0` low-nibble-4 residue.
*Predicted:* in the register-witness probe of §5.5 the witness registers written are
exactly those of an 8-byte consumption.
*Refuter:* a different witness pattern — which measures the true length directly and
resolves EXP-0148's OPEN item by a method it did not use (EXP-0148 tried six *static*
length rules scored on corpus tokenization; this is a *hardware* measurement).

**H5 (`mesh_out_src` has no compute carrier).** The 2-byte `04 XX` mesh output-source op
is not produced by, and not live in, any compute-stage own-MSL program.
*Predicted:* no own-MSL compute provocation emits it, and splicing `04 XX` into a compute
carrier is inert or faults for every XX.
*Refuter:* some XX produces a predictable output change — then `sel` is live in compute.

**H6 (the fences still have no ordering-specific litmus).** EXP-0141 and EXP-0147 both
declined to promote `scoreboard_fence`/`compute_fence_scoped`. This experiment
**pre-commits to the same restraint**: a fence field is promoted **only** if a litmus is
demonstrated that detects a spliced-OUT barrier, on this target, in this carrier.
*Predicted:* our carriers have no such power; the fields stay unpromoted.
*Refuter:* the litmus control (a barrier removed from a program whose result depends on it)
changes the output — then and only then a fence sweep means something.

## 3. Variables

* **Independent:** exactly one instruction field (or one named raw byte of a multi-byte
  field) per case, at one resolved anchor, in one carrier.
* **Controlled:** carrier source, dispatch shape, every input buffer, the acceleration
  structure geometry, the runner binary, `db.json`, the splice offset.
* **Dependent:** the read-back output words, the command-buffer status, and the OS
  fault-classification string.

## 4. Confounders and how each is handled

1. **Cross-agent GPU contamination.** Up to eight agents share this GPU.
   `...ErrorInnocentVictim` failures are retried (up to 6×) and never scored; a `fault`
   verdict requires reproduction in ≥2 of 3 non-innocent attempts; the count of other GPU
   runner processes is recorded per run.
2. **`STATUS OK` with nothing executed.** Every output buffer is bound pre-filled with
   `POISON_WORD(i) = 0xDEADBEEF + i`, and every RT carrier writes a query-independent
   **integrity sentinel** `out[1] = 7.5f` before touching the query. A word that reads back
   as its own poison is UNWRITTEN, not zero.
3. **Zero oracles hide silent zeros.** The acceleration-structure geometry is deliberately
   TWO geometries with the closest hit at primitive id 2, so **every** RT oracle is
   non-zero (3, 1, 10, 4, 2, 1, 1). A silent zero can never score as a pass.
4. **Anchors inside a program that does not tokenize end-to-end.** The RT carriers are
   8–25 kB and desynchronise. Offsets come from a **resync walk** (`analysis/resync.py`),
   and every anchor carries its `after_gap` flag. A resync offset is NEVER trusted on its
   own: each anchor gets two pre-registered **liveness controls** (§5.2) and no field at an
   anchor that fails both is promoted.
5. **Splice-archive path reuse** gives ~8 % phantom `CMDBUF_ERROR` (EXP-0141): every
   request writes a UNIQUE archive path.
6. **Cascades.** The unmutated carrier is re-validated every 120 cases; two consecutive
   failures abandon the carrier and the run resumes in a fresh process.
7. **Register aliasing of the sentinel.** The dispatch's warning (EXP-0138 lost six sweeps
   because reading r11 as a source zeroes it) applies to *synthesised* programs. Arms R, S
   and H splice into COMPILED carriers and do not name registers, so the sentinel is a
   separate output word on an independent store rather than a register. Arm L, which does
   synthesise, uses witness registers r1..r5 and a sentinel written **before** the
   instruction under test from a register the probe never names.

## 5. Method, per arm

### 5.1 Carriers (all authored or reused own-MSL; all oracles host-computed)

| id | kernel / function | grid,tg | out | host oracle |
|---|---|---|---|---|
| `rq_cprim` | `k_rq_getters.metal` / `k_cand_prim` | 1,1 | 0 (4 w) | `[3.0, 7.5]` |
| `rq_cgeom` | … / `k_cand_geom` | 1,1 | 0 | `[1.0, 7.5]` |
| `rq_cdist` | … / `k_cand_dist` | 1,1 | 0 | `[10.0, 7.5]` |
| `rq_ccount` | … / `k_cand_count` | 1,1 | 0 | `[4.0, 7.5]` |
| `rq_mprim` | … / `k_comm_prim` | 1,1 | 0 | `[2.0, 7.5]` |
| `rq_mdist` | … / `k_comm_dist` | 1,1 | 0 | `[1.0, 7.5]` |
| `rq_mtype` | … / `k_comm_type` | 1,1 | 0 | `[1.0, 7.5]` |
| `rq_all` | `k_rq_prim.metal` / `k` | 1,1 | 0 (8 w) | `[4,3,1,10,2,0,1,1]` |
| `sfusin` | `k_sfu_sin.metal` / `k` | 8,8 | 1 | `fast::sin(a[i])`, tol 1e-3 |
| `sfucos` | `k_provoke.metal` / `k_sfu_cos` | 8,8 | 1 | `cos(a[i])`, tol 1e-3 |
| `sfumix` | `k_provoke.metal` / `k_sfu_sincos` | 8,8 | 1 | `sin+cos+tan`, tol 1e-2 |
| `u64eq` | `k_u64eq.metal` / `k` | 8,8 | 2 | `a[i]==b[i]` |
| `roundm` | `k_roundmodes.metal` / `k` | 8,8 | 1 | `rint+floor+ceil+trunc+round` |
| `h4fma` | `k_provoke.metal` / `k_h4_fma` | 8,8 | 2 | `fma(x,y.wzyx,x.wzyx)*y.yxwz` (half4) |
| `h3mix` | `k_provoke.metal` / `k_h3_mix` | 8,8 | 2 | `mix(x,y,0.25)*fma(x,y,y.zxy)` (half3) |
| `synth` | `kernels/carrier_synth.metal` / `k` | 1,1 | 0 | per case (arms L and M) |

Every carrier's unmutated baseline is captured as the first case of its arm and re-checked
every 120 cases.

### 5.2 Anchor resolution and the two liveness controls (binding)

For each target mnemonic, `analysis/resync.py` enumerates every occurrence in the
carrier's own compiled `_agc.main`. For each candidate anchor two controls run **before**
any field sweep, and both are recorded:

* **L1 — opcode-group control:** `byte0 ^= 0x01` (a different opcode group at the same
  offset).
* **L2 — erase control:** every byte of the instruction replaced by `0x00`.

An anchor is **LIVE** iff L1 or L2 changes the output away from the baseline (any of
`wrong_value`, `silent_zero`, `not_written`, `fault`, `hang`). Fields are swept only at
LIVE anchors. An anchor where both controls reproduce the baseline is recorded as
`inert_or_unreached` and **nothing at it is promoted** — the FIELD-SWEEP-PROTOCOL §3.2
requirement, made empirical.

### 5.3 Coverage (FIELD-SWEEP-PROTOCOL §3)

Per LIVE anchor, for every field `db.json` declares:

* `w <= 8` → **all 2^w values**, dense.
* `w > 8` → `{0, 1, 2, max-1, max}`, every power of two, and ≥16 interior samples
  including asymmetric ones. Multi-byte `raw`/`imm` fields are additionally swept
  **byte-by-byte** (all 256 values per constituent byte), recorded under
  `<instr>.byte+N@<carrier>` with a `component_of` link, exactly as EXP-0146 did.

### 5.4 Oracle and falsifiers

The oracle is the carrier's host-computed unmutated result (§5.1); for arm L it is the
witness-register pattern computed on the host. **Pre-registered `expect_match = False`
cases** (at least one per arm):

* **R-F1** `sr_read_wide.sel` set to the value another getter kernel uses — expected to
  return that other property's oracle, not this carrier's.
* **R-F2** `ray_move.dst` set to the destination of a register the store reads — expected
  to corrupt the output.
* **S-F1** `sfu_marker.byte+0 = 0x00` — EXP-0146 (M4) reports this flips `fast::sin`'s sign
  on range-reduced rows; expected to mismatch here too.
* **H-F1** `h_coord_hi.opsel = 0x00` — expected to mismatch (op-select is load-bearing).
* **L-F1** an `op04` candidate declared 8 bytes but followed immediately by the witness
  `mov_imm` — expected to write witness r5 iff the true length is 6.
* **M-F1** `mesh_out_src` spliced with `sel = 0x00` over a live 2-byte instruction —
  expected to mismatch (it destroys a real instruction).

If every falsifier passes, the sweep has demonstrated no discriminating power and **no
field is promoted from that arm**.

### 5.5 Arm L — the `op04_len8` hardware length probe (new method)

EXP-0148 tested six *static* length rules and scored them on corpus tokenization; all six
measured worse than the status quo, and it left the item OPEN. This arm measures the length
**on the hardware** instead, and is A/B'd against nothing — it is a different question.

A program is synthesised in `carrier_synth`:

```
sentinel: mov_imm(r15, 91) ; device_store(out[11], r15)      <- independent of the probe
seed:     mov_imm(r1..r5, 0)                                  <- witnesses start at 0
probe:    <candidate op04 bytes, 6 bytes> mov_imm(r5, 5)      <- 8 bytes total
witness:  mov_imm(r1,1) mov_imm(r2,2) mov_imm(r3,3) mov_imm(r4,4)
store:    device_store(out[1..5], r1..r5)
          stop
```

The witness pattern read back **measures the consumed length directly**:

| observed | implied length |
|---|---|
| r1..r4 = 1..4, r5 = 5 | **6** — decoding resumed inside our 8-byte blob |
| r1..r4 = 1..4, r5 = 0 | **8** — the trailing `mov_imm(r5,5)` was consumed |
| r1 = 0, r2..r4 = 2..4, r5 = 0 | **10** |
| r1 = r2 = 0, r3, r4 set | **12** |

Candidate byte patterns are the `op04_len8` instances **actually observed in our own G17P
compiles** (`0442a22a4f808634`, `0442922c0f808612`, `04429b132f6b0002`, …), never
invented ones.

### 5.6 Arm F — the fence litmus-power test (promotion pre-emptively declined)

Before any fence value is swept, a **litmus control** runs: the carrier's own barrier
instruction is replaced by inert padding of the same length. If the output does not change,
the carrier cannot detect a removed barrier, and per H6 **no fence field is promoted from
this experiment**, regardless of how many values "pass". This is the same restraint
EXP-0141 and EXP-0147 exercised and is recorded as a bounded negative, not a gap.

## 6. Raw-record schema (FIELD-SWEEP-PROTOCOL §4)

One JSON object per case, appended to `raw/<run_id>/sweep.jsonl` and `fflush`+`fsync`ed
immediately:

```json
{"arm":"R","i":17,"rep":0,"carrier":"rq_cdist","instr":"sr_read_wide","field":"sel",
 "value":72,"anchor":2134,"after_gap":false,"bytes":"04c8...","observed":{...},
 "oracle":{...},"match":false,"outcome":"wrong_value","status":"OK","statuses":null,
 "fault_classes":null,"innocent_retries":null,"expect_match":true,"note":""}
```

`outcome` ∈ `ok` | `silent_zero` | `wrong_value` | `not_written` | `fault` | `hang` |
`nondeterministic` | `undecodable`.

## 7. Environment, timeouts, safety

* Every remote call is wrapped in `perl -e 'alarm N; exec @ARGV'`.
* Per-request watchdog 10 s; the persistent runner is killed and restarted on a wedge.
* **Two reproduced hangs abort an arm; six abandon a carrier** (EXP-0128's rule).
* Bulk sweeps run **unlocked and concurrent** (NEO-TARGET-BRIEF); `gpulease.sh` is taken
  only for re-validation and for any arm that has already hung once.
* `macvdmtool` is forbidden to this agent without exception. If the neo stops answering:
  STOP and report BLOCKED.
* `raw/` is pulled back into this repository as it is produced.

## 8. Analysis plan, fixed in advance

1. **Two gated runs.** run01 and run02 are independent captures of the same frozen case
   list. A field is promoted only from cases that AGREE across both runs.
2. **Re-validation.** Every non-`ok` case of run01 is re-run under the GPU lease; a
   `fault`/`hang` that does not reproduce is re-classified and excluded from the gate.
3. **Verdicts.** `analysis/verdicts.py` writes `analysis/field_verdicts.json` in the
   FIELD-SWEEP-PROTOCOL §5 schema, using **only** the eight labels of
   `docs/evidence-classification.md`, every entry carrying `range`, `target: G17P` and
   `evidence: ["EXP-0157"]`.
4. **Emittability.** A descriptor is reported EMITTABLE only when **every** field
   `db.json` declares for it reaches `hardware-run` or `isolated-byte-diff` in this
   experiment or already holds one in `validation.json`.
5. **db defects** go under `"db_defects"`; `db.json` is **not** edited.

## 9. What this experiment will NOT claim

* No fence field is promoted unless §5.6's litmus control demonstrates ordering-specific
  detection power on this target.
* No field is promoted from an anchor that failed both liveness controls.
* No M4 result is relabelled G17P; a G16G↔G17P disagreement is reported as a finding.
* Nothing is promoted from a single run, or from a single observation of a fault.
