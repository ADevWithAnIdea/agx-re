# EXP-0222 results — generated G17P `iadd2` / `isub2` recipe

Status: **canonical recipe proven over the tested r0..r23, 32-bit register-register envelope.**

Target: Apple A18 Pro / G17P, macOS 26.6 build 25G5043d, Metal family Apple9.  Clean-room
classes: OWN-SHADER carrier, HW-PROBE, and (after three failed generated hypotheses) an own-MSL
byte differential used only to nominate a hardware sweep.  No Apple-authored binary or shader was
inspected.  No compiler-emitted instruction field was copied into the generated recipe.

## Result

For a 32-bit operation over the tested GPR range, generate the ten-byte instruction with:

```text
addsub       = 1 add, 0 subtract
lenbit       = 1
srcB_reg_hi  = 0
b2_bit0      = 0
store_en     = 1
b2_fmt       = 0x15
dst          = (D << 1) | 1
opmode       = 2
srcB_imm_hi  = 0
srcA         = 0xa8
opc_tail2    = 0x05
```

The two physical register selectors and arithmetic order are:

```text
ADD(A,B): srcB_ext=A<<2, srcB_imm=B<<2     result = first + second
SUB(A,B): srcB_ext=B<<2, srcB_imm=A<<2     result = second - first = A-B
```

Start `opc_tail` at `0x11`.  Bit 2 releases/zeroes the first physical source after it is read;
bit 1 releases/zeroes the second:

| `opc_tail` | first source | second source |
|---|---|---|
| `0x11` | retain | retain |
| `0x13` | retain | release to zero |
| `0x15` | release to zero | retain |
| `0x17` | release to zero | release to zero |

Because subtraction reverses the logical operands in the two physical source positions, a compiler
must reverse the release-bit association too.  When a released source aliases D, the destination
write wins and D contains the arithmetic result.  `A==B`, `D==A`, and `D==B` are all valid.

## Evidence

The two formal runs each contain 165 generated programs: eight hardware slot probes, one baseline,
one arithmetic refuter, 16 lifecycle/alias/consumer cases, 11 load-provenance/high-register cases,
28 cross-register cases, and 100 deterministic random DAGs of 2..64 operations.  The random cases
use two disjoint plans, r0..r6 and r16..r22.

- 312/312 exact semantic cases matched the independent complete-state oracle across the two runs.
- The deliberately wrong first-source selector fired in both runs.
- Generated-program and complete-output SHA-256 agree per case between canonical and shuffled
  orders: 0/165 disagreements.
- Gate A: zero requested/actual byte disagreements and zero decoder aliases.
- Gate D: `COPIED=0`, `CARRIER=0`; donor lists empty in all 330 dispatches.
- Gate E: six quiet samples, zero foreign runners, zero recovery-count change, zero fault, hang,
  victim, malformed response, or sentinel failure.

Run the verifier rather than trusting these totals:

```sh
python3 experiments/EXP-0222-iadd-canonical/analysis/verify222.py
```

Raw captures are `raw/g17p_e0222_run01` and `raw/g17p_e0222_run02`.

## What was corrected

1. The old generator's factor-of-two/pair selector was wrong.  G17P register-register sources use
   factor-of-four selectors in this form.
2. The existing prose described subtraction in the wrong physical order.  Hardware computes
   second minus first.
3. The fixed `opc_tail=0x17` point was not a harmless constant: it releases both inputs.  This was
   why prior hand-generated arithmetic produced the right destination while apparently destroying
   its sources.
4. A directly preceding `device_load` may feed either physical source without a float-style route
   change.  The same fixed recipe works after zero or one intervening instruction in the tested
   cases.

## Bounded null observations, not unused bits

The 32-way L1 hardware sweep crossed `opmode` bit 0, `srcB_ext` bit 0, `srcA` bit 2, and the two
release bits.  All eight settings of the first three controls produced the same arithmetic and
retention truth table when the sources came from `mov_imm`.  Their roles remain unknown; the result
only proves that R1's conservative fixed values work in this envelope.  They may encode provenance,
cache, width, or another condition absent from this carrier.

## Exact claim boundary

Proven here: 32-bit register-register add/subtract, modulo 2^32; registers r0..r23 as sources and
destinations; `mov_imm`, earlier-`iadd2`, and `device_load` operand provenance; source release,
aliases, immediate consumers, and 64-op chains.

Not claimed here: inline-immediate mode; signed overflow flags or carry/borrow outputs; 8/16/64-bit
forms; registers r24..r95; uniform sources; every value of the fixed fields; or any other integer
instruction.  A backend may use this recipe now, but it must keep values live conservatively with
`opc_tail=0x11` until its allocator has true last-use information.

