# EXP-0054 — M4 scissor and depth-bias behavior

## Question and scope

This experiment asks how the public Metal scissor and depth-bias inputs behave on
the local M4 for asymmetric/edge/empty rectangles, two viewport-indexed scissors,
constant/slope signs, and sign-matched clamps. It supplies bounded behavioral
evidence toward `AGX_RE_INFORMATION_GAPS.md` P0.3.

It does **not** identify `isp_scissor_base`, `isp_dbias_base`, private descriptor
bytes, integer-depth-bias selection, kernel/firmware ownership, or Linux UAPI
marshaling. No BO was captured or inspected. A18 Pro is untested.

## Auditable process

The process history is part of the result:

1. `PRE_REGISTRATION.md` was committed alone as `13d200c5` before any source
   compilation or GPU execution.
2. Public-header review caught oppositely signed clamp inputs and missing flat
   slope controls. The original was preserved; `PRE_REGISTRATION_AMENDMENT.md`
   corrected them and was committed alone as `7a7fde9c`, still before any build.
3. Fresh processes runs01/02 completed the corrected 19-case matrix with complete
   guarded bytes. Their magnitude-100 clamp pairs were byte-identical because the
   observed displacement was only about `5.96e-6`, below the `0.001` clamp. This
   falsified the preregistered strict-reduction expectation without testing an
   engaged clamp.
4. That negative result was preserved. `PRE_REGISTRATION_FOLLOWUP.md` froze a
   change of only the four large-bias magnitudes to 100000 and was committed alone
   as `4c43187a` before the follow-up source was compiled or run.
5. Fresh processes runs03/04 executed the final byte-identical source. They are
   canonical for the engaged-clamp result; runs01/02 remain successful process and
   falsification evidence.

The harness embeds only authored MSL, compiles it with the public runtime, and
observes public status/errors plus complete RGBA8Unorm and Depth32Float readbacks.
Every 1024-byte image is retained inside a 1088-byte record with exact 32-byte
prefix/suffix guards. No hash or aggregate substitutes for the bytes.

## Frozen matrices

Single scissors are full `(0,0,16,16)`, asymmetric `(3,5,7,4)`, edge
`(15,14,1,2)`, zero-width `(6,7,0,5)`, and zero-height `(6,7,5,0)`.

The two public multi-scissor cases use identical full-target viewport transforms.
Slot 0 remains `(1,2,5,6)`; slot 1 changes from `(9,3,4,10)` to `(11,8,3,5)`.
Two authored full-screen primitives select viewport indices 0/1 and write distinct
colors.

The final depth matrix contains 12 cases: flat/sloped strict controls, constant
and slope signs, flat slope-only controls, and matched unclamped/clamped
`constant = ±100000` pairs. Negative cases use `less`; the positive clamp pair
uses `greater`. See the two preregistration amendments for the exact table and
falsifiers.

## Reproduction

Use new append-only run IDs on the stated target:

```sh
python3 run.py --run-id m4_YYYYMMDD_runNN
python3 analysis/analyze.py
python3 make_manifest.py
python3 verify.py
```

The runner applies 60-second build and 120-second process timeouts, writes exact
argv/stdout/stderr/start/exit records, preserves failures, records the target,
tool versions, public-header hashes, Git revision, and exact historical/final
source hashes, then writes a complete per-run SHA-256 inventory. The executable is
temporary and never retained or inspected.

`analysis/analyze.py` enforces a closed 23-line process transcript, exact case
order and field sets, byte-models every scissor color image and guard, binds every
depth image to its exact retained SHA-256, checks finite depth, and requires exact
repetition. `verify.py` independently binds both complete stdout hashes, exact
build/run argv, four raw inventories, two historical source reconstructions, all
three committed preregistration blobs and Git order, regenerated analysis, clean
scope, and the complete committable manifest.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + OWN-SHADER source + PUBLIC
Inputs inspected: authored Objective-C/MSL; public Metal headers/status/errors;
  complete color/depth/guard bytes allocated by the authored process
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command/state/unknown BO payload tracing: NONE
Generic memory scan / pointer following: NONE
Mutation/splice/replay: NONE
Reproduction: python3 run.py --run-id NEW; python3 analysis/analyze.py; python3 verify.py
Evidence: raw/, analysis/summary.json, analysis/report.txt, manifest.json
```
