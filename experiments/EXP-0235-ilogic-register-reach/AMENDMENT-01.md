# EXP-0235 AMENDMENT-01 — freeze the full `ilogic` descriptor confirmation

Frozen after both sparse discovery runs and before any formal dispatch. Repository base:
`c19af0bb`.

## Sparse result

`g17p_e0235_discovery01` and `g17p_e0235_discovery02` each dispatched eight slot probes plus the
same 48 positive cases and two controls in opposite orders. Both completed with 58 `OK` statuses,
zero faults, zero hangs, and identical instruction bytes and complete observations for every case.
Both wrong-oracle controls fired.

For both semantic XOR sources, encoded r0..r63 read and released the exact physical register.
Encoded r64..r127 read and released r`(R & 63)`; independently seeded physical r64..r95 remained
unchanged. All destination nibbles r0..r15 wrote the requested register after both sources were
released. The narrow pre-dispatch tokenizer hypothesis framed every generated instruction as one
ten-byte `ilogic`, including the `0xe1` source descriptor that motivated it.

The immutable work-only evidence hashes are:

```text
c339d717cb88e8b6a60ac75a3231a6e09b04f538af859c0172bc2bbd4c2706b3  discovery01/sweep.jsonl
396e58d3e2eff9a794fc2e56373192f308be422e299e8a257a04a2f25ca6ea6d  discovery01/05_run_manifest.json
214f4e4c06cf0dbc4b367c6dc5b26e7d09761c7e8fb1d6593c784af3ca42c827  discovery02/sweep.jsonl
c74b31e752ddfa193015dc8f90d2b563761e2d16d2011b1a00dcd2bd2075ca99  discovery02/05_run_manifest.json
```

Discovery files remain work-only and are not formal evidence.

## Frozen model

In this canonical ten-byte 32-bit two-input LUT form, each source byte has a seven-bit encoded
register payload plus the required register-class/parity bit. The effective GPR is `R & 63`:

- encoded R=0..63 directly reads and releases physical r0..r63;
- encoded R=64..127 aliases and releases physical r0..r63 respectively;
- an aliased high descriptor does not read or release physical r64..r95;
- the complete one-byte descriptor namespace has no beyond-range code in this form;
- the four-bit destination writes exactly r0..r15 and cannot name r16..r95.

The release claims are specific to XOR, which semantically depends upon both sources. EXP-0226
separately establishes that other LUT functions release exactly the sources they depend upon.

## Frozen formal matrix

Each formal run contains all encoded R=0..127 for semantic A and semantic B (256 cases), all 16
destination nibbles, two wrong-oracle controls, and eight slot probes: 282 dispatches total. Direct
cases predict the exact physical source; high descriptors predict r`(R & 63)`. Distinct codewords
and pre/post observations distinguish modulo-16, modulo-32, modulo-64, and physical-high models
where their register numbers differ, including the release target.

Run once in canonical order as `g17p_e0235_run01` and once in reverse order as
`g17p_e0235_run02`. Any fault, hang, recovery, foreign runner, byte disagreement, complete-state
mismatch, donor/carrier field, or failure of either control rejects confirmation. Device
unresponsiveness requires an immediate stop without recovery or reboot.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
