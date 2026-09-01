# EXP-0232 pre-registration — canonical `iadd2` register reach

Frozen before the first hardware dispatch. Repository base: `f0d90814`.

## Question

What exact physical GPR sets can the already-proved canonical ten-byte 32-bit `iadd2` recipe read
through each source role and write through its destination role on G17P?

EXP-0222 proved all three roles only through r23. The encoding geometry predicts asymmetric sets:
the first source selector is a 7-bit `reg<<2` field, the second is an 8-bit `reg<<2` field, and the
destination is an 8-bit `(reg<<1)|1` field with a previously measured hardware fault at r95.
Field width is not accepted as register reach; this experiment executes every canonical in-range
descriptor.

## Frozen primary model

- **Source A:** `srcB_ext = A<<2` directly reads exactly r0..r31.
- **Source B:** `srcB_imm = B<<2` directly reads exactly r0..r63.
- **Destination:** `dst = (D<<1)|1` directly writes r0..r94.
- Both sources are retained with `opc_tail=0x11`, and destination publication follows source reads
  on aliases.

The first unrepresentable canonical source-A descriptor is r32 (`128`, outside the 7-bit field);
the first unrepresentable canonical source-B descriptor is r64 (`256`, outside the 8-bit field).
These are representation bounds for this fixed canonical form, not hardware faults. Alternate
extension/control-field combinations remain separate capability questions and are not silently
declared impossible.

The destination field can represent r95, but prior G17P hardware evidence in EXP-0139/EXP-0146
classifies r95 as the first contained address fault. EXP-0232 rechecks every valid r0..r94 value
without spending the quiet formal run on an already-established fault/recovery event.

## Matrix

- 32 source-A cases: r0..r31 dense.
- 64 source-B cases: r0..r63 dense.
- 95 destination cases: r0..r94 dense.
- Two wrong-oracle controls, one source and one destination.
- Two formal runs in canonical and reverse order on Apple A18 Pro / G17P.

Every selected source and every modulo-16/32 rival receives a separately observed codeword before
the add. Destination cases seed and observe the physical destination and its modulo-16/32/64
rivals. Dynamic index registers are chosen from r13..r15 outside the case's relevant set, so the
store index's release cannot destroy a measured operand.

## Five gates

- **A:** the actual dispatched body must decode as exactly one generated `iadd2`, with no byte or
  descriptor disagreement.
- **B:** source/destination/alias pre-witnesses, complete three-buffer state, and the sentinel must
  pass; both wrong-oracle controls must fail.
- **C:** every main result and all retained/alias state must match the independent modulo-2^32 host
  model in both runs. Exact source selection must beat modulo-16/32 alternatives where the tested
  range distinguishes them.
- **D:** all fields are generated from the EXP-0222 canonical recipe. `COPIED=0` and `CARRIER=0`
  are mandatory.
- **E:** two quiet opposite-order G17P runs must agree case-for-case, with no foreign runner,
  unexplained recovery, fault, hang, or restart.

## Scope and finite-resource rule

This closes per-role direct register reach for one canonical 10-byte b32 register-register form.
It does not close immediate, b16, b64/pair, uniform, compressed, or alternate extension-field
forms. Those remain distinct until executed. The maximum valid and first invalid destination are
r94/r95; the source canonical namespaces end by field representation at r31/r63. No statement
about a larger alternate form is inferred.

Every dispatch has a 20-second watchdog and raw JSONL is append-only. If the device becomes
unresponsive, immediately stop, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
