# AMENDMENT-01 — freeze the retained-source FMA point

Frozen after the disclosed pre-freeze run `g17p_e0224_pilot01`, before any V2 dispatch.

The pilot executed 14 generated hypotheses after the eight S0 binding probes.  Gate A reported
zero requested/actual disagreements and zero whole-program aliases; Gate D reported no copied or
carrier-derived instruction fields; there were no faults or hangs.  The two deliberately wrong
host models both mismatched.

The four H3 cases were complete-state exact:

```text
dst=D
srcA=(A<<1)|1
op=0x06
srcB=(B<<1)|1
ctrl_len=0x01
srcC=C<<1
ctrl=0x02
srcmods=0xc0
```

This is the V2 retained-source candidate for FP32 `D = fma(A,B,C)`.

The pilot also isolated three post-read lifetime controls:

- changing `op` from `0x06` to `0x1e` zeroed A and B while preserving the arithmetic result;
- changing `ctrl_len` from `0x01` to `0x81` zeroed C while preserving the arithmetic result;
- when D aliases a released source, destination publication wins.

Therefore V2 models `op` bit 3 as release A, `op` bit 4 as release B, and `ctrl_len` bit 7 as
release C.  The arithmetic class remains `op & 7 == 6`.  Bit 5 of `op` is separately crossed in
V2 because older dense evidence found it neutral only in a bounded carrier; no global "unused"
claim is permitted.

## Frozen V2 promotion matrix

V2 contains:

- dense D=r0..r15;
- each source role A/B/C independently at r0..r23;
- destination and source aliases;
- the full A/B/C release truth table, including release/destination aliases;
- directly preceding load production in every source role and at gaps 0, 1, and 4;
- ordinary signed/zero cases and an FMA-vs-mul-then-add cancellation vector;
- 100 deterministic FMA DAGs of 2..64 operations;
- a wrong-C and a wrong-operation refuter.

Every case predicts the complete r0..r23 state and all three buffers.  Promotion requires two
quiet G17P captures in different orders, exact positives, firing refuters, no decoder/byte-ledger
errors, no donor fields, and no cross-run program or output differences.
