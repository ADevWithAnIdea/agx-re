# EXP-0049 results: M4 command-link structural controls

## Verdict

**PARTIAL. P0.5 remains open.** The unchanged public-Metal controls reproduce
EXP-0043's direct CDM 732/733 and alternating-state VDM 328/329 first known-link
boundaries twice, with fresh boundary repetitions inside each run. Compute
encoder-per-dispatch and seven client padding allocations leave the complete
tested CDM source/target command bytes unchanged. The same padding leaves the
tested alternating-state VDM source/target bytes unchanged.

Changed command/state shapes do not retain a safely identifiable first link in
the four-VA allowlist. Indirect compute, stable graphics state, and one draw per
pass all hit the frozen stop condition. Their workloads complete correctly, but
the experiment does not inspect or infer their alternate continuation targets.

This is `DATA-TRACE-VALIDATED` for the repeated direct/state-heavy boundaries
and tested invariance. Link semantics remain `STRUCTURAL`; no link was mutated,
replayed, or proved hardware-consumed. All findings are local M4/G16G only and
do not validate A18 Pro/G17P.

## Direct observations

### Process integrity

Across two main runs and two refinement runs, all **226** fresh authored GPU
processes:

- exited zero without a process timeout;
- reported Metal command-buffer status 4 and no error;
- matched the harness-computed final compute or render readback; and
- captured only exact preclassified command-BO mappings.

The nonempty `failures.json` files record expected strict-analysis stop
conditions, not GPU/process failures. There was no device loss or reboot.

### Repeated known-link boundaries

| Variant | Last count without known link | First count with exact known link | Link offset | Repetition |
| --- | ---: | ---: | ---: | --- |
| CDM direct | 732 | 733 | `0x7dd0` | identical across both main runs and both fresh boundary pairs per run |
| CDM encoder per dispatch | 732 | 733 | `0x7dd0` | same |
| CDM direct + pad7 | 732 | 733 | `0x7dd0` | same |
| VDM state every draw | 328 | 329 | `0x7b18` | same |
| VDM state every draw + pad7 | 328 | 329 | `0x7b18` | same |

The exact pairs remain:

- CDM: `0x20000100 0x00158000`, with independently allowlisted target BO
  `0x10000158000`;
- VDM: `0x80000000 0x00088000`, with independently allowlisted target BO
  `0x88000`.

At the first linked count, all three CDM variants have identical complete
source SHA-256
`a1e46bd5c7bb9ef122f232c4a7d100d3ae557e29d4b06b14f5acb88c2350eeea`
and target SHA-256
`50439db3397f622cd2cc6f4b5f19112915af6d7fe90bb9da8089544d5b4761e7`.
The two VDM variants likewise share source SHA-256
`e2afe5eae65cbe0251e729334c5fc2a227a8a1bc050f5a4663c413755b351bf1`
and target SHA-256
`8c2da0b2f5f6d994d2c0d10d058d7b1c4fb32d84270d14c7a72a9fbb304d4fb5`.

Therefore the long compute-encoder boundaries are coalesced at this command
level, extending EXP-0043's two-dispatch observation to the rollover boundary.

### Controlled client allocation movement

Seven authored `0x3000` allocations changed client resource addresses:

| resource | unpadded | padded |
| --- | ---: | ---: |
| compute output | `0x10000030200` | `0x1000002d200` |
| vertex buffer | `0x10000030300` | `0x1000002d300` |
| authored indirect buffer | `0x10000030900` | `0x1000002d900` |

The command BOs, first known-link threshold, link offset, link words, and known
target remained byte-identical for the matched direct/state-heavy variants.
This is a bounded allocator perturbation, not a general relocation proof.

## Bounded structural stops

### Indirect CDM

In both refinements, counts through 256 completed with no captured known target.
At count 512 the independently allowlisted `0x10000158000` BO was allocated,
but the exact EXP-0043 pair was absent from `0x100000b8000`. The same mismatch
occurred at the main count-2048 control.

The allocation alone is not promoted to a link. The first rollover threshold,
link opcode/address packing, and destination for this indirect shape are
`UNKNOWN`. No new target was located or inspected.

### Stable-state VDM

At count 1024, the preclassified `0x18000` source contains 1024 recognized
direct-draw signature matches in authored `3,6,...` order. At count 2048, it
contains 1958 such matches while the command completes with the correct final
readback. This is consistent with continuation or another record shape outside
the recognized source sequence, but does not prove either: the final pixel does
not establish that every earlier authored draw executed. No allowlisted target
is present at 2048 and no other BO is inspected. At count 4096, the known
`0x88000` BO is present and contains 174 recognized direct-draw signatures, but
the exact EXP-0043 pair is absent from `0x18000`.

Stable state increases the observed high-count source occupancy from the
state-every-draw shape's 328 to 1958 recognized signatures. The exact first
rollover count and destination remain `UNKNOWN` because the required boundary
pair was not captured within the allowlist.

### One draw per render pass

By count 64 the known `0x88000` BO is allocated, but `0x18000` still contains
64 recognized direct-draw signatures in authored order, `0x88000` contains no
matching signature, and the exact link pair is absent. At the main 4096-draw
control, the source contains 196 recognized signatures and the known target
contains none. The remaining API calls are not represented by that recognized
signature in either inspected BO; their encoding, location, and execution are
not established.

Pass-per-draw therefore reduces the observed high-count source occupancy below the
state-every-draw shape's 328, but neither the target allocation at count 64 nor
the 196-packet high-count occupancy establishes an exact rollover threshold.
The threshold and destination remain `UNKNOWN`.

## Hypothesis outcomes

- **H1 supported:** the direct CDM 732/733 boundary and exact pair reproduce.
- **H2 bounded negative:** the indirect shape's observed allowlisted structure
  lacks the exact known source pair; its continuation topology, first link,
  and destination remain unknown.
- **H3 supported for this workload:** ending every compute encoder leaves the
  complete boundary command bytes identical to one encoder.
- **H4 directionally supported, exact thresholds incomplete:** recognized
  source-signature occupancy orders stable state (1958) above
  state-every-draw (328) above pass-per-draw (196), but only the middle shape
  has an exact allowed boundary. This count does not prove the location or
  execution of unmatched API calls.
- **H5 supported only for matched direct/state-heavy variants:** pad7 changes
  authored client VAs without changing tested command link bytes/destinations.

## Remaining gaps and safe implementation stance

- Whether the observed links are hardware-consumed remains unknown.
- Indirect-CDM, stable-state VDM, and pass-boundary VDM link formats/targets are
  not identified. Do not synthesize them from these captures.
- No general segment-capacity formula, arbitrary relocation rule, call/return,
  barrier, cache-control, nested-chain, malformed-link, or recovery behavior is
  established.
- No independent command packer or Linux producer/consumer test was run.
- No A18 Pro/G17P result exists; transfer remains unvalidated.
- Formal raw records did not retain size/SHA-256 identity for the rebuilt
  authored interposer and probe executables. Their source hashes, build commands,
  invocation paths, and live outputs are retained; no binary identity is
  reconstructed after the fact.

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: authored MSL and buffers; public Metal status/readback; exact
  four-VA EXP-0043-preclassified CDM/VDM command mappings only
Apple binary introspection: NONE
Apple auxiliary/helper program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Executing command-memory mutation or replay: NONE
Raw repetitions: two main + two refinements, 226 fresh GPU processes
Evidence: raw/, analysis/summary.json, analysis/report.txt, manifest.json
```
