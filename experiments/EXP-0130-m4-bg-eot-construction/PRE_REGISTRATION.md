# PRE_REGISTRATION -- EXP-0130: M4 BG/EOT construction (P0.4)

Frozen before either official capture run. Git revision, source hashes,
environment, and timeouts below are pinned; captures are validated against
these recorded values, never against a moving `HEAD` (`CLAUDE.md`/
`SUBAGENT_BRIEF.md`: repo `HEAD` moving because a sibling experiment landed
is not contamination).

## 0. Context and what this experiment does NOT redo

Already established, cited, not repeated:

- EXP-0048 + EXP-0108 (M4, 40-case/11-axis IOKit inventory): Metal's own
  render path emits **no distinct BG/EOT program record** visible to
  userspace; the shader code window is exactly `0x10000` B in every tested
  case. `drm_asahi_bg_eot.usc`/`rsrc_spec` cannot be located or replicated
  by searching Apple's own captured traffic -- there is nothing there to
  find (bounded negative, not a gap in searching).
- EXP-0120 (M4): read `mesa/include/drm-uapi/asahi_drm.h` in full; `bg`,
  `eot`, `partial_bg`, `partial_eot` are **unconditional** fields of
  `struct drm_asahi_cmd_render`, required on every render regardless of
  whether a partial render occurs; there is no TVB/tiler-heap field at all.
- EXP-0029 (A18) + EXP-0117 (M4): HW-validated that an explicit
  `[[color(n)]]` fragment INPUT compiles to `tile_read` (byte0 `0x67`,
  byte+1 `0x0e`) and an ordinary fragment output compiles to
  `frag_color_store` (byte0 `0xe7`, byte+1 `0x06`); EXP-0117 additionally
  HW-validated, on M4, a full tile_read+ALU+frag_color_store "programmable
  epilog" construction for logic ops (8/8 exact) and established that
  Metal's blend-descriptor compiler elides `tile_read` when the
  *pipeline's MTLBlendFactor* configuration reduces to a dst-independent
  identity at PSO-creation time.
- EXP-O2D (A18, historical, pre-M4-directive): HW-validated an
  `imageblock<T>`-based tile-shading construction (tile render pipeline,
  `dispatchThreadsPerTile`) that reads and overwrites the imageblock, and
  showed the tile dispatch is folded into the render control stream with
  no separate submission. **Not replicated on M4 here** (see `RESULTS.md`
  Deferred).

This experiment does NOT repeat EXP-0048/0108's IOKit inventory sweep, does
NOT repeat EXP-0117's blend-factor/logic-op matrix, and does NOT attempt to
locate an Apple-authored BG/EOT program (established impossible/absent by
the above). It targets exactly the remaining gap those experiments named:
**construct our own program(s) that perform the BG/EOT role, get them to
execute on real M4 hardware, and verify by pixel readback against a host
oracle** -- plus a precise account of what blocks registering a construction
as the literal `drm_asahi_bg_eot.usc`/`rsrc_spec` fields.

## 1. Questions and falsifiable hypotheses

### H1 -- EOT-shaped read+write is constructible and executes correctly

**Claim:** a fragment-shaped MSL program that declares an explicit
`[[color(0)]]` input and writes a value to attachment 0 -- i.e. the two
operations "read the tilebuffer" and "write an attachment" that a driver's
EOT program must perform -- compiles via the public `newLibraryWithSource:`
API, runs on the real M4 GPU via an ordinary render pass, and produces a
pixel value that is an exact function of the tile's pre-existing content
(established via `MTLLoadActionClear` with an exact float clear color) and
of the shader's own logic, matching a Python-computed host oracle exactly
(float32-exact inputs, zero rounding ambiguity).

- Independent variable: the fragment function's source code (three
  variants: `f_eot_evict` -- pure passthrough of the read value with no
  combination; `f_eot_ctrl` -- a paired control that never reads
  `[[color(0)]]` at all; `f_eot_combine` -- reads and combines with a
  second, runtime, non-constant-foldable operand).
- Controlled variables: target format (`RGBA32Float`, exact arithmetic, no
  unorm rounding/clamping), target size (2x2, single full-screen triangle,
  center texel read back), pipeline state (`blendingEnabled=NO` throughout
  -- any combination happens in explicit shader ALU, never via an
  `MTLBlendFactor` descriptor, so EXP-0117's blend-descriptor-level fold
  does not apply here by construction).
- Expected observation if true: for every tested `(dst, src)` pair,
  `f_eot_combine`'s and `f_eot_evict`'s measured pixel exactly equals the
  oracle; `f_eot_ctrl`'s measured pixel equals its `konst` argument
  regardless of the clear color (`dst`) used for that render pass.
