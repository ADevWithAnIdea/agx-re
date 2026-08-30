# Subagent briefing (read this + `../CLAUDE.md` + `../CODEX.md` before every experiment)

You are a clean-room reverse-engineering agent. Working dir: `/Users/user/asahi_re/public/agx-re`.
**`../CLAUDE.md` is governing law and `../CODEX.md` is the binding process contract** — read both.
This brief is the standing operational context; your dispatch prompt adds the specific task.

## Prime Directive (non-negotiable)
CLEAN ROOM ABOVE ALL — better NO result than a TAINTED one.
- **NEVER disassemble/decompile/introspect the machine code of ANY Apple binary** (Metal, AGX*,
  IOGPU, kexts, firmware, the shader compiler). No `otool -tv`/`-tV`, `objdump -d`, Ghidra, lldb
  disassembly, class-dump, radare2 on anything Apple. The ONLY machine code you may inspect is
  shaders **we compiled from our own MSL**.
- Allowed: compile our own MSL, manipulate/run our own compiled bytes, observe outputs (OWN-SHADER);
  hardware probing (HW-PROBE); black-box data tracing at the userspace↔kernel boundary (DATA-TRACE);
  reading public/open-source refs — `gpu_knowledge/`, `mesa/` (PUBLIC).
- **Never leave `/Users/user/asahi_re/public/agx-re` on the LOCAL machine.** If any step's
  cleanliness is unclear, STOP and report — do not guess. **This includes scratch, pilot and
  dry-run files: do NOT write to local `/tmp` or anywhere outside the repo, not even briefly.**
  Use a `work/` subdirectory inside your own experiment directory. Two agents have already tripped
  this while root-causing (EXP-0098, EXP-0109); both self-disclosed and relocated, which is the
  right response — but the rule is absolute, and a quick throwaway probe is exactly when it gets
  broken.
- **On the neo (the remote target) this rule is different, because it is a compute target rather
  than the evidence store.** Work under a dedicated directory there (e.g. `~/agxre/<EXP-NNNN>/`),
  keep it tidy, and **copy every artifact you intend to keep back into your experiment directory
  in this repo**. Nothing on the neo is evidence until it is pulled back and committed here. Do
  not read or modify anything on the neo outside your own working directory.

## Targets

- **A18 Pro / G17P is THE test target** (user directive 2026-08-28). `users-MacBook-Neo.local`,
  **DHCP — currently `192.168.10.243`**; if it moves, ask the orchestrator, do not scan blindly.
  `AGXAcceleratorG17P`, arch `applegpu_g17p`, **5 GPU cores**, macOS 26.6, Metal family Apple9,
  **full Xcode present** (`/Applications/Xcode.app`) — richer than the M4 ever was.
  Build ObjC there: `clang -fobjc-arc -framework Metal -framework Foundation`; runtime
  `newLibraryWithSource:` is verified working.
- **The local M4 is RETIRED for GPU work — do NOT run experiments on it.** Local GPU testing
  destabilized WindowServer, took `MTLCompilerService` down machine-wide, and killed agents
  mid-capture. The M4 hosts the repo and does analysis only. Committed M4 evidence stays valid on
  its own target; **closure is now measured against full G17P**.
- **`macvdmtool` is FORBIDDEN to subagents, without exception.** Only the orchestrator may run it,
  only when the neo is unresponsive. If the neo stops answering, **STOP and report BLOCKED** with
  where you were — do not attempt any recovery yourself.
- **M5 (`192.168.170.253`) is a separate completed workstream — do not probe it.**

**Recovery model (remote target).** Illegal shader encodings are usually fault-contained
(per-command-buffer error, no wedge). The structural gain of the G17P pivot is that a wedge now
costs the **remote** machine, not the orchestrator and not this repo — on the M4 a bad run took out
WindowServer and killed agents mid-capture. Still: isolate one change per dispatch, hard-timeout
every compile/dispatch/render/trace, and save progress incrementally (`PROGRESS.md` after every
milestone). **Evidence lives in this repo on the M4, so pull results back promptly** — do not let
captures accumulate only on the neo, where a reboot loses them. If the neo stops responding:
**STOP and report BLOCKED** with where you were; recovery is the orchestrator's job.

## A shell hazard that has now silently corrupted work TWICE in one session

**Do not chain a state-changing step behind `&&` and assume it ran.** Both of these happened on
2026-08-30, hours apart, to different actors:

- The orchestrator appended a `PROVENANCE.md` row inside `cmd1 && cmd2 && cat >> PROVENANCE.md <<EOF`.
  **The append silently did not execute**, while `git commit` beside it succeeded — so the commit
  looked complete and the paper trail was not. It was caught only because a later edit to that row
  failed to find its own text. A merged verdict with no citation is exactly the reverse-chain gap
  EXP-0176 spent a whole experiment measuring.
- EXP-0179's `sync.sh push` returned non-zero inside a chained command, so a gated pass **executed
  against the STALE pre-amendment harness** — 6 cases instead of 8, remote hashes not matching local.
  It burned a run id, which was retained and marked defective rather than topped up or deleted.

**The rule: after any push, write, or generate step whose output you will then depend on, VERIFY IT
SEPARATELY** — re-read the file, compare the remote hash, count the rows. EXP-0179's own conclusion is
the one to copy: *"I now verify remote hashes after every push instead of trusting `&&`."* A silent
no-op inside a chain is indistinguishable from success in the exit code, and both failures above
produced artifacts that looked correct.

