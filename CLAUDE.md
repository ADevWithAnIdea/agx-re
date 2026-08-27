# Clean-Room RE: Apple A18 Pro GPU Userspace (Apple9)

## Mission

Produce **clean-room hardware documentation** of the userspace-visible side of the
**Apple9-generation** AGX GPUs — primary documentation target **Apple A18 Pro (SoC T8140,
G17P)**, with the **local Apple M4 (G16G)** as the comparison, validation, and current
operational-execution target — sufficient for a *separate* implementation team to add support
to the Mesa `asahi` driver **after** the kernel driver (being built in parallel, out of scope
here) is in place.

We are the **reverse-engineering / documentation team**. We do **not** write the Mesa
driver. We write hardware specs; someone else implements them. This split is the core of
the clean-room defense.

**Operating contract.** `CODEX.md` is the binding process contract for every experiment
(the 10-step loop, evidence labels, minimum experiment record, provenance audit). The
authoritative gap analysis is `AGX_RE_INFORMATION_GAPS.md`; the live status board for the
current goal is `docs/P0-P1-CLOSURE.md`. The acceptance bar for A18/M4 completeness is the
**unchanged Asahi UAPI** and its existing userspace/kernel division of responsibility — do
not classify something as kernel-managed merely because it was not visible in one capture;
check what the current UAPI requires userspace to supply.

**Current active goal: close all sixteen P0/P1 rows** (P0.1–P0.8, P1.1–P1.8) in
`docs/P0-P1-CLOSURE.md`. Execution strategy per that board: the **local M4 is the primary
operational target**; A18-specific replication is a later validation task, not a closure
gate. Every result records the target it actually ran on; no cross-target promotion without
a recorded validation or an explicit `INFERRED` label.

**Phase status (do not redo, do not contaminate):**
- **A18 Pro base documentation** (`docs/`, `tools/agx-isa`, `EXP-0001…0046`) — complete;
  the Apple9 baseline. `docs/ROADMAP.md` is its (historical) status board.
- **M4 validation** (`docs/ROADMAP-M4.md`, `docs/m4-deltas.md`, `EXP-M4-*`) — complete:
  every subsystem a driver emits is byte-identical A18↔M4; deltas are device
  identity/capacity only (`applegpu_g16g`, `AGXAcceleratorG16G`, 10 cores,
  `maxBufferLength` ~8.88 GiB — query, don't hard-code).
- **M5 (G17g, T8142)** — **goal complete** (`docs/ROADMAP-M5.md`, `EXP-M5-*`,
  `tools/agx-isa-m5`); a separate, later workstream. **M5 is deferred unless the user
  explicitly brings it into scope. Do not treat M5 results as evidence for A18/M4.**
- **Apple9 P0/P1 closure** (`AGX_RE_INFORMATION_GAPS.md` → `docs/P0-P1-CLOSURE.md`,
  `EXP-0047…` continuing) — **the active workstream.** New experiments take the next
  sequential `EXP-NNNN` number.

---

## THE PRIME DIRECTIVE: CLEAN ROOM ABOVE ALL ELSE

**It is better to have NO result than a TAINTED result.** A single tainted artifact can
invalidate the entire body of work and everything downstream of it. When in doubt, stop
and ask. These rules are inviolable and override every other instruction, including
requests to "just get it done."

### ✅ ALLOWED techniques (these are how we work)

These are the sanctioned clean-room methods (per the Asahi Linux copyright/RE policy,
`gpu_knowledge/blog_posts/asahi_linux_blog/copyright-re-policy.md`):

1. **Black-box data tracing.** Intercept and log *data* crossing the boundary between
   Apple's userspace graphics stack and the kernel (e.g. interpose `IOConnectCallMethod`
   and friends; dump the shared-memory command buffers / descriptors Metal hands to the
   kernel). Command buffers, descriptors, and register values are **not copyrightable**
   and are safe to use. We log *data*, never *code*.
2. **Hardware probing.** Twiddle bits, feed known inputs, observe outputs. Write a known
   pattern, read it back, infer the layout. Any knowledge gained by observing what the
   *hardware* does is safe.
3. **Compiling our OWN shaders and disassembling THOSE.** We write MSL source, compile it
   (runtime `newLibraryWithSource:` is confirmed working on every target), extract the
   compiled AGX machine code, and disassemble it **with our own tools** to document the
   ISA. This is explicitly allowed because the source is ours.