- Falsifier: any case where the measured pixel does not exactly match the
  oracle (float32 bit-exact, since all chosen values have exact float32
  representations); or where `f_eot_ctrl`'s output varies with `dst`
  (would mean the paired control is not actually independent of the tile,
  invalidating it as a control); or where `f_eot_evict`'s/`f_eot_combine`'s
  output does NOT vary with `dst` across the tested range (would falsify
  "the read is load-bearing").
- Known confounders: (a) Metal's compiler may recognize a pure
  read-then-write-unchanged shader as a semantic no-op and elide the
  underlying instructions entirely, relying on the render pass's own
  fixed-function load/store actions instead of the shader body -- this is
  a *structural*, not behavioral, confound, checked directly per (H2)
  below, not assumed away; (b) `-ffast-math` (default `MTLCompileOptions`)
  could in principle reorder float ops, but every chosen value set has an
  exact result under any legal float32 reassociation of `dst*2.0+src` (no
  catastrophic cancellation, no reassociation-sensitive terms) so this is
  not expected to matter and is noted, not silently assumed.

### H2 -- structural: which authored shapes actually reach the hardware ops

**Claim:** the compiled AGX bytes for `f_eot_combine`'s fragment stage
contain both `tile_read` (`67 0e 54`) and `frag_color_store` (`e7 06 54`)
as literal byte substrings (per EXP-0029's established encoding, reproduced
fresh here on M4 via `tools/shdump`+`agxparse.py`, read-only use); the
compiled bytes for `f_eot_ctrl` (no `[[color(n)]]` parameter) contain
`frag_color_store` but NOT `tile_read`; and the compiled bytes for
`f_eot_evict` (pure identity) are checked without assuming either is
present -- reported exactly as observed.

- Falsifier: `f_eot_combine`'s bytes lacking `tile_read` or
  `frag_color_store` would falsify "this shape reaches the hardware read/
  store instructions"; `f_eot_ctrl`'s bytes containing `tile_read` would
  falsify the paired-control design itself (would need to be re-designed).
- **Pilot note (informal, `work/`, pre-freeze, not part of the gated
  evidence):** an initial pilot run already showed `f_eot_evict` compiles
  to a 16-byte stub containing *neither* op -- the compiler proves the
  identity shader a total no-op (structurally identical in shape to
  EXP-0117's independently-discovered `on_dstonly` 16-byte stub, but
  reached from an entirely different code path: an explicit
  `[[color(n)]]`-to-output identity, not an `MTLBlendFactor`
  Zero/One-descriptor reduction). This pilot observation motivates
  `f_eot_combine` as the primary non-elidable construction and is
  **independently re-derived** by the official gated runs below (the
  pilot capture itself is not promoted as evidence; see `CAPTURE_CONTRACT.
  json` and `RESULTS.md` for the officially gated structural records).

### H3 -- registering a real `drm_asahi_bg_eot` field is unreachable from this host

**Claim:** no path reachable from this test host can write a value that a
real `DRM_IOCTL_ASAHI_SUBMIT` call consumes as `drm_asahi_bg_eot.usc`/
`rsrc_spec`, because (a) this host runs macOS (confirmed: `sw_vers`), not
Linux, so no `drm_asahi` kernel driver or device node exists on it at all;
and (b) even setting aside the OS mismatch, this project's own command-
stream capability (P0.5, `docs/P0-P1-CLOSURE.md`) is `OPEN` -- there is no
established, independently-generated VDM/CDM control-stream submission path
on this host that bypasses Metal's own pipeline/render-pass construction,
so there is no same-OS mechanism either to synthesize an equivalent
record and have it consumed by anything other than Metal's own (opaque,
uneditable-by-us) internal translation to firmware structures.
- Falsifier: discovery of any `/dev/dri/renderD*`-class node, any
  `drm_asahi`-named IOKit service, or any documented-here independent
  command-stream submission path on this host. Checked directly (`uname`,
  `ls /dev/dri* 2>&1`, a grep of this repo's own `docs/P0-P1-CLOSURE.md`
  P0.5 row) as part of this experiment, not assumed.

## 2. What is explicitly NOT attempted here (scope bound, stated up front)

- Raw byte-splicing of the tile_read/frag_color_store opcode bytes
  themselves as an additional falsifier tier (would require re-verifying a
  safe same-length single-byte mutation for THIS freshly-compiled kernel's
  exact register allocation before splicing, which is real additional
  work with real fault/wedge risk for marginal incremental evidence beyond
  the paired-control + structural-presence design already above). The
  paired-control (`f_eot_ctrl`) and structural op-presence checks (H2) are
  the falsifiers used instead. This is a deliberate, disclosed scope
  bound, not a silently dropped item.
