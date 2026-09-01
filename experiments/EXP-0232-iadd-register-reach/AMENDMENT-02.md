# EXP-0232 Amendment 02 — G17P r95/r96 confirmation

Frozen after the immutable Amendment-01 run refuted its primary model and before any `H2` dispatch.

## Result that forces this amendment

`raw/g17p_e0232_boundary01` observed:

- D94 exact before and after every hazard;
- **D95 exact**, refuting the M4-derived expected-fault model;
- D96 and D127 contained command-buffer faults;
- zero hangs, with the device responsive and later controls exact.

The Amendment-01 verifier remains failed. It must not be rewritten to accept the new result.

## New frozen target model and confirmation

On G17P, the canonical b32 `iadd2` destination set is r0..r95 inclusive. r95 is the maximum valid
physical GPR, r96 is the first invalid destination, and larger encodable destinations remain
invalid rather than wrapping.

Confirm in two measured-quiet runs in canonical and reverse order:

```text
D95 exact control
D96 expected contained fault
D95 exact recovery control
D127 expected contained fault
D95 exact recovery control
```

The two runs must have identical actual instruction bytes and observations for every exact case,
contained faults at D96/D127, no hang, no foreign runner, and exact controls after each fault. The
automatic recovery-count delta is recorded rather than required to be zero because two deliberate
faults are part of each run. No manual recovery or reboot is authorized.

If SSH or the device becomes unresponsive, immediately stop and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
