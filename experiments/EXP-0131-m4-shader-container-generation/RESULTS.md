# EXP-0131 results: M4 shader container field map + live splice-and-execute
# hardware-consumer proof (P0.7 / DRV-SHADER-01)

## Verdict

**P0.7 remains OPEN, but this experiment closes one of its two most-cited
remaining gaps and materially advances the other.**

1. **EXP-0042's "whether hardware or firmware consumes these bytes remains
   unproven without a controlled live selector/header splice" is now
   answered for the CODE payload: HW-VALIDATED.** A single byte, decoded and
   chosen via our own `tools/agx-isa` field model (not copied from any
   captured Apple record), written directly into the LIVE, POST-CREATION
   code-BO record (not the pre-creation archive), changes the hardware's
   rendered output on the very next draw exactly as predicted, with the
   write's persistence independently confirmed via a second `iotrace`
   snapshot. This is the strongest evidence level this project's process
   defines (`CODEX.md`: "independently generated encoding executed
   successfully on hardware").
2. **The "opaque following 0x80-byte record" EXP-0042 flagged as UNKNOWN is
   structurally reclassified**: it is not independent per-FS metadata; it is
   simply the START OF THE NEXT CODE RECORD in the code BO (here, the vertex
   shader's own header + constant_program), because Metal packs code records
   back-to-back and EXP-0042's selector arithmetic (`header + record_size +
   0x40`) lands exactly `0x40` bytes into whatever record follows. This is
   supported by (a) an independently-obtained exact match to EXP-0042's own
   "A VS: header 0x400, size 0x100" table entry from a completely different
   compiled shader, and (b) a live mutation of that exact field
   (`corrupt_next_record_header`) that leaves this experiment's own draw
   unaffected, consistent with (but not sole proof of) that reclassification.
3. **Task 2 (construct a full container from scratch and get it selected)
   was deliberately NOT attempted.** Locating the live FS/VS selector field
   is `EXP-0127-m4-shader-selection`'s assigned angle per the dispatch's own
   coordination instruction; informal calibration here found the field this
   experiment initially assumed (recalled from EXP-0042 as "pool+0x08") did
   not correlate with an actual pipeline switch in a from-scratch two
   pipeline test (see PROGRESS.md Milestone 1 step 6), and re-deriving the
   selector independently would duplicate EXP-0127's mandate. **Task 3 (the
   dispatch's own named fallback -- "minimal modification of a REAL
   container that hardware still accepts") is what this experiment achieves,
   at the strongest evidence level.**
4. **Task 1 (complete field map) and Task 4 (extent/alignment by
   construction) both advance**: header (`record_size`), main, and the
   "following record" boundary are each independently mutated and observed;
   results below split them FIRMWARE-CONSUMED vs. ARCHIVE/CREATION-TIME
   BOOKKEEPING with the mutation evidence to support each classification.

All results are M4/G16G only (macOS 26.6.2, Metal 4). No A18 Pro/G17P run
exists (hands-off per `CLAUDE.md`); per repo convention this is the
operational Apple9 evidence via the established A18=M4 byte-identity
finding, not a direct G17P observation.

## Gate results

- `verify.py --selftest`: **9/9 PASS** (schema round-trips a realistic
  gated record; rejects an injected code-window-VA-shaped value in the
  gated payload; rejects an `addr_*` key leaked into the gated payload;
  proves the gated payload is byte-identical across two records that differ
  ONLY in their real addresses; proves it correctly DIFFERS when real
  content differs; round-trips a literal `header_size_zero` fixture from
  recorded reality; round-trips the missing/unparseable-JSON sentinel shape).
- `verify.py --seqtest`: **5/5 PASS** (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT
  state representability and mutual exclusivity).
- Smoke gate: **PASSED** before `raw/` was created, both official runs
  (`work/smoke_m4_20260828_run01/`, `work/smoke_m4_20260828_run02/`, never
  under `raw/`).
- `verify.py --captured m4_20260828_run01 m4_20260828_run02`: **PASS, 7/7
  cases byte-identical gated payload.** Stronger than case-by-case: the
  entire `raw/<run-id>/02_results.jsonl` file is **sha256 byte-identical
  across both runs** (`946b5f56...204eed9e`), while the corresponding
  `02_results_addrs.jsonl` (GPU VAs, CPU pointers, live offsets) legitimately
  DIFFERS between the two runs -- e.g. `splice_green_field`'s `addr_bo_cpu`
  is `0x102c68000` in run01 and `0x102d30000` in run02 (`manifest.json`,
  `raw/*/02_results_addrs.jsonl`). This is the standing gate's required
  proof that GPU-address nondeterminism is real, present, and correctly
  excluded rather than merely asserted.
- All 14 case invocations (7 cases x 2 runs) reproduced **identically**:
  same `post_mutation_bgra`, same `post_mutation_hang` (always `false`, i.e.
  no true GPU hang anywhere in this experiment), same process exit
  code/signal per case. No host wedge. No `macvdmtool`. No A18 touched.

## 1. Container field map, with firmware-consumed vs. archive-bookkeeping

All offsets below are for `render_min.metal`'s fragment record specifically
(header `0x340` within the `0x10000000000`-family code BO, `record_size
0xc0`, main at `0x3c0`, 54 bytes); the FRAMING RULE (not the exact numbers)
is EXP-0042's, reproduced here byte-for-byte from a fresh, independent
compile:

```
header (u32 record_size @ +0x00, zero-pad through +0x3f)   -- 0x40 bytes
constant_program (authored, 64 or 128 B for tested shapes)  -- @ +0x40
main (_agc.main, hardware-executed code)                    -- follows const_program
zero padding to record_size                                 -- to record end
[[ next record's own header begins at header+record_size ]]
```

| field | firmware/HW vs. archive | evidence (this experiment) |
|---|---|---|
| **`main` program bytes** (`_agc.main`) | **FIRMWARE/HARDWARE-CONSUMED.** Directly executed on every draw from the exact live memory location. | `splice_green_field`: HW-VALIDATED (below) |
| **header `record_size` (own record, +0x00)** | **NOT re-consulted at per-draw code-fetch time** (main still fetched/executed correctly with the field corrupted to `0x00000000` or `0xFFFFFFFF`). **DOES matter to something else**: corrupting it to `0` reproducibly crashes the harness *process* (SIGBUS) during teardown, both official runs, i.e. it IS read by macOS Metal userspace at least once post-creation (deallocation/resource-walk time). Classified: **ARCHIVE/CREATION-TIME (macOS-userspace) BOOKKEEPING for the per-draw code-fetch path; separately consumed by macOS userspace at teardown.** No hardware/firmware consumption demonstrated for this field. | `header_size_zero`, `header_size_max` (both cases, both runs) |
| **"following 0x80-byte record"** (EXP-0042: opaque) | **RECLASSIFIED, structural**: it is the NEXT code record's own header+constant_program (not independent FS metadata). A live corruption of its leading 4 bytes (`corrupt_next_record_header`, → `0xFFFFFFFF`) has **no observed effect on this draw** -- consistent with, but (disclosed up front in `PRE_REGISTRATION.md`) not sole independent proof of, that reclassification, since a null result on an unrelated record cannot by itself distinguish "harmless because it's unrelated" from "harmless because content there is generally unconsulted". | `corrupt_next_record_header`; structural cross-check in PROGRESS.md Milestone 1 step 5 (independently reproduces EXP-0042's exact "A VS: header 0x400, size 0x100" numbers from a different compiled shader) |
| **`constant_program`** (64 B for this shader) | **NOT independently tested this experiment** -- for `render_min.metal` specifically it decodes as a single `stop` (`0e000000`) plus `0600`-repeat filler (i.e. this trivial shader needs no real prolog), so mutating it would not distinguish hypotheses without a shader that actually uses a nontrivial constant program. Flagged as follow-up, not silently omitted. | PROGRESS.md Milestone 1 step 3 (decode only) |
| **entry point** | The main program begins immediately after `constant_program` (`header + 0x40 + const_len`); no separate entry-point field was found or needed -- execution starts at record layout's own fixed offset, once the (out-of-scope-here) selector directs the draw to this record. | structural, all cases |
| **resource specifiers (GPR/texture/sampler/buffer counts)** | **NOT located in this record** for `render_min.metal` (which declares none). Consistent with EXP-0110's compute-side finding that resource-count metadata is archive/compile-time bookkeeping realized elsewhere (the argument-buffer table), not in the executed code record itself. Extending this claim to graphics with resource-bearing shaders is future work (this experiment's authored shader deliberately has zero textures/samplers/buffers, to keep the mutation matrix small and safe). | not exercised this experiment |

## 2. HW-VALIDATED: live-container splice-and-execute (`splice_green_field`)

### Observed

`main+0x06` (the `val` field of the first `frag_color_pack` instruction,
per `tools/agx-isa/agxisa.py tokenize` on our own compiled bytes) reads
`0x80` in every fresh compile of `render_min.metal`. EXP-0008 already
HW-VALIDATED, at the ARCHIVE/pre-creation level (`tools/agxtest/agxrender.m`),
that `0x80`→`0x40` at this exact byte flips the rendered green channel
`0.502`→`0.251`. This experiment reproduces that exact byte value from an
independent, in-process compile, then writes `0x40` directly into the LIVE,
POST-CREATION code BO (not the archive) and redraws with the SAME
already-created `MTLRenderPipelineState`:

| | `baseline_bgra` | `post_mutation_bgra` | both runs |
|---|---|---|---|
| `splice_green_field` | `4080ffff` | `4040ffff` | byte-identical |

`post_read_ok=true` and a second post-draw `iotrace` snapshot confirmed the
written byte (`0x40`) was still present afterward (not reverted or shadowed).
`post_mutation_completed=true`, `post_mutation_status=4`
(`MTLCommandBufferStatusCompleted`), `post_mutation_hang=false`.

### Interpreted

The green channel changed from `128/255` (`0.502`) to `64/255` (`0.251`),
exactly the value our own field edit specified, on a FRESH command buffer
that never touched the archive/pipeline-creation path again -- only the
live code-BO bytes were mutated. This is only possible if the hardware
fetches fragment code from this exact live memory location at draw time,
not from a macOS-private cached/shadow copy fixed at creation. Combined with
`splice_wrong_field` (adjacent byte `main+0x07`, `src_present_mask`
`0x50`→`0x40`) showing **no observed pixel change** -- i.e. this experiment
also shows the effect is FIELD-SPECIFIC, not "any byte flip near there
does something" -- the `splice_green_field` result is a controlled,
falsifiable, positive match, not a coincidence of nearby memory corruption.

Evidence: **HW-VALIDATED** (per `CODEX.md`'s strongest tier: "independently
generated encoding executed successfully on hardware"). The generated value
came from our own `tools/agx-isa` field decode + a chosen replacement value,
not from copying any other Apple-authored record.

## 3. Extent/alignment boundary sweep (Task 4)

| case | mutation | result | interpretation |
|---|---|---|---|
| `header_size_zero` | own header u32 → `0x00000000` | draw completes normally, output UNCHANGED (`4080ffff`); harness PROCESS crashes (SIGBUS) at teardown, reproducibly, both runs | `record_size` is not read at per-draw code-fetch time, but IS read by macOS userspace at some point after creation (teardown/dealloc). Contained: GPU itself never faults or hangs; only the CPU-side test process crashes, after all evidentiary data was written. |
| `header_size_max` | own header u32 → `0xFFFFFFFF` | draw completes normally, output UNCHANGED (`4080ffff`), clean process exit | Same conclusion as above for the per-draw path, WITHOUT the teardown crash -- i.e. the crash is specific to the zero value, not to "any corrupted header", an asymmetry worth flagging for a future targeted follow-up but not further chased here (out of scope; not safety-relevant since it is CPU-side and contained). |
| `truncate_main_early` | `main+0x0a..+0x35` (44 bytes) replaced with `stop` immediately + zero | draw completes normally; output becomes `00000000` -- exactly the render pass's OWN `clearColor` (`0,0,0,0`), not garbage, not a fault | Confirms `stop` behaves as an unconditional halt (consistent with `tools/agx-isa`'s `stop` descriptor) and that skipping `frag_tile_setup`/`frag_color_store` means NOTHING is written to the tile for that draw -- the load/clear value shows through. This is also useful ABI evidence: a fragment program that never reaches its color-store step is not implicitly given a default output. |
| `corrupt_next_record_header` | next record's leading u32 (VS's own header, per Task 1's reclassification) → `0xFFFFFFFF` (`write_before` independently confirms the pre-corruption value was `0x00000100` little-endian, i.e. `record_size=0x100` -- an exact match to EXP-0042's own "A VS" table entry, obtained without ever reading that table during this run) | draw completes normally, output UNCHANGED (`4080ffff`) | No fault, no hang, no visible effect on THIS (fragment) draw from corrupting an adjacent record's header. Does not by itself prove the adjacent record is inert (a null result cannot); does independently corroborate the specific numeric layout EXP-0042 reported. |

No case in this experiment produced `post_mutation_hang=true` (a genuine,
watchdog-timed-out GPU hang); every mutation was either fully absorbed
(no visible effect) or produced the exact predicted, bounded visual change.
This differs from EXP-0116's CDM boundary matrix (which did find a genuine
`encoding_max` hang case) -- consistent with this experiment's mutations all
staying within the SAME already-resident, already-referenced code BO region
(never reaching for an unmapped or wildly out-of-range address), a
deliberately more conservative sweep given the dispatch's explicit "note
EXP-0116's warning" safety instruction.

## GENERATED vs. COPIED, per field (closure-relevant distinction)

| field | status | evidence |
|---|---|---|
| `splice_green_field`'s replacement byte (`main+0x06 = 0x40`) | **GENERATED**: decoded via `tools/agx-isa` as the `frag_color_pack` `val` field, and the replacement value chosen by us (not copied from any other captured Apple record) -- though the SPECIFIC numeric mapping (0x40 → green 0.251) was first established by EXP-0008 at the archive level; this experiment independently re-derives the same byte from a fresh compile and is the first to apply it to the LIVE container | `harness/codesplice.m` `splice_green_field` branch; PROGRESS.md Milestone 1 steps 1-2 |
| `splice_wrong_field`'s replacement byte (`main+0x07 = 0x40`) | **GENERATED + TESTED**, a genuinely novel probe (not previously tested by any prior experiment) | same |
| `header_size_zero`/`header_size_max`/`corrupt_next_record_header` values (`0x00000000`/`0xFFFFFFFF`) | **GENERATED**: chosen boundary values, not copied from any capture | same |
| `truncate_main_early`'s `stop` + zero-fill | **GENERATED**: our own choice of where to truncate and what opcode to place there (`0e000000`, the already-validated `stop` encoding from `tools/agx-isa`'s DB) | same |
| Record header/constant_program/main FRAMING RULE itself | **REPRODUCED, not newly discovered**: this experiment independently re-derives EXP-0042's exact framing from a fresh, differently-shaped compile (a genuine independent confirmation, not a re-read of EXP-0042's own capture) | PROGRESS.md Milestone 1 step 3 |
| A full container built from wholly new bytes at a NEW, unclaimed code-BO location, selected via a newly constructed selector value (Task 2, full form) | **NOT ACHIEVED, explicitly deferred to `EXP-0127`** | see Verdict §3 |
| Fresh, never-before-compiled machine code executed via this mechanism | **NOT ACHIEVED**: every case here mutates an already-Metal-compiled record's bytes (field edits / truncation / header corruption), never assembles and places a wholly independent instruction sequence. The `splice_green_field` edit IS "our own assembled bytes" in the sense of being decoded/re-encoded via `tools/agx-isa`, but it is a single-field edit of an existing valid program, not a from-scratch program. | same limitation EXP-0116 named for its own task 3 |

## What P0.7 still needs

- **Task 2, full container construction + independent selection**, is
  unaddressed here by design (deferred to `EXP-0127`'s selector work); once
  that selector encoding is known, this experiment's own finding --that the
  live code-BO region is genuinely hardware-consumed and directly
  writable-- gives a clear, validated next step: place a full hand-built
  record (header + our own constant_program + our own from-scratch main) in
  unclaimed code-BO space and redirect the (then-known) selector to it.
- **A from-scratch (not field-edited) instruction sequence** executed via
  this mechanism, to move beyond "our own assembled bytes as a field edit"
  to "our own assembled program". `tools/agx-isa`'s assembler already
  supports the needed instructions (`frag_color_pack`, `frag_tile_setup`,
  `frag_color_store`, `stop`) structurally, but full correctness of a
  from-scratch fragment epilog was not attempted here because the exact
  `val`/`conv_scale` packing semantics beyond the ONE validated byte are not
  yet in `tools/agx-isa`'s DB (see PROGRESS.md Milestone 1 step 1) --
  DRV-ABI-01 territory, not re-derived here.
- **`constant_program` mutation** (untested this experiment; `render_min`'s
  own constant_program is degenerate filler for this trivial shader).
- **Resource-bearing shaders** (textures/samplers/buffers): this
  experiment's shader deliberately has none, to keep the safety envelope
  small; the resource-specifier portion of Task 1 is therefore still
  entirely open.
- **The header-zero SIGBUS's exact mechanism** (why zero specifically
  crashes teardown and `0xFFFFFFFF` does not) is disclosed as an observed,
  reproducible, CONTAINED fact, not further root-caused (CPU-process-level,
  not GPU/firmware, and therefore lower priority for a hardware
  specification).
- **A18 Pro replication** (hands-off per `CLAUDE.md`; M4 result treated as
  the operational Apple9 evidence via the established A18=M4 byte-identity
  finding).

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: harness/codesplice.m (authored ObjC, embedded MSL source
  byte-identical to EXP-0008-fragment-extraction/kernels/render_min.metal,
  sha256 a3996254101cc3f2d6c138bbf0e278d696409a57a7abe3f449b9dedbca907054);
  IOKit boundary allocation metadata and content for the single BO
  structurally matching our own authored compiled fragment signature
  (byte-exact match of our own extracted _agc.main, chain-identified by
  content, never by a hand-copied address); public command-buffer
  status/error/readback; tools/agx-isa/agxisa.py used read-only, offline,
  during calibration only, to decode (never author from a captured Apple
  record) the one field this experiment edits.
Apple binary introspection: NONE.
New technique this experiment adds vs. EXP-0042/0110/0116: direct CPU-
  pointer writes into this process's own registered GRAPHICS shader CODE
  container (0x10000000000-family), strictly POST-PIPELINE-CREATION and
  pre-next-commit -- the graphics analogue of EXP-0116's CDM command-segment
  mutation technique, applied here to the code payload itself rather than a
  command-stream link field.
Reproduction: README.md's command block; verify.py --selftest/--seqtest are
  self-contained (no device needed); run.py --run-id <id> reproduces a full
  official capture end to end.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/ (02_results.jsonl
  sha256-identical across both runs: 946b5f566eb7f63239deede9c87e3cfe09674734c45919b8118e827e204eed9e),
  analysis/report.json, CAPTURE_CONTRACT.json, manifest.json.
```

Every shader dispatched or compiled was authored in this experiment's own
`kernels/render_min.metal` (a verbatim, hash-verified copy of an already
clean-room-attested prior experiment's own authored source, not an
Apple-authored shader). `tools/iotrace/iotrace.c` was used exactly as
committed, never edited (hash recorded per-run in `00_inputs.json`). No
Apple binary, framework, kernel, firmware, or Apple-authored shader was
inspected, disassembled, decompiled, strings-scanned, debugged, or traced.