- Reproducing EXP-O2D's `imageblock<T>`/tile-render-pipeline construction
  on M4 (A18-only today). Attempted only as time permits after H1-H3 are
  gated; if not reached, reported as explicitly deferred, not silently
  dropped.
- Sweeping NaN/Inf boundary bit patterns through the clear-color path
  (`MTLClearColorMake` takes `double`; canonicalization behavior for NaN/
  Inf through that specific conversion is untested here). Explicit UNKNOWN
  in `RESULTS.md`.
- Any A18 Pro replication (hands-off per `CLAUDE.md`).

## 3. Case matrix (frozen, `harness/casematrix.py`)

- 8 `dst` boundary/asymmetric cases (`DST_CASES`): zero, small
  positive/negative integers, large mixed-sign fractional, near
  `+-3.0e38`, tiny power-of-two fractions, an asymmetric mix including a
  large negative, and a signed-zero probe -- run under both `evict` and
  `ctrl` modes (16 behavioral cases).
- 4 `(dst, src)` pairs for `combine` mode (`COMBINE_CASES`), spanning
  zero/negative/large-magnitude operands (4 behavioral cases).
- 3 structural byte-extraction records (`f_eot_evict`, `f_eot_ctrl`,
  `f_eot_combine`), each: compile via `shdump --render`, extract fragment
  stage hex via `agxparse.py --stage fragment --extract-hex`, record
  presence/absence of `670e54` (tile_read) and `e70654`
  (frag_color_store) substrings.

Total per run: 20 behavioral + 3 structural = 23 records.

All values in `DST_CASES`/`COMBINE_CASES` are exactly representable in
IEEE-754 float32 (verified: integers, half-integers, and sums of at most a
few power-of-two fractions with no more than 24 significant bits), so the
Python-`repr()`-computed oracle and the GPU float32 readback are compared
for exact equality, not tolerance.

## 4. Environment (frozen)

```
git rev-parse HEAD (agx-re):       cf544b4dd1fb37047c7cfee6a70a0d1a87628666
git status --porcelain (agx-re):   dirty (concurrent sibling-experiment
                                    untracked dirs only; none touch this
                                    experiment's files -- see SUBAGENT_BRIEF
                                    "HEAD moving is not contamination")
mesa/ pinned revision:             3c4d3e46d19f2f4e951f3ae059543b03592f7944
                                    (materialized 87d02c34, EXP-0044 baseline)
Host:                              Apple M4, 10 GPU cores, macOS 26.6.2 (25G82)
Metal:                             Metal 4
Date frozen:                       2026-08-28T08:23:01Z (approx; see PROGRESS.md)
```

Source hashes (SHA-256, frozen at this pre-registration):

```
kernels/eot_construct.metal   2bf4863d0739ef2a7a76dc959c2fcc85aaf93cf7cf2a15c66f5e3525cd778831
harness/render_eot.m          48ea3a62b5b8c504e8313cb7e1578ac4713a0dabe7dcdf7052e0134804149178
harness/run.py                a68575f33dde1762d4b9af94d64cdb67333cb4cc8a2e1a65e38e33e8b103329a
harness/casematrix.py         a65d9a86662e5edad55dd6a2aeeba00ba7e8f33502dc3ce7439a43dee20939f6
```

(Two pre-freeze source revisions preceded this final frozen set, both caught by
the NON-RECORDED smoke gate before either official run id was spent -- see
`PROGRESS.md`: (1) `%.9g` stdout precision was insufficient to round-trip a
double for the largest-magnitude case, fixed to `%.17g`; (2) the original
`d4_near_fmax` used a decimal literal, `3.0e38`, that is not exactly
representable in float32, fixed to exact powers of two. Both fixes are
reflected in the hashes above, which are what the official runs below were
captured against.)

Pinned tool inputs (read-only use of `tools/*`, hashes match the live repo
copies at freeze time; compiled into this experiment's own `harness/`, never
edited in place):

```
tools/shdump/shdump.m         115e9f0e88a393b95b10545c63c140dc8c8fb7cd3f17c27f21506f7529f36dad
tools/shdump/agxparse.py      72911ee524fa1e327914445a0b38837b4a71e8525565a03f2cb7f520733c6a0f
```

Mesa reference files cited by `RESULTS.md` (PUBLIC, read-only, hashed for
audit; pinned mesa revision above):