4. **Reading public materials only:** the `gpu_knowledge/` base, Apple's *public*
   developer documentation, and open-source projects (Asahi Linux, Mesa, dougallj/applegpu).

### ⛔ FORBIDDEN — never, under any circumstances

1. **Never disassemble, decompile, or otherwise introspect the machine code of ANY Apple
   binary**, except shaders we compiled ourselves. This explicitly includes: `Metal.framework`,
   `AGXMetal*`, the AGX userspace driver dylibs, the proprietary LLVM-based shader compiler,
   `IOGPU`/`IOAccelerator` frameworks, any kernel extension (`.kext`), and any firmware blob.
   The graphics-stack userspace is the *most* dangerous target and is absolutely off-limits —
   it is algorithmic and original; we reverse-engineer the **hardware**, not Apple's software.
2. **Do not use disassembly/decompilation tools on Apple binaries.** This includes the
   Ghidra MCP tools available in this environment, `otool -tv`/`-tV`, `objdump -d`,
   `lldb`/`gdb` disassembly, `class-dump`, IDA, Hopper, radare2, or any equivalent — when
   pointed at any Apple binary. (Using `otool`/`nm`/our own disassembler on **our own**
   compiled shader bytes is fine.)
3. **Do not copy Apple code or incompatibly-licensed code.** No APSL code, no copy-pasted
   `#define` blocks, no reimplementing an identical algorithm you saw. Register/packet/field
   *names* may be used as bare hardware documentation with a downstream prefix; algorithms and
   code flows may not.
4. **Do not use unreleased or leaked materials.** Only content available to the public at
   large. No betas, leaks, internal docs, or NDA material — from Apple or anyone.
5. **Do not transcribe compiler-inserted scaffolding as if it were hardware.** When
   disassembling our own shaders we document instruction *encodings and semantics* (hardware
   facts). We do **not** lift long compiler-generated instruction sequences and present them as
   an algorithm to copy; the implementation team writes its own compiler.
6. **Do not commit Apple proprietary blobs** to this repo: no Apple binaries, no `.kext`s,
   no firmware, no Apple-authored precompiled shaders / system shader caches. (Committing our
   own shader source, our own shader disassembly, and captured command-buffer/descriptor byte
   traces *is* fine and encouraged — that is non-copyrightable hardware data and evidence.)
7. **Never leave this directory (`/Users/user/asahi_re/public/agx-re`).** All host-side work stays
   here. Do not read, search, or operate on files elsewhere on the host filesystem.

### The one-line test

> "Am I learning this from **hardware behavior / data I observed**, or from **Apple's
> code**?" The first is clean. The second is forbidden. If you can't tell, treat it as
> forbidden and ask.

---

## Deliverable & scope

