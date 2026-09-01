# EXP-0230 Amendment 02 — independently materialize r92–r95

Frozen after the red run01/run02 audit and before run03/run04.

## Exact gap

The original formal pair leaves exactly 16 main cases semantically undecidable: S=92..95 × two
source halves × two index plans. Their high-source seed store usually read zero after a 95-load
wave, so the frozen Gate B rule excludes them. The move destination still matched `mod64` in both
runs, but this amendment does not use that as closure.

## Successor carrier

For each S=92..95 case, generate only three loaded values:

1. destination r2 receives `codeword(2)`;
2. the competing modulo-64 register r(S-64), r28..r31, receives its own distinct codeword;
3. high source rS receives `codeword(S)`.

Immediately after each load, a generated `device_store` with the proven load-forwarding mode
(`addr_mode=0x56`) writes the value to an independent pre-state location. EXP-0220 established that
this mode forwards the live result and keeps it in the destination register. Four independent
`mov_imm(index,0)` instructions then separate the final materialization from `n3_mov`.

## Frozen hypotheses and coverage

- **MOD64 (primary, from EXP-0230 partial):** S92..95 read r28..r31.
- **DIRECT96:** S92..95 read their distinct high-register values.
- **ZERO:** the upper source class reads zero.

Coverage is dense over S=92..95 × source half low/high × index plans r14/r15: 16 main programs,
plus one wrong-source oracle control per plan. The instruction destination is r2 low half and the
source is retained. Complete relevant observations are destination before/after, high source
before/after, modulo-64 rival before/after, low-bank snapshot, and independent pre/post sentinels.

## Done gate

Both canonical and reverse runs must have:

- exact high-source and lower-rival seed witnesses in every main case;
- one unique zero-mismatch semantic model across all 16 cases;
- both wrong-oracle controls firing;
- zero Gate-A, donor, descriptor-alias, cross-run byte, state, sentinel, fault, hang, victim,
  foreign-runner, and recovery-count failures;
- all eight descriptor byte values 184..191 represented under each index plan.

This amendment changes no run01/run02 raw data or interpretation. It is a narrow missing-gate rerun,
not a replacement of EXP-0230.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
