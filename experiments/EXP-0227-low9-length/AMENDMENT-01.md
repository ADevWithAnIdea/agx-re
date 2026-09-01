# EXP-0227 Amendment 01 — freeze formal confirmation

Frozen after the disclosed pilot and before either formal dispatch. The original
`PRE_REGISTRATION.md` and pilot are unchanged.

## Pilot result that authorizes confirmation

`g17p_e0227_pilot01` completed 13 dispatches (eight slot probes plus five
length cases) with zero hangs, faults, restarts, foreign retries, stray writes,
or recovery-count change. All three disputed-prefix causal cases executed all
four staircase markers and the +12 resynchronization marker, uniquely selecting
length 4 among `{4,6,8,10,12}`. The previously enumerated `0x21` compact form
did the same. The identical program with the deliberately wrong r0 host model
was rejected as `wrong_value`, establishing detection power.

Exact dispatched candidate prefixes:

```text
H1 immediate and destination controls: 09 01 20 05
P1 known compact control:               09 01 21 05
```

This remains pilot evidence because it is one canonical-order run with one
quiet-process sample.

## Formal protocol

Run exactly twice:

| run | order | seed |
|---|---|---:|
| `g17p_e0227_run01` | canonical | 0 |
| `g17p_e0227_run02` | reverse | 1 |

Each capture uses the unchanged `run227.py`, frozen input hashes, slot map
`out=0,mem=1,imem=2`, 20-second dispatch timeout, and hang budget 1. A quiet
sampler begins five seconds before dispatch and remains alive for five seconds
afterward at 0.25-second requested intervals. Pre/post hardware snapshots and
all harness/dependency hashes are copied into the append-only run directory.

## Formal acceptance gate

`analysis/formal227.py` is frozen before the runs. It must establish:

1. five length cases per run, all `status=OK`, no restart/foreign retry, sentinel
   intact, no stray writes, Gate A clean, and zero donor fields;
2. each H1/P1 case uniquely infers length `[4]`, all expected markers and the
   +12 marker execute, and the H1/P1 complete-state host comparisons match;
3. the wrong-model control mismatches as preregistered and reports
   `control_detected=true`;
4. the non-slot case order is exactly reversed between runs;
5. per-case generated-program hashes, complete output-buffer hashes, outcomes,
   and observed marker values agree across runs;
6. slot mapping reproduces in both runs;
7. every quiet sample has zero foreign runner, both pre/post snapshots have
   `busy_count=0`, recovery-count delta is zero, and at least two quiet samples
   were captured per run;
8. the run metadata identifies G17P / Apple A18 Pro.

Any device unresponsiveness invokes the plan's hard stop: pause, preserve the
last raw record, mark the goal blocked, and perform no recovery or reboot.

Passing this gate promotes **only** this fact to hardware-validated:

> On tested G17P generated streams, low-nibble-9 byte+2 low-three-bit selector
> 0 at the `09 01 20 05` point is a four-byte instruction boundary.

It does not prove all selector-0/1 values, other low-nibble-9 byte0 high
nibbles, all alignments, or the full Step 1 grammar.