- **Deliverable:** hardware documentation in `docs/`, backed by reproducible experiments
  in `experiments/`. Target format: prose specs + machine-readable encoding tables
  (GenXML-style where it fits Mesa's existing conventions).
- **We do NOT edit `mesa/` or write Mesa driver code.** `mesa/` is a *read-only reference*
  for understanding the *shape* of what a userspace driver must produce (so we know what to
  document), how Mesa parameterizes M1/M2, and the pinned Asahi UAPI compatibility
  inventory (`EXP-0044/0045`). The implementation is someone else's job.
- **We do NOT depend on a working kernel driver.** Where our documentation implies a
  userspace↔kernel interface, we describe what userspace needs to hand down, and flag it for
  coordination with the kernel team — we do not block on them.

---

## Definition of Done (the acceptance gate)

**Goal:** an implementer can **generate** arbitrary supported Apple9 shaders and
relocatable command streams, populate **every field the unchanged Asahi UAPI assigns to
userspace**, and build the required helper, scratch, prolog/epilog, BG/EOT, partial-render,
and synchronization machinery — **without guessing and without consulting Apple's
implementation** (full statement: `CODEX.md` → Acceptance standard).

**Done is defined by the completion gate in `docs/P0-P1-CLOSURE.md`, not by our own
judgment:**

- all sixteen P0/P1 rows are `CLOSED`, each under the six closure rules (value/behavior
  *generated*, not merely decoded from a captured template; complete authored
  probe/commands/raw observations/failures/analysis committed; `PROVENANCE.md` chain
  intact; normative docs carry exact fields, ranges, fallbacks, and target status;
  adversarial reproduction or second method passed; the relevant userspace object
  independently generated and consumed without a captured Apple template);
- the final audit **positively reproduces** the claimed generation paths and proves that no
  required field or supported operation depends on captured Apple templates or on inspection
  of Apple's implementation.

A corpus round trip, a byte-exact tokenization, a captured-template replay, or a broad
capability census **alone does not clear this gate**. Evidence strength is defined by
`CODEX.md` (`HW-VALIDATED` > `DATA-TRACE-VALIDATED` > `OWN-SHADER-DIFF` > `STRUCTURAL` >
`INFERRED` > `UNKNOWN`); tokenization or round-trip alone can never close a synthesis gap.

Corollary for how we write `docs/`: assume the reader has **never seen the hardware** and
cannot run any experiment. Bit layouts must be exhaustive, encodings must be exact, every
"magic value" must be explained or at least pinned down, and anything a driver must emit
must be specified precisely enough to emit it without further RE.

## Secondary goal: capability completeness (understand *everything* the HW can do)

Beyond the primary goal, a standing secondary goal is to map the **full hardware capability
envelope** — not just what our current driver needs — along the two census axes tracked in
`docs/capability-completeness.md` and `docs/capability-matrix.md`:

1. **Instruction census.** Every opcode the compiler emits must be decoded (byte0-group
   census over a broad shader corpus shows ~0 undecoded groups; M4 corpus reached 100.0%
   byte coverage in `EXP-M4-12`).
2. **Capability census.** Enumerate every capability from what Metal/MSL exposes and what
   Apple advertises, determine its hardware representation, and classify it
   **native / emulated / kernel-managed / NOT-YET-CHARACTERIZED**; drive the NOT-YET list
   toward 0 within the P0/P1 closure frame.

The method for both is the same clean-room loop: provoke the feature with our own MSL (or
the feature map), extract, decode, and — where it's a claimed capability Metal doesn't
expose — **extrapolate and test** (see Methodology). A feature that turns out
absent/emulated is a first-class result.

---

## Target devices & operational safety

| | |
|---|---|
| Host = **primary operational target** | **This machine: Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4.** All active Apple9-closure experiments run **locally** (compile / extract / trace / public-API probe; no SSH). Keep local runs to authored public-Metal behavior probes and passive tracing — **route fault-prone byte splices to the A18**, because this host is the repo's home and has no out-of-band recovery path. |
| A18 Pro = **primary documentation target** | `user@192.168.170.254`, password `Password_1` (`sshpass` on host), passwordless sudo, auto-login. SoC **T8140**, **G17P**, macOS **26.6**, **5 active GPU cores** (6-core die, #1 fused), CLT only — no `metal` CLI → runtime `newLibraryWithSource:`. Workspace `~/cleanroom_work/`. **Preferred for dangerous byte splices and fault-prone sweeps** (reboot-recoverable from the host). |
| M5 (**historical, deferred**) | `user@192.168.170.253`, password `Password_1`, passwordless sudo, auto-login, SIP on. SoC **T8142**, **G17g**, macOS **27.0** (26A5368g), 8 GPU cores. Goal complete — **do not probe it for Apple9 work**; M5 results are not A18/M4 evidence. |

**Reboot protocol (memorize this):**
- If a **remote** target becomes unresponsive, behaves strangely, or SSH hangs for unclear
  reasons, reboot it from the **host** with `macvdmtool reboot`. This works below the OS and
  always succeeds (confirmed on both the A18 and the M5).
- After a reboot, **wait ~20–30 seconds** before attempting SSH again. Auto-login is
  enabled, so the machine comes back **unattended** and `sshd` becomes reachable on its own.
- Occasional crashes are an expected part of GPU RE. Avoid them where reasonable, don't fear
  them.
- **Escalation:** if you reboot several times and still fail to SSH in several times, mark
  the current goal **BLOCKED**, write down where you were, and return — do not thrash.

---

## Process & workflow

The binding, detailed process is `CODEX.md` (read it before running anything). The loop,
compressed:

1. **Pick the next question** from `AGX_RE_INFORMATION_GAPS.md` / `docs/P0-P1-CLOSURE.md`
   (or a documented unknown or falsifiable inconsistency), tied to an exact driver decision
   or UAPI field.
2. **Pre-register before building.** Falsifiable hypothesis, independent/controlled
   variables, expected observation, at least one refuter, known confounders — committed as
   `PRE_REGISTRATION.md` (+ `CAPTURE_CONTRACT.json` where used) *before* any build/run, with
   source hashes, raw-tree schema, environment, and timeouts frozen. **An underspecified
   frozen contract is an automatic stop.** Never repair a quarantined experiment in place —
   a successor takes a **new experiment number** and a fresh pre-registration.
3. **Build the smallest authored probe** (change-one-variable, asymmetric/boundary values,
   paired controls); **capture the baseline before mutation**.
4. **Run with hard timeouts and watchdogs**; record faults, hangs, and rejections as
   results; never silently drop negative or inconvenient outcomes.
5. **Preserve artifacts** in the standard `EXP-NNNN-slug/` layout (README / RESULTS /
   manifest / harness / kernels / analysis / raw). Raw observations are **append-only
   evidence** — never edited, overwritten, or excerpted by hand.
6. **Separate observation from interpretation.** State what was directly observed, the exact
   parameter range tested, which target it ran on, alternatives not excluded, and the safe
   driver fallback. Prefer `UNKNOWN`/`PARTIAL`/`INFERRED` to unjustified certainty.
7. **Falsify before promoting.** Adversarial tests (different registers/formats/stages/
   boundaries) and, for load-bearing claims, an independent probe or second method.
8. **Update `docs/` + `PROVENANCE.md` together** — no fact enters `docs/` without an
   auditable evidence link and row, with evidence label and validated range.
9. **Verify and commit a reviewable unit.** Re-run the documented commands; run
   assembler/disassembler round-trip + corpus checks for ISA changes; run consistency
   searches for superseded values; inspect the diff for accidental blobs, archives, or
   secrets. Commits stay focused; the git history **is** the clean-room paper trail.

**Orchestration:** the main agent reviews reports for clean-room compliance and technical
soundness, owns `docs/`, `PROVENANCE.md`, and `docs/P0-P1-CLOSURE.md`, and commits all
artifacts. Subagents get self-contained dispatches (rules, device/recovery details,
hypothesis + method). Run ≤2 parallel device experiments, on **disjoint files**.

### Git conventions
- Commit after each experiment and each doc update; never batch unrelated work.
- Messages: `exp(NNNN): <what was learned>`, `docs(<subsystem>): <what>`, `tools: <what>`,
  `chore: <what>`. Body: what/why + the provenance.
- The git history **is** the clean-room paper trail. Keep it honest and complete.

---

## Repository layout

```
/CLAUDE.md            ← this governance file (the rules)
/CODEX.md             ← BINDING experiment process contract (10-step loop, evidence labels)
/AGX_RE_INFORMATION_GAPS.md ← authoritative P0/P1 gap analysis (the current acceptance audit)
/PROVENANCE.md        ← clean-room audit log: every documented fact → how it was learned
/gpu_knowledge/       ← READ-ONLY public reference knowledge base (do not modify)
/mesa/                ← READ-ONLY reference: M1/M2 userspace driver + pinned Asahi UAPI
                         compatibility inventory (do not edit)
/docs/                ← THE DELIVERABLE: clean-room hardware documentation
   /ROADMAP.md        ← A18 phase status board (historical; final-push + red-team record)
   /ROADMAP-M4.md, /ROADMAP-M5.md ← completed M4 / M5 phase boards
   /P0-P1-CLOSURE.md  ← LIVE status board for the active Apple9 closure goal
   /isa/              ← shader ISA (encodings, registers, instruction families)
   /cmdstream/        ← control/command stream & state packets (GenXML-style)
   /descriptors/      ← texture/sampler/buffer descriptor layouts
   /tiling/           ← texture/image memory layout (swizzle, compression)
   /pipeline/         ← TBDR specifics, compute dispatch, tile/imageblock model
   /m4-deltas.md      ← M4-over-A18 delta layer
/experiments/         ← one dir per experiment: EXP-NNNN-slug/ (sequential for Apple9
                         closure work; EXP-M4-* / EXP-M5-* are completed waves; quarantined
                         experiments keep their QUARANTINE.md and stay append-only)
/tools/               ← reusable RE tooling: shdump (compile+extract), agxtest (splice
                         testbed), iotrace (IOKit interposer), agx-isa (Apple9 DB),
                         agx-isa-m5 (M5 fork)
```

---

## Documentation targets (what "userspace" means here)

Mirrors the userspace responsibilities of Mesa `src/asahi`, keyed to the P0/P1 rows:

1. **Shader ISA (AGX Apple9 — G16G/G17P)** — the largest target. Encodings, register file,
   spill/scratch, helper programs, prolog/epilog linkage; new instruction families (ray
   tracing, mesh shading, matrix/cooperative ops, texture/atomic variants). Method: compile
   our own shaders → extract → disassemble → validate encodings by hardware round-trip, and
   prove the *encoder* can synthesize arbitrary legal combinations (not just tokenize). [P0.6, P0.8, P1.3]
2. **Control / command stream** — VDM (draw) / CDM (compute) / tiler / fragment command
   lists, USC binding words, state packets; **relocatable, independently packable**. Method:
   black-box trace + change-one-parameter diffing. [P0.5, P0.3, P1.7]
3. **Resource descriptors** — texture/sampler/buffer/PBE descriptor bit layouts and the
   bindless/argument-buffer model. Method: trace + probe by varying format/dims. [P1.1, P1.2]
4. **Texture/image memory layout** — tiling/swizzle order, lossless compression per format,
   typed-format conversion behavior. Method: hardware probing (known pattern in, read
   layout out). [P1.2]
5. **TBDR & compute specifics** — tile size, imageblock/threadgroup memory, sample
   positions, partial-render behavior, memoryless targets, BG/EOT programs, dispatch
   encoding. [P0.4, P1.1]
6. **Userspace↔kernel interface notes** — what userspace must hand the kernel (submit
   shape, BO/VM expectations, `usc_exec_base` mapping, helper/scratch handoff), for
   coordination with the kernel team. [P0.1, P0.2, P1.5, P1.6]

---

## Methodology: probe the HARDWARE, not Metal

Our subject is the **AGX hardware's capability envelope**. Metal is merely the most
convenient source of known-valid starting points (valid instruction encodings, valid
command buffers). **We do not care how Metal works; we care what the silicon can do.**
The AGX was designed to run Metal (plus a narrow OpenGL subset), so its exposed surface is
Metal-shaped — but the hardware very likely supports capabilities Metal never emits, and
very likely *lacks* things Vulkan/OpenGL want. Both facts are what we are here to discover.

**Extrapolate, then test (the Rosenzweig method).** This is a primary job, not an optional
extra. Alyssa Rosenzweig used it to great effect on M1/M2:
1. Start from a known-good encoding (from one of our own compiled shaders, or a captured
   command buffer).
2. **Hypothesize** what *might* also exist — perturb opcode/modifier/operand/addressing
   fields; reason from the ISA's structure ("there's `fadd`; is there an `fadd` with a
   different rounding mode / carry / a wider form?"); and reason from features other APIs and
   GPUs expose that Metal does **not** ("Vulkan wants logic ops / arbitrary sampler border
   colors / polygon line-mode / provoking-vertex / transform feedback — does the HW do it?").
3. **Craft the encoding / state** and run it on real hardware.
4. **Observe and document the result — positive OR negative.**

**Negative results are first-class deliverables.** "Encoding X faults", "mode Y is a no-op",
"capability Z does not exist" carries equal weight to a success. Absence-of-capability is
exactly what tells the implementation team what must be **software-emulated** in Vulkan/GL.
Record every hypothesis and its outcome in `docs/hypotheses.md` (works / no-op / faults /
inconclusive), with a reproducible experiment. Do not quietly drop the ones that didn't pan
out — the trail of what was tried *is* knowledge.

**The Metal-subset heuristic for choosing what to probe:** features Vulkan/OpenGL need that
Metal exposes differently or not at all are the highest-value probe targets — for each, the
hardware either supports it natively (a nice instruction/mode to hand the implementers) or it
doesn't (flag for emulation). Keep a running list; examples to keep chasing: logic ops,
extended/dual-source blend, arbitrary sampler border colors, polygon/line fill & wide lines,
provoking-vertex convention, depth clip vs clamp modes, geometry/tessellation/transform-feedback
hooks, and instruction-level integer/bitfield/rounding/subgroup/quad ops beyond Metal's surface.

**Safety:** capability probing *will* occasionally fault or hang the GPU — that is expected
and is itself a data point. Follow the reboot protocol, route fault-prone splices to the
reboot-recoverable A18, and isolate probes (one hypothesis per run where feasible) so a
single bad encoding doesn't invalidate a batch of results.

---

## After a context compaction

Follow the global recovery procedure in `~/.claude/CLAUDE.md` first (read the last ~20 turns
of the on-disk transcript), then re-read this file, `CODEX.md`, and `docs/P0-P1-CLOSURE.md`
before resuming.
