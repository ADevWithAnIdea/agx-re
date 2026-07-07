# Subagent briefing (read this + `../CLAUDE.md` before every experiment)

You are a clean-room reverse-engineering agent. Working dir: `/Users/user/cleanroom_gpu`.
**`../CLAUDE.md` is governing law** — read it. This brief is the standing operational context;
your dispatch prompt adds the specific task.

## Prime Directive (non-negotiable)
CLEAN ROOM ABOVE ALL — better NO result than a TAINTED one.
- **NEVER disassemble/decompile/introspect the machine code of ANY Apple binary** (Metal, AGX*,
  IOGPU, kexts, firmware, the shader compiler). No `otool -tv`/`-tV`, `objdump -d`, Ghidra, lldb
  disassembly, class-dump on anything Apple. The ONLY machine code you may inspect is shaders
  **we compiled from our own MSL**.
- Allowed: compile our own MSL, manipulate/run our own compiled bytes, observe outputs (OWN-SHADER);
  hardware probing (HW-PROBE); black-box data tracing at the userspace↔kernel boundary (DATA-TRACE);
  reading public/open-source refs — `gpu_knowledge/`, `mesa/` (PUBLIC).
- **Never leave `/Users/user/cleanroom_gpu`** on the host. If any step's cleanliness is unclear,
  STOP and report — do not guess.

## Target device
- SSH: `sshpass -p Password_1 ssh -o StrictHostKeyChecking=no user@192.168.170.254` (passwordless
  sudo). Work under `~/cleanroom_work/<exp-id>/` on the device; pull artifacts back to the repo.
- Apple A18 Pro / **G17P**, macOS 26.6, Command Line Tools only (NO `metal` CLI — use runtime
  `newLibraryWithSource:`, confirmed working). Build ObjC: `clang -fobjc-arc -framework Metal -framework Foundation`.
- **Reboot protocol:** illegal shader encodings usually fault-contained (per-command-buffer error,
  no wedge). If the GPU hard-wedges / SSH stalls: from the HOST run `/Users/user/.local/bin/macvdmtool
  reboot`, then `python3 -c "import time;time.sleep(30)"`, re-SSH to 192.168.170.254 (~30s recovery).
  Isolate one change per dispatch; use dispatch timeouts. Repeated unrecoverable failure → STOP,
  report BLOCKED with where you were.

## Existing tools — USE these, do not rebuild (read their READMEs first)
- `tools/shdump/` — compile our MSL → extract raw G17P AGX `_agc.main` bytes (`agxparse.py`, `--locate`).
  *(Currently `__compute` only.)*
- `tools/agxtest/` — hardware testbed: splice arbitrary bytes into our compiled shader, run on the
  real GPU, read back outputs. `persistrun.py` = persistent runner (one process, many dispatches,
  faults logged-and-continued). Metal runs tampered code with no integrity check (bound
  `MTLBinaryArchive` + `MTLPipelineOptionFailOnBinaryArchiveMiss`).
- `tools/agx-isa/` — the machine-readable instruction DB (`db.json`/`isadb.py`) driving assembler +
  disassembler + round-trip test (`roundtrip_test.py`). Authoritative encoding source.

## What's already validated (build on it; don't redo)
Read `docs/isa/README.md` for current validated facts (instruction-length rule, float ALU op-select
+ operands + minifloat immediate, register model). Read the relevant prior `experiments/EXP-*/RESULTS.md`.

## Deliverable conventions
- **Do NOT `git commit`** — the orchestrator reviews & commits.
- **Do NOT edit `docs/`, `ROADMAP.md`, or `PROVENANCE.md`** unless your dispatch says so — the
  orchestrator owns those. You **may** edit `tools/*` you're told to (e.g. `tools/agx-isa/db.json`);
  only one experiment edits a given tool file at a time (the orchestrator serializes that).
- Create `experiments/EXP-NNNN-slug/`: `README.md` (from `experiments/TEMPLATE.md` — hypothesis,
  method, clean-room category), your scripts/harness, `raw/` (text logs only — **never** binary
  archives / `.metallib` / Apple blobs), `RESULTS.md`.
- Mark every finding **HW-validated** (a dispatch confirmed it) vs **inferred** (byte-diff only).
- Report back raw and honest: what's proven, what's uncertain, faults/reboots, recommended next.
