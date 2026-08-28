# EXP-0131 progress log

## Milestone 0 -- setup + reading (2026-08-28)

Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (DRV-SHADER-01), `docs/P0-P1-CLOSURE.md`
(row P0.7), `experiments/EXP-0042-graphics-code-selection/RESULTS.md`,
`experiments/EXP-0110-m4-command-container-packing/RESULTS.md`,
`experiments/EXP-0116-m4-command-generation/{RESULTS.md,PRE_REGISTRATION.md,harness/linksplice.m}`.
Checked for the sibling `EXP-0127-m4-shader-selection` (graphics selector
side, per dispatch): at read time it had only kernel scaffolding
(`kernels/vs_uniform.metal`, `kernels/vs_varied.metal`,
`analysis/gen_kernels.py`), no `PRE_REGISTRATION.md` yet, targeting the VDM
VS-token generalization -- confirmed disjoint from this experiment's
container/code-splice angle. Did not touch `EXP-0127`'s files.

## Milestone 1 -- informal calibration, DISCLOSED (not evidence)

All calibration below ran inside `work/` (never outside the repo, never
`/tmp`). Binaries: `work/bin/shdump` (from `tools/shdump/shdump.m`,
unmodified), `work/bin/iotrace.dylib` (from `tools/iotrace/iotrace.c`,
unmodified, built with `-framework IOKit -framework CoreFoundation` per that
tool's own `build.sh` -- the first build attempt omitted those frameworks
and failed to link; corrected before any capture).

