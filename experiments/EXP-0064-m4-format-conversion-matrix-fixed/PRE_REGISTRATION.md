# EXP-0064 pre-registration — corrected M4 public typed format matrix

Date frozen: 2026-08-20 (America/Los_Angeles). Target: local M4/G16G only;
there is no A18, native Apple9, descriptor, Linux-UAPI, or compiler claim.

This is a new P1.2 experiment. EXP-0062 is quarantined non-evidence and is not
cited as a result. The question is limited to public Metal behavior: for six
named renderable formats, what are the full owned physical backing bytes after
one authored fragment store, and what four words does an authored typed compute
`tex.read(uint2(0))` return in a subsequent encoder of the same public command
buffer?

## Exact frozen backing contract

Each case owns exactly two shared buffers. These are the only payload bytes that
may be retained or opened after command completion:

| backing | prefix | payload | suffix | exact total | retained form |
| --- | ---: | ---: | ---: | ---: | --- |
| render backing | 64 B `0x5a` | 256 B row | 64 B `0xa5` | **384 B** | exactly 768 lowercase hex characters |
| compute backing | 64 B `0x5a` | 16 B / four uint32 words | 64 B `0xa5` | **144 B** | exactly 288 lowercase hex characters |

The 1x1 texture starts at render offset 64 with `bytesPerRow=256`. Every raw
case record must include both full strings, decoded physical texel bytes, four
little-endian compute words, and every guard verdict. Any length mismatch,
missing/extra record, bad hex, nonregular file, symlink, special file, or
unexpected path is a hard stop before payload interpretation.

## Frozen clean-room boundary

Allowed: complete authored MSL committed in `kernels/`, authored public
Metal/Foundation harness code, public status/error objects, and the two full
owned readback buffers above. Before execution the runner retains source SHA-256,
repository revision, `sw_vers`, tool version, device name, and machine identity.

Forbidden: Apple or non-authored binary/code inspection; compiled shader-byte or
archive/library retention/parsing; IOKit/private API/interposer use; BO/resource/
command/state/code trace or dump; metadata parsing; pointers, replay, or memory
mutation. The compiler is a public-API black box only.

## Matrix and hypotheses

The committed MSL defines one common full-screen triangle, five float fragment
outputs, one uint fragment output, and separate float/uint typed readers. Cases:

| case | public format | fragment output | reader |
| --- | --- | --- | --- |
| rgba8unorm_edges | RGBA8Unorm | (-.25,.5,1.25,128/255) | float |
| bgra8unorm_edges | BGRA8Unorm | same | float |
| rgba8srgb_threshold | RGBA8Unorm_sRGB | (.0031308,.0031309,.5,.5) | float |
| r16unorm_midpoint | R16Unorm | (.5,0,0,1) | float |
| rgba16float_edges | RGBA16Float | (-0,1,65504,.333251953125) | float |
| r32uint_exact | R32Uint | 0xdeadbeef | uint |

H1: the two UNorm cases clamp tested endpoints and differ only by declared
RGBA/BGRA channel order; their typed readbacks agree with stored normalized
values. H2: the sRGB case follows the public transfer/quantization calculation
at the named binary32 inputs. H3: R16Unorm midpoint and selected finite RGBA16F
values produce public half encodings and expanded typed reads. H4: R32Uint store
and read preserve the named word. A pipeline/command failure, wrong full backing,
guard change, wrong typed vector, failed public calculation, or repeat mismatch
falsifies the relevant hypothesis. No NaN/inf/subnormal, filtering, blending,
atomic, capability-table, native, or A18 generalization is claimed.

## Runs, safety, and promotion gate

Two append-only runs, six fresh processes each, are mandatory. Each process gets
a fresh device, queue, backing buffers, texture, library, pipelines, and exactly
one command buffer; render precedes compute. Parent process timeout is 20 seconds
with 10-second compile/completion caps. Timeout/fault/reset stops that run with
no automatic retry/recovery. The second run starts only after a first-run exact
path/length/hash completeness preflight succeeds.

Results stay unstaged for independent audit. Promotion requires exact two-run
agreement, full retained buffer/guard evidence, valid target/environment/revision
records, a fail-closed verifier, and a separate documentation review. Otherwise
record a stop or quarantine without an in-place amendment.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API
Apple binary, helper, auxiliary, command/state/code/unknown-BO inspection: NONE
Compiled code bytes or archives inspected: NONE
```
