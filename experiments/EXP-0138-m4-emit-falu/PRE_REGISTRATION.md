# EXP-0138 — PRE-REGISTRATION (frozen before the gated runs)

**Experiment:** `EXP-0138-m4-emit-falu` — move the float-ALU (FALU) family from
*decodable* to *emittable*.
**Target:** Apple **M4 / G16G**, local host only. macOS 26.6.2 (25G82), Metal 4.
No A18 Pro contact of any kind (hands-off, `CLAUDE.md`). No M5.
**Row:** `DRV-ISA-01` / `P0.6` (per-field emitter grade, `docs/evidence-classification.md`).

## 0. Scope

`tools/agx-isa/validation.json` leaves **98 fields** across **16 float-ALU
instructions** below emitter grade (`hardware-run` / `isolated-byte-diff`):

```
copysign 1 · falu2 1 · falu2_ext 9 · falu2_srcmod10 13 · falu2_uni 8 · falu2i 2
falu3 8 · falu3_ext 7 · falu3_srcmod12 11 · falu_acc 4 · falu_srcmod12b 9
fspecial 11 · fspecial_est 5 · half_alu 2 · half_alu_ext8 4 · half_alu_fma12 3
```

(The dispatch named 17 instructions / 107 fields; `falu2_ext8b` and its 9 fields
were **deleted from `db.json` by EXP-0148** — it was never an instruction — so
the real target is 16 instructions / 98 fields. This is recorded, not silently
adjusted.)

**Priority order (fixed before running):** `falu2.mod_lo` first and alone if
nothing else lands; then `copysign.operands`, `half_alu.dst`/`.opflags`,
`falu2i.imm_flag`/`.ctrl_lo`; then `falu3`, `fspecial`, `falu_acc`, then the
`_ext` / `_srcmod` variants.

## 1. Hypotheses (falsifiable, with refuters)

**H-MODLO — `falu2.mod_lo` is an operand-SOURCE selector, not a spare modifier.**
`mod_lo` is byte+5 bits[2:0] of the falu2-family base layout. `half_alu`'s
byte+5 at the same bit positions was HW-observed on A18 (EXP-M4-14) to suppress
one operand or the other; and OUR OWN compile of `a[t] + u` (a `constant float&`)
emits `falu2` with `mod_lo = 2` and a `srcB_reg` that is not a live GPR.
*Predicted:* bit0 makes srcA read the uniform register file at `srcA_reg`; bit1
makes srcB read it at `srcB_reg`; bit2 behaves like bit1.
*Refuter (pre-registered as a case):* with a `constant float4&` bound holding
{101,202,303,404}, `mod_lo=2` and `srcB_reg=2` (an index the uniform file does
**not** hold) must NOT return the GPR answer 8.0. If it does, H-MODLO is dead.
*Also refuted if:* the eight values are indistinguishable, or the uniform values
never appear.

**H-FALU3-LAYOUT — `db.json`'s field names for `falu3`/`falu3_ext` are off by one
slot.** From our own `fma(a0,a1,a2)` anchor `09 01 1e 05 81 08 02 c0` and the
falu2-family byte layout: byte0's high nibble (`dst_lo`) is the DESTINATION,
byte+1 (`dst`) is the FIRST SOURCE descriptor, byte+3 (`srcA`) is the SECOND,
byte+4 (`srcB`) is a control byte whose low 2 bits are the 0x09-group LENGTH
selector, byte+5 (`srcC`) is the THIRD SOURCE. *Refuter:* a dense 0..255 sweep
of byte+1 / byte+3 / byte+5 that does **not** track `(reg<<1)|is32` against the
13 seeded registers.

**H-HALF-LAYOUT — the same off-by-one applies to `half_alu*`.** `db.json` models
byte0 as a fixed `0x10` match and byte+1 as `dst`. Predicted: byte0's high
nibble is the destination and byte+1 is the first source descriptor.
*Refuter:* sweeping byte+1 leaves the result unchanged, or sweeping byte0's high
nibble does.

**H-REGDESC — every float-ALU operand byte is `(reg<<1)|is32` with bit7 the
HW-tested-inert top bit**, and register values obey EXP-0112's aliasing rule
(`r(R mod 64)` for R in 64..112; 126/127 fault). *Refuter:* a descriptor sweep
whose hits do not land on the seeded registers.

**H-NULL (every other field).** The default, explicitly-labelled hypothesis for
a field with no prior semantics is **"this field is inert: changing it does not
change the instruction's result."** Every such case carries the anchor result as
its oracle, so a mismatch is a positive finding, not a missing prediction.

## 2. Variables

*Independent:* exactly one field of exactly one instruction per case.
*Controlled:* carrier program, seeded register contents, operand registers, all
other fields of the instruction under test, buffer bindings, grid/threadgroup
(1/1), the compiled carrier (byte-identical across both runs).
*Measured:* the destination word, the integrity-sentinel word, one source
register, the command-buffer status, and the OS fault-classification string.

## 3. Method

Two execution modes, both validated in the pilot (`PROGRESS.md` M1):

* **MODE A** — a hand-built program replaces the whole `_agc.main` of
  `kernels/carrier.metal` (1218 B) or `kernels/carrier_uni.metal` (1246 B, with
  a `constant float4&` bound so the uniform file is live). It seeds r0..r12 with
  13 distinct EXACT minifloat constants via `falu2i`, executes ONE instruction
  under test, then stores the destination (word 0), the control register r11
  (word 4, the integrity sentinel), and r0 (word 8).
