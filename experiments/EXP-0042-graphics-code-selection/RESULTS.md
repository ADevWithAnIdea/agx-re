# EXP-0042 results — M4 graphics pipeline selection

## Verdict

P0.2 and P0.7 are still **OPEN**, but two earlier interpretations are materially
corrected on M4/G16G:

1. graphics pipeline selection is not just an unselected positional walk; vertex and
   fragment stages have separable per-draw selectors; and
2. `0x58000+0x08` is not an FS byte size. It is a code-window-relative selector into a
   0x80-byte record immediately following the selected fragment code record.

The unchanged-UAPI-compatible interpretation is promising: the observed code BO is always
at the 4 GiB-aligned VA `0x10000000000`, and the FS selector is 32-bit and relative to that
window. Mapping that base exactly to Linux `usc_exec_base` is **INFERRED, not demonstrated**.
No Linux submission was made and no A18 Pro was tested in this experiment.

## Direct observations

### 1. Live switching works and is readback-distinguishable

All authoritative command buffers completed. A and B render stable full-target results:

| final FS | center BGRA | full-target FNV-1a |
|---|---|---|
| A / small / equal-a | `2914ebff` (A) or `2e1ae5ff` (matrix) | stable per harness |
| B / large / equal-b | `33cc0dff` (B) or `38c70fff` (matrix) | stable per harness |

`AB`, `ABAB`, and `BAAB` end with the B value; `BA`, `BABA`, and `ABBA` end with
the A value. The four-stage matrix reproduced identically on its second pass. Raw:
`raw/run_ab_p0/stdout.txt`, `raw/run_ba_p0/stdout.txt`, and
`raw/run_stage_equal/stdout.txt`.

### 2. Code-window base is stable under ordinary allocation perturbation

The live code BO was registered at `0x10000000000`, size `0x10000`, in all authoritative
runs. Seventeen preallocated client BOs moved the authored vertex buffer from
`0x10000018200` to `0x10000031a00`, but did not move or change the AB code BO:

| run | vertex buffer | code BO SHA-256 |
|---|---:|---|
| AB, no padding | `0x10000018200` | `893b8b46…eafe6a3` |
| AB, 17 BOs first | `0x10000031a00` | `893b8b46…eafe6a3` |

Changing only compile order to BA kept the base but changed record order and code-BO hash,
as expected. This proves stability for the tested allocator perturbation; it does not prove
the base is architecturally fixed for every process or queue.

### 3. Vertex selection uses a VDM bind token, not a code offset

When a VS is initially bound or actually changed, a VDM record contains this pair:

```text
record +0x1c: 0x00000500
record +0x20: vertex token
```

For AB creation order, A uses `0x40` and B uses `0xc0`. Reversing only creation order makes
B use `0x40` and A use `0xc0`. Sequences `ABAB` and `BABA` repeat the corresponding token at
every switch. The small/large stage matrix is more discriminating:

| pipeline | VS | FS | VDM token |
|---|---|---|---:|
| SS | small | small | `0x40` |
| SF | small | large | `0x40` |
| LS | large | small | `0xc0` |
| LF | large | large | `0xc0` |
| EA / EB | small | equal A/B | `0x40` |

Thus the token selects the distinct VS, not the entire render pipeline and not the FS.
Two tested distinct VS objects fit `0x40 + 0x80 * creation_index`; a general generator is
not established. On a consecutive same-VS draw the compact delta record omits this `0x500`
pair, confirming it is a state bind rather than a mandatory draw header field.

The A/B-correlated VDM words at record `+0x08` (`0x01000000/0x01000040`) and `+0x10`
(`0x0404/0x0606`) are stable source/pipeline properties, but all six stage-matrix pipelines
share `0x01000040/0x0606`. Their GPR/uniform/resource semantics are therefore **UNKNOWN**.

### 4. Fragment selection is a relative cursor into the code BO

`0x58000+0x08` selects the FS independently of the VDM VS token. Four structurally checked
fragment variants satisfy:

```text
fs_selector = fs_code_record_header + record_size + 0x40
```

The term after the code record is a 0x80-byte sized record; the selector addresses its
payload at header `+0x40`.

| FS | code header | record size | following 0x80 header | selector | readback class |
|---|---:|---:|---:|---:|---|
| small | `0x340` | `0x180` | `0x4c0` | `0x500` | red |
| large | `0x640` | `0x340` | `0x980` | `0x9c0` | green |
| equal-a | `0xc00` | `0x180` | `0xd80` | `0xdc0` | red |
| equal-b | `0xe00` | `0x180` | `0xf80` | `0xfc0` | green |

This falsifies the earlier “FS code size” interpretation. In particular, `equal-a` and
`equal-b` have:

- byte-identical 142-byte `_agc.main` bodies (SHA-256
  `1bc13bfa…8fcb2a6d`);
- different authored 128-byte constant programs;
- equal live code-record sizes (`0x180`);
- byte-identical 64-byte payloads at `0xdc0` and `0xfc0`; and
- different selectors and output.

