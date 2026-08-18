# EXP-0055 results — bounded M4 scissor/depth-bias state correlations

## Verdict

**PARTIAL; P0.3 remains OPEN.** Two exact repetitions show one stable
fixed-function-state correlation: every tested nonzero public constant or slope
depth-bias input changes `0x58000 + 0x36` from `0x00` to `0x02`. Sign, magnitude,
constant versus slope, and clamp value are not distinguished there. Therefore
`0x02` is only a nonzero-depth-bias enable candidate for this public M4 path.

Every scissor coordinate/extent change, both multi-scissor slot-x changes, and
both clamp-only changes produce the expected different public readback while
the complete `0x58000` and `0x68000` allowed payloads remain byte-identical within
their respective pairs. This is a strong bounded negative for these two captures,
not evidence that the private arrays or values do not exist elsewhere.

No result establishes hardware consumption, `isp_scissor_base`,
`isp_dbias_base`, array stride/count, integer-depth-bias mode, native command
synthesis, Linux UAPI mapping, kernel/firmware ownership, or A18 Pro behavior.

## Direct process observations

Both runs used Apple M4 / Mac16,10, arm64, macOS 26.6.2 build 25G82. Each run:

- executed exactly 19 cases under `plain` and `pad64k` schedules;
- launched 38 fresh processes, for 76 total across both runs;
- completed every public command with status 4 and no error;
- retained full 1088-byte guarded color images and, for depth cases, full
  1088-byte guarded depth images;
- reported zero color/depth/padding guard errors;
- captured exactly one `0x8000` pair at `0x58000` and one `0x88e0` pair at
  `0x68000` for every process; and
- passed exact path, metadata, handle, occurrence, trace, size, cap, and role
  preflight before any payload byte was opened or hashed.

All 76 public stdout records reproduce byte-exactly. The experiment retains 152
allowed `.bin` payloads total—76 per run—and all 76 corresponding cross-run
payload comparisons are byte-exact. Both allocation schedules also retain the prior
`0x58000 + 0x14 = 0x19` drawn Clear/Store and `+0x53 = 0x00` no-blend role
anchors for the scissor baseline.

There are no live-run failures, timeouts, GPU faults, device losses, retries, or
reboots. `failures.jsonl` is intentionally zero bytes in both runs. Two executed
final-verifier failures plus the independent pre-commit audit failures and their
mechanical corrections are preserved in `analysis/failures.md`; none changed raw
evidence. The current verifier reconstructs the exact pre-hardening runner bytes
and binds their SHA-256, while the current tools fail closed on unknown trace
records and on any artifact outside the global allowlist.

## Public readback controls

The seven single-scissor results exactly model half-open integer rectangles:

| case | rectangle | drawn pixels |
| --- | --- | ---: |
| base | `(2,3,7,5)` | 35 |
| x | `(4,3,7,5)` | 35 |
| y | `(2,5,7,5)` | 35 |
| width | `(2,3,9,5)` | 45 |
| height | `(2,3,7,8)` | 56 |
| empty width | `(2,3,0,5)` | 0 |
| empty height | `(2,3,7,0)` | 0 |

The multi baseline writes 30 slot-0 pixels and 40 slot-1 pixels. Changing only
slot 0 x or slot 1 x moves only that slot's exact pixel map and preserves both
counts. No cross-slot color appears.

Every one-draw depth result is finite. Selected observed ranges are:

| case | minimum | maximum |
| --- | ---: | ---: |
| zero | `0.211718723` | `0.563281238` |
| constant -1 | `0.211718664` | `0.563281178` |
| constant +1 | `0.211718783` | `0.563281298` |
| slope -1 | `0.192968711` | `0.544531226` |
| slope +1 | `0.230468705` | `0.582031190` |
| large -100000 | `0.205758259` | `0.557320774` |
| clamp -0.001 | `0.210718706` | `0.562281191` |
| large +100000 | `0.217679188` | `0.569241703` |
| clamp +0.001 | `0.212718710` | `0.564281225` |

Every negative input moves all stored depths below the zero case; every positive
input moves them above. Both clamps strictly reduce every pixel's absolute
displacement versus the same-sign magnitude-100000 control. These checks qualify
the state comparisons; EXP-0054 remains the primary behavioral evidence.

