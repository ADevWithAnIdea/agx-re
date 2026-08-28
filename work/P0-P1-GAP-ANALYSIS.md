# P0/P1 per-row gap analysis — what actually remains

**Author:** desk agent (no GPU work performed; no experiment run, no device touched).
**Date:** 2026-08-28. **Scope:** the sixteen rows of `docs/P0-P1-CLOSURE.md`
(P0.1–P0.8, P1.1–P1.8), all currently `OPEN`.
**Not a verdict.** This file records, per row, what is established, what is missing as a
testable question, what class of blocker holds it, the cheapest next step, and which of the
six closure rules in `CLAUDE.md` / `docs/P0-P1-CLOSURE.md` the row currently fails.
Marking a row `CLOSED` is the orchestrator's judgement, not this document's.

**Sources read:** `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`docs/evidence-classification.md`, `docs/P0-P1-CLOSURE.md`, `PROVENANCE.md`,
`APPLE9_RE_IMPLEMENTATION_GAPS.md`, `work/RESUME-STATE.md`, `work/GAPS-COVERAGE.md`,
`tools/agx-isa/validation.json`, `mesa/include/drm-uapi/asahi_drm.h`, and the `RESULTS.md`
of EXP-0076, 0082, 0083, 0084, 0085, 0090, 0093, 0106, 0107, 0110, 0112, 0114, 0116, 0117,
0120, 0121, 0122, 0123, 0124, 0125, 0126, 0127, 0128, 0130, 0131, 0132, 0133, 0134, 0136,
0137, 0139, 0140, 0141, 0144, 0146, 0147, 0148.

---

## 0. Reading guide

### 0.1 The three blocker classes

| class | meaning | correct response |
|---|---|---|
| **EVIDENCE** | a hardware/data question is genuinely unanswered and *is* answerable on the local M4 | dispatch an experiment |
| **DECISION** | the evidence is as complete as this host's envelope allows; what is missing is a ruling on what the row's acceptance bar means, or a scope ruling from the user | ask the user / orchestrator, do not dispatch |
| **PLATFORM** | structurally unreachable from macOS on this host, regardless of effort | record the bound, stop probing, hand to the kernel team |

### 0.2 The six closure rules (abbreviated as R1–R6 below)

1. value/behaviour **generated**, not merely decoded from a captured template;
2. complete authored probe / commands / raw observations / failures / analysis committed;
3. evidence chain recorded in `PROVENANCE.md`;
4. **normative `docs/`** carry exact fields, ranges, fallbacks, target status;
5. adversarial reproduction or a second method passes;
6. the relevant **userspace object independently generated and consumed** without a captured
   Apple template.

### 0.3 Three systemic findings that cut across every row

**(a) R4 is the most widely failed rule, and it is pure desk work.** A large share of the
last two days' results have a `PROVENANCE.md` row but have never been written into
`docs/`. Verified spot checks:

- `docs/` contains **no occurrence of `helper_program` at all** — P0.1 has no normative
  chapter anywhere in the deliverable.
- EXP-0126's `ppp_multisamplectl` round-half-up rule and the 1/32 ÷ 3/32 tie bisection
  appear **only** in `docs/P0-P1-CLOSURE.md` (a status board, not a normative doc) — not in
  `docs/cmdstream/`, not in `docs/mesa-userspace-requirements.md`.
- EXP-0137's `Model B` vs `Model C` barycentric result is **not** in `docs/isa/README.md`
  or `docs/isa/encoding-tables.md`.

**(b) R3 has seven concrete holes.** These experiments have committed `RESULTS.md` but
**no `PROVENANCE.md` row** (`grep -c` over `PROVENANCE.md`):

| experiment | row it serves | why the hole matters |
|---|---|---|
| `EXP-0107` (`e9a4fadc`) | P0.1 | the 454× scratch-pressure negative + the 261,728 B ceiling |
| `EXP-0125` (`53f5fff8`) | P0.1 | the third independent negative + the exact 261,740 B stage-uniform ceiling |
| `EXP-0110` (`0266f58c`) | P0.5 / P0.7 | CDM-vs-VDM relocation split, M4 state-packet reproduction |
| `EXP-0116` (`d5d8fbee`) | P0.5 / P0.7 | **the hand-built CDM link that real hardware followed** — the single strongest P0.5 result in the repo is unprovenanced |
| `EXP-0121` (`1143ec55`) | P0.6 | the whole OPT-01..11 NIR contract |
| `EXP-0122` (`f2b8ef66`) | P1.5 | VM/sparse conventions, the 2^43 wrap |
| `EXP-0123` (`1143ec55`) | P1.8 | line/point/polygon rules and the hard-limit table |

**(c) "A18 replication" appears as a residual on all sixteen rows and is a DECISION, not an
evidence gap.** `CLAUDE.md` suspends A18 work by user directive; the closure board says
A18 replication "is suspended, not a closure gate". But
`APPLE9_RE_IMPLEMENTATION_GAPS.md`'s whole-handoff gate item 10 still demands "Independent
G16G and G17P evidence matrices". Those two documents disagree. **Until the user rules on
which text governs, no row can be honestly declared closed against the gate as written.**
This is the single highest-leverage decision on the board — it affects all sixteen rows
simultaneously.

---

# P0 rows

---

## P0.1 — Userspace scratch allocator and VS/FS/CS helper-program ABI (`DRV-UAPI-01`)

### 1. What is now established

- **Three independent, well-controlled negatives, at three different points of the process
  lifecycle**, all on M4/G16G:
  - `EXP-0041` — 0–576 B declared scratch, narrow allowlisted BO comparison: no
    helper/scratch record.
  - `EXP-0107` (`e9a4fadc`) — the same negative at **~454× the pressure**: 0 → **261,728 B**
    declared per-thread scratch, CS/VS/FS, 64 → **4,194,304** dispatched threads, up to 1,000
    genuine spill/fill passes, 30 cases × 2 byte-identical captures, with a *widened*
    DATA-TRACE boundary (content of **every** BO the process registers, not four allowlisted
    roles). `bo_count`(27)/`bo_total_bytes`(2,428,032) are **identical at every K level**;
    the compound case (K=49,152 @ 1,048,576 threads and K=65,430 @ 4,194,304) is
    **byte-identical in footprint** to the K=1,536 case at the same grid — footprint tracks
    grid only, never declared scratch.
  - `EXP-0125` (`53f5fff8`) — the negative at **init time, before the first compile**: the
    address-free BO inventory is byte-identical between a never-spilling and a
    98,320 B/thread-spilling process at **all six** lifecycle checkpoints
    (`DEVICE_CREATED` → `POST_DISPATCH`), in both gated runs. The code window
    (`0x10000000000`, exactly `0x10000` B) is present and constant-size **from
    `DEVICE_CREATED` onward**. Selector 5 ("shared pages") was **never called** in either
    variant, either run.
- **A precise, HW-validated, stage-uniform compile-time ceiling.** `EXP-0125` bisected to
  4-byte (one array element) resolution, independently for CS, VS and FS, all converging on
  the identical boundary: **last success K=65,431 = 261,740 B declared; first failure
  K=65,432 = 261,744 B.** Failure mode is a clean `nil` from
  `newComputePipelineStateWithFunction` / `newRenderPipelineStateWithDescriptor` with the
  public string `"Compute function exceeds available stack space"` — no fault, no hang, no
  corruption. This is **≈2.003× below Mesa's own `AGX_MAX_SCRATCH_DWORDS = 131,072`**
  (a constant Mesa itself flags "Unknown if this goes higher"); the residual ~0.1–0.3% is
  reported, not resolved.
- **A real, characterized concurrent-exhaustion failure mode.** `EXP-0125` H4: `n_queues ≤ 4`
  is always clean (12/12 trials, both runs); above that, **silent numerical corruption**
  (`checksum_mismatch` with a clean Metal status and finite output), never a graceful
  rejection. The onset threshold is **session-variable** (run01 first failed at 8, run02 was
  clean through 16 and first failed at 32) — reported as the finding, not smoothed.
- **The public UAPI itself explains the negatives.** `mesa/include/drm-uapi/asahi_drm.h:883-887`:
  the helper program's "most important role is dynamically allocating scratch/stack memory
  for individual subgroups, by partitioning **a static allocation shared for the whole
  device**. It is supplied by userspace via `drm_asahi_helper_program` and **internally
  dispatched by the hardware** as needed." A device-wide static allocation dispatched by
  hardware is exactly what a per-process, pressure-correlated userspace trace cannot see.

### 2. What is still missing (as testable questions)

- Q1. Does `drm_asahi_helper_program.binary`'s bottom-bits tag use the same
  `agx_usc_addr`-relative 32-bit offset + low-bit tag convention as `drm_asahi_bg_eot.usc`?
  (Answerable only against a real firmware consumer.)
- Q2. What does `helper.cfg` bit 16 do on Apple9 hardware? Mesa sets it iff
  `preamble_uses_scratch`; no Apple9 observation exists for any bit.
- Q3. Which special registers does the helper read `data` through, and what are the
  NEXT/ACK/NACK doorbell encodings?
- Q4. What is the scratch header / per-core block-list / block-descriptor / bucket /
  max-active-subgroups / address-shift geometry?
- Q5. **Answerable on M4 today:** is the ~261,740 B compile-time ceiling a
  per-core-pool-derived number? A 1.10 TB naive `declared × total_threads` allocation cannot
  exist on a 16 GB host and the workload completes correctly, so *something* pools it — but
  the pool's geometry is not observed.
- Q6. **Answerable on M4 today:** is `EXP-0125` H4's silent corruption above `n_queues≈8`
  actually scratch-pool contention, or contention over an unrelated shared GPU resource?
  A control that raises `n_queues` with a **provably non-spilling** kernel discriminates
  these in one experiment.

### 3. Blocker class

**PLATFORM for Q1–Q4; EVIDENCE for Q5–Q6; DECISION for the row as a whole.**

Q1–Q4 concern a structure that (per the UAPI's own text) is a device-static allocation
dispatched by hardware, supplied through a Linux ioctl that does not exist on this host.
Three methodologically different probes have now returned the same negative. `EXP-0125`'s
own conclusion is the honest one: *the scratch/helper mechanism is not observable from
userspace's IOKit resource-map boundary on macOS*, and a Linux implementer "should not
expect a captured Apple template for this UAPI struct."

**The row should stop reading as though more probing will close it.** What it needs is a
ruling on whether P0.1 closes as (a) a *constructed-from-first-principles* specification
against the UAPI struct plus the hardware-measured envelope (ceiling, failure modes,
concurrency limit) that this project *has* produced, or (b) it is formally reclassified as a
kernel-team handoff item and removed from the P0 closure set. Option (a) is defensible and
the evidence is already in hand; option (b) is cheaper. Either way it is the user's call.

### 4. Cheapest next step

**Desk, hours, no GPU:** write the P0.1 chapter — there is currently *nothing* in `docs/`
about helper/scratch. It should state: the three negatives and their exact tested ranges;
the exact ceiling (261,740 B, stage-uniform, HW-VALIDATED, M4); the failure mode taxonomy
(clean compile-time rejection is the only one below the ceiling; silent corruption above
`n_queues≈8` with a session-variable onset); the safe driver fallback (`n_queues ≤ 4` tested
clean; validate declared scratch against 261,740 B); and an explicit "unobservable from
macOS userspace — hand to kernel team" boundary statement for the `binary`/`cfg`/`data`
fields. Add the two missing `PROVENANCE.md` rows for `EXP-0107` and `EXP-0125` in the same
pass. **Then put the DECISION above to the user.**

### 5. Closure rules currently failed

- **R1** — nothing about the helper protocol is generated; the ceiling and failure modes are
  measured envelope facts, not a generated helper program.
- **R3** — `EXP-0107` and `EXP-0125` have **no `PROVENANCE.md` row at all**.
- **R4** — `docs/` has no helper/scratch chapter (`helper_program` appears zero times).
- **R6** — no helper program or scratch BO has been generated and consumed.
- R2 and R5 pass (both experiments have full artifact trees, two-run byte-exact gates, and
  `EXP-0125` is itself the second method for `EXP-0107`'s negative).

---

## P0.2 — Graphics shader selection and code-BO handoff (`DRV-UAPI-02`)

### 1. What is now established

- **The VS token derivation rule is SOLVED and HW-VALIDATED** (`EXP-0127`, `8195a230`):
  `token(n) = 0x2c0 + 0x80·n` for the n-th pipeline-state object bound in a queue's
  lifetime, **independent of the compiled VS code's size** — proven by an 8-function
  interleaved size sweep (`[0,48,4,40,12,32,20,24]` unrolled FMAs) where every step after the
  first is exactly `0x80` regardless of neighbour size. Verified against ~35 checkpoints for
  n=1..505. `n=0` is a distinguished non-formula case (`0x1c0`, a `0x100`-short anomaly,
  reproduced in every sweep and pilot). The field is **at least 32 bits**, refuting the
  earlier "8-bit token" framing.
- **A precise capacity boundary with base relocation.** At the **507th bind (n=506)** the
  token jumps `0xffc0 → 0x2b0040`; a brand-new `0x40000`-byte BO appears at raw VA
  `0x2b0000` (never seen at any earlier checkpoint), and `token(506) − 0x2b0000 = 0x40` —
  the same "record header + 0x40" pattern EXP-0042 found. The `+0x80` rule then resumes
  exactly against the **new** base for n=507..649. All 650 draws completed; no fault, no hang.
- **`0x58000+0x08` is NOT the FS code selector — HW-VALIDATED negative.** Splicing one
  pipeline's live pool record with another *real, freshly discovered* FS's own natural
  selector value, strictly pre-commit, lands the write (`post_selector` confirms) and
  completes cleanly (`status=4`) but renders **the originally bound FS** in all four tested
  directions (red↔green, red↔blue). This directly refutes EXP-0042's implicit reading.
- **The field is nevertheless real, hardware/firmware-dereferenced state:** out-of-range
  values (`S_GREEN+0x2000000`, `|0x80000000`, `0xffffffff`) reliably `PageFault`. Discovered
  natural values this run: `S_RED=0x4c0`, `S_GREEN=0x880`, `S_BLUE=0xcc0`.
- **Code-window relocation category: INVARIANT.** The code BO VA (`0x10000000000`) and the
  VDM/FF-state family (`0x18000`/`0x58000`) are unchanged under 64 MiB of client padding and
  under 4 extra queues — the same perturbations that moved EXP-0110's CDM chain by
  `+0x4080000`. Two distinct relocation axes now documented: invariant under allocator
  pressure, but **demand-relocating** once ~`0x10000` bytes of container capacity is exhausted.
- **A genuine hardware nondeterminism discovered by the cross-run gate:** near-miss selector
  values (`+4`, `−1`, `−2` from a natural selector) render **differently across runs** while
  reporting a clean `status=4` every time; no single offset is the reliable flip point across
  capture pairs. Root cause `UNKNOWN`, honestly excluded from the gate.
- **`usc_exec_base` mapping: NOT demonstrated, and now positively complicated.** The
  capacity-boundary growth region sits at raw VA `0x2b0000` — **far below** `0x10000000000`
  and not reachable by an unsigned `addr − shader_base` subtraction the way Mesa's own
  `agx_usc_addr()` computes it.

### 2. What is still missing (as testable questions)

- Q1. **Where is the true FS code-selection decision made?** Concretely: does splicing a
  candidate field inside the **VDM draw record** (rather than the `0x58000` pool) redirect
  which FS executes? `EXP-0127` never touched the VDM draw record.
- Q2. **Does the VS token actually select?** `EXP-0127` fully characterized the token's
  *derivation* but **never spliced it**. Bind pipeline A, overwrite its VDM `+0x20` field
  with pipeline B's own token, observe which VS runs. This is the direct VS analogue of the
  FS redirect that produced the load-bearing negative.
- Q3. What do the other ~0x70 bytes of the 0x80-byte auxiliary record do? Only its existence
  and the `+0x40` payload address were ever probed.
- Q4. Does the 506-creation capacity boundary generalize across VS code sizes, to FS-side
  accumulation (only 3 FS objects were ever live), and to mixed VS+FS in one queue?
- Q5. Is the `0x2b0000` growth region reachable through the same base register as the main
  code window, or through a per-stage `USC_EXEC_BASE_TA`-style register? (The pinned UAPI
  structurally allows three independent-but-usually-tied registers.)

### 3. Blocker class

**EVIDENCE**, cleanly — with one **PLATFORM** tail. Q1–Q4 are all answerable on the local M4
with the technique `EXP-0127` already built and validated (live pre-commit pool/record
splice). Only the *literal* `usc_exec_base` end-to-end demonstration (Q5's confirmation half)
requires a Linux `DRM_IOCTL_ASAHI_SUBMIT`, which does not exist on this host.

### 4. Cheapest next step

**Q2 — the VS-side redirect.** It reuses `EXP-0127`'s existing harness, its existing
`vstoken` discovery path, and its existing splice mechanism; the only new code is writing
into the VDM `+0x20` bind field instead of the `0x58000+0x08` pool field. It is a
change-one-variable extension of a validated method, and it is the natural falsification
target given the FS redirect's negative: if the VS token *does* redirect, then selection is
per-stage and asymmetric, which is a major structural fact; if it does *not*, then both
per-stage selector candidates are eliminated and the search moves to the VDM draw record
(Q1) with the field space much narrower.

### 5. Closure rules currently failed

- **R1** — the selection *mechanism* is not generated; a token value can be predicted from
  the derivation rule but has never been used to select anything.
- **R4** — `docs/cmdstream/README.md` still carries EXP-0042's superseded implicit reading
  of `0x58000+0x08`; EXP-0127's HW-VALIDATED refutation has not been promoted.
- **R5** — the racy misalignment behaviour is unresolved (`UNKNOWN` root cause), so the
  boundary map is only partially adversarially reproduced.
- **R6** — no code container has been placed at an unclaimed address and selected.
- R2 passes; R3 passes (`PROVENANCE.md` row present for EXP-0127).

---

## P0.3 — Apple9 value for every existing render/compute UAPI field (`DRV-UAPI-03`)

### 1. What is now established

- **All 65 leaves of `EXP-0045`'s field matrix now carry an explicit four-stage chain**
  (userspace derivation → UAPI value → kernel/firmware marshaling → observed Apple9
  behaviour), each with a `asahi_drm.h` file:line citation, an evidence label and a status
  (`EXP-0126`, `b0a0a1b0`): **7 MAPPED / 58 PARTIAL / 0 undeterminable within the 65.**
- **`ppp_multisamplectl` is SETTLED.** The captured sample-position BO is **not** a separate
  submit parameter — `ppp_multisamplectl` **is** the packed value. New M4 evidence:
  exhaustive confirmation of the full 1/16 grid (16/16 X points, 8/8 Y points reproduce
  exactly at both sample counts 2 and 4), and the **first exact tie bisection on any target**:
  `0.03124→0.0`, `0.03125→0.0625`, `0.09374→0.0625`, `0.09375→0.125` — **round-half-up**.
  Top-boundary behaviour: `0.94→0.9375`, but **`0.99→1.0`** (i.e. nibble 16, outside the
  nominal 4-bit range — **no ceiling clamp** at this representation stage); `1.0` and `-0.001`
  fire a **process-terminating assertion**, not a catchable `NSError`.
- **`render.samples` is exactly `{1,2,4}`**, boundary-tested both ways over
  `{0,1,2,3,4,5,6,7,8,16}`; every unsupported count aborts with an assertion naming the count.
- **A real UAPI documentation discrepancy found and flagged, not silently resolved:**
  `isp_merge_upper_x/y`'s header comment says `tan(60°) * width`; Mesa's code computes
  `fui(tan_60 / cs->cr.width)` — **division**. Neither formula is Apple9-validated here.
- **`isp_bgobjvals` clarified beyond the header:** Mesa ORs the raw stencil clear byte into a
  fixed **`0x300`** baseline, not "bottom 8 bits" alone.
- **`compute.cdm_ctrl_stream_end` for the chained case:** Mesa's own reference driver uses a
  hardcoded placeholder `65536 /* XXX */`; this project's 732-records-per-CDM-segment constant
  (`EXP-0043`, reproduced by `EXP-0049`/`0110`/`0116`) is better-grounded than upstream's
  placeholder — but no replacement `end` formula has been derived either.
- **`EXP-0055`'s `0x58000+0x36` candidate is now named**: convergent identification as
  "Fragment control.Depth bias enable, bit 17" (Mesa's PUBLIC `cmdbuf.xml` bit layout, anchored
  by `EXP-0110`'s independently observed `0x58000+0x34` bit 18 = "Stencil test enable").
  Explicitly **not** spliced, so it stays `DATA-TRACE-VALIDATED`/`STRUCTURAL`.
- **The `command_timestamp_frequency_hz` item is correctly bounded as
  UNDETERMINABLE-FROM-USERSPACE** — it is a kernel-supplied read-only output; macOS's own GPU
  timestamps are already software-calibrated nanoseconds, not raw ticks, so no macOS
  observation can stand in for it.

### 2. What is still missing (as testable questions)

- Q1. **Answerable on M4:** where do the `isp_scissor_base` / `isp_dbias_base` arrays live?
  The 16-byte Scissor and 12-byte Depth-bias record shapes are now known from PUBLIC source;
  **no BO has ever been searched using those shapes as a template.** `0x58000`/`0x68000` are
  ruled out (`EXP-0054`/`0055`), which is a bounded negative, not an untried search.
- Q2. **Answerable on M4:** does `isp_merge_upper_x/y` multiply or divide? A splice feeding a
  value that is wrong under exactly one of the two formulas, observing triangle-merge
  behaviour, discriminates them.
- Q3. **Answerable on M4:** `render.layers` has **no dedicated experiment**. (`EXP-0126`
  corrected the field matrix's `EXP-0028` citation as a mismatch — that experiment is
  texture-array layer *stride*, not render-pass layer *count*.)
- Q4. Is `EXP-0055`'s bit 17 causally the depth-bias enable? A single-bit splice with the rest
  of the word held constant answers it.
- Q5. What is the numeric value of `zls_ctrl`, `ppp_ctrl`, `isp_zls_pixels`, and the four
  BG/EOT `rsrc_spec` words on Apple9?

### 3. Blocker class

**Mixed — and the split is the useful part.**

- **PLATFORM** for Q5 and for `command_timestamp_frequency_hz`: these are *submit-parameter-only,
  firmware-marshaled registers*. They are absent from every userspace BO by construction
  (`docs/kernel-interface.md` §4.3/§6). This is a structural property of the macOS boundary,
  not a probing shortfall. Roughly the entire "no macOS observation point" cluster inside the
  58 PARTIALs falls here.
- **EVIDENCE** for Q1–Q4: four concrete, cheap, M4-answerable questions.
- **DECISION** on what the row's `MAPPED` bar means for a firmware-private register whose
  *layout* is fully known from PUBLIC source and whose *userspace derivation* is fully
  specified, but whose *Apple9 value* can never be observed from this host. If the answer is
  "PUBLIC layout + specified derivation + a recorded structural-absence proof = MAPPED for a
  firmware-private register", a large fraction of the 58 flips today. If it is not, P0.3
  cannot close on this host at all.

### 4. Cheapest next step

**Q1 — the scissor/depth-bias array template search.** It is a pure re-analysis of BO content
this project already knows how to capture: scan every registered BO for the 16-byte
`MaxX/MinX u16, MaxY/MinY u16, MinZ/MaxZ f32` and 12-byte `bias/slope/clamp f32` shapes while
sweeping exactly the three depth-bias inputs `EXP-0054` already swept. It reuses the
`EXP-0055` harness wholesale, changes only the search target, and would either locate two
UAPI-mandatory arrays or produce a much stronger bounded negative than "not at
`0x58000`/`0x68000`". Q2 and Q4 fold naturally into the same dispatch.

### 5. Closure rules currently failed

- **R1** — 58 of 65 leaves rest on PUBLIC Mesa-derived shape, not on a generated Apple9 value.
- **R4** — the settled `ppp_multisamplectl` grid/rounding/boundary rules and the `render.samples`
  range live **only in `EXP-0126/RESULTS.md` and the status board**; no normative `docs/`
  chapter carries them.
- **R5** — the bit-17 identification is convergent but unspliced; no second method.
- **R6** — no render/compute submit record has been independently generated and consumed.
- R2 and R3 pass.

---

## P0.4 — BG/EOT/partial-BG/partial-EOT programs (`DRV-UAPI-04`)

### 1. What is now established

- **The core EOT operation is CONSTRUCTED and HW-VALIDATED on M4** (`EXP-0130`, `5c677b72`):
  `f_eot_combine` — authored entirely from our own MSL — reads the tilebuffer via
  `[[color(0)]]`, computes `dst*2.0 + src`, and writes the attachment. Behaviourally exact
  against a host float32 oracle on 4/4 boundary `(dst, src)` pairs in **both** gated runs
  (3·2+1=7; −10·2+1=−19; 1000000·2+2=2000002; 0.5·2+2=3), with the 8-case `dst` sweep
  (zero, ±2^126, ±2^-120, signed zero, large mixed-sign fractional) exact for `f_eot_evict`.
- **Structurally verified, not just behaviourally.** `f_eot_combine`'s 120 extracted bytes
  contain `670e5404...` at internal offset 12 and `...e7065404...` near the end — byte-exact
  matches to `EXP-0029`'s `tile_read` (`0x67 0x0e 0x54`) and `frag_color_store`
  (`0xe7 0x06 0x54`) encodings, **reproduced fresh on M4** (EXP-0029 was A18-only) from an
  independently authored kernel.
- **A decisive negative with real driver consequence:** the pure-identity shape
  (`return dst;`) compiles to **16 bytes containing neither `tile_read` nor
  `frag_color_store`** — the compiler elides both and defers correctness entirely to the
  render pass's fixed-function load/store actions. **A driver author cannot use a
  passthrough shape to validate the tilebuffer path.** Independently reproduces `EXP-0117`'s
  blend-descriptor elision from a completely different code path.
- **A paired control proves it isn't coincidence:** `f_eot_ctrl` (no `[[color(n)]]`
  declaration) returns its `konst` sentinel **invariant across all 8 different clear colours**;
  `f_eot_evict`/`f_eot_combine` track `dst` exactly.
- **`partial_bg` and `partial_eot` are precisely specified with file:line citations.**
  `partial_bg` = `bg` **plus one unconditional override**: `load |= partial_render;`
  (`agx_state.c:3090`, `hk_cmd_draw.c:310`) — every present attachment must load on resume,
  overriding whatever the app's `loadOp` said. `partial_eot` = `eot` with
  `should_store |= partial_render;` (`hk_cmd_draw.c:299`); gallium literally assigns the same
  compiled program to both `eot` and `partial_eot`. Neither driver references anything
  TVB/tiler-heap-specific — consistent with `EXP-0120`'s finding that the UAPI has no such field.
- **`EXP-0120` (`24cec78d`) bounds partial render's observability**: no distinguishable
  multi-pass/reload mechanism engages for tile-concentrated geometry from 1 to **20,000,000**
  triangles — timing is a single clean linear fit (R²>0.998, both runs) with *decreasing*
  marginal cost, and the BO size-multiset and IOKit selector histogram are byte-identical
  across the whole sweep.
- **`EXP-0147` (uncommitted working tree) makes `tile_read` and `tile_read_mrt` EMITTABLE** —
  all 7 / 6 fields promoted, with the tilebuffer read proven live on the observed pixel by a
  clear-colour control and a litmus-power probe. This directly feeds P0.4.

### 2. What is still missing (as testable questions)

- Q1. What do the `usc` pointer's low tag bits mean? Mesa ORs `| 4` for eot/partial_bg/partial_eot
  and `| 4` or `| 8` for bg depending on `nr_cbufs >= 4`; **Mesa's own genxml does not name
  the field.** Not decoded here, not guessed.
- Q2. Is `rsrc_spec`'s bit layout on Apple9 actually Mesa's M1/M2-class `Counts` word
  (`cmdbuf.xml:406-416`), or a shifted/reordered Apple9-specific packing? Currently PUBLIC
  hypothesis only. Also undecoded: gallium's `unknown=0xFFFF` set only for **non-store** (bg)
  pipelines.
- Q3. **Does a fused `store_block_agx`-class tile-to-memory instruction exist on Apple9, and
  is it reachable from any public Metal path?** Every store this project has ever extracted
  is the ordinary `frag_color_store`/`image_write` family sourced from an explicit ALU
  register. `EXP-0130` explicitly labels this `UNKNOWN`, **not** a negative claim.
  The one untried public surface is tile shading (`imageblock<T>`,
  `MTLTileRenderPipelineDescriptor`, `dispatchThreadsPerTile:`).
- Q4. `AGX_BG_LOAD` as such — a `txf` against a bindless image built from the destination
  attachment's own memory — has never been HW-validated *in the BG role* (only cited as
  "ordinary texture sampling").
- Q5. Can a real `drm_asahi_bg_eot.usc`/`rsrc_spec` pair be populated and consumed by firmware?

### 3. Blocker class

**PLATFORM for Q5 — definitively, and checked directly.** `EXP-0130`'s `raw/host_check.json`
records: `uname` reports Darwin (`RELEASE_ARM64_T8132`); **`/dev/dri` does not exist**; **no
`asahi`- or `drm`-named entry in `kextstat`**. `struct drm_asahi_bg_eot` is consumed by
`DRM_IOCTL_ASAHI_SUBMIT` on a `drm_asahi`-backed kernel. **There is categorically no way,
from any userspace program on this machine, to populate that struct and have real
kernel/firmware consume it** — independent of anything about this project's tooling. A second,
independent ground also blocks it: P0.5 is OPEN, so even a same-OS alternative path does not
exist.

**This row must stop reading as though more probing closes it.** Its board text still lists
`usc`/`rsrc_spec` field values as an open item alongside genuinely-open items, which
misrepresents the situation.

Q1, Q2, Q4 are **EVIDENCE** but constrained: Q1/Q2 are only fully answerable against a real
consumer (PLATFORM), though Q2's Apple9-side half could be attacked by locating the four
`rsrc_spec` words in a captured render submission if such a location exists. Q3 is **EVIDENCE**
and fully answerable on M4 today.

**DECISION required:** does P0.4 close on (program content constructed + HW-validated) +
(UAPI field shape specified at the citation level with a recorded platform-absence proof)?
If yes, this row is close. If closure requires firmware consuming the struct, it can never
close on this host and should be reclassified.

### 4. Cheapest next step

**Q3 — the tile-shading probe.** `EXP-0130` explicitly deferred it as "attempted only as time
permits", and it is the single named public Metal surface that could reach the fused
tile-to-memory eviction op. It is a bounded new-harness experiment
(`MTLTileRenderPipelineDescriptor` + `dispatchThreadsPerTile:` + imageblock layout), it turns
a documented `UNKNOWN` into a first-class positive or negative, and `EXP-O2D` already
established the general mechanism on A18 so the shape is known. Cheaper still, and worth
doing first: **land `EXP-0147`** (already captured, `tile_read` emittable) and write the P0.4
program-side chapter into `docs/pipeline/`.

### 5. Closure rules currently failed

- **R1** — the *program* is generated (passes); the *UAPI record* is not, and cannot be here.
- **R4** — the constructed BG/EOT program spec, the `partial_bg`/`partial_eot` override rules,
  and the compiler-elision warning are not in `docs/pipeline/` or `docs/cmdstream/`.
- **R5** — `EXP-0130` §6 item 8 explicitly names adversarial byte-splicing of the constructed
  `tile_read`/`frag_color_store` sequence as out of scope; the paired control substitutes at a
  weaker tier.
- **R6** — the render/attachment object is constructed only through Metal's own render pass;
  the `drm_asahi_bg_eot` record is never generated.
- R2 and R3 pass.

---

## P0.5 — Complete relocatable VDM/CDM/PPP/USC command and state packing (`DRV-CMD-01`)

### 1. What is now established

- **A hand-built link value was followed by real silicon — HW-VALIDATED** (`EXP-0116`,
  `d5d8fbee`). `skip_seg1`: `seg0`'s tail link, computed fresh each run from that run's own
  just-discovered `seg2` address (never hand-copied), redirected execution so that `seg1`'s
  732 dispatches provably never ran (`buf_MID` still holds the pre-encode sentinel
  `0x5eed1000`) while `seg2`'s 36 unmodified records ran correctly (`buf_A = 0xc0000023`,
  `seg2`'s own last authored tag, computed in advance). Byte-identical across two gated runs.
- **A 17-case link-target boundary map, with a finite-resource table.** Highlights:
  `tag` must be exactly `0x20` for CDM→CDM (`0x00` and VDM's own `0x80` both `PageFault`);
  target offsets `+0/+1/+2` from a valid head succeed while `+4`/`+8` fault; a link may start
  execution **mid-segment**; `2^40` faults but **`2^44` and `2^46` silently ALIAS back to a
  valid segment** (the most dangerous mode found — a wrong-but-legal pointer executes with no
  error); the field's own ceiling `0x00ffffffffffffff` with `tag=0xff` produces a genuine
  **GPU HANG**, not a fault (contained, no host wedge); a cross-command-buffer link into an
  uncommitted chain faults even though the bytes are correct and correctly shaped.
- **Two hardware nondeterminisms the cross-run gate itself discovered:** how much of a
  *faulted* command buffer's earlier legitimate work is visible in memory is **racy**; and
  hang-class recovery labels flip between `ErrorHang` and `ErrorInnocentVictim` for the same
  case. Both were used to correct the schema; neither raw capture was repaired.
- **Relocation behaviour splits by structure kind** (`EXP-0110`, `0266f58c`): the CDM chain is
  **client-heap-relative** (moves uniformly by `+0x4080000` under 64 MiB of padding) and
  queue-invariant; the VDM/FF-state chain is **invariant under both**. First evidence
  distinguishing relocation *by structure kind*.
- **Link grammar generalizes:** `target = ((hi32 & 0xffffff) << 32) | lo32`, `tag = hi32 >> 24`
  now confirmed against **four distinct CDM targets** (two of them obtained under a real 64 MiB
  relocation) and one new VDM target. **Segment capacity 732 records is uniform across first
  and continuation segments** (`732·0x2c = 0x7dd0` in an `0x8000` BO). VDM first-segment
  capacity 603 for the tested draw shape; VDM continuation uniformity untested.
- **The A18 state-packet schema reproduces byte-exact on M4** — EXP-0019's entire FF-state pool
  bit layout and VDM bind-pair template for depth/stencil/blend/cull, first M4 confirmation.
  One newly observed field: `0x58000+0x34` bit 18, set in an all-off baseline and cleared the
  instant depth *or* stencil is configured.
- **A precise negative on code selection (`EXP-0116` task 3):** a hybrid CDM record with only
  the `+0x08` code/uniform-window pointer swapped verbatim between two back-to-back kernels
  (`0x00007970` vs `0x00007973` — a difference of 3) executed as **neither** kernel and
  faulted. The 3-unit delta is far too small to be a shifted absolute code pointer; the field
  reads as a per-dispatch preamble/uniform-context slot index valid only in its original
  position.

### 2. What is still missing (as testable questions)

- Q1. Where exactly is the link-target alias boundary? Bounded only to "somewhere in
  `(2^40, 2^44]`" by two points. Since aliasing is **silent**, this is a safety-critical range.
- Q2. Can a link legally reach memory made resident by an **earlier, separately committed**
  submission (as opposed to an uncommitted one)?
- Q3. Does a **VDM-native** link splice work, mirroring `EXP-0116`'s CDM method? Only
  `tag_vdm` on a CDM chain was tested, as a negative cross-tag probe.
- Q4. Can a whole CDM/VDM **record** (not just its link) be independently constructed and
  executed? Every record used so far is Metal-authored, relocated at most.
- Q5. What are the complete PPP and USC schemas? Barriers, calls, indirect packets, and the
  remaining `0x58000` sub-blocks EXP-0019 left opaque (`+0x39` constant, full write-mask bit
  isolation, provoking vertex, MRT) are untouched.
- Q6. What is the true encoding rule of the CDM `+0x08` field — segment-relative offset,
  monotonic per-encoder counter, or something else?
- Q7. Does *any* perturbation move the VDM/FF-state base? `EXP-0110` tried two and got two
  negatives; "queue-context-fixed" is a hypothesis, not a proven mechanism.

### 3. Blocker class

**EVIDENCE, overwhelmingly.** Every one of Q1–Q7 is answerable on the local M4 with the
pre-commit CPU-write technique `EXP-0116` validated. Only the "Linux mapping" tail of the
board's text is PLATFORM. This is the row where more probing genuinely does close things —
and it is also the row with the most remaining surface (the whole PPP/USC schema plus an
independent packer).

### 4. Cheapest next step

**Q3 + Q6 in one dispatch.** The VDM link splice is a direct copy of `EXP-0116`'s validated
CDM method against a structure whose grammar (`tag = 0x80`, same split-address transform) is
already confirmed at two targets — near-zero new risk, and it converts VDM link generation
from `DATA-TRACE-VALIDATED` to `HW-VALIDATED`. Q6 needs only a controlled differential across
**3+ kernels at systematically varied encode positions** (rather than two back-to-back
dispatches) to discriminate counter-vs-offset, and it unblocks the P0.7 half of `EXP-0116`'s
negative at the same time.

### 5. Closure rules currently failed

- **R1** — the *link* is generated (passes, HW-VALIDATED); the *record*, the PPP/USC state
  packets, and the whole packer are not.
- **R3** — `EXP-0110` and `EXP-0116` have **no `PROVENANCE.md` row**. The strongest P0.5
  result in the repository is currently outside the audit chain.
- **R4** — the link-target finite-resource table, the silent-alias hazard, the relocation
  split, and the newly observed `0x58000+0x34` bit 18 are not in `docs/cmdstream/README.md`.
- **R6** — no complete command/state stream has been independently packed and consumed.
- R2 and R5 pass (17-case boundary matrix, three capture pairs, two disclosed schema
  corrections, retained raw).

---

## P0.6 — Compiler-ready ISA and opcode property model (`DRV-ISA-01`)

### 1. What is now established

- **The row is now directly measurable**, which is itself the biggest change.
  `tools/agx-isa/validation.json` (`generated: 2026-08-28`, spec
  `docs/evidence-classification.md`) labels every field:

  | | count | share |
  |---|---:|---:|
  | `hardware-run` | 239 | 23.1% |
  | `isolated-byte-diff` | 80 | 7.7% |
  | **emitter-grade total** | **319 / 1036** | **30.8%** |
  | `corpus-correlation` | 204 | 19.7% |
  | `tokenization-only` | 244 | 23.6% |
  | `single-template-inference` | 16 | 1.5% |
  | `untested` | 253 | 24.4% |
  | **emittable instructions** | **21 / 171** | **12.3%** |
  | decodable-not-yet-emittable | 150 | |

  Emittable: `device_load`, `device_store`, `frame_prologue`, `get_sr`, `ibitcount`,
  `if_push`, `iunary`, `link_save_restore`, `mov_imm`, `psel`, `reg_move_c0`, `reg_move_c1`,
  `reg_move_c2var`, `reg_move_c9`, `reg_move_cb`, `sel`, `spill_frame_marker`, `stop`,
  `tex_addr_setup`, `threadgroup_barrier`, `uniform_mov`.
  **This number is already stale-low:** `EXP-0147` (7 more instructions incl. `matrix_mac`
  and `tile_read`) and `EXP-0144` (44 of 51 pack/convert fields) are captured but
  **uncommitted**, and `validation.json`'s last commit is `a7261f64` (EXP-0140).
- **The largest single synthesis blocker is gone** (`EXP-0141`, `5a9df52b`).
  `device_load.dst_lo`/`dst_ext9` carry **no register information at all**. To land a load in
  register R: `extmode = 2·R` (**bit 0 a don't-care**), `dst_lo = 1` exactly, `dst_ext9` bit 0
  = 1 — three constrained bits across the nine those fields span. Exhaustive: all 4 `dst_lo`
  values × all 128 `dst_ext9` values at four independent target registers (r3, r7, r20, r33),
  plus the full 512-value 2-D product at r7; the accepted set (64 of 512) is **identical at
  every target register** and factorises as `{dst_lo==1} × {dst_ext9 odd}`. `extmode` 0..127
  all match, 128..255 silently zero.
- **`ibfe.offset` is LITERAL while `ibfe.width` is mod-32** — opposite out-of-range rules on
  one instruction, and **the hardware does not implement NIR's offset masking** (literal
  model 64/64 vs mod-32 32/64) (`EXP-0139`, `7d2ba093`; 73 of 137 IALU fields to emitter
  grade, 129,839 dispatches, 0 hangs).
- **A native single-instruction 64-bit integer ADD that Apple's compiler never emits**
  (`EXP-0146`, `f36b2ac4`): flipping only byte0 bit 7 (`0x1f`→`0x9f`) of the compiled
  `ulong` subtract gives a 64-bit ADD with carry. `ilogic` reaches **all 16** two-input
  boolean functions (refining EXP-0102's "10 of 16"); `carry_gen` is a two-operand compare,
  not marker+source; all six `I64-*` questionnaire items answered.
- **The instruction-length rule was wrong and is fixed** (`EXP-0148`, `2c93efcb`): the
  low-nibble-9 rule selected 6/8/10/12 from `byte+4`, which for the **compact** forms is the
  *next instruction's leader byte*. `falu2_ext8b` was **never an instruction** — 45/146
  firings → **0/0**. Four corrections validated: round-trip stays 302/302, corpus files
  tokenizing end-to-end **803 → 832**, strict leftover 395,390 → 389,368 bytes, resync gaps
  4,902 → 4,548 (30 files fixed, 1 broken). `op04_len8` stays honestly OPEN — six candidate
  rules all measured worse.
- **11 more instructions became emittable in one capture** (`EXP-0140`, `a7261f64`), including
  `mov_imm`, `get_sr`, `sel`, `psel`, `uniform_mov`, five `reg_move` variants and `if_push`.
  `get_sr`'s `dp_width`/`dp_marker` are **not** don't-cares: exact acceptance masks
  `(v & 0xD3) == 0x10` and `(v & 0xE6) == 0x06`; wrong values usually return a wrong answer
  **without a fault**. `sel.body` is three located byte-fields, not one opaque 24-bit raw.
- **The generation proof is strong at the DAG level** (`EXP-0112`, `d5d8fbee`): a generator
  built purely from documented previously-HW-VALIDATED rules synthesized **100 random
  dataflow DAGs** (2–35 nodes, 44/100 requiring genuine physical register reuse, up to 13 of
  14 pool registers simultaneously live) — **140/140 `expect_match=True` cases passed in both
  runs, 21/21 `expect_match=False` behaved exactly as pre-registered**, zero hand-tuning.
  Register-boundary sweep: `extmode = 2·R` confirmed dense for R=0..63; **silently aliases to
  `r(R mod 64)` for R∈[64,112]**, faults at 126/127.
- **Four hand-built programs** (`EXP-0090`, `32016991`): P1 arithmetic chain, P2 memory round
  trip, P3 real loop + if/else → select, 24/24 against an independent Python oracle in both
  runs; P4 (register-pressure/move) reported as a first-class negative.
- **The whole Part-II questionnaire is 181 items, of which ~145 now carry a committed verdict**
  (`work/GAPS-COVERAGE.md`, itself now slightly stale-low: `I64-01..06` are answered by
  EXP-0146 and P2-01/03/05 by EXP-0134/0135/0136 since it was written).
- **The NIR contract is answered for OPT-01..11** (`EXP-0121`, `1143ec55`): `lower_fdiv=false`,
  `lower_fpow=false` (naive `exp2(y*log2(x))` returns NaN for 22/53 edge cases; `pow`'s body
  is ~27× larger), `has_fused_comp_and_csel=true` (one `isel8` covers FP32/I32/U32 × 6
  conditions, 825/825), `has_ldexp` **not supported** as tested, and
  **`has_atomic_load_store` must be FALSE** — OPT-10 is NO (a plain fenced load does not
  reliably observe a cross-thread write: 300/300 iterations never completed) even though
  OPT-11 is YES.

### 2. What is still missing (as testable questions)

- Q1. **717 of 1036 fields are not emitter-grade** (253 `untested`, 244 `tokenization-only`,
  204 `corpus-correlation`, 16 single-template). **150 of 171 instructions are decodable but
  not emittable.** Which specific fields block the highest-value families?
- Q2. `EXP-0139` names the shape of what remains: **44 of its 64 still-blocked fields are
  operand selectors or compare/condition selectors** in the `isel*`/`icmpsel`/`imad`/`iminmax`
  families. A single-carrier splice can prove such a field is live but cannot establish its
  **value → register-number mapping**, because every wrong value points at a register the
  carrier never seeded. **Does a seeded-register carrier per family close them?** (The
  `iadd2`/`ibitcount` arms show it does for those two.)
- Q3. `falu2.mod_lo` — the single field blocking the ISA's most-used instruction
  (`EXP-0138`, effectively fresh; pilot already found `mod_lo` bit 1 = "srcB reads the
  UNIFORM register file").
- Q4. Does the generator still work **without copying anything verbatim**? `EXP-0112`'s
  generator produced its 100 correct DAGs only by copying `device_load.dst_lo`/`dst_ext9`
  from a compiled shader. `EXP-0141` has now replaced that with a rule. **Re-running the
  generator with the rule substituted for the copy is the direct R1/R6 test.**
- Q5. `tg_addr_compute`: **an unresolved A18↔M4 divergence.** `EXP-M4-14` (A18) found byte0's
  high nibble live with **both** `0x1c` and `0xfc` reproducing the baseline. On M4, of all 256
  values **only `0x1c`** works; `0xfc` does not reproduce. Byte+1 accepts exactly 32 of 256
  (`{v : v&0x03==2 and v&0x10==0}`); bytes +2..+5 are inert over all 256 values each.
  **`EXP-0141` therefore keeps the EMITTABLE VETO on this instruction**, correctly. Whether
  the divergence is a device difference or a carrier/method difference is **UNKNOWN** and, per
  the A18 hands-off directive, currently untestable.
- Q6. `op04_len8`'s length rule (six candidates all measured worse than the status quo).
- Q7. 27 Part-II items remain unanswered — notably `MEM-18`/`MEM-19` (the uniform/constant-
  program slot-population path), `TEX-01/12/19/20/21/22/28`, `TRIG-01/02`, `SFU-04`,
  `ENC-03/15/16`.

### 3. Blocker class

**EVIDENCE, and the largest volume of it on the board.** The emit wave is the right
instrument and is measurably working (5 → 21 emittable instructions, 169 → 319 emitter-grade
fields in one wave). Three of the ten emit experiments have **not yet run** (`EXP-0142` TEX,
`EXP-0143` FRAG+SIMD, `EXP-0145` bf16/half) and one (`EXP-0138` FALU) is effectively fresh;
two more (`EXP-0144`, `EXP-0147`) are captured but unmerged.

One **PLATFORM/DECISION** tail: Q5 cannot be resolved without touching the A18, which the
user has forbidden. It should be recorded as a permanent `UNKNOWN` with the M4-only rule
documented, or the user must re-scope A18.

One **DECISION**: the row's closure bar. `EXP-0090`'s synthesis acceptance test says
"DRV-ISA-01 cannot be closed regardless of decode coverage" until hand-built programs pass —
they have (24/24). But 150 of 171 instructions remain non-emittable. **Does P0.6 close on
"every initially supported NIR family is emittable" (a much smaller set than 171), or on the
full instruction census?** `APPLE9_RE_IMPLEMENTATION_GAPS.md` says "every initial compiler
family", which is the former; the board's 171-instruction metric implies the latter. The
user should pick.

### 4. Cheapest next step

**Q4 — re-run `EXP-0112`'s generator with `EXP-0141`'s `device_load` destination rule
substituted for the verbatim copy.** It is one afternoon of harness work against an existing,
fully validated 161-case generator, and it is the **direct** test of closure rules 1 and 6 for
this row: it converts "100 correct programs, one field copied from Apple's compiler output"
into "100 correct programs, nothing copied". No new hardware technique, no new risk, and it
retires the single most-cited caveat on the project's central synthesis claim.

Second cheapest: **land `EXP-0144` and `EXP-0147`** and re-run `work/merge_verdicts.py` +
`validate_labels.py` + `roundtrip_test.py` — pure desk work that moves the headline number
by roughly seven instructions and ~70 fields.

### 5. Closure rules currently failed

- **R1** — passes for the DAG generator and the four hand-built programs; fails for 150 of
  171 instructions, and is caveated for `device_load` until Q4 is done.
- **R3** — `EXP-0121` (the whole NIR contract) has **no `PROVENANCE.md` row**.
- **R4** — `docs/isa/encoding-tables.md` and `docs/isa/agx3.xml` are generated from
  `db.json` + `validation.json` and **need regeneration** after EXP-0148's DB changes
  (3 descriptors added, 2 deleted) and every subsequent label merge.
- **R6** — a *whole shader container* has never been independently generated and consumed
  (that is P0.7's half; the ISA half is at "programs spliced into a compiler-produced
  container").
- R2 and R5 pass strongly (`FIELD-SWEEP-PROTOCOL.md` §7 mitigations, two-run gates,
  pre-registered falsifiers, majority-of-N adjudication).

---

## P0.7 — Shader container, extent, metadata and resource-spec generation (`DRV-SHADER-01`)

### 1. What is now established

- **The hardware-consumer proof EXP-0042 named as missing now exists — HW-VALIDATED**
  (`EXP-0131`, `ec55e03e`). A single byte written into the **LIVE, post-pipeline-creation**
  code BO — `main+0x06`, the `frag_color_pack` `val` field, located with `tools/agx-isa`, not
  copied from any Apple record — changes the rendered pixel `4080ffff → 4040ffff` on a fresh
  draw reusing the **same already-created `MTLRenderPipelineState`**. The adjacent byte
  (`main+0x07`, `src_present_mask`) produces **no** pixel change, so the effect is
  field-specific rather than incidental corruption. A second `iotrace` snapshot confirms the
  written byte persisted. Both runs byte-identical (`02_results.jsonl` sha256
  `946b5f56…204eed9e`), while `02_results_addrs.jsonl` legitimately differs.
- **The container framing rule is independently reproduced** from a fresh, differently-shaped
  compile: `header (u32 record_size @ +0x00, zero-pad to +0x3f)` → `constant_program @ +0x40`
  → `main` → zero pad to `record_size` → next record's header at `header + record_size`.
- **A firmware-consumed vs. archive-bookkeeping split with mutation evidence per field.**
  `main` bytes: firmware/hardware-consumed. Header `record_size`: **not re-consulted at
  per-draw code-fetch time** (both `0x00000000` and `0xFFFFFFFF` render clean) but **is** read
  by macOS userspace at teardown (`0x0` reproducibly SIGBUSes the harness process at dealloc;
  `0xFFFFFFFF` does not — a disclosed asymmetry).
- **EXP-0042's "opaque following 0x80-byte record" is reclassified**: it is simply the start
  of the **next code record** (Metal packs records back-to-back, and EXP-0042's
  `header + record_size + 0x40` arithmetic lands `0x40` into whatever follows). Independently
  corroborated: `corrupt_next_record_header`'s `write_before` read `0x00000100` — an exact
  match to EXP-0042's own "A VS: header 0x400, size 0x100" entry, obtained without consulting
  that table.
- **`truncate_main_early` gives useful ABI evidence:** replacing `main+0x0a..+0x35` with an
  immediate `stop` produces exactly the render pass's own `clearColor`, not garbage — a
  fragment program that never reaches its color-store step is **not** implicitly given a
  default output.
- **Metadata/resource split** (`EXP-0110`): the live CDM launch record is **byte-identical
  across a 0..8 bound-buffer sweep**; buffer count instead governs the argument-buffer table's
  entry count and the preamble's length. The argument table tracks **compiler-visible usage,
  not the API binding count** (`live_kbuf1` binds one real buffer, table shows 0 entries).
  Four newly surveyed `__GPU_METADATA` fields: `1` (`=2·nbuf`), `3` (`=8·nbuf`) for
  `nbuf ≥ 2`, and `38`/`42` (both constant `8`, present iff any texture is declared) — with an
  honestly reported unresolved inconsistency in the texture sweep.

### 2. What is still missing (as testable questions)

- Q1. **Can a full container be built from scratch — our own header + our own
  `constant_program` + our own from-scratch `main` — placed at unclaimed code-BO space, and
  selected?** `EXP-0131` deliberately deferred the selection half to `EXP-0127`, which then
  **refuted** the selector it was going to use. This is the row's central open item and it is
  now **blocked on P0.2's Q1/Q2**.
- Q2. What is the CDM `+0x08` code/uniform-window pointer's true encoding rule?
  (`EXP-0116` task 3's precise negative: a verbatim copy across two records, relocated, does
  not execute as either kernel — it faults.)
- Q3. Does the resource-specifier portion exist in the code record for a **resource-bearing**
  shader? `EXP-0131`'s shader deliberately declares zero textures/samplers/buffers.
- Q4. Does `constant_program` mutation change behaviour? Untested — `render_min`'s is
  degenerate filler (a single `stop` plus `0600` repeat).
- Q5. Where else, if anywhere, do metadata fields `1`/`3`/`38`/`42` surface in a live
  structure? Only the CDM record and a coarse preamble-length proxy were checked; the USC BO
  (`0x10000130000` family) was not.

### 3. Blocker class

**EVIDENCE, with a hard sequencing dependency on P0.2.** Q1 cannot be attempted until the
true selection mechanism is known — the code-BO is proven writable and proven
hardware-consumed, so the *placement* half is solved; only *selection* blocks it. Q2–Q5 are
independently answerable today.

### 4. Cheapest next step

**Q3 — repeat `EXP-0131`'s mutation matrix on a resource-bearing shader.** It reuses the
entire validated harness (live code-BO splice, two-run gate, address exclusion) and changes
only the authored MSL to declare and actually use one texture, one sampler and one buffer.
It answers the whole "resource specifiers" clause of `DRV-SHADER-01` that `EXP-0131`
explicitly left "entirely open", at near-zero incremental risk. Q4 rides along free (author a
shader with a non-degenerate `constant_program`).

### 5. Closure rules currently failed

- **R1** — the container is *mutated*, never generated; `EXP-0131` states this plainly
  ("never assembles and places a wholly independent instruction sequence").
- **R3** — `EXP-0110` and `EXP-0116`, which carry the metadata split and the `+0x08` negative,
  have **no `PROVENANCE.md` row**.
- **R4** — the container framing rule, the firmware-vs-archive field table, and the
  truncate/`stop` ABI fact are not in `docs/isa/` or `docs/cmdstream/`.
- **R6** — no shader container has been independently generated and consumed.
- R2 and R5 pass.

---

## P0.8 — Complete VS/FS/CS ABI, shader linking and programmable epilogs (`DRV-ABI-01`)

### 1. What is now established

**All nine of `EXP-0117`'s enumerated DRV-ABI-01 sub-items are now addressed**
(`EXP-0117` `53f5fff8`, 148 cases × 2 byte-identical; `EXP-0137` `e2390303`, 29 cases × 2
byte-identical):

1. **Programmable-blend epilog — CLOSED, HW-VALIDATED across the full advertised surface.**
   All 19 `MTLBlendFactor` values (23/23 including dst-role checks) and all 5
   `MTLBlendOperation` values match the standard blend equation to float precision. The blend
   constant is **not** clamped to `[0,1]`. NaN/±Inf propagate bit-exact through Add.
   `blendingEnabled=YES` on an integer format is a **fatal process abort**, not an error.
   sRGB attachments blend **in linear space**. Structurally: the compiler constant-folds the
   blend equation at pipeline-creation time and emits `tile_read` **only** when the
   destination's actual value is needed. Attachment count 1..8 all render independently;
   index 8 is a hard fatal API ceiling.
2. **Logic ops constructed and validated** — AND/OR/XOR/INVERT via `tile_read` + ALU +
   `frag_color_store`, a Vulkan `VK_LOGIC_OP_*`-class capability the fixed-function blend
   descriptor cannot express, bit-exact on 8/8 constructed cases including all-zero/all-one.
3. **CS sysvals — CLOSED by citation** to `EXP-0092` (`96f9dade`).
4. **FS output ordering — CLOSED.** Source order is provably irrelevant (two functions in
   opposite order compile **byte-identical**). A depth-test failure suppresses color **and**
   stencil writes, and the stencil op that fires is exactly the one configured — verified in
   both directions as a paired control.
5. **The barycentric anomaly is RESOLVED** (`EXP-0137`). The trigger is **the fragment shader
   reading `[[position]]`** — not output count, not an extra varying, not the harness. Full
   factorial: `count3_const`, `count3_vary`, `attach3ctrl` all read
   `(0.24348931, 0.13476601, 0.62174469)`, identical to base; `pos2`, `posread_noout`, `pos3`
   all flip to `(0.48697862, 0.26953202, 0.24348938)`. Structurally, the baseline compiles
   `barycentric_coord` to only **2 `iter` ops and 0 `fspecial`** — perspective *numerators*
   with a sum-to-one complement and **no normalize step**; position-touching variants gain 2
   coefficient slots and ≥1 `fspecial` (the W-denominator + reciprocal). Numerically confirmed
   in **two independent triangle/`w` geometries**: no-position matches `Model B`
   (`b_i = l_i/w_i`, `b_2 = 1−b_0−b_1`), position-touching matches `Model C`
   (fully normalized perspective-correct). **Driver consequence:** a backend must
   *unconditionally* emit the full numerator + W-denominator + reciprocal + normalize
   sequence. There is **no MSL escape hatch** — `[[barycentric_coord, center_perspective]]`
   and `center_no_perspective` both compile byte-for-byte identically to the incomplete form.
   Convention: `.x/.y/.z` follow **emission (assembly) order** (`vid%3==0,1,2`), cross-checked
   against `primitive_id`'s independently established convention.
6. **`primitive_id` — CLOSED.** Tracks assembly order, not index values; **resets to 0 per
   instance**.
7. **MSAA centroid-vs-sample — CLOSED.** Within one partially covered pixel (N=4) the two live
   invocations report identical `centroid` but measurably different `sample` values.
   `[[sample_mask]]` = exactly `popcount(mask & ((1<<N)-1))/N`, bits ≥N silently inert.
8. **CALL-ABI — CLOSED.** `byte+6` is uniformly `0x54` across six call topologies (resolving
   EXP-0109's flagged `0x54`-vs-`0x56` discrepancy); nesting depth 1..128 all correct, no
   depth limit in range. Framing: `frame_marker` (`43 00 00 01`) before, `call`, then
   `pop_reconverge` (`0f 06 04 02 00 00`).
9. **Stencil overflow — CLOSED.** Values >255 **truncate** to low 8 bits (256→0, 257→1,
   4294967295→255); `int` is compile-rejected.
10. **Split prolog/epilog register-crossing — CONSTRUCTED and validated** (`EXP-0137` §2).
    Two compiler regimes both observed and reported: a single-call-site fragment "epilog"
    was **inlined** despite `[[clang::noinline]]` (2 regions, 0 `call`s), while a vertex
    prolog and a 2-call-site compute helper were kept genuinely out-of-line (**3 Mach-O
    regions** with real local symbols and real `call` instructions). This **refines** — does
    not reverse — EXP-0109's "no third region ever appears". Arguments land in **raw
    destination registers 0xa..0xe (r10–r14)** for 5 scalar arguments, an exact extension of
    EXP-0035's "consecutive from r10". Out-of-range fetch across a call boundary reads
    **exactly zero**, matching the inline model. `[[color(0)]]` on a non-entry parameter is
    **syntactically accepted and semantically inert** — a disclosed refutation of the
    experiment's own pre-registered expectation.

### 2. What is still missing (as testable questions)

- Q1. What is the **exact physical register numbering of a multi-component CALL return**?
  Structurally confirmed (4 post-call retrieval ops for a float4 vs 1 for a scalar) but the
  retrieval uses a different move class (`reg_move_c9`/`rtq_state_move`) than the argument
  path, and no splice pinned the numbers. `EXP-0137` flags it `STRUCTURAL`, DRV-ISA-01
  territory.
- Q2. Does the CALL boundary compose correctly under genuine **register-pressure/spill**
  conditions for a prolog/epilog-shaped callee? Cited from EXP-0035's general case, not
  re-stress-tested.
- Q3. Per-sample depth/stencil MSAA suppression under a **split** epilog — `EXP-0117` §3.3
  flagged the general case `PARTIAL`.
- Q4. Are **format-conversion epilogs** independently generated across the advertised formats?
  The board's own closure text asks for "independently generated blend/**logic**/**conversion**
  epilogs across advertised formats". Blend (23/23) and logic (8/8) are done; the *conversion*
  half is currently covered by P1.2's format work, not by a generated epilog.

### 3. Blocker class

**DECISION first, then a small amount of EVIDENCE.**

Every named sub-item is addressed and `EXP-0137` says so explicitly, while correctly noting
that flipping the board row "requires an orchestrator-level audit across the full evidence
set (this experiment plus EXP-0109/0117/0029/0031/0035/0092) and a `PROVENANCE.md` update,
which is the orchestrator's job". **The row is currently blocked on that audit, not on more
probing.** Q1–Q4 are genuine but narrow evidence items, and Q1 is arguably DRV-ISA-01's.

### 4. Cheapest next step

**The orchestrator audit + docs promotion.** Specifically: write the barycentric `Model B` /
`Model C` finding and the "always emit the full perspective sequence" rule into
`docs/isa/README.md` (it appears nowhere in `docs/` today); write the prolog/epilog seam
contract (r10-consecutive arguments, resource merging is a pipeline-wide table fixed before
codegen, `[[color(n)]]`-on-callee is inert) into `docs/isa/` or a new ABI chapter; add the
blend/logic epilog spec to `docs/pipeline/`. Then decide Q4's scope. **No GPU work required.**

### 5. Closure rules currently failed

- **R4** — the dominant failure. Essentially none of `EXP-0117`/`EXP-0137`'s results have
  reached `docs/`; `grep` finds no `Model B`/perspective-numerator text in `docs/isa/`.
- **R6** — a programmable epilog has been *constructed as MSL and executed*, but never
  generated as raw bytes and consumed independently of Metal's pipeline object.
- R1 (constructed epilogs, hand-authored call topologies), R2, R3, R5 (two-run byte-exact,
  paired controls, factorial design, disclosed refutations) all pass.

**This is the closest row on the board to closable.**

---

# P1 rows

---

## P1.1 — Complete PBE and render-attachment structures (`DRV-PBE-01`)

### 1. What is now established

- **Depth/stencil slot reuse — CONFIRMED and generalized, HW-VALIDATED** (`EXP-0132`,
  `633cd06b`, 16 cases × 2 runs, 15/16 byte-exact + 1 tolerated content-read flake).
  Depth and stencil populate the **same k-indexed 0x20-byte MRT descriptor array** as color,
  at `k=ncolor` (depth) and `k=ncolor+1` (stencil) — not fixed k=1/k=2. The adversarial
  `ncolor=2` case places depth at k=2 and stencil at k=3 exactly as predicted. Depth prefix
  `628800f8017c0008` is **byte-identical** to EXP-0108's independently captured value under a
  freshly built, race-fixed harness; stencil is distinct (`224068f9017c0008`). Memoryless
  depth **still populates k=1**, with byte 7 flipping `0x08 → 0x00`.
- **Layer/mip selection is NOT in the per-attachment record — HW-VALIDATED negative.**
  The k=0 LOAD record is byte-identical across slices 0/1/3 of an `arrayLength=4` target and
  across levels 0/2 of a `mipCount=3` target. The **only** difference between `mipCount=1` and
  `mipCount=3` is **word1 bit 26** — the exact bit `format-table.md` §5 already documents as
  the *sampled-texture* descriptor's "mipmapped" flag. New positive structural finding: the
  PBE/render-target descriptor and the sampled descriptor share that flag convention.
- **Two genuinely different silent failure modes at the boundaries.** `slice = arrayLength`
  is **silently accepted** (`cb_status=4`) and **destructively zeroes slice 0's prior
  content** while other slices keep their canary — not a modular wraparound (that would have
  produced the clear colour, not zero). `level = mipCount` is a **pure no-op** — no valid
  level shows any effect. A driver must validate both itself; the API does not.
- **MSAA resolve targets take the next free k slot in BOTH arrays.** For
  `MultisampleResolve` and `StoreAndMultisampleResolve` identically: k=0 LOAD has type nibble
  `4` (2DMultisample); **k=0 STORE is entirely zero**; k=1 LOAD **and** k=1 STORE are both
  populated with type nibble `2`. Generalizes the "next free k" rule to a third attachment kind.
- **`attachment-slot-b` NOT reproduced** — the fixed VA `0x10000120000` never appeared as a
  present named role in any of 16 cases, despite exercising every axis EXP-0108 reported it
  correlating with. Reported as a genuine negative and correctly interpreted: the safe
  conclusion is that the VA is **not a stable, harness-independent address**, not that the
  role does not exist.

### 2. What is still missing (as testable questions)

- Q1. **Where does layer/mip selection actually live?** `EXP-0132`'s own successor spec is
  precise: full-**content** capture (not just presence/size) of `vdm-command-state` and
  `fixed-function-render-state` across the same `l1..l4`/`m1..m3` matrix, diffed the same way.
- Q2. What is `attachment-slot-b`'s role? Needs EXP-0108's VA-free region-count-delta method
  applied to this harness's full inventory.
- Q3. What are the access/control 8-byte word, coherency bits, rotation/mode, reserved-value
  enumeration and program-ID ownership? Not located.
- Q4. Does resolve take `k=ncolor` and push depth/stencil to `k=ncolor+1/+2`, or do
  depth/stencil take priority? **Untested combination.**
- Q5. Does the 3-segment 0x300-stride LOAD/RENDER/STORE chain exist on M4 at all? Still only
  A18-observed (EXP-G1b); `EXP-0132` adds a second independent M4 confirmation that M4 does
  **not** reach it even for the simplest single-attachment case.
- Q6. Compressed/ASTC/BC attachments, cube/cube-array, sparse residency, and layered rendering
  via `[[render_target_array_index]]` (only the host-side `.slice`/`.level` path was exercised).

### 3. Blocker class

**EVIDENCE, and unusually well-specified.** `EXP-0132` wrote its own successor spec for Q1 and
Q2 with the exact schema change required. Nothing here is platform-blocked.

### 4. Cheapest next step

**Q1 — widen `EXP-0132`'s frozen schema to deep-capture `vdm-command-state` and
`fixed-function-render-state`, and re-run the identical `l1..l4`/`m1..m3` matrix.** It is a
schema change plus a re-run of a harness that already exists, already passes five standing
gates, and already produces byte-exact cross-run records. It answers a UAPI-mandatory question
(`render.layers` is also a P0.3 PARTIAL leaf with no dedicated experiment), and Q4 costs one
extra case in the same matrix.

### 5. Closure rules currently failed

- **R1** — no PBE/attachment descriptor has been generated; every record is Metal-authored and
  observed.
- **R4** — the consolidated field map in `EXP-0132` §3 has not been promoted into
  `docs/descriptors/README.md` or `docs/pipeline/README.md`.
- **R6** — no render/attachment object has been independently generated and consumed.
- R2, R3, R5 pass (adversarial `ncolor=2`, two independent slice/level values, two store-action
  variants, two-run byte-exact gate).

---

## P1.2 — Per-format API capability and conversion table (`DRV-FMT-01`)

### 1. What is now established

- **The full public `MTLPixelFormat` enum × 11 capability axes: 138 × 11 = 1518 cells, every
  cell exercised, byte-exact across two runs** (`EXP-0133`, `d2a65b04`; 1548 cases per run,
  each axis its own process). Every non-`ok` cell is explained by exactly four structural
  rules, verified to zero mismatches against a full pre-capture precheck.
- **Eligibility is an unconditional `abort()`, not a soft query.** There is no public API to
  ask "is format X renderable" without either already knowing or crashing the process — **a
  driver must carry a static allowlist and cannot safely probe.** This is a first-class
  driver-facing finding.
- **`Depth24Unorm_Stencil8` (255) and `X24_Stencil8` (262) are not valid pixel formats on this
  device at all** — bare `newTextureWithDescriptor:` aborts before any usage check, despite
  `API_AVAILABLE` annotations implying general availability.
- **Rounding rules are NOT uniform across widths.** `unorm16` ties round **DOWN**
  (`1.5/65535 → 0x0001`, `2.5/65535 → 0x0002`, non-tie control `5.9/65535 → 6`), the
  **opposite** of `unorm8`'s round-half-**up** (`EXP-0079`, `84851b4f`: `2.5/255 → 0x03`).
  Cross-checked inside one 4-channel store, so it is not a single-channel artifact.
- **snorm is symmetric at both widths:** `round(c·127)` at 8-bit (`−1.0 → 0x81`, refuting the
  asymmetric mapping) and `round(clamp(c,−1,1)·32767)` at 16-bit (`−1.0 → 0x8001`).
- **Reduced-float store narrowing TRUNCATES TOWARD ZERO** (fp16/fp11/fp10/RGB9E5), refuting
  round-to-nearest-even, with a positive-direction probe refuting round-away-from-zero
  (`EXP-0079`). **Normalized-integer and reduced-float stores therefore use different
  rounding rules on the same path.**
- **sRGB encode is bit-exact to the IEC 61966-2-1 reference on compute `access::write`**
  (0.0031308 → `0x0a`, 0.5 → `0xbc`, 0.95 → `0xf9`) — refuting "compute writes bypass sRGB".
  Typed-read **decode** lands within ~0.03–0.1% relative but **not** bit-exact — consistent
  with a hardware polynomial approximation; the exact curve is `UNKNOWN`.
- **`Depth32Float_Stencil8` aspects are independently addressable with zero cross-contamination.**
- **Capability-envelope divergences from Metal's documentation**, all hardware-verified:
  all 76 compressed-family formats accept `storage_read` **and** `storage_write` (construction
  and dispatch only — content not verified, explicitly disclosed); all 8 deprecated PVRTC
  formats behave like every other compressed family; `BGR10_XR`/`BGRA10_XR` are fully
  general-purpose; **21 of 22 integer-kind formats support `texture2d` atomics** (broader than
  prior `R32Uint`-only evidence); integer linear filtering is **not rejected at any stage**.
- **Layout:** `minimumLinearTextureAlignment` is a uniform **16 bytes** across every tested bpp
  class; `bytesPerRow` must still be `≥ width·bpp` rounded up to that granularity (a hard
  Metal abort otherwise). Compressed/depth/stencil/YUV formats abort the alignment query itself.
- **Compression interaction is bounded** (`EXP-0134`, `2e398db0`): `ShaderWrite`,
  `PixelFormatView`, or a linear layout each **independently** disable lossless compression —
  so a first driver can ship correct with compression off at no correctness cost, and
  `EXP-0133`'s own results are not confounded (none of its textures were compression-eligible).
- **RGB32 is re-confirmed absent** by a second independent method (full enum enumeration vs.
  EXP-0095's texel-buffer probing).

### 2. What is still missing (as testable questions)

- Q1. Bit-exact decode arithmetic for the **76 compressed formats** beyond BC1's two
  solid-color probes. This is a real per-family effort: BC2–7, BC6H, ETC2/EAC, ASTC block
  modes each need their own authored encoder/decoder oracle. **BC1's two candidate 565→8-bit
  expansion formulas remain undiscriminated** because both probes saturate their channels.
- Q2. **Content verification** for the `renderable`/`blendable`/`msaa`/`resolve`/`depth_stencil`
  axes — all 138×5 of those cells are command-buffer-completion-only, no attachment readback.
  Same for compressed `storage_read`/`storage_write`.
- Q3. What does integer linear filtering actually **return** for non-uniform content —
  nearest-fallback or fabricated interpolation? Only "not rejected" is established (the probed
  texture was zero-filled).
- Q4. What is the exact sRGB decode approximation and its error bound?
- Q5. Swizzle and pack/unpack behaviour beyond `format-table.md` §3's channel-arrangement /
  numtype orthogonality.
- Q6. Everything is 2D-level-0-only: mips beyond level 0, array layers, cube faces, 1D/3D.

### 3. Blocker class

**EVIDENCE, all of it, and all of it answerable on M4.** No platform limitation touches this
row. Q1 is the only genuinely large item; Q2–Q6 are moderate.

### 4. Cheapest next step

**Q2 — add readback to the five completion-only axes.** `EXP-0133`'s harness already renders,
blends, resolves and depth-tests for every one of these cells; it just does not read anything
back (a deliberate choice to keep each process minimal against the three hard-abort classes).
Adding a small readback to the 55 renderable / 36 blendable / 55 msaa / 55 resolve / 5
depth-stencil `ok` cells converts a large block of `STRUCTURAL` cells into `HW-VALIDATED` ones
without any new technique. Q3 rides along (upload a non-uniform pattern to the R32Uint probe).

### 5. Closure rules currently failed

- **R1** — capability results are generated (own MSL, own harness — passes); the compressed
  decode rules are not established at all.
- **R4** — `docs/descriptors/format-table.md` needs the unorm16-rounds-down rule, the
  truncate-toward-zero reduced-float rule, the static-allowlist requirement, and the
  divergence list.
- R2, R3, R5, R6 substantially pass (three retained quarantined attempts fully disclosed, two
  gated runs byte-exact, formats independently constructed).

**Note on process:** `EXP-0133`'s quarantined attempt 3 was killed by a `git_revision`
cross-run gate — the exact `EXP-0082` landmine `SUBAGENT_BRIEF.md` already documents. It
happened anyway. Worth a harness-template fix, not just a doc note.

---

## P1.3 — Texture/image ISA breadth and edge behaviour (`DRV-TEX-01` + Part II `TEX-*`)

### 1. What is now established

- **All 28 `TEX-*` questionnaire items have a recorded disposition** (`EXP-0106`, `2858c20f`;
  56 cases × 2 runs byte-identical, 40 match / 9 abort-confirmed / 7 rejection-confirmed /
  **0 deviation, 0 unexpected**). 21 answered; 7 explicitly deferred with named successors.
- **`EXP-0114` (`72c2dde8`)** closes TEX-15, TEX-16's raw-splice half, and EXP-0094's
  gradient-operand register field (49 cases × 2, byte-identical, zero faults).
  **A first-class corrected premise:** the texture-read `op+4` selector is **neither** the MSL
  binding index **nor** a compacted use-order index — a 128-declared/3-read shader compiles to
  `op4_sequence: [0, 128, 0]`, i.e. the first and third reads share a value while addressing
  different textures. **`op+4` is a short-lived compiler-reused register/uniform-slot
  reference, not a per-resource identifier.**
- **The LOD ABI is exact** (`EXP-0094`, `6d3ad2ef`):
  `effective_LOD = clamp(clamp(base_LOD + bias, lodMinClamp, lodMaxClamp), 0, mipCount−1)`,
  exact over 26 cases including signed zero, subnormals, ±Inf, NaN and clamp-order interaction.
  `bias(NaN) → mip 0` but `gradient(NaN/Inf) → mip 8`.
- **The texture/image dimension-format matrix is closed for tested scope** (`EXP-0095`,
  `47954e44`): the texel-buffer ceiling is `2^28` and **texel-size-INDEPENDENT** (falsifying
  the addendum's own formula); fetch/read returns zero while sample/gather CLAMPs at an
  illegal layer; the image table is 128 entries (8 for read_write/atomic); **bindless has no
  mirroring**, unlike EXP-0083's buffer slots.
- **`texture2d` atomics work on 21 of 22 integer formats** (`EXP-0133`), broader than prior
  `texture_buffer`/argument-buffer evidence.
- **Sampler filter/address behaviour** is bounded by `EXP-0063`/`EXP-0066` at the public API
  level.

### 2. What is still missing (as testable questions)

- Q1. **What is the TRUE 0–127 texture selector?** `EXP-0114`'s own successor spec names it:
  decode the 4-byte, byte0-low-nibble-`0xb` instruction immediately preceding each texture-read
  bundle, using a differential pair with a **single** live texture at two distinct
  `[[texture(N)]]` indices (removing the register-reuse confound), then splice-validate.
- Q2. **Can raw sampler-descriptor fields beyond Metal's clamps be injected?** `EXP-0136`
  (`2e2bc21a`) proved **anisotropy works natively to at least 128×** — Metal's 16× cap is pure
  software — by patching the live descriptor-pool entry. The remaining untested raw fields:
  the 3-bit aniso field holding 5/6/7, the 7-bit lodMax field above 112 (14.0), address codes
  4/6/7, border code 3, and the **MSL 4.0 per-sampler `bias` state field** whose bit location
  is undecoded. The named method: locate the **sampler** side of the per-stage direct-binding
  table (the texture side was proven reachable in `EXP-0016`; the sampler side was found
  unreachable only via the *explicit argument-buffer* path in `EXP-M4-08`, which is a
  different mechanism).
- Q3. TEX-01 — does a native `txp` projective-divide form exist? Needs `op+2` opcode-space
  fuzzing beyond every compiler-reachable value.
- Q4. TEX-12 sparse-texel residency; TEX-19/20 bindless texture ceiling at 1,000,000;
  TEX-21/22 bindless sampler ceiling at 499,999/500,001 (prior evidence is **A18-only**,
  EXP-O2B, never M4-validated).
- Q5. Are texture instructions **emittable**? `EXP-0142` (TEX emit sweep, `tex_sample`
  coordinate + result registers, 7 instructions / 46 blocking fields) **has not been run** —
  its directory has harness and kernels but no `PROGRESS.md` content and no `RESULTS.md`.

### 3. Blocker class

**EVIDENCE.** Every question is answerable on M4. Q2's sampler-table location is the one with
a real chance of failing (the argument-buffer path already failed once), but the direct
`[[sampler(n)]]` path has genuinely never been tried and `EXP-0016` proved the analogous
texture path works.

### 4. Cheapest next step

**Run `EXP-0142`** — it is already dispatched, pre-registered, pilot-complete and queued as
batch 3. It directly serves the row's own closure text ("generated encodings … remain
required") and is the only P1.3 item that moves the `validation.json` emittability metric,
which also feeds P0.6. Q1 (the `0xb`-leader selector decode) is the natural companion since
both concern the same instruction bundle.

### 5. Closure rules currently failed

- **R1** — texture ISA is decoded, not generated; `tex_addr_setup` is the only emittable
  member of the family.
- **R4** — `EXP-0114`'s `op+4` correction and `EXP-0136`'s 128× aniso finding need to reach
  `docs/descriptors/format-table.md` and `docs/isa/`.
- **R6** — no texture descriptor or texture instruction sequence has been independently
  generated and consumed.
- R2, R3, R5 pass.

---

## P1.4 — Vulkan/GL-grade memory and synchronization model (`DRV-MEM-01`)

### 1. What is now established

**This row's board text is materially out of date — several items it lists as "still needed"
are closed.**

- **The `0x07` fence/barrier family is decoded and ATOM-07..11 are CLOSED for tested scope**
  (`EXP-0093`, `d3e7d1ba`; addendum bundle B, 128 cases × 2 with identical verdict tuples).
  `threadgroup_barrier(mem_texture)` is a genuine acquire (`sub=0x14`) / release (`sub=0x04`)
  pair, correcting a `db.json` note. **`byte+3` bit 0 (`0x85` vs `0x84`) is the
  execution-convergence enable, independent of the memory-fence class** — densely
  re-confirmed by `EXP-0141` (all 128 odd `mem_scope` values pass, all 128 even fail with the
  same 224 stale lanes). ROG proven causally by splice-neutering. ATOM-11 is a **negative**:
  buffer- and texture-tagged ROG use different mechanisms.
- **Asymmetric fencing is NOT safe — a load-bearing correction.** At ≥4 producer/consumer
  pairs, relaxed messaging corrupts up to **100%**; only fully symmetric fencing gives 0
  mismatches. `EXP-0051` saw none only because it ran at 1–2 pairs. `EXP-0098` (`fc804669`)
  generalizes this to the command level: encoder-order and symmetric fences are safe (0/48
  raced) while untracked+asymmetric is unsafe — indexed raced **8/8 every mode, to 99.997%
  stale**.
- **The hardware register interlock is re-validated on M4** (`EXP-0085`, `2e693a58`; 56 cases
  × 2, 56/56 PASS): load, dependent-load, texture-read and atomic-result each feed a consuming
  ALU with **zero authored slack and no software wait**, to N=65536 plus a
  48-loads-per-thread adversarial case, corroborated by structural tokenization showing no wait
  ops. Plus the atomics op-table (subtract selector `0x1b` distinct from add `0x10`), native
  single-transaction compare-exchange, and the SIMD pre-combine boundary (reducible ops only,
  only at a compile-time-provably uniform address).
- **Memory-operand field semantics are established by splice** (`EXP-0082`, `311d3f3e`;
  2164 cases × 2 byte-identical): index scales as an element index per `elem_size` (with
  4-byte align-down for codes 1/2); `idx_off` is fixed 4-byte on load and 16-byte on store;
  the immediate offset is **unsigned 11-bit, 0..2047, no holes**; **no** non-power-of-two
  stride form; **no** mod-2^32 wrap.
- **Dynamic 64-bit addressing and per-lane divergent buffer selection are HW-VALIDATED**
  (`EXP-0084`, `783fe693`): four independent byte-exact constructions, each dynamically loaded
  pointer receiving its own context.
- **`has_atomic_load_store` must be FALSE** (`EXP-0121` OPT-10/11): a plain fenced load does
  **not** reliably observe a cross-thread write (300/300 iterations never completed at
  PAIRS=1), while a plain **store** observed by an **atomic** load is clean at every scale.
  An asymmetric, not a wash.
- **The memory-model chapter is published** — `docs/isa/memory-model.md` (promoted `446a5f28`)
  is one of the few normative chapters that exists.

### 2. What is still missing (as testable questions)

- Q1. What is the mapping from these shader-visible fences to **hardware cache domains**
  (USC, texture, PBE, tile memory, tiler, fragment, compute, host)? `DRV-MEM-01` asks for a
  producer/consumer pair matrix across all of them; the current evidence covers the
  shader-facing subset.
- Q2. What are the UAPI `vdm_barrier` / `cdm_barrier` semantics, and the flush/invalidate
  operations?
- Q3. `MEM-18`/`MEM-19` — the **uniform/constant-program slot-population path** — remain the
  two unanswered `MEM-*` items, flagged open by both `EXP-0083` and `EXP-0084`.
- Q4. `dev_scoreboard_fence` and `mem_fence` were swept and **deliberately not promoted**
  (`EXP-0141` H6): neither carrier has a memory-**ordering** observable, so the sweeps bound
  acceptance and dataflow-inertness only. A carrier with a real ordering observable is needed.
  `mem_fence8` is untested — it is emitted only by `intersection_query` traversal and
  `agxrun_persist` cannot bind an acceleration structure.
- Q5. Host mapping and cache maintenance for CPU↔GPU transitions.

### 3. Blocker class

**EVIDENCE for Q1, Q3, Q4; PLATFORM for Q2** (`vdm_barrier`/`cdm_barrier` are UAPI submit
fields with no macOS observation point, the same structural absence as P0.3's firmware
registers); **bookkeeping** for the row's board text, which still lists the closed `0x07`
family as outstanding.

### 4. Cheapest next step

**Correct the board row, then Q3.** The board text costs minutes and currently misdirects the
next wave. `MEM-18`/`MEM-19` are the only two Part-II `MEM-*` items unanswered out of 22, both
already scoped by `EXP-0083`/`EXP-0084`, and both fall inside the user's declared
load/store/SSBO priority cluster — so they are simultaneously the cheapest and the
highest-priority remaining evidence item on this row.

### 5. Closure rules currently failed

- **R4** — `docs/isa/memory-model.md` exists but predates `EXP-0093`'s symmetric-fencing
  requirement and `EXP-0121`'s `has_atomic_load_store=false`; both are driver-critical and
  neither is in a normative chapter.
- **R6** — no synchronization object has been independently generated at the command-stream
  level (`vdm_barrier`/`cdm_barrier` are PLATFORM-blocked; the shader-level fences are
  emittable-adjacent but `mem_fence` was correctly not promoted).
- R1, R2, R3, R5 pass — this is the best-evidenced P1 row.

---

## P1.5 — Robustness, sparse residency and VM conventions (`DRV-ROBUST-01`)

### 1. What is now established

- **The owned-buffer robustness model is established** (`EXP-0076`, `446a5f28`; 106 cases × 2,
  212 executions, zero faults, byte-identical): accesses execute as **independent naturally
  aligned units with per-unit align-down addressing**; OOB units read zero and OOB stores are
  discarded with guards intact; unaligned loads are **not** byte-exact; OOB atomic exchange
  reads 0.
- **The base-slot census is complete** (`EXP-0083`, `8d47a271`; 351 cases × 2, 702 executions,
  byte-identical): the selector is **effectively 7-bit** — slots 128..255 mirror 0..127 on
  every op path, with no third behaviour anywhere; no aliasing or holes among populated slots
  1..30; **31 slots usable via direct binding** (a binding-population edge, explicitly not
  claimed as an architectural ceiling); out-of-range slots are fault-contained but silently wrong.
- **VM conventions are bounded** (`EXP-0122`, `f2b8ef66`; 87 cases × 2, 0 mismatches):
  `heapBufferSizeAndAlignWithLength:` returns **`heap_align = 256` for all 62 rows** across
  31 lengths × 2 storage modes (not the 16 KiB page/sparse granularity one might guess);
  `maxBufferLength = 9,534,832,640` is an **exact, off-by-one-tested, storage-mode-symmetric
  ceiling** (`max` allocates, `max+1` and `max+256` do not); the allocator is a deterministic
  bump allocator with immediate address reuse **within one process** (three identical passes
  return byte-identical addresses).
- **The guard/zero region is narrow, not page-wide** — offset 4096 past a 64-byte allocation
  reads zero, but `16384−256`, `16384−4`, `16384`, `16384+4`, `16384+256` all read non-zero.
- **A `2^43` addressing wraparound boundary** is well-evidenced (and explicitly distinguished
  from the allocator's own `vm_start`/`vm_end`, which remain UNKNOWN).
- **Sparse participation works** for a representative cross-section (`EXP-0133`): heap +
  sparse-heap texture creation complete for RGBA8Unorm, R32Uint, BC1_RGBA, ASTC_4x4_LDR and
  Depth32Float; `sparseTileSizeInBytes = 16384` uniformly.
- **`EXP-0125`'s H4** additionally establishes a real concurrency-robustness bound: silent
  numerical corruption above a session-variable `n_queues` threshold, never below 4.

### 2. What is still missing (as testable questions)

- Q1. What are `vm_start` / `vm_end` and the kernel-reserved region? Not established as an
  **allocator** property — only the `2^43` addressing wraparound is well-evidenced, and
  `EXP-0122` explicitly declines to equate the two. The lowest address ever observed is
  `0x10000018000` (suggestively `2^40 + 0x18000`).
- Q2. What are the protection and sharing rules? **Not probed at all** — no cross-process,
  cross-`MTLDevice`, `IOSurface` or shared-event test exists.
- Q3. What is the root cause of the sparse write-persistence negative (`EXP-0122` §3.5)? The
  negative is solid; the mechanism is not. The macOS-26 `placementSparsePageSize` / MTL4
  sparse-mapping path is **untested** and named as the next step.
- Q4. Can two sparse resources alias the same physical tile backing? Untested.
- Q5. Is there a general `firstMipmapInTail` formula spanning format/dimension/page-size?
  Per-case values are directly queryable; no closed form derived.
- Q6. Does the `2^43` wraparound hold for texture addressing, argument-buffer-indirect
  pointers, and non-32-bit widths? Only 32-bit `device`-pointer load/store was tested.
- Q7. `MEM-18`/`MEM-19` (shared with P1.4) — the uniform/constant-program slot-population path.

### 3. Blocker class

**EVIDENCE for Q2–Q7; PLATFORM/kernel-side for Q1 and for the "kernel reservation, chip
feature parameters, BO protection/sharing/device-address rules" clause of `DRV-ROBUST-01`.**
`EXP-0122` is explicit: "Everything here is a public-Metal-API black-box observation; no claim
is made about the underlying kernel/firmware implementation." `vm_start`/`vm_end` are
`DRM_IOCTL_ASAHI_GET_PARAMS` outputs — the same class as
`command_timestamp_frequency_hz`, which `EXP-0126` correctly classified
UNDETERMINABLE-FROM-USERSPACE.

### 4. Cheapest next step

**Q3 — the MTL4 / `placementSparsePageSize` sparse-mapping path.** `EXP-0122` named it as the
concrete next step and the harness already exists; it converts the single largest sparse
`UNKNOWN` on the row into a mechanism. Q4 (aliasing) folds into the same dispatch since both
need the same `MTLHeap` lifecycle harness — and that harness also unblocks **TEX-12** on P1.3.

### 5. Closure rules currently failed

- **R3** — `EXP-0122` has **no `PROVENANCE.md` row**.
- **R4** — the 256-byte alignment, the exact `maxBufferLength` boundary, the narrow-zero-region
  finding and the `2^43` wrap are not in a normative `docs/` chapter.
- **R6** — no VM/sparse object has been independently generated and consumed.
- R1, R2, R5 pass.

---

## P1.6 — Complete query and timestamp semantics (`DRV-QUERY-01`)

### 1. What is now established

- **`EXP-0124` (`bf3bfbb8`; 85 cases × 2, cross-run gate PASS, 0 issues) answers most of the
  row**, several items as clean negatives:
  - **Pipeline statistics do not exist natively on M4.** `device.counterSets` contains
    **only** `"timestamp"` — no `"statistic"`, no `"stageUtilization"`, despite both being
    documented public constants. **A driver must emulate GL/D3D-style counters entirely.**
  - **Only stage-boundary sampling is supported.** `AtDraw`/`AtDispatch`/`AtTileDispatch`/
    `AtBlit` are all `FALSE`, and calling the per-command
    `sampleCountersInBuffer:atSampleIndex:withBarrier:` selector for them **hard-aborts the
    process** with an uncatchable assertion (reproduced 3×). A driver must use the
    pass-descriptor `sampleBufferAttachments[i].startOfEncoderSampleIndex/
    endOfEncoderSampleIndex` mechanism exclusively. Independently confirms `EXP-0027`'s A18
    DATA-TRACE finding via a second, public-API method and extends it to two more boundaries.
  - **Exact counter-heap ceiling: `sampleCount = 4096` succeeds, `8192` is gracefully
    rejected** (`MTLCounterSampleBufferErrorOutOfMemory`); `0` also rejected; everything up to
    2^40 rejected without a crash. 32 KiB at 8 bytes/sample.
  - **`resolveCounterRange:` on a Private-storage sample buffer SIGSEGVs uncatchably**;
    Managed is silently accepted and behaves as Shared.
  - **Occlusion counting mode ACCUMULATES** across repeated `setVisibilityResultMode`
    activations at the same offset within one encoder; an intervening `Disabled` does not
    reset it; distinct offsets never interfere.
  - **GPU-side `resolveCounters:` in a later encoder of the SAME command buffer reads
    stale/zero data**; in a separate later command buffer it matches the CPU-side resolve exactly.
  - **An empty encoder never reaches its stage-boundary sample point** — both slots read
    untouched-zero, not `MTLCounterErrorValue`.
- **`EXP-0052` (`cad2132b`)** establishes equal/monotonic public CPU/GPU pairs, ordered samples
  within each pass and post-completion resolve; **falsifies** strict cross-pass non-overlap.

### 2. What is still missing (as testable questions)

- Q1. What is `command_timestamp_frequency_hz`, and what does Linux `GET_TIME` return?
- Q2. What is the private counter-heap **layout** (the byte format the firmware writes), as
  opposed to its allocation limits?
- Q3. Reset / availability / wrap semantics — tick wraparound was not driven to its boundary.
- Q4. Broader stages and queues, and simultaneous-query interactions beyond the tested set.

### 3. Blocker class

**PLATFORM for Q1 — decisively.** `EXP-0126` establishes the reasoning precisely:
`command_timestamp_frequency_hz` is a **kernel-supplied read-only output**; macOS's own GPU
timestamps are already software-calibrated nanoseconds (CPU/GPU anchor pairs + drift
correction via `MTLCounterSampleBuffer`), **not** the raw hardware tick count a Linux driver
would DMA into a `drm_asahi_timestamp` location. That number "literally does not exist
anywhere in the macOS userspace-visible surface."

**PLATFORM for Q2** as well — the private heap layout is firmware-written and never crosses
the macOS userspace boundary.

Q3/Q4 are **EVIDENCE** but small.

**DECISION:** this row is, on the macOS envelope, essentially complete apart from two
structurally unobservable items. It should be re-scoped to "closed for the userspace-observable
surface, with Q1/Q2 handed to the kernel team" or the user should accept that it cannot close.

### 4. Cheapest next step

**Desk: write the query/timestamp chapter and re-scope the row.** All of `EXP-0124`'s
driver-facing rules (never call the per-command sampling selector; static-allowlist pipeline
statistics as absent; the 4096 ceiling; Private-storage resolve is a SIGSEGV; occlusion
accumulates; same-command-buffer GPU resolve reads stale) are actionable driver constraints
sitting only in an experiment directory. Then put the DECISION to the user.

### 5. Closure rules currently failed

- **R1** — nothing is generated; every result is an observed API/hardware behaviour. (For this
  row that may be the right bar — a driver does not *generate* a counter heap format it cannot
  observe.)
- **R4** — no query/timestamp chapter in `docs/`.
- **R6** — no counter heap has been independently generated and consumed (PLATFORM-blocked).
- R2, R3, R5 pass.

---

## P1.7 — Indirect and device-generated commands (`DRV-INDIRECT-01`)

### 1. What is now established

- **The GPU-authored writable ICB grammar works end-to-end — HW-VALIDATED** (`EXP-0124`):
  MSL `render_command`/`compute_command` with `set_vertex_buffer`/`set_kernel_buffer`,
  `draw_primitives`/`draw_indexed_primitives`, `reset()`, `inheritBuffers=YES` inheritance,
  and **out-of-bounds command indices silently absorbed** without fault or corruption of
  in-range slots.
- **GPU-authored `.set_barrier()` on a `ConcurrentDispatch` ICB command is fully effective**
  (0/16 trials raced across both runs); omitting it exposes a real race
  (6/16 = 37.5% combined) with the exact predicted stale-sentinel signature every time.
- **An exact `maxCommandCount` crash boundary:** `6,391,319` works, `6,391,320` SIGSEGVs —
  both runs converged to the identical integer via 24-probe bisection with **zero monotonic
  violations**. (`EXP-0098` separately found `maxCommandCount` SIGSEGVs at 8,388,608 and that
  ICB `location > maxCommandCount` faults.)
- **Primitive restart is honored for `TriangleStrip`** (0xFFFFFFFF/0xFFFF splits the strip,
  never consumed as vertex data) but **not for `Point`** (the sentinel is treated as an
  ordinary huge index) — extends `EXP-0098`'s point-topology finding with a strip positive.
- **The indirect-dispatch parameter format is confirmed byte-exact:** `(X,Y,Z)` written by a
  compute kernel into a `MTLDispatchThreadgroupsIndirectArguments`-shaped buffer produces
  exactly `X×Y×Z` threadgroups in that axis order; a **non-4-byte-aligned**
  `indirectBufferOffset` (tested at 2) is accepted without rejection.
- **`[[instance_id]]` is ABSOLUTE** in GPU-driven draws (`EXP-0098`, `fc804669`), and
  encoder-order + symmetric fencing is safe (0/48 raced) while untracked+asymmetric is not.
- **`EXP-0053` (`e31dfb46`)** establishes indirect-argument timing, zero/nonzero work, ICB
  ranges, reset/re-encode and one optimization-equivalence case.

### 2. What is still missing (as testable questions)

- Q1. What are the **native CDM direct/indirect global/local mode bits** in the command stream
  (as opposed to the Metal API surface)? This is the same object P0.5 owns; P1.7 cannot get
  ahead of it.
- Q2. Multi-draw / multi-dispatch **links and barriers** at the command-stream level, count
  buffers, and bounds rules.
- Q3. Validation and cache-flush transitions around device-generated commands.
- Q4. Base vertex / base instance in the indirect path specifically (`EXP-0092` established the
  sysval side).

### 3. Blocker class

**EVIDENCE, but sequenced behind P0.5.** The public-Metal half of this row is in good shape;
what remains is the *command-stream* half, which is P0.5's object. Dispatching P1.7 work
before P0.5's packer exists would duplicate effort. The "Linux mapping" tail is PLATFORM.

### 4. Cheapest next step

**None independently — fold Q1/Q2 into the P0.5 command-stream dispatch.** If a standalone
step is wanted, the cheapest is desk: promote `EXP-0124`'s ICB grammar, the exact
`6,391,319`/`6,391,320` boundary, the strip-vs-point restart asymmetry and the unaligned-offset
acceptance into `docs/cmdstream/README.md`, and correct the board row (which still lists
"multi-draw/dispatch/count/restart/bounds" as wholly open when restart and bounds now have
answers).

### 5. Closure rules currently failed

- **R1** — the ICB *contents* are generated on the GPU by our own MSL (passes); the CDM/VDM
  indirect **packets** are not.
- **R4** — none of `EXP-0124`'s indirect findings are in `docs/`.
- **R6** — no indirect command packet has been independently generated at the command-stream
  level.
- R2, R3, R5 pass.

---

## P1.8 — Conformance numerical, rasterization and limits (`DRV-RASTER-01`)

### 1. What is now established

- **FP32 division is answered exactly** (`EXP-0074`, `ae63b41f`): bit-exact versus a
  correctly-rounded binary32 reference except **DAZ+FTZ**; a single DAZ+FTZ model predicts
  **4171/4171** cases; FTZ proven independently of DAZ; NaNs always canonical `0x7FC00000`.
- **Line rasterization** (`EXP-0123`, `1143ec55`; 98 cases × 2 byte-identical, 98 PASS):
  half-open interval, **endpoint excluded**, per-column row = evaluate at pixel-center x and
  floor. The exact-integer `y=4.0` tie resolves to the **lower** row (interval effectively
  `(r, r+1]` at that boundary). A zero-length line rasterizes **nothing**.
- **Point rasterization has a genuine non-monotonic table:** sizes 0.5–1.9 → 1×1; **2.0
  exactly → 2×2**; 2.1–3.5 → 3×3. Both runs agree bit-for-bit. **A driver must reproduce the
  table, not a `ceil`/`round`/`floor` approximation.** (`EXP-0097`, `eef37ca8`, separately
  covers the 511 px clamp ceiling, NaN/Inf clamping and the negative-size anomaly band.)
- **Polygon modes:** Fill (72 lit) and Lines (38 lit) only. **`VK_POLYGON_MODE_POINT` does not
  exist; conservative rasterization does not exist** (no API surface at all); wide lines are
  not available through the documented public API. Depth clamp and depth clip are both native.
- **Varying capacity and pre-raster outputs are CLOSED** (`EXP-0097`): **124 user scalar
  components**, per-component and consumed-only, identical at float/float2/float3/float4/half
  granularity; clip-distance 8 independent; **provoking vertex is FIXED to the first vertex**
  (must be emulated for GL).
- **Fragment kill/sample-mask/discard/demote is CLOSED** (`EXP-0091`, `4c2df727`; 78/78 cases
  byte-identical): a dedicated 6-byte submission op (`byte0=0x57, byte2=0x54`) implements
  kill/target-mask — previously undecoded anywhere in the repo.
- **Threadgroup addressing and capacity** (`EXP-0100`, `f5c321c4`): CLOSED for 2884/2900 splice
  and 145/145 budget cases; PARTIAL on 16 racy `byte+1` values `(v&0x17)==0x04`; store
  `idx_off` ×16 B vs load ×4 element asymmetry; **the combined 65536 B threadgroup-memory
  ceiling is NOT API-validated — it silently corrupts.**
- **`EXP-0047` (`ae63b41f`)** bounds fp32/fp16 subnormal, qNaN/minmax, signed-zero and rounding
  for ten authored M4 paths; **`EXP-0102`/`EXP-0103`** answer all `INT-*`, `PACK-*`, `FP-*`,
  `TRIG-*` and `SFU-*` questionnaire items bar four.

### 2. What is still missing (as testable questions)

- Q1. What is the exact sub-pixel snapping granularity at the line-rule integer boundary?
  Shown coarser than 0.01 px, not bisected.
- Q2. Partial-clip behaviour (one vertex in range, others out) under `.clip` vs `.clamp`; and
  `MTLViewport.znear/zfar` outside `[0,1]` combined with clip/clamp mode.
- Q3. Is there a hidden third `setTriangleFillMode:` mode reachable off the documented enum?
- Q4. What is the exact `simd_shuffle` out-of-range source-lane mapping? Reproducible but not a
  simple modulo for every tested value.
- Q5. The **undocumented-selector wide-line observation** (`EXP-0123` §4) — explicitly flagged
  to the coordinator and **not decided**.
- Q6. One non-reproducible MSAA + A2C + depth + occlusion crash, deliberately excluded from the
  gated matrix and not re-chased.
- Q7. `TRIG-01`/`TRIG-02` and `SFU-04` remain unanswered (need field-level splice; `db.json`
  internals stay `INFERRED`).

### 3. Blocker class

**EVIDENCE, all small.** Nothing on this row is platform-blocked. Q5 is arguably a **DECISION**
— it is an observation the experiment deliberately escalated rather than resolved.

### 4. Cheapest next step

**Q1 + Q2 + Q3 in one small dispatch** against `EXP-0123`'s existing 98-case harness — all
three are additional cases in a matrix that already exists, already passes 22/22 selftest and
7/7 seqtest, and already produces byte-identical cross-run records. Q4 rides along.
**Resolve Q5 by asking the user** whether an undocumented selector is in scope (it touches the
clean-room boundary question of what "public API" means).

### 5. Closure rules currently failed

- **R3** — `EXP-0123` has **no `PROVENANCE.md` row**, so the entire line/point/polygon rule set
  and the hard-limit table are outside the audit chain.
- **R4** — the rasterization rules and the "what must be emulated for GL/Vulkan" table are not
  in `docs/pipeline/README.md`.
- **R6** — no rasterization state object has been independently generated and consumed
  (couples to P0.5's PPP schema).
- R1, R2, R5 pass.

---

# Summary table — all sixteen rows, ranked cheapest to close

"Cheapest" = least remaining work to reach a defensible `CLOSED`, counting a required user
decision as cheap (minutes) but a *blocked* decision as expensive.

| rank | row | dominant blocker | cheapest next step | rules failed | notes |
|---:|---|---|---|---|---|
| 1 | **P0.8** ABI/epilogs | **DECISION** (orchestrator audit) | promote to `docs/`, run the cross-experiment audit | R4, R6 | all nine sub-items addressed; `EXP-0137` says so explicitly. **Closest to closable.** |
| 2 | **P1.6** query/timestamp | **PLATFORM** (2 items) + DECISION | write the chapter; re-scope the row | R1, R4, R6 | complete for the macOS-observable surface; `command_timestamp_frequency_hz` provably unobservable |
| 3 | **P1.4** memory/sync | bookkeeping + EVIDENCE (2 items) | correct the stale board row; then `MEM-18`/`MEM-19` | R4, R6 | board lists ATOM-07..11 as open; `EXP-0093` closed them. Best-evidenced P1 row |
| 4 | **P0.1** scratch/helper | **PLATFORM** + DECISION | write the (nonexistent) chapter; ask the user how it closes | R1, R3, R4, R6 | three independent negatives; UAPI text explains why tracing can't see it |
| 5 | **P0.4** BG/EOT | **PLATFORM** (UAPI half) + EVIDENCE (Q3) | land `EXP-0147`; then the tile-shading probe | R4, R5, R6 | program side constructed + HW-validated; `/dev/dri` absent, checked directly |
| 6 | **P1.8** raster/limits | EVIDENCE (small) | 3–4 extra cases in `EXP-0123`'s existing matrix | R3, R4, R6 | plus one user decision on the undocumented wide-line selector |
| 7 | **P1.5** robustness/VM | EVIDENCE + PLATFORM (`vm_start/end`) | the MTL4 sparse-mapping path (also unblocks TEX-12) | R3, R4, R6 | `EXP-0122` named its own successor precisely |
| 8 | **P1.7** indirect/DGC | EVIDENCE, **sequenced behind P0.5** | fold into the P0.5 dispatch; meanwhile promote to `docs/` | R1, R4, R6 | public-Metal half in good shape |
| 9 | **P1.1** PBE/attachments | EVIDENCE (well-specified) | widen `EXP-0132`'s schema, re-run the same matrix | R1, R4, R6 | successor spec already written by the experiment |
| 10 | **P1.2** formats | EVIDENCE (Q1 large, rest moderate) | add readback to the 5 completion-only axes | R1, R4 | 138×11 breadth done; 76 compressed decode oracles are the long pole |
| 11 | **P0.2** shader selection | EVIDENCE | the VS-side token redirect splice | R1, R4, R5, R6 | one HW-validated negative already reversed the working hypothesis |
| 12 | **P1.3** texture ISA | EVIDENCE | run the queued `EXP-0142` | R1, R4, R6 | 21/28 `TEX-*` answered; 7 deferred with named successors |
| 13 | **P0.7** shader container | EVIDENCE, **sequenced behind P0.2** | resource-bearing repeat of `EXP-0131` | R1, R3, R4, R6 | HW-consumer proof obtained; from-scratch container blocked on selection |
| 14 | **P0.3** UAPI field map | **PLATFORM** (large) + DECISION + EVIDENCE | scissor/dbias array template search | R1, R4, R5, R6 | 58/65 PARTIAL; a large fraction has no macOS observation point at all |
| 15 | **P0.5** command/state packing | EVIDENCE (large volume) | VDM link splice + CDM `+0x08` differential | R1, R3, R4, R6 | the hand-built CDM link is HW-VALIDATED but unprovenanced |
| 16 | **P0.6** compiler-ready ISA | EVIDENCE (largest measured) | re-run `EXP-0112`'s generator with `EXP-0141`'s rule | R1, R3, R4, R6 | 21/171 emittable, 319/1036 fields; 3 emit experiments not yet run |

---

# Cross-cutting conclusions for the orchestrator

### Rows genuinely close to closable
**P0.8** (all sub-items addressed; needs an audit and a docs pass, no GPU), **P1.6** (complete
for the observable surface), **P1.4** (board text is the main thing that is stale).

### Rows blocked by a platform limitation no amount of work fixes on this host
- **P0.4's UAPI half** — `/dev/dri` absent, no drm/asahi kext, checked directly in
  `EXP-0130/raw/host_check.json`. `drm_asahi_bg_eot` cannot be populated or consumed here.
- **P0.3's firmware-marshaled registers** — `zls_ctrl`, `ppp_ctrl`, `isp_zls_pixels` and the
  four `rsrc_spec` words are submit-parameter-only and absent from every userspace BO by
  construction.
- **P0.1's helper/scratch struct** — three methodologically distinct probes, three negatives;
  the UAPI's own text ("a static allocation shared for the whole device … internally
  dispatched by the hardware") explains why a userspace correlation trace cannot see it.
- **P1.6's `command_timestamp_frequency_hz` and private heap layout** — the raw tick frequency
  does not exist anywhere in macOS's userspace-visible surface.
- **P1.5's `vm_start`/`vm_end`** — `GET_PARAMS` outputs, same class.
- **P1.4's `vdm_barrier`/`cdm_barrier`** — same class.
- **P0.6's `tg_addr_compute` A18↔M4 divergence** — resolvable only by touching the A18, which
  the user has forbidden.

### Rows needing a decision from the user, not more evidence
1. **The A18 question, which governs all sixteen rows.** `CLAUDE.md` and
   `docs/P0-P1-CLOSURE.md` say A18 replication is suspended and not a closure gate;
   `APPLE9_RE_IMPLEMENTATION_GAPS.md`'s whole-handoff gate item 10 demands "Independent G16G
   and G17P evidence matrices". These cannot both stand. **Resolve this first** — it is the
   single change that most affects how many rows can close.
2. **What "MAPPED" means for a firmware-private UAPI field** (P0.3, P0.4, P1.4, P1.6). If a
   fully specified userspace derivation + a PUBLIC bit layout + a recorded structural-absence
   proof is sufficient, several rows move a long way today. If observing the firmware value is
   required, four rows can never close on this host.
3. **P0.1's disposition** — construct-from-first-principles specification, or formal kernel-team
   handoff and removal from the P0 set.
4. **P0.6's closure bar** — "every initially supported NIR family emittable" (the gap doc's own
   wording) or "the full 171-instruction census" (what the board's metric implies).
5. **P1.8's undocumented wide-line selector** — `EXP-0123` escalated it deliberately rather
   than deciding whether an undocumented selector is in scope.

### Two mechanical debts worth clearing before the next wave
- **Seven experiments have no `PROVENANCE.md` row** (`EXP-0107`, `0110`, `0116`, `0121`,
  `0122`, `0123`, `0125`) — including `EXP-0116`, whose hand-built CDM link is the strongest
  P0.5 result the project has. Rule R3 is failing for five rows on pure bookkeeping.
- **`docs/` promotion has fallen roughly two days behind `PROVENANCE.md`.** R4 is the most
  widely failed rule across all sixteen rows, it is 100% desk work, and it is the rule the
  Definition of Done treats as the actual deliverable.