* **MODE B** — ONE instruction is spliced in place inside a compiled carrier
  from `kernels/probes.metal`, scaffolding intact. Used for fp16, `copysign`
  and the SFU forms, whose operands cannot be hand-seeded.

**Coverage rule (protocol section 3.3):** every field of width ≤ 8 is swept
**densely over its whole encodable range**. Wider fields (the 16/32/48-bit
`ext`/`ext_srcmod` tails) are swept **byte by byte**, each constituent byte over
0..255 with the others at their anchor value; the whole-field space is not
claimed. 7-bit register fields are swept over 0..15 dense plus the boundary set
{16,24,31,32,40,48,63,64,66,67,95,96,112,120,125,126,127}.

**16,202 cases.** Two independent gated runs, separate processes.

## 4. Contamination controls (FIELD-SWEEP-PROTOCOL section 7 — binding)

1. **Unique splice-archive path per request** (~8% phantom `CMDBUF_ERROR`
   otherwise; this experiment's own pilot saw exactly that).
2. **Poisoned output buffer.** `agxrun_persist` only allocates an output buffer
   if the index was not also supplied as an input, so the harness binds the
   output index to a file of `0xDEADBEEF`. "Nothing was written" is therefore
   distinguishable from "zero was written" — the mistake EXP-0140 retracted.
3. **Majority-of-3 before any `fault` verdict.** A single non-OK observation is
   never recorded as a property of the field.
4. **OS fault-classification string recorded verbatim**;
   `Discarded`/`InnocentVictim`-class failures are retried and segregated as
   machine evidence, never encoding evidence.
5. **Baseline re-validation every 200 cases per carrier.** A failed baseline is
   a GPU error cascade: the child process is restarted and the event recorded in
   `raw/<run>/cascades.json`.
6. **Integrity sentinel per case.** MODE A: r11 (seeded by an instruction
   independent of the one under test) must read back 26.0 and the untouched
   words must still hold the poison. MODE B: the poison must be gone from
   out[0]. A case failing its sentinel is `invalid_run`, never a field
   observation.

## 5. Safety

`falu_srcmod12b` `opsel == 4` corrupts an unrelated, independently seeded
register (EXP-0119) — it is **excluded from every sweep**. `half_alu_fma12` and
`falu_srcmod12b` are `emit_unsafe` in `db.json` because their length
over-consumes the following instruction's leader byte; for `half_alu_fma12` the
trailing `ext` field is therefore **not swept** (a sweep there would be sweeping
the next instruction). Hard 12 s watchdog per request. After two genuine hangs in
one arm, that arm STOPS and is reported PARTIAL.

## 6. Outcome vocabulary

`ok` | `silent_zero` | `wrong_value` | `fault` | `hang` | `undecodable`
(protocol section 4), extended with `victim` (segregated machine evidence),
`invalid_run` (sentinel failed) and `exploratory` (a case whose oracle is
explicitly `null` because no semantics were pre-registered). The extension is
declared here so no outcome is silently reinterpreted later.

## 7. Promotion rule (decided before seeing the data)

A field is labelled `hardware-run` only if **all** hold:
1. the sweep is dense over the field's whole encodable range (or, for a wide
   tail, over the constituent byte actually claimed);
2. the field is demonstrably LIVE on the observed output path (at least one
   value changes the result, or the family's own operands provably flow through
   it);
3. every pre-registered prediction for that field either matched or was
   explicitly refuted and replaced by a rule that then matches;
4. the per-value outcome map is **identical in both gated runs**;
5. no case in the field's sweep is `invalid_run` or unresolved-`victim`.
Otherwise the field keeps a weaker label. Fields whose only evidence is
"changing it did nothing" are labelled `hardware-run` ONLY when the field is
live-path-adjacent and the inertness is the emitter-relevant fact; where
inertness could equally mean "the operand never reached the output", the field
is left `untested` and said so.

## 8. Frozen inputs

`CAPTURE_CONTRACT.json` (sibling file) freezes: repo revision, the SHA-256 of
every authored harness/kernel file and of every read-only tool this experiment
executes, the carrier `_agc.main` lengths and anchor bytes, the environment, the
timeouts, and the raw-tree schema. A capture is valid if those authored blob
hashes match; repo `HEAD` moving because a sibling experiment landed is not
contamination.

## 9. Known confounders

* **Nine to ten sibling GPU experiments run concurrently on this host.** That is
  the reason for section 4 and it will be stated in `RESULTS.md`.
* Metal in-process memoization of a library built from source (defeated by
  `agxrun_persist`'s per-request `newLibraryWithURL:`).
* Register release/last-use bits (`opflags` 19/20): the instruction under test
  is built with `opflags=0` unless `opflags` is itself the swept variable, so a
  later read-back store cannot see a released source. (Found in the pilot.)
* The 0x09-group instruction LENGTH is selected by `byte+4`'s low 2 bits, so
  several fields that `db.json` models as ordinary modifiers re-length the
  instruction. Those cases are expected to desync and are recorded, not hidden.
* `db.json` changed under this experiment (EXP-0148). Every anchor was
  re-verified byte-for-byte against the current `isadb` before freezing.
