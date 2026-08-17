# Codex Process for Clean-Room AGX Reverse Engineering

This file is the operating contract for work in this repository.

The primary target is the **Apple A18 Pro / G17P**. The **Apple M4 / G16G** is the
Apple9 comparison and validation target. M5 work is deferred unless the user
explicitly brings it into scope.

## The process is part of the deliverable

The goal is not merely to obtain correct-looking answers. The goal is to produce
hardware facts through a clean-room process that another person can audit,
reproduce, falsify, and use without consulting Apple's implementation.

**Process quality is as important as technical outcome.** A result without its
method, inputs, raw observations, and provenance is not a result for this project.
It must not enter the hardware documentation.

The repository must preserve both:

1. the outcome: the hardware fact, negative result, or bounded unknown; and
2. the proof trail: the question, hypothesis, exact experiment, authored inputs,
   raw output, analysis, validation, limitations, and clean-room provenance.

If evidence is missing, ambiguous, irreproducible, or tainted, record the gap and
run a new clean experiment. Never reconstruct evidence from the desired conclusion.

## Absolute clean-room boundary

We reverse-engineer **hardware behavior**, not Apple's software.

### Allowed sources of knowledge

- **HW-PROBE:** run controlled inputs on live A18 Pro or M4 hardware and observe
  outputs, faults, timing, memory contents, or other externally visible behavior.
- **DATA-TRACE:** record data crossing the boundary from our own process to the
  kernel/firmware, including call parameters, command buffers, descriptors,
  register values, and mapped buffer contents. Log data, never Apple code.
- **OWN-SHADER:** write our own MSL, compile it through the public runtime API,
  extract only the machine code produced from that source, and analyze or splice
  those bytes with our own tools. This exception applies only to shaders whose
  complete source we authored or whose permissively licensed source and provenance
  are committed in this repository.
- **PUBLIC:** use publicly available specifications, presentations, documentation,
  and open-source projects. Public sources may identify questions, terminology, or
  the shape of a required interface. Apple9 hardware values must still be established
  by live probing unless explicitly documented as public-source facts.

### Forbidden sources and techniques

**Never disassemble, decompile, dump symbols from, strings-scan, debug, trace the
code of, inspect executable sections of, or otherwise introspect any Apple binary.**

This includes, without limitation:

- Metal, AGX, IOGPU, or IOAccelerator frameworks and dylibs;
- Apple's proprietary shader compiler or other toolchain binaries;
- kernel extensions, kernel code, firmware, system shader caches, and precompiled
  Apple-authored shaders;
- Apple executables or libraries inspected with Ghidra, IDA, Hopper, `otool`,
  `nm`, `objdump`, `strings`, LLDB/GDB disassembly, class-dump, radare2, or an
  equivalent tool.

It is permitted to invoke documented/public APIs from our own harness and treat the
Apple stack as a black box. It is not permitted to learn from the stack's code.

Do not use leaked, unreleased, private, or NDA material. Do not copy Apple code or
incompatibly licensed implementation code. Do not turn a compiler-generated sequence
from one of our shaders into an algorithm to copy; isolate and document hardware
instruction encodings and behavior instead.

When the source of a fact is unclear, treat it as forbidden and stop. A missing fact
is preferable to a fact that can contaminate the project.

## Target discipline

- Probe A18 Pro/G17P directly for A18 facts.
- Use M4/G16G to validate the Apple9 common model and identify explicit deltas.
- Do not promote an A18 observation to an M4 fact, or the reverse, without a recorded
  validation or an explicit `INFERRED` label.
- Prefer the reboot-recoverable A18 target for dangerous byte splices or fault-prone
  sweeps. Every device operation must have a hard timeout and a documented recovery
  path.
- Do not treat M5 results as evidence for A18/M4. M5 is a later, separate workstream.

## Standard experiment workflow

Every new hardware claim follows this loop.

### 1. Select a concrete question

