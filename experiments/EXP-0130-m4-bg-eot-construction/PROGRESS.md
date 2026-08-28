# PROGRESS -- EXP-0130

- **2026-08-28T08:23Z** -- Dispatch received. Read `CLAUDE.md`, `CODEX.md`,
  `experiments/SUBAGENT_BRIEF.md`. Reviewed prior established work: EXP-0048,
  EXP-0108, EXP-0120 (RESULTS.md, full read), EXP-0029, EXP-0117 (relevant
  sections). Read `mesa/include/drm-uapi/asahi_drm.h` and Mesa's own
  construction path: `mesa/src/asahi/lib/agx_bg_eot.{c,h}`,
  `mesa/src/gallium/drivers/asahi/agx_state.c` (`agx_build_bg_eot`),
  `agx_pipe.c` (`agx_flush_render`), `mesa/src/asahi/vulkan/hk_cmd_draw.c`
  (`hk_build_bg_eot`), `hk_queue.c` (`asahi_fill_vdm_command`),
  `mesa/src/asahi/genxml/cmdbuf.xml` (`Counts` struct, USC struct layouts).
  Also read `mesa/src/asahi/compiler/agx_compile.c` /`agx_opcodes.py` for
  cross-generation context on `block_image_store` (M1/M2-class backend;
  read as PUBLIC context only, not promoted as an Apple9 fact anywhere).
- **08:23Z** -- Confirmed EXP-0130 is a free experiment number (highest
  existing was EXP-0135; no gap conflict) and set up
  `experiments/EXP-0130-m4-bg-eot-construction/{harness,kernels,analysis,raw,work}`.
