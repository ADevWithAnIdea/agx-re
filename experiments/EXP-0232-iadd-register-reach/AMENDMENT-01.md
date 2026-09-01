# EXP-0232 Amendment 01 — G17P destination first-invalid boundary

Frozen before any `H` arm dispatch. The two main formal captures are complete and immutable.

## Correction

`PRE_REGISTRATION.md` incorrectly calls the existing r95 destination fault evidence “prior G17P
hardware evidence.” The cited EXP-0139/EXP-0146 fault map is **M4/G16G**, not G17P. EXP-0232's
new dense G17P runs directly prove r0..r94 valid, but cross-target evidence cannot close r95 on the
target. This amendment corrects the provenance error; it does not reinterpret the completed runs.

## Added target-boundary arm

Run this exact sequence once under a measured-quiet window, with a fresh complete program for every
entry:

```text
D94 exact baseline
D95 expected contained fault
D94 exact recovery baseline
D96 expected contained fault
D94 exact recovery baseline
D127 expected contained fault
D94 exact recovery baseline
```

D95 is the first candidate invalid destination, D96 is its immediate successor, and D127 is the
largest structurally encodable destination. A hazard case passes only on a contained command-buffer
fault with no hang. Every D94 neighbour must execute exact complete state. Requested/actual bytes,
framing, donor ledger, target process samples, and recovery counters are retained. Automatic driver
handling of a contained fault is recorded; no manual recovery or reboot is authorized.

If SSH or the device becomes unresponsive, immediately stop, preserve the last append-only record,
perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