Choose a question from `AGX_RE_INFORMATION_GAPS.md`, the userspace-requirements
matrix, a documented unknown, or a falsifiable inconsistency. Define which exact
driver decision or hardware field the answer will support.

For A18/M4 completeness, the current acceptance bar is the unchanged Asahi UAPI and
its existing userspace/kernel division of responsibility. Do not classify something
as kernel-managed merely because it was not visible in one macOS capture. Check what
the current UAPI requires userspace to supply.

### 2. State a falsifiable hypothesis

Write down, before running the experiment:

- the proposed encoding, semantic, layout, or negative claim;
- the independent variable and controlled variables;
- the expected observation if the hypothesis is true;
- at least one observation that would refute it;
- known confounders, such as compiler transformations, allocator movement, caching,
  firmware-owned data, or inspecting the wrong buffer object.

### 3. Build the smallest authored probe

Use our own source and tools. Prefer change-one-variable experiments, paired controls,
asymmetric values, boundary values, and inputs that distinguish competing explanations.
For ISA work, separate these evidence levels:

- compiler-emitted correlation;
- differential compilation;
- byte-exact tokenization or round trip;
- splice-and-observe hardware validation;
- independently generated encoding executed successfully on hardware.

The later levels are stronger. Tokenizing observed bytes does not prove that a compiler
can synthesize arbitrary operands or unobserved combinations.

### 4. Capture the baseline before mutation

Save the authored source, build/run command, target identity, relevant OS/tool versions,
repository revision, unmodified output, and expected readback before changing bytes or
parameters. A mutation without a retained baseline is not independently reviewable.

### 5. Run on live hardware with safety controls

- Apply hard timeouts to compilation, dispatch, rendering, tracing, and remote commands.
- Use watchdogs for large sweeps and preserve the last completed case.
- Record faults, hangs, rejected programs, and recovery actions as results.
- Do not silently discard negative or inconvenient outcomes.
- Change one parameter at a time where possible; use multi-point and boundary sweeps
  before generalizing a formula.

### 6. Preserve all experiment artifacts

Every experiment gets a committed directory such as:

```text
experiments/EXP-NNNN-short-name/
  README.md            # question, hypothesis, method, commands, clean-room statement
  RESULTS.md           # observations, interpretation, limitations, verdict
  manifest.json        # target/tool/revision metadata and artifact hashes when practical
  harness/             # authored runners and tracing/probe code
  kernels/             # authored MSL inputs
  analysis/            # repeatable analysis scripts and derived reports
  raw/                 # immutable raw logs, byte traces, readbacks, and failures
```

Equivalent layouts already used by the repository are acceptable, but the same
information must be present.

Raw observations are append-only evidence. Do not edit a raw capture to make it tidy,
overwrite a previous run, or keep only a hand-selected excerpt. If a raw artifact is too
large or cannot legally be committed, commit a manifest containing its exact origin,
size, cryptographic hash, retention location, generation command, and a small lawful
diagnostic excerpt. Never commit an Apple binary, proprietary blob, or Apple-authored
precompiled shader.

Keep failed probes, compile rejections, no-op splices, faults, and counterexamples. They
bound the hardware just as positive results do.

### 7. Separate observation from interpretation

`RESULTS.md` must distinguish:

- what was directly observed;
- the interpretation supported by those observations;
- alternative explanations not yet excluded;
- the exact parameter range tested;
- whether the result reproduced on A18, M4, or both;
- what remains unknown and the safe driver fallback.

Never state a universal rule from a narrow sweep without labeling the untested parameter
space. Prefer `UNKNOWN`, `INFERRED`, or `PARTIAL` to unjustified certainty.

### 8. Falsify before promoting

Use adversarial tests designed to break the proposed rule: different registers, formats,
dimensions, stages, resource counts, alignment boundaries, op variants, and repeated state
transitions. Where practical, require an independent probe or a second method before a
load-bearing claim is marked validated.

When a later experiment corrects an earlier result, preserve the earlier record. Mark it
`SUPERSEDED`, cite the correcting experiment, update every derived document, and search for
stale copies of the old claim.