1. Compiled `kernels/target_fs.metal` (an early authored probe, superseded --
   see below) via `shdump --render`, extracted the fragment `_agc.main` (54
   bytes) via `agxparse.py`, tokenized it with `tools/agx-isa/agxisa.py`.
   Confirmed it fully tokenizes (7 instructions, 0 leftover bytes) but does
   NOT obviously expose the RGBA literal as a separate `mov_imm`-style
   instruction -- the color is folded into `frag_color_pack`'s `val`/
   `conv_scale` fields, whose full encoding tools/agx-isa's DB does not yet
   resolve (`conv_scale`'s enum is partial).
2. Rather than reverse-engineer that packing from scratch, reused
   `experiments/EXP-0008-fragment-extraction/kernels/render_min.metal`
   VERBATIM (`float4(1.0,0.5,0.25,1.0)`; diffed byte-identical against the
   original, sha256 `a3996254101cc3f2d6c138bbf0e278d696409a57a7abe3f449b9dedbca907054`)
   because EXP-0008 already HW-validated, at the ARCHIVE level
   (`tools/agxtest/agxrender.m`), that `_agc.main[0x06]` is the green-channel
   `val` byte: `0x80`->`0x40` flips the rendered green channel
   `0.502`->`0.251`. This experiment's OWN compile of the identical source
   reproduces the identical 54-byte main and the identical byte at offset
   `+0x06` (`0x80`), confirmed via `shdump`+`agxparse.py` before writing any
   harness code. This became the frozen `ORIG_MAIN`/target field for the
   official `splice_green_field` case.
3. `work/calib0.m`: compiled `render_min.metal` in-process (NOT via the
   archive/`FailOnBinaryArchiveMiss` path -- the ordinary
   `newLibraryWithSource:`+`newRenderPipelineStateWithDescriptor:` path that
   produces the LIVE code-BO record EXP-0042 found), drew once (baseline
   `bgra=4080ffff`, matching EXP-0008's own A18 baseline exactly), dumped via
   `iotrace` SIGUSR1, located the live 54-byte main verbatim inside the
   `0x10000000000`-family BO at offset `0x3c0` (cpu pointer + offset,
   confirmed independently readable via a SECOND redump using iotrace's own
   `mach_vm_read_overwrite` path, not just our own pointer dereference).
   Header at `0x3c0-0x80=0x340` read `record_size=0xc0` -- an EXACT,
   independently-obtained match to EXP-0042's documented "A FS" framing
   shape (header/zero-pad/constant_program/main/zero-pad), even though this
   experiment used a different compiled shader.
4. Extended `calib0.m` to WRITE 1 byte (`cpu + 0x3c0 + 6 := 0x40`, i.e. the
   already-known-good `val` field edit) directly into that live memory,
   confirmed via redump that the write persisted, then issued a SECOND,
   FRESH command buffer using the SAME already-created `MTLRenderPipelineState`
   object and read back the target texture: **`bgra=4040ffff`** -- the
   green byte flipped exactly as EXP-0008 predicted, but this time via a
   mutation of the LIVE, POST-CREATION container, not the archive. This is
   the experiment's centerpiece result; see RESULTS.md.
5. Dumped and manually inspected the full `0x300-0x600` region of the code
   BO (`work/calib0.m`'s captured dump) to understand what EXP-0042 called
   the "following 0x80-byte record". Found: `header=0x400`, and reading its
   leading u32 gives `record_size=0x100`; bytes at `0x480` onward are real
   ALU/memory instructions (not filler) -- this is an EXACT independent
   match to EXP-0042's own documented "A VS: header 0x400, size 0x100"
   entry. **Conclusion: the "following record" is not independent per-FS
   metadata; it is simply the START OF THE NEXT CODE RECORD (here, the
   vertex shader's own header+constant_program), because Metal packs
   adjacent code records back-to-back and EXP-0042's selector formula
   (`header + record_size + 0x40`) is arithmetically "one past this record,
   landing 0x40 bytes into whatever comes next".** This refines (does not
   contradict) EXP-0042's own careful "reported only as opaque DATA-TRACE
   structure" framing -- see RESULTS.md field map.
6. `work/calib2.m`: built two pipelines (red/blue), drew red then blue (a
   genuine pipeline SWITCH) in separate command buffers, dumped after each,
   diffed the `0x58000` FF-state-pool BO. Result: `+0x08` (the field this
   experiment initially assumed, from memory of EXP-0042's "0x58000+0x08"
   note, to be the live FS selector) read **0x0 in BOTH captures** -- i.e.
   it did not correlate with the switch at all in this simpler two-pipeline
   case. The field that DID change was `+0x14` (`0x4a19`->`0x4a0a`, a
   16-bit-scale delta of 15, not address-shaped). **This did not match my
   own recollection of EXP-0042's exact field closely enough to proceed
   confidently, and reverse-engineering the true live FS selector is
   explicitly EXP-0127's assigned angle ("graphics-selection side") per the
   dispatch's coordination instruction.** Per that instruction, I stopped
   here rather than attempting to independently re-derive or hijack the
   selector mechanism -- see RESULTS.md "Task 2" for the honest scope
   statement.
7. Smoke-tested the FINAL harness (`harness/codesplice.m`, not `calib0.m`)
   standalone against all 7 planned cases before writing this
   `PRE_REGISTRATION.md`:
   - `baseline_check`, `splice_green_field`, `splice_wrong_field`,
     `header_size_max`, `truncate_main_early`, `corrupt_next_record_header`:
     all completed cleanly (process exit 0), matching or refining the
     predictions now frozen in `casematrix.py`.
   - `header_size_zero`: the GPU command buffer completed normally
     (`status=4`, unchanged output `bgra=4080ffff`) and the harness's own
     `--out` JSON was written completely and validly BEFORE a **contained,
     reproducible `SIGBUS` (Bus error) during process teardown** (after
     `fclose(g_out)`, in the final `free_dumps`/autoreleasepool-drain path).
     Reproduced twice. This is NOT a GPU fault/hang (`MTLCommandBufferStatus`
     was 4/completed both times, and the very next process launched cleanly)
     -- it is a CPU-process-level crash, fully contained, that happens only
     when the record's own `record_size` header field is corrupted to zero.
     Read as informative: it suggests macOS Metal's OWN userspace resource
     teardown (not necessarily the GPU/firmware) walks/uses this field
     AFTER creation, at least at pipeline/device teardown -- i.e. it is
     CONSUMED by something, just not (per the unaffected redraw) by the
     per-draw hardware code-fetch path. `run.py` treats a nonzero exit or a
     signal as a recorded result (never a silent failure): it reads the
     already-written `--out` JSON regardless of the exit code/signal and
     logs the process outcome alongside it in `01_process.jsonl`. No host
     wedge, no GPU hang, in either reproduction.

No evidentiary claim in `RESULTS.md` rests on this section alone; the
official two-run capture is what raw/ and RESULTS.md report against. This
section exists per repo convention (EXP-0110/EXP-0116) to disclose the
process history honestly, including a deviation-free but noteworthy crash
discovery.

## Milestone 2 -- pre-registration frozen

`PRE_REGISTRATION.md` and `CAPTURE_CONTRACT.json` written; harness/schema/
run/verify hashes frozen; git revision pinned at `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`
(dirty tree -- sibling experiments commit continuously; per repo norm this is
expected and not contamination, see `SUBAGENT_BRIEF.md`). `verify.py
--selftest` (9/9) and `--seqtest` (5/5) both pass with no GPU/raw/
dependency.

## Milestone 3 -- official runs (2026-08-28, complete)

- Smoke gate (`run.py --run-id m4_20260828_run01 --smoke-only`): PASS,
  `work/smoke_m4_20260828_run01/case_baseline_check.json`, never under `raw/`.
- Official run 1 (`m4_20260828_run01`): all 7 cases executed, one process
  each. `header_size_zero` reproduced the disclosed SIGBUS at teardown
  exactly as predicted in `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json`;
  every other case exited 0. `run.py` correctly read the already-written
  `--out` JSON for `header_size_zero` despite the crash and logged the
  process outcome in `01_process.jsonl`.
- Second smoke gate + official run 2 (`m4_20260828_run02`): identical
  outcome per case (same `post_mutation_bgra`, same hang/exit/signal
  pattern for all 7 cases).
- `verify.py --seqtest` re-run with both official run dirs present:
  RUN02_PRESENT checks now active, 5/5 PASS.
- `verify.py --captured m4_20260828_run01 m4_20260828_run02`: **PASS, 7/7**.
  `raw/*/02_results.jsonl` is sha256 byte-identical between the two runs
  (`946b5f566eb7f63239deede9c87e3cfe09674734c45919b8118e827e204eed9e`), while
  the corresponding `02_results_addrs.jsonl` differs (confirmed: e.g.
  `splice_green_field`'s `addr_bo_cpu` is `0x102c68000` in run01 vs.
  `0x102d30000` in run02) -- the standing "prove GPU addresses vary and are
  excluded" gate is satisfied non-vacuously.
- `analysis/report.py m4_20260828_run01 m4_20260828_run02`: every one of the
  7 pre-registered predictions in `casematrix.PREDICTIONS` matched the
  observed outcome exactly, and every case was cross-run deterministic.
  `analysis/report.json` written.
- No host wedge, no GPU hang (`post_mutation_hang=false` in all 14 case
  invocations), no `macvdmtool`, no A18 Pro touched.

See `RESULTS.md` for the full field map, verdict, and remaining P0.7 gaps.
