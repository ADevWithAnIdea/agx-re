# EXP-0236 pre-registration — materialized canonical `falu3` register reach

Frozen before the first EXP-0236 hardware dispatch. Repository base: `79e961ac`.

## Question

What exact physical GPR sets can each source role and the destination of EXP-0224's canonical
eight-byte retained-source FP32 FMA directly access on G17P, once every source has completed its
first load-result handoff? What does every finite source descriptor tier do?

EXP-0224 proved the FMA semantics and r0..r15 envelope, but its r16..r23 discovery seeded sources
with unresolved `device_load` results and observed a mixed pattern. That experiment correctly
refused to turn the mixture into a register rule. EXP-0236 separates the variables: after each
generated load, an accepting generated store consumes the pending result, verifies its exact bits,
and retains the materialized data GPR. Only then does `falu3` read it. This experiment is about
ordinary/materialized GPR reach, not pending-producer acceptance.

## Frozen sparse hypothesis

For all three canonical source descriptors, encoded R=0..63 directly reads physical r0..r63 and
encoded R=64..127 aliases r0..r63 respectively. All three sources remain unchanged under the
retained recipe. The destination nibble directly writes exactly r0..r15.

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

## Sparse matrix and detection

Each source role tests encoded R={0,15,16,18,19,20,23,24,31,32,47,48,63,64,79,80,95,96,111,
112,127}. The matrix deliberately retests the EXP-0224 mixed r16..r23 region. The destination
tests r0..r15 densely. Two wrong-oracle controls must fire. Each run therefore contains 79 positive
cases, two controls, and eight slot probes: 89 dispatches.

Every physical target and modulo-16/32/64 candidate receives a distinct, exact finite binary32
value where the register numbers differ. Pre/post observations prove that all three sources are
retained. The host oracle predicts the fused result from the effective candidate source; a correct
destination alone cannot hide a wrong source-selection model. Run twice in opposite orders.

Sparse runs are discovery evidence only. If they agree, freeze a separate amendment specifying
the dense direct range, complete source-byte namespaces, aliases/holes/faults, and formal run IDs
before promotion captures.

## Gates and stop rule

- Gate A: exactly one generated eight-byte `falu3` body with exact requested/actual fields and no
  framing alias.
- Gate B/C: distinct source candidates, complete predicted output state, retained-source pre/post
  observations, and both refuters must discriminate the model.
- Gate D: `COPIED=0`, `CARRIER=0`.
- Gate E: quiet opposite-order G17P runs with no unexplained fault, hang, recovery, or restart.

Every dispatch has a 20-second watchdog and zero-hang budget. If SSH or the device becomes
unresponsive, stop immediately, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
