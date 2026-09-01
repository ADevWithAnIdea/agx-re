# AMENDMENT-09 — integer compare map and float-discriminator correction

Frozen after `g17p_e0223_mode_valid01`, before any F1 dispatch or further Metal inspection.

## Integer compiler result

With R1's register sources and `flags=0xc0`, use:

| NIR predicate | `cmp_mode` | `cc` | selection |
|---|---:|---:|---|
| unsigned A > B | `0x02` | `0x04` | T : F |
| unsigned A < B | `0x02` | `0x05` | T : F |
| signed A > B | `0x02` | `0x06` | T : F |
| signed A < B | `0x02` | `0x07` | T : F |
| A == B | `0x06` | `0x07` | T : F |
| A != B | `0x06` | `0x07` | F : T |

LE/GE are generated with the opposite strict comparison and swapped T/F.  C1 proved all four
strict relations against positive less/greater/equal and signed-vs-unsigned-discriminating -1/+1
inputs.  C2B proved equality over the same set.

Bits 3 and 4 of both primary mode values alias arithmetically in this carrier; keep them clear.
`cc` values with
bit 5 or bit 6 set leave D unchanged for all five integer relations.  Other `cc` low forms and the
bit-7 forms have measured vectors but are not needed by this compiler recipe and remain unnamed.

## `cmp_mode` finite structure

The stopped C2 capture reaches every byte value: exactly `(mode & 3) == 2` executes; every other
value faults on 2..9 distinct relations.  C2B runs all nine relations for all 64 legal values.

Within the legal set:

- bit 2 clear uses the relational `cc`; bit 2 set performs equality at `cc=7`;
- bits 3/4 are aliases in this carrier;
- high source-class 000 selects the GPR T operand;
- high source-class 100 selects that GPR and **releases/zeroes T after the read**, regardless of
  which side the predicate selects;
- class 001 produces `0x00000100` when true for the fixed T descriptor;
- classes 010, 011, 101, 110, and 111 produce zero when true here.

Those high bits are real source-class and lifecycle controls, not unused space.  Their general
descriptor/value maps remain a capability-discovery follow-up.  A compiler needing a retained GPR
true source uses 0x02/0x06; adding bit 7 is valid only at T's true last use.  The false-source
release control has not yet been localized.

## Correction: C2 did not prove float semantics

C2's float inputs were positive 1.0/2.0, equality, and NaN.  Positive IEEE-754 bit patterns order
the same way as signed positive integers, so the apparent LT vector at mode 0x02 is equally explained
by the already-proven signed-integer comparison.  NaN versus 1.0 is false under both tested models.
Therefore **no float compare claim is made from C2**.

## F1: second generated float attempt

Before consulting another compiler output, sweep all 32 finite `opsel` values at the conservative
mode points:

1. `cmp_mode=0x02`, `cc=2` and `cc=3`, across +1/+2, -2/-1, -1/-2, -0/+0, and NaN/+1;
2. `cmp_mode=0x06`, `cc=0`, across float equal, unequal, signed-zero equality, and NaN.

The negative-pair and signed-zero cases distinguish IEEE float order/equality from signed integer
bit-pattern order.  Record full u32 outputs, not just the low byte: C2 showed alternate source
classes can return 0x100 while sharing a low byte with zero.

F1 is the second independent generated float-family attempt after C2's exhaustive mode sweep.  If
no F1 setting implements the required float vectors, the multiple-failure threshold is satisfied
for a fresh authored-MSL float nomination; compiler bytes may nominate fields but may not be copied.