### 9. Update documentation and provenance together

No hardware fact enters `docs/` unless the same change provides an auditable evidence link.
For each promoted fact:

- cite the experiment and precise raw/derived artifact;
- add or update its row in `PROVENANCE.md`;
- assign an evidence category and strength;
- state the validated range and remaining unknowns;
- update relevant capability, roadmap, porting, requirements, and gap documents;
- check that summaries do not retain superseded values.

Suggested evidence labels, from strongest to weakest:

- `HW-VALIDATED` — independently generated or spliced value changed live behavior as predicted;
- `DATA-TRACE-VALIDATED` — controlled input changes correlated with captured boundary data and,
  where applicable, hardware readback;
- `OWN-SHADER-DIFF` — isolated correlation in code compiled from our source;
- `STRUCTURAL` — length, framing, or round-trip known but semantic fields incomplete;
- `INFERRED` — plausible and explicitly awaiting falsification;
- `UNKNOWN` — not established.

### 10. Verify and commit a reviewable unit

Before committing:

- rerun the relevant probe or analysis from documented commands;
- run assembler/disassembler round-trip and corpus checks for ISA changes;
- run consistency searches for superseded values;
- ensure every claimed file and raw artifact exists;
- verify the clean-room statement and provenance row;
- inspect the diff for accidental proprietary blobs, generated archives, secrets, or
  unrelated changes.

Keep commits focused: experiment evidence first, then derived documentation when practical.
The git history is part of the clean-room paper trail and must remain intelligible.

## Minimum experiment record

An experiment is not complete unless a reviewer can answer all of these questions from the
repository alone:

1. What precise question was asked, and why did it matter?
2. What was the pre-registered hypothesis and falsifier?
3. Which target and software/tool revisions were used?
4. Were every inspected shader byte and every executable probe authored by us or from a
   committed permissively licensed source?
5. What exact commands reproduce the run and analysis?
6. Where are the complete raw observations, including failures?
7. How were observations converted into the documented fact?
8. What parameter range was actually exercised?
9. What independent validation or adversarial test was performed?
10. Which documentation and `PROVENANCE.md` entries depend on the result?
11. Can the reviewer verify that no Apple binary was introspected?

If any answer is missing, the experiment is incomplete and its conclusions must remain out
of the normative specification.

## Clean-room provenance audit

Every experiment `README.md` and `RESULTS.md` must contain a short clean-room attestation:

```text
Clean-room provenance: [HW-PROBE / DATA-TRACE / OWN-SHADER / PUBLIC]
Inputs inspected: <authored source and lawful data artifacts>
Apple binary introspection: NONE
Reproduction: <commands or script entry point>
Evidence: <raw paths and hashes/manifest>
```

The attestation is necessary but not sufficient. Its claims must be checkable against committed
source, raw artifacts, manifests, and history. Periodically audit the chain:

```text
documented fact
  -> PROVENANCE.md row
  -> experiment RESULTS.md
  -> analysis script/report
  -> immutable raw capture
  -> authored probe inputs + exact reproduction command
```

Broken links, missing raw data, unexplained manually copied bytes, or an unknown source break the
chain. Downgrade or remove the dependent fact until the chain is restored by a new clean probe.

## Acceptance standard

The current authoritative gap analysis is `AGX_RE_INFORMATION_GAPS.md`. Earlier PASS reviews are
historical evidence of broad decoding coverage, not proof of a complete driver specification.

Completion means an implementer can generate arbitrary supported Apple9 shaders and relocatable
command streams, populate every field assigned to userspace by the unchanged Asahi UAPI, and build
the required helper, scratch, prolog/epilog, BG/EOT, partial-render, and synchronization machinery
without guessing or consulting Apple's implementation.

A corpus round trip, a successful captured-template replay, or a broad capability census is useful
evidence, but none alone clears this gate. The gate passes only when the synthesis specification,
UAPI mapping, raw evidence, and clean-room provenance chain all pass review.