- **08:24Z** -- Authored `kernels/eot_construct.metal` (three fresh MSL
  fragment functions: `f_eot_evict`, `f_eot_ctrl`, `f_eot_combine`) and
  `harness/render_eot.m` (own Metal/ObjC render harness, modeled on the
  already-HW-validated single-pass RGBA32Float pattern in EXP-0117's
  `harness/render.m`, freshly re-authored, not copied). Built and ran ad
  hoc pre-freeze checks (not `raw/`, `work/` only):
  - `evict` mode: result == dst exactly for one large-magnitude case.
  - `ctrl` mode: result == konst regardless of dst clear color, for three
    dst values.
  - Extracted `f_eot_evict`'s compiled fragment bytes via a
    locally-rebuilt `tools/shdump`/`agxparse.py` (read-only use, pinned
    hashes recorded in `PRE_REGISTRATION.md`) and found it is **16 bytes
    containing neither `tile_read` nor `frag_color_store`** -- the
    compiler proves the pure-identity shader a no-op. This directly
    motivated adding `f_eot_combine` (non-foldable ALU) as the primary
    non-elidable construction, and updated the `f_eot_evict` source
    comment to state this accurately (not the originally-assumed "compiles
    to tile_read+frag_color_store" claim) before freezing hashes.
- **08:30Z** -- Ran the H3 host-environment check (`raw/host_check.json`):
  confirmed Darwin/macOS kernel, no `/dev/dri`, no `asahi`/`drm` kext, and
  cross-referenced `docs/P0-P1-CLOSURE.md` P0.5 row (`OPEN`, no
  independent command-stream packer). All three falsifier conditions for
  H3 checked and not found.
- **08:30Z** -- Froze `PRE_REGISTRATION.md` and `CAPTURE_CONTRACT.json`
  with source hashes and `pre_gpu_timestamp_utc`.
- **08:31Z** -- Ran the NON-RECORDED smoke gate (`work/smoke/smoke1`):
  23/23 processes completed OK, but the analysis-side comparison caught a
  genuine mismatch on `d4_near_fmax`: the case value `3.0e38` is **not**
  exactly representable in float32 (a rounding-ambiguous literal), so the
  double-precision oracle and the float32 GPU readback legitimately
  differed at the last bit when compared as raw doubles. **This is exactly
  what the smoke gate exists to catch, before either official run id was
  spent.** Fixed `harness/casematrix.py` (decimal literal `3.0e38` ->
  exact powers of two `2**126`/`2**-120`) and re-ran (`smoke2`,
  `work/smoke/smoke2`): 23/23 OK, but the *quick sanity comparator itself*
  (not `analysis/verify.py`, which did not exist yet) still flagged a
  false mismatch on the same case -- root-caused to `render_eot.m`'s
  `%.9g` stdout precision being insufficient to round-trip a double
  exactly for a ~1e38-magnitude value. Fixed `harness/render_eot.m`
  (`%.9g` -> `%.17g`), rebuilt, re-ran (`smoke3`, `work/smoke/smoke3`):
  23/23 OK, 0 mismatches under a proper float32-aware comparison. Both
  fixes are disclosed in `PRE_REGISTRATION.md` and reflected in the final
  frozen source hashes (which is what the official runs below were
  captured against). `work/smoke/smoke1` and `smoke2` are left in place
  (not deleted) for transparency per project convention; neither is
  promoted as evidence.
- **08:33Z** -- Ran official capture `m4_20260828_run01` (`raw/`): 23/23
  OK, 0 fail, 0 timeout.
- **08:34Z** -- Ran official capture `m4_20260828_run02` (`raw/`): 23/23
  OK, 0 fail, 0 timeout.
- **08:35Z** -- Wrote `analysis/verify.py` (fixtures copied verbatim from
  `work/smoke/smoke3/records.jsonl`, per the standing gate requirement).
  Ran `python3 analysis/verify.py --selftest --seqtest --captured`:
  **--selftest 14/14 PASS, --seqtest 6/6 PASS, --captured 10/10 PASS.**
  No mismatches; every behavioral case matches its float32 oracle in both
  runs independently; the structural claim (evict: neither op, ctrl:
  store-only, combine: both ops) holds byte-identically in both runs; the
  paired-control invariant (ctrl constant across the 8-value dst sweep,
  evict genuinely varies across it) holds in both runs.
- **08:36Z** -- Decision: the tile-shading/`imageblock<T>` construction
  route (EXP-O2D's A18-only precedent) is **explicitly deferred**, not
  attempted fresh on M4 in this dispatch -- disclosed scope bound, not a
  silently dropped item (see `PRE_REGISTRATION.md` Section 2 and
  `RESULTS.md` "Deferred"). The core tile_read+ALU+frag_color_store
  construction (H1/H2) already provides decisive, triangulated
  (behavioral + structural + paired-control) evidence for the specific
  ABI question this experiment targets; the incremental cost of a second,
  independent hardware mechanism outweighed its incremental evidentiary
  value given the time available for this dispatch.
- **08:40Z** -- Wrote `RESULTS.md`, `README.md`, `manifest.json`.
  Re-verified several Mesa file/line citations against fresh `grep -n`
  output while writing `RESULTS.md` and corrected several off-by-a-few-lines
  errors (e.g. `hk_cmd_draw.c:611-618` -> `:455-465`, several `cmdbuf.xml`
  struct ranges) before finalizing.
- **08:45Z** -- **Post-capture hygiene fix, disclosed:** while doing a
  final directory listing, found that `harness/run.py`'s structural-record
  build step had written compiled Metal binary-archive containers
  (`.bin`, `MetalLib`/`applegpu` Mach-O, confirmed via `file`) into
  `raw/m4_20260828_run0{1,2}/work/` -- a `SUBAGENT_BRIEF.md` violation
  (`raw/` must be text logs/JSON only, never binary archives, regardless
  of authorship). **The captured evidence itself (`records.jsonl`) was
  never affected**: it contains only the already-extracted hex strings
  and booleans (the actual evidence), never a path or reference to the
  `.bin` files, and `analysis/verify.py --captured`'s 10/10 PASS gate does
  not read or depend on them. Deleted the three stray `.bin` files and the
  now-empty `work/` subdirectories from both `raw/` run trees (`raw/`
  itself, and every file that remains in it, is otherwise untouched from
  official-capture time), and fixed `harness/run.py` to write build
  scratch to `work/build_scratch/<run_id>/` (outside `raw/`) for any
  future reproduction. `harness/run.py`'s hash changed as a result
  (`a68575f3...` at freeze time -> `a70c72f8...` now); this is recorded
  here and in `manifest.json` rather than silently updating
  `PRE_REGISTRATION.md`'s frozen value, since the frozen hash correctly
  reflects what the two official runs were actually captured against --
  the fix is to the harness's *build-scratch output location* for future
  runs, not to anything that changed the meaning of the already-gated
  `records.jsonl` data. Re-ran `python3 analysis/verify.py --selftest
  --seqtest --captured` after the cleanup: still **14/14, 6/6, 10/10
  PASS** (as expected -- the gate never touched the deleted files).
- **08:47Z** -- No git commits made (orchestrator owns commits per
  `SUBAGENT_BRIEF.md`). No files written outside this experiment
  directory. No `docs/`, `PROVENANCE.md`, or `docs/P0-P1-CLOSURE.md`
  edits made.
