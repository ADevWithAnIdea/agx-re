# EXP-0236 AMENDMENT-01 — freeze full materialized-`falu3` confirmation

Frozen after both sparse discovery runs and before any formal dispatch. Repository base:
`e4bb77ff`.

## Sparse result

`g17p_e0236_discovery01` and `g17p_e0236_discovery02` each dispatched eight slot probes plus the
same 79 positive cases and two controls in opposite orders. Both completed with 89 `OK` statuses,
zero faults, zero hangs, and identical instruction bytes and complete observations case-for-case.
Both wrong-oracle controls fired.

After each load result was consumed by an accepting store, all three retained FMA source roles
read r0..r63 directly. This includes every retested r16..r23 point that produced mixed results in
EXP-0224 without an explicit first-handoff consumer. Encoded r64..r127 read r`(R & 63)`; physical
r64..r95 remained intact. Every destination nibble r0..r15 worked. All sources were retained.

The immutable work-only evidence hashes are:

```text
c6395bab223e3807e13b25337b26282df9b78217fc962273035881f28e6cb36a  discovery01/sweep.jsonl
7914296de15c590c5dd9d43bb357262316ee42b0dd09593cd03a23cb70739bdf  discovery01/05_run_manifest.json
e7663fdbb7dbcd302f2cccd72f131c177c17d639d84d0a7c123da95725477d04  discovery02/sweep.jsonl
7225cf3d12dd09567657318d991394c33bc57f99fc9fa5a17f681f2dccafe983  discovery02/05_run_manifest.json
```

Discovery files remain work-only and are not formal evidence.

## Frozen model

In EXP-0224's canonical eight-byte retained-source FP32 FMA, all three source descriptors have the
same materialized-GPR reach:

- encoded R=0..63 directly reads physical r0..r63;
- encoded R=64..127 aliases physical r0..r63 respectively;
- physical r64..r95 cannot be directly named by these fields;
- every source remains unchanged;
- the four-bit destination writes exactly r0..r15.

This model intentionally does not absorb EXP-0224's unresolved adjacent-load behavior. A pending
load result and an ordinary materialized GPR are different input-state classes. The former belongs
to the scoreboard protocol; the latter is the register-access result confirmed here.

## Frozen formal matrix

Each formal run contains all encoded R=0..127 for source A, B, and C (384 cases), all 16
destination nibbles, two wrong-oracle controls, and eight slot probes: 410 dispatches total. Each
source load is first handed to an accepting store and its exact bits are checked. Distinct finite
binary32 values and complete pre/post observations distinguish direct, modulo-16, modulo-32,
modulo-64, and physical-high models where their register numbers differ.

Run in canonical order as `g17p_e0236_run01` and reverse order as `g17p_e0236_run02`. Any fault,
hang, recovery, foreign runner, byte disagreement, complete-state mismatch, donor/carrier field,
source mutation, or failed control rejects confirmation. Device unresponsiveness requires an
immediate stop without recovery or reboot.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
