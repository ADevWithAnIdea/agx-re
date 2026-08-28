# EXP-0084 M4 dynamic buffer addressing (MEM-20/21/22)

Answers Part-II questionnaire items **MEM-20, MEM-21, MEM-22** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` — the bindless/descriptor-array blockers
for a Vulkan-grade Apple9 compiler:

- **MEM-20** — can Apple9 load/store through a 64-bit device address held
  dynamically in a GPR/register pair, without first assigning it to a
  statically encoded base slot?
- **MEM-21** — can a non-uniform, per-lane index select DIFFERENT buffer
  base addresses for different lanes in one SIMD group (vs. a uniform
  whole-dispatch selection)?
- **MEM-22** — when given more live buffer resources than the direct-slot
  path holds, does the toolchain reject, fall back to a dynamic-address
  path, or split/preload — and does that fallback actually execute
  correctly on hardware?

Method: 14 frozen cases across three kinds. **Dispatch** (12 cases,
`harness/probe.m`): compile our own MSL (`kernels/probes.metal`,
`kernels/cap_kernels.metal`) with the public Metal API, obtain dynamic
device addresses ONLY through public mechanisms (`MTLBuffer.gpuAddress`;
Metal's implicit argument-buffer `MTLArgumentEncoder` API), dispatch on the
real M4 GPU, and read back which buffer each lane actually dereferenced —
direct behavioral HW-PROBE + OWN-SHADER evidence, with an explicit uniform-
selection control (MEM-21 broadcast) contrasted against a thread-id-derived
per-lane-divergent selection (MEM-21 positive) and a single-lane-outlier
control. **Decode** (1 case, `analysis/decode_case.py`): compile the
`splice_target` kernel with `tools/shdump`, tokenize with `tools/agx-isa`
(our own instruction DB, imported as a library — never shelled out to a
disassembler on an Apple binary), and apply a frozen structural
identification algorithm to locate the exact `device_load` instruction
fields responsible for the dynamic dereference — static, OWN-SHADER
evidence for the mechanism. **Splice** (1 case, `analysis/splice_case.py` +
`harness/splice_run.m`): hand-perturb ONE byte (the identified
`index_reg` field) in our own compiled bytes and re-execute the archive on
real hardware (`MTLPipelineOptionFailOnBinaryArchiveMiss`, the established
`tools/agxtest` technique) — the strongest evidence tier, an independently
synthesized encoding change causing a predicted, observed hardware output
change, not merely a tokenized observation.

Full design, hypotheses, refuters, the exact frozen case matrix, and the
splice identification algorithm are in `PRE_REGISTRATION.md`.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API. Every dynamic
device address dereferenced anywhere in this experiment comes from our own
CPU-side harness writing a backing `MTLBuffer`'s public `.gpuAddress` (or
Metal's public `MTLArgumentEncoder`) into an ordinary data buffer — never
from inspecting Apple binary code. `tools/shdump`, `tools/agx-isa`,
`tools/agxtest` are read-only prior clean-room tooling from this same
project (their own provenance is documented in their own trees); this
experiment invokes/imports them without editing them.

Commands (in order):

```sh
python3 -B verify.py --selftest        # required before any build; runnable pre-GPU
python3 -B verify.py --seqtest         # gate-order state machine; runnable pre-GPU
python3 -B make_manifest.py --check
python3 -B verify.py --preflight       # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B verify.py --selftest && python3 -B verify.py --seqtest
python3 -B verify.py --between-runs
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B verify.py --selftest && python3 -B verify.py --seqtest
python3 -B verify.py --captured        # full byte-identity cross-run gate
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
```

Scope: **local M4 (G16G) only.** No A18 Pro (G17P) claim, no cross-target
inference — the A18 is hands-off for all work in this repository.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness/runner/verifier/decode/splice
sources; `tools/shdump`, `tools/agx-isa`, `tools/agxtest` (read-only)
Apple binary introspection: NONE
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260827-run01`, `raw/m4-20260827-run02`, `manifest.json`
