# EXP-0231 results — memory-mediated register transfer

**Verdict: PASS on G17P.** A fully generated adjacent `device_store rS -> mem` / `device_load
mem -> rD` sequence transfers a 32-bit value exactly across every tested low/middle/high register
direction, including physical r64..r95. No intervening instruction is required in this carrier.

Pre-registration commit: `bb97fcf1`. Formal runs:

- `raw/g17p_e0231_run01` — canonical order, 154 dispatches.
- `raw/g17p_e0231_run02` — reverse order, 154 dispatches.

Each run contains 8 slot probes, 144 main cases, and 2 negative controls. There were zero faults,
hangs, victims, runner restarts, or foreign retries.

## 1. Semantic result

All **144/144 main cases per run** matched complete host state, for **288/288** across the formal
pair. The matrix was:

- sources `{r0,r11,r16,r63,r64,r95}`;
- destinations `{r1,r10,r17,r62,r65,r94}`;
- store-to-load gaps `{0,1,4,16}`.

That covers all nine low/middle/high direction classes at every gap, with four independent
source/destination pairs in each direction/gap cell. In particular, all 36 gap-zero cases passed
in each run. The actual body at gap zero was exactly two adjacent generated instructions:

```text
device_store rS -> bound device scratch
device_load  bound device scratch -> rD
```

The scratch word and both post-load destination observations equalled the source codeword in every
case. The exact model was the unique zero-mismatch model:

| frozen model | mismatching main cases |
|---|---:|
| exact | **0 / 144** |
| stale destination | 144 / 144 |
| zero | 144 / 144 |
| source aliases modulo 64 | 48 / 144 |
| store absent / load old memory | 144 / 144 |

The 48 modulo-64 mismatches are exactly the cases with an upper-tier source. Low/middle cases
necessarily collide with exact under that model, so they are not misreported as independent
discriminators.

## 2. Lifecycle result

The sequence deliberately used nonzero index values that address the same byte by different
instruction-specific formulas:

```text
store: r14 = 4, idx_off = 199 -> byte 3200
load : r15 = 7, idx_off = 793 -> byte 3200
```

After the sequence, **r14 read 0 in 288/288 main observations** and **r15 read 7 in 288/288**.
Therefore the store consumes and releases its index register, while the load retains its index
register. The source itself remained unchanged in **288/288**, and the loaded destination remained
stable after its immediate forwarding observation in **288/288**.

The load result is still an in-flight producer: the immediately following store used the already
established `addr_mode=LOADFWD` acceptance path. EXP-0231 proves adjacent store→load memory
visibility; it does not erase the separate load→consumer publication rules.

## 3. Five gates

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Both runs have byte-identical program hashes and actual body ledgers case-for-case; 0 decode disagreements, 0 descriptor aliases, and every main/control body has the exact pre-registered store + fillers + load mnemonic sequence. |
| **B — detection** | **PASS.** All pre-source, destination-poison, retained-source, alias, index-lifecycle, scratch, and sentinel channels worked. `ctl_wrong_store` failed on exactly four scratch bytes and `ctl_wrong_load` failed on both four-byte destination observations in both runs. |
| **C — semantics** | **PASS.** 144/144 exact per run, exact is the unique zero-mismatch model, and 0 cases are semantically undecidable. |
| **D — generation** | **PASS.** Per run: `RULE=806096`, `FREE=19798`, `CARRIER=0`, `COPIED=0`, including unreachable generated padding. No required field or instruction byte came from compiler output. |
| **E — target/reproduction** | **PASS.** 28 quiet samples per run, 0 foreign processes/runners/compiler services, 0 recovery-count change, unchanged last-recovery timestamp, 0 hangs, and 0 runner restarts. |

Machine-readable gates: `analysis/formal_result.json` and `analysis/gate_e_result.json`.

## 4. What this closes, and what it does not

This is a compiler-usable, bit-preserving transfer fallback for values involving any GPR tier.
Together with EXP-0221/EXP-0230's dense endpoint rules, a backend can spill an r0..r95 value to a
bound scratch word and reload it into an r0..r95 destination. It is not evidence for a cheap direct
GPR move involving the upper tier, and it does not determine the scratch allocation capacity,
alignment envelope, first-invalid address, concurrent-lane behavior, or optimal scheduling policy.

No general scoreboard wait is required between the tested store and same-address load. This is a
statement about this device-memory dependency path, not a claim that all memory operations are
globally ordered or that arbitrary load consumers need no acceptance control.

## 5. Clean-room provenance

Clean-room provenance: OWN-SHADER + HW-PROBE.

The programs were assembled from documented project rules and executed through the public Metal
API on Apple A18 Pro / G17P. Apple binary introspection: **NONE**.