```
mesa/include/drm-uapi/asahi_drm.h                69fe416b7294dfec4794217bd11379effd53caff4e86010bb803f1b34bdf5e89
mesa/src/asahi/lib/agx_bg_eot.c                   c8d9076cd0ae130e90e8aa740e654199b97a7cd5f148128e9ff045e76fe43894
mesa/src/asahi/lib/agx_bg_eot.h                   867b478d08f9b9c12096eca57e35006be3d54735fe23295ce4acc2c197180224
mesa/src/asahi/lib/agx_tilebuffer.h               52921ff09a45de63ba29be8a3929fef8351c38cd4af2912e8f7600dc8d38ffe3
mesa/src/gallium/drivers/asahi/agx_state.c        5015b75863202a170f8d6015eb82a76a70ecd4b92204894fa3d1886b1baa94ba
mesa/src/gallium/drivers/asahi/agx_pipe.c         e29b0c206bdadfa14de83c439526fef5f8d8650a3f7ae223aa2e8e945386d86e
mesa/src/gallium/drivers/asahi/agx_state.h        6d5e7f85849bce3c3f2e5569373a24f6c0d692217a8e493754298750b755e7ab
mesa/src/asahi/vulkan/hk_cmd_draw.c               ff89d7f8202785daacca5a43cc55b3148369f660d8a1e5c07ca2fdc4c9d300b6
mesa/src/asahi/vulkan/hk_queue.c                  8f528cdbfb9c8d44ba6a69bc99a7ca493ffc9def9649ef1d1110a6dd9d245fa0
mesa/src/asahi/genxml/cmdbuf.xml                  6bc10b31f5519584e28af65be046d35cae09dfa1fc94222bd11897f2cb1ad21a
mesa/src/asahi/compiler/agx_compile.c             1a5b056a18ffdd1fa6d3813129221e0ead2bf114c794844bbc14bdcd5ebc0c27
mesa/src/asahi/compiler/agx_opcodes.py            23d6d6312784a96e67aa9073deb55415c079b915899367c8b9a4075763f92446
mesa/src/asahi/lib/agx_device.h                   e6ba76e16b2aace0ebf8b1ff2348cb800ad6cc254cef633d490de5bc203bfda3
mesa/src/compiler/nir/nir_intrinsics.py           6a0b9d5e6123735918080736f793988da1284ec769a816ccdd606f8bc849f470
```

`agx_compile.c`/`agx_opcodes.py` are Mesa's compiler backend targeting an
earlier (M1/M2-class) AGX generation -- read here as PUBLIC cross-generation
context only (CLAUDE.md: PUBLIC sources "identify questions, terminology, or
the shape of a required interface"; Apple9 hardware values still require our
own live probing). No specific byte/opcode value from these two files is
promoted as an Apple9 fact anywhere in `RESULTS.md`.

## 5. Timeouts and safety

- Per-case (`render_eot`) hard timeout: 20 s (`subprocess.run(timeout=)`).
- Per structural build (`shdump`): 30 s. Per extract (`agxparse.py`): 15 s.
- One change per case (a single fragment function + a single `(dst, src)`
  pair per process). One process per case (no persistent-runner reuse).
- Target surface is 2x2 `RGBA32Float`, a single full-screen triangle, no
  compute dispatch, no atomics, no scratch/spill pressure -- minimal fault
  surface. No raw byte-splicing (see Section 2): the highest-risk technique
  in this project's toolkit is deliberately not used here.
- If the host wedges or behaves strangely: stop, mark this experiment
  BLOCKED in `PROGRESS.md`, do not attempt any tool-based recovery.

## 6. Gates (standing, this dispatch)

- `--selftest`: pure-Python unit checks of `analysis/verify.py`'s own
  parsing/oracle/comparison logic against hand-built fixture strings, no
  GPU required.
- `--seqtest`: checks `CAPTURE_CONTRACT.json`'s recorded `PRE_GPU` state
  predates `raw/<run01>/` which predates `raw/<run02>/` (directory
  existence + recorded timestamps), i.e. `PRE_GPU -> RUN01_PRESENT ->
  RUN02_PRESENT`.
- NON-RECORDED smoke gate: one full pass of `harness/run.py` into
  `work/smoke/` (discarded from evidence, not deleted, per project
  convention) BEFORE either official run id is spent.
- No nondeterministic field in byte-compared records: `wall_s` and
  `gputime_ns` are excluded from the cross-run byte-exact comparison;
  every other field (mode, case_id, dst, konst/src, result, expected,
  returncode, hex, contains_tile_read/frag_color_store) is compared
  byte-exact between run01 and run02.
- Fixtures from recorded reality: `analysis/verify.py --selftest`'s
  fixtures are literal copied lines from the NON-RECORDED smoke run's own
  `records.jsonl`, not hand-fabricated.
