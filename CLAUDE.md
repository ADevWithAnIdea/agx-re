# Clean-Room RE: Apple A18 Pro GPU Userspace

## Mission

Produce **clean-room hardware documentation** of the userspace-visible side of the
Apple A18 Pro GPU (SoC **T8140**, Metal feature family **Apple9**), sufficient for a
*separate* implementation team to add support to the Mesa `asahi` driver **after** the
kernel driver (being built in parallel, out of scope here) is in place.

We are the **reverse-engineering / documentation team**. We do **not** write the Mesa
driver. We write hardware specs; someone else implements them. This split is the core of
the clean-room defense.

The A18 Pro GPU is generationally different from the M1 (Apple7) and M2 (Apple8) parts
that Mesa currently supports. Everything about *how much* it differs is an empirical
question this effort answers by probing hardware and tracing data — never by looking
inside Apple's code.

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
   (runtime `newLibraryWithSource:` is confirmed working on the device), extract the
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
7. **Never leave this directory (`/Users/user/cleanroom_gpu`).** All host-side work stays
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
  document) and how Mesa parameterizes M1/M2. The A18 Pro implementation is someone else's job.
- **We do NOT depend on a working kernel driver.** Where our documentation implies a
  userspace↔kernel interface, we describe what userspace needs to hand down, and flag it for
  coordination with the kernel team — we do not block on them.

---

## Target device & operational safety

| | |
|---|---|
| Host (here) | macOS, this repo at `/Users/user/cleanroom_gpu`. `sshpass`, `macvdmtool` available. |
| Target | `user@192.168.170.254`, password `Password_1`. Apple A18 Pro, SoC T8140, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / feature family Apple9. SIP **disabled**. `user` is a sudoer (sudo needs the password). |
| Toolchain on target | Command Line Tools only (`clang`, `python3`, `git`). **No `metal` CLI** → we use **runtime** MSL compilation (confirmed working). Full Metal offline toolchain can be installed later if needed. |
| Device workspace | `~/cleanroom_work` on the target. Keep all experiment code/data there, then pull artifacts back here to commit. |

**Reboot protocol (memorize this):**
- If the device becomes unresponsive, behaves strangely, or SSH hangs for unclear reasons,
  reboot it from the **host** with `macvdmtool reboot`. This works below the OS and always
  succeeds.
- After a reboot, **wait 20 seconds** before attempting SSH again.
- Occasional crashes are an expected part of GPU RE. Avoid them where reasonable, don't fear
  them.
- **Escalation:** if you reboot several times and still fail to SSH in several times, mark
  the current goal **BLOCKED**, write down where you were, and return — do not thrash.

---

## Process & workflow

The loop, repeated until the documentation is complete enough to implement from:

1. **Pick the next question** from the current phase (see `docs/ROADMAP.md`).
2. **Spawn subagent(s)** with a specific, self-contained experiment task. Give each the
   clean-room rules, the device credentials, the reboot protocol, and a precise hypothesis +
   method. Independent experiments run in parallel.
3. Subagents **run experiments on the device**, capture raw data, and **report back** with:
   hypothesis, exact procedure, raw results, and analysis. (Subagents inherit these rules and
   are equally bound by the Prime Directive.)
4. The **main agent reviews** the report for clean-room compliance and technical soundness,
   then **commits all artifacts** (scripts, raw captures, written results) into this repo.
5. **Update `docs/`** with any facts that are now established, each with a provenance citation.
6. Repeat.

**Every experiment is reproducible.** No fact enters `docs/` without an experiment (or public
citation) that a third party could re-run to reproduce it. Process matters as much as outcome:
if it isn't written down and committed, it didn't happen.

### Git conventions
- Commit after each experiment and each doc update; never batch unrelated work.
- Messages: `exp(NNNN): <what was learned>`, `docs(<subsystem>): <what>`, `tools: <what>`,
  `chore: <what>`. Body: what/why + the provenance.
- The git history **is** the clean-room paper trail. Keep it honest and complete.

---

## Repository layout

```
/CLAUDE.md            ← this governance file (the rules)
/PROVENANCE.md        ← clean-room audit log: every documented fact → how it was learned
/gpu_knowledge/       ← READ-ONLY public reference knowledge base (do not modify)
/mesa/                ← READ-ONLY reference: M1/M2 userspace driver (do not edit)
/docs/                ← THE DELIVERABLE: clean-room hardware documentation
   /ROADMAP.md        ← phases, open questions, status
   /isa/              ← shader ISA (encodings, registers, new instruction families)
   /cmdstream/        ← control/command stream & state packets (GenXML-style)
   /descriptors/      ← texture/sampler/buffer descriptor layouts
   /tiling/           ← texture/image memory layout (swizzle, compression)
   /pipeline/         ← TBDR specifics, compute dispatch, tile/imageblock model
/experiments/         ← one dir per experiment: EXP-NNNN-slug/ (see experiments/README.md)
/tools/               ← reusable RE tooling we build (interposer, probe harness,
                         our-own-shader compiler+extractor, disassembler extensions)
```

---

## Documentation targets (what "userspace" means here)

Mirrors the userspace responsibilities of Mesa `src/asahi`. Priority order:

1. **Shader ISA (AGX, A18 Pro / Apple9 variant)** — the largest target. Encoding deltas vs
   G13/G14, register file & Dynamic-Caching implications, and new instruction families (ray
   tracing, mesh shading, any matrix/cooperative ops, changed texture/atomic ops). Method:
   compile our own shaders → extract → disassemble → validate encodings by hardware round-trip.
2. **Control / command stream** — how userspace encodes work: VDM (draw) / CDM (compute) /
   tiler / fragment command lists, USC binding words, and state packets. Method: black-box
   trace + change-one-parameter diffing.
3. **Resource descriptors** — texture/sampler/buffer descriptor bit layouts and the (bindless/
   argument-buffer) resource model. Method: trace + probe by varying format/dims.
4. **Texture/image memory layout** — tiling/swizzle order and lossless compression per format.
   Method: hardware probing (known pattern in, read layout out).
5. **TBDR & compute specifics** — tile size, imageblock/threadgroup memory, sample positions,
   partial-render behavior, memoryless targets, dispatch encoding — especially anything changed
   by Dynamic Caching.
6. **Userspace↔kernel interface notes** — what userspace must hand the kernel (submit shape,
   BO/VM expectations), for coordination with the kernel team. Lower priority.

---

## After a context compaction

Follow the global recovery procedure in `~/.claude/CLAUDE.md` first (read the last ~20 turns
of the on-disk transcript), then re-read this file and `docs/ROADMAP.md` before resuming.