Related, and the same shape one level up: **a clean result from a stub is not evidence a defect is
absent.** EXP-0179's offline stub failed to reproduce the shared runner's hang cascade, and it
recorded that as an OBSERVATION rather than a gate, because the real failure needs scheduling luck.
It relied on the structural fix, not the passing stub.

## Process — the parts that most often bite (full contract: `../CODEX.md`)
- **Pre-register before you build.** Commit-ready `PRE_REGISTRATION.md` (+ `CAPTURE_CONTRACT.json`
  where the dispatch says so): falsifiable hypothesis, variables, expected observation + a refuter,
  confounders, frozen source hashes, raw-record schema, environment, timeouts. **An underspecified
  frozen contract is an automatic STOP** — do not fill gaps as you go.
- **Baseline before mutation**; change one variable at a time; asymmetric/boundary values.
- `raw/` is append-only immutable evidence: text logs / JSON only — never binary archives,
  `.metallib`, or Apple blobs. Keep failures, faults, and no-ops; they bound the hardware.
- Separate **observed** from **interpreted**; state the exact tested range and target (**G17P is now the test target**; older results are
  M4/G16G — never silently generalize between them); label evidence (`HW-VALIDATED` / `DATA-TRACE-VALIDATED` /
  `OWN-SHADER-DIFF` / `STRUCTURAL` / `INFERRED` / `UNKNOWN`). Tokenizing bytes or a round trip
  never proves an encoding can be *synthesized*.
- **Assume the host will crash mid-run.** It has repeatedly. Design so a kill costs at most one
  milestone: append each case record to `raw/` as it completes (never buffer results in memory to
  write at the end), `fflush` after every record, write a timestamped `PROGRESS.md` entry after
  every milestone, and write partial `RESULTS.md` sections as soon as their data exists. On resume,
  re-orient from your own files — `PROGRESS.md`, the frozen contract, and what is actually in
  `raw/` — never from memory of what you were doing.
- **A partial capture is retained, never reused.** If a kill leaves a half-finished run directory,
  leave it exactly as it is, note it, and capture under a **new** id. Do not top it up, delete it,
  or reuse its id.
- **Pin the revision at pre-registration; do not gate on live `HEAD`.** Record the git revision
  (and dirty flag) in your frozen contract at pre-registration time and compare captures against
  **that recorded value**, not against whatever `HEAD` is when run02 starts. The orchestrator
  commits other experiments' results continuously, so a cross-run gate written as "HEAD must not
  move" will abort mid-sequence through no fault of your experiment (this happened to EXP-0082).
  A capture is valid if the *authored blob hashes* match; repo `HEAD` moving because a sibling
  experiment landed is not contamination.
- **Never reuse or overwrite a run id.** If a capture looks defective, retain it and either
  quarantine with a named successor or capture the replacement under a **new** id. "Nothing was
  promoted yet" is not a licence to erase evidence (EXP-0085 did this; it cost auditability).
- **Never repair or rerun a quarantined experiment in place** (see its `QUARANTINE.md`); a
  successor takes a NEW experiment number and a fresh pre-registration.

## Existing tools — USE these, do not rebuild (read their READMEs first)
- `tools/shdump/` — compile our MSL → extract raw AGX `_agc.main` bytes (`agxparse.py`, `--locate`).
- `tools/agxtest/` — hardware testbed: splice arbitrary bytes into our compiled shader, run on the
  real GPU, read back outputs (`agxrender.m`; `persistrun.py` = persistent runner, faults
  logged-and-continued). Metal runs tampered code with no integrity check (bound `MTLBinaryArchive`
  + `FailOnBinaryArchiveMiss`).
- `tools/agx-isa/` — machine-readable Apple9 instruction DB (`db.json`/`isadb.py`) driving assembler
  + disassembler + round-trip test (`roundtrip_test.py`). Authoritative encoding source.
  (`tools/agx-isa-m5/` is the M5 fork — do not touch it for Apple9 work.)
- `tools/iotrace/` — DYLD interposer: captures our own process's IOKit traffic + BO contents.

## What's already validated (build on it; don't redo)
The authoritative task list is `../APPLE9_RE_IMPLEMENTATION_GAPS.md` (read your dispatched item
plus its "areas already covered" section). Status of the sixteen P0/P1 closure rows:
`../docs/P0-P1-CLOSURE.md`. Established facts: `docs/isa/README.md` and the relevant prior
`experiments/EXP-*/RESULTS.md`.

## Deliverable conventions
- **Do NOT `git commit`** — the orchestrator reviews & commits.
- **Do NOT edit `docs/`, `PROVENANCE.md`, `docs/P0-P1-CLOSURE.md`, `CLAUDE.md`, or `CODEX.md`**
  unless your dispatch says so — the orchestrator owns those. You **may** edit `tools/*` you were
  told to (e.g. `tools/agx-isa/db.json`); only one experiment edits a given tool file at a time.
- Create `experiments/EXP-NNNN-slug/` per `../CODEX.md` §6: `README.md` (question, hypothesis,
  method, commands, clean-room category), `PRE_REGISTRATION.md`, `manifest.json`,
  `harness/`+`kernels/` (authored code), `analysis/` (repeatable scripts + reports), `RESULTS.md`
  (observations vs interpretation, tested range, target, limitations, verdict).
- Report back raw and honest: what's proven, what's uncertain, faults/reboots, recommended next.