The selector's location, rather than its payload contents or record extent, chooses the
associated preceding FS program. This is DATA-TRACE-VALIDATED on M4. Whether the consumer
is hardware or firmware remains unproven without a controlled live selector/header splice.

### 5. Authored live code-record framing

The archive extractor and live BO agree byte-for-byte for every authored A/B stage. The
live records observed here are:

```text
u32 record_size                 # multiple of 0x40, reaches next record
zero bytes through header+0x3f # true for these authored code records
authored constant_program       # 64 or 128 bytes in A/B
authored _agc.main
zero padding to record_size
```

Examples under AB order:

| stage | header | size | constant program | main offset / bytes |
|---|---:|---:|---:|---:|
| A FS | `0x340` | `0xc0` | 64 B at `0x380` | `0x3c0` / 54 B |
| A VS | `0x400` | `0x100` | 64 B at `0x440` | `0x480` / 88 B |
| B FS | `0x500` | `0x300` | 128 B at `0x540` | `0x5c0` / 558 B |
| B VS | `0x880` | `0x200` | 128 B at `0x8c0` | `0x940` / 268 B |

BA order relocates those exact authored bytes to B FS/VS at `0x340/0x6c0` and A FS/VS at
`0x8c0/0x980`. Ordinary client allocation padding leaves all four offsets unchanged.

The matrix also disproves a fixed `[FS][VS]` pair repeated per pipeline. New stage functions
are appended and reused: changing only FS reuses the same VS token/code; changing only VS
reuses the same FS selector/code. The live container is a cache of stage records plus adjacent
records, not four independent duplicated whole-pipeline containers.

`code_bo+0x00 = 0x340` points to the first authored shader record. Bytes before `0x340` and
records after the last proven authored match may include unknown helper programs. They were
not disassembled, semantically analyzed, or attributed. The 0x80 following-record payload is
reported only as opaque DATA-TRACE structure.

### 6. Generic pointer-scan result is quarantined

An initial analysis draft performed an aligned-pointer scan over every captured BO in three
dumps. That scope was not restricted to previously correlated command/state/descriptor BOs,
so root audit quarantined its negative output. It is process evidence only and supports no
hardware conclusion. The positive selector results above come from the explicit live VDM
BO at `0x18000`, the explicit pool BO at `0x58000`, and exact matches of our authored shader
bytes in the code BO at `0x10000000000`.

## Interpretation and evidence strength

| statement | classification |
|---|---|
| A/B and six matrix pipelines coexist and switch correctly on one M4 queue | HW-VALIDATED |
| `(0x500, 0x40/0xc0)` is a per-change VS bind pair for tested VS objects | DATA-TRACE-VALIDATED |
| `0x58000+0x08` is the tested FS relative selector with the formula above | DATA-TRACE-VALIDATED |
| 0x40-byte code header and record extent for matched authored stages | OWN-SHADER + DATA-TRACE-VALIDATED |
| following 0x80 record is consumed by HW/FW | UNKNOWN; structural correlation only |
| VS token formula beyond two distinct VS objects | INFERRED/untested |
| code base maps exactly to Linux queue `usc_exec_base` | INFERRED; no Linux test |
| VDM `+0x08/+0x10` and opaque payload fields are complete resource specs | UNKNOWN |
| A18 Pro uses the same values | INFERRED from broader Apple9 work, not evidence here |

## Remaining P0.2 / P0.7 gaps

- End-to-end Linux proof that `usc_exec_base` is the 4 GiB-aligned base used by these
  selectors, including address translation, low-bit tags, queue lifetime, and multiple
  queues/BOs.
- A synthesis rule for arbitrary VS tokens, including deletion/cache reuse, more than two
  VS functions, cross-library linking, and prolog/epilog combinations.
- Live mutation evidence identifying whether record sizes and following 0x80 records are
  consumed by hardware, firmware, or only macOS userspace.
- Full schema/writer for the following record and all stage/resource properties: GPRs,
  uniforms, textures, samplers, shared/tile memory, scratch, preambles, and stage flags.
- Exact executable program extent/entry when constant programs, main programs, linked
  parts, helpers, and arbitrary alignment coexist.
- An independently generated packer that launches these pipelines, rather than observing
  Metal's packer.
- Direct A18 Pro/G17P replication.

The safe driver conclusion is therefore not “walk all blocks positionally.” Preserve a
queue-relative code window, emit explicit separable VS/FS selection state, and keep the
generation-specific packer disabled until the remaining token/resource schemas are proven.

## Clean-room attestation

Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER

Inputs inspected: committed authored MSL and harnesses, live output/readbacks, IOKit
boundary data from our process, and only the compiled bytes of the exact authored shaders.
Unknown helper/program regions were retained but not inspected semantically.

Apple binary introspection: NONE

Reproduction: `README.md` commands and the timeout-enforced checked-in runners.

Evidence: `raw/derived/analysis_summary.txt`, authoritative capture stdout/logs and full
workspace maps indexed by `raw_manifest.sha256`, plus exact own-shader hex under
`raw/own_shader*`. `raw/quarantine/` is retained for audit but is not evidence for the
verdict.