## Allowed-state differentials

### Nonzero depth-bias enable candidate

The following one-factor comparisons all change exactly one allowed byte and no
other byte in either BO:

| comparison from zero | `0x58000 + 0x36` | `0x68000` |
| --- | --- | --- |
| constant `-1` | `00 -> 02` | identical |
| constant `+1` | `00 -> 02` | identical |
| slope `-1` | `00 -> 02` | identical |
| slope `+1` | `00 -> 02` | identical |
| constant `-100000` | `00 -> 02` | identical |
| constant `+100000` | `00 -> 02` | identical |

The offset and exact before/after byte reproduce in both runs and both allocation
schedules. It distinguishes zero from nonzero tested bias state, but does not
distinguish constant from slope, sign, or magnitude. It is therefore a
`DATA-TRACE-VALIDATED` correlation candidate, not a complete field encoding or
proof that hardware directly consumes this byte.

No aligned qualified changed word contains the exact authored binary32 bits for
constant, slope, or clamp. No integer-mode selector was tested or identified.

### Clamp values are outside this observed boundary

Each sign-matched clamp case changes the full authored depth image relative to
its same-sign unclamped large-bias control. Nevertheless both complete allowed
BOs are byte-identical for each clamp-only pair in all four observations. Thus
neither allowed snapshot exposes a reproducible clamp value or clamp-enable
differential for these cases.

This does not mean clamping is firmware-owned, absent, or stored at any particular
unobserved address. The safe result is only that the value is not distinguishable
inside these exact post-completion captures.

### Scissor and multiple-scissor values are not located

All six single-scissor changes and both multi-slot changes alter the complete
authored color image as predicted. For each corresponding pair, every byte of
both allowed payloads is identical across runs and schedules. H1 and H2's expected
allowed-state differentials are therefore falsified within this boundary.

No inference is made about an unobserved scissor array, its base, its stride, or
empty-entry representation. The experiment deliberately did not scan for another
mapping or follow a value from these captures.

### Allocation perturbation

The pad64k schedule preserves all qualifying semantic pair differentials. It also
causes stable schedule-only opaque changes in `0x58000`: `+0x15` changes
`0x4a -> 0x50` for every case, and the multi cases additionally change `+0x89`
the same way. These exact lists repeat across both runs and are retained in
`analysis/summary.json`.

Those bytes are only allocation-schedule correlations. They are not interpreted
as addresses or relocations, and their values are never dereferenced or followed.
The `0x68000` plain/pad captures are identical within every case.

## Hypothesis outcomes

- **H1 falsified with bounded negative:** no single-scissor component delta in
  either allowed mapping despite exact changed readback.
- **H2 falsified with bounded negative:** no distinguishable multi-slot delta in
  either allowed mapping despite exact changed readback.
- **H3 partial:** nonzero constant/slope state correlates with one enable-candidate
  byte; exact values, sign, term selection, and clamp are not located.
- **H4 supported:** exact state VAs, sizes, occurrences, role anchors, and semantic
  pair differentials survive the controlled authored allocation schedule.
- **H5 supported:** all complete public readbacks and guards match the frozen
  behavioral model in both repetitions and schedules.

## Remaining gaps and safe boundary

P0.3 remains OPEN. The first `0x8000` bytes at `0x58000` and first `0x88e0` bytes
at `0x68000` do not expose the tested scissor/clamp values. The location and
format of private scissor and depth-bias arrays, base/stride/count rules, empty
entries, integer-depth bias, and Linux marshaling remain UNKNOWN. A18 Pro was
not tested, and no M4 observation is transferred to it.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + DATA-TRACE + OWN-SHADER source
Inputs inspected: authored Objective-C/MSL and readbacks; public Metal status;
  boundary metadata; exact preclassified M4 state BOs 0x58000 and 0x68000 only
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command BO contents inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Generic BO/memory scan: NONE
Mutation/splice/replay: NONE
Target: M4/G16G-class only; A18 Pro untested
Evidence: raw/m4_20260817_run01, raw/m4_20260817_run02, analysis/, manifest.json
```
