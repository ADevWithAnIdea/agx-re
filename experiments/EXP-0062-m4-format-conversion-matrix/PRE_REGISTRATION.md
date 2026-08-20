# EXP-0062 pre-registration — M4 public typed format conversion matrix

Date frozen: 2026-08-20 (America/Los_Angeles)

Target: local Apple M4 / G16G only. This batch makes no A18 Pro/G17P, native
Apple9 descriptor, Linux UAPI, or compiler-implementation claim.

Gap: P1.2 in `AGX_RE_INFORMATION_GAPS.md` requires per-format feature and
conversion behavior. EXP-0048 established five uniform render-store examples
while locating M4 MRT/PBE structures. It deliberately did not exercise
saturation/rounding edges, typed shader reads, float16 expansion, or sRGB
decode/encode behavior. This new experiment is a public behavioral probe only;
it neither captures nor relates results to private records.

## Question and driver decision

For a small, explicitly named set of public Metal renderable formats, what
physical shared-buffer bytes result from an authored fragment store at selected
conversion edges, and what values does an authored compute shader read back from
the same texture in the immediately following encoder?

The driver-facing value is a bounded API-level conversion table and safe public
fallback guidance. It cannot establish that the same conversion is performed by
native PBE/epilog instructions or establish an Asahi descriptor, blend program,
or Linux format table.

## Frozen clean-room boundary

This is `HW-PROBE + OWN-SHADER source + PUBLIC API` only. It may use complete
authored MSL in `kernels/`, authored Objective-C harness/analysis code, public
Metal/Foundation APIs, public pipeline/command-buffer status, and the complete
contents of the experiment's own shared render and compute readback buffers.

It must not use IOKit, private APIs, interposers, BO/resource-map tracing,
command/state/code-buffer capture, archive/library dumping, metadata parsing,
pointer following, memory mutation/replay, system caches, or any binary/code
inspection. No compiled shader bytes, of either authored or non-authored code,
may be retained or inspected. No Apple binary, framework implementation,
compiler implementation, kernel, firmware, helper, or auxiliary program may be
opened, scanned, disassembled, debugged, or otherwise introspected.

The harness may compile complete authored MSL only through public Metal APIs and
treat the result as a black box. It records source SHA-256 before compilation,
the public target/OS/repository/tool identity before each run, and complete
authored readback buffers after command completion.

## Frozen inputs and matrix

All cases render a single 1x1 pixel via the same authored full-screen triangle,
then an authored compute encoder reads `tex.read(uint2(0))` from that exact
texture and writes a four-word bit-pattern vector to an owned shared buffer.
The two encoders are in one public command buffer, render precedes compute, and
the texture usage is only `RenderTarget | ShaderRead`. There is no CPU write to
the texture after the render encoder begins.

The texture is backed by one owned shared allocation at an offset after a
64-byte `0x5a` prefix guard, with a fixed 256-byte row followed by a 64-byte
`0xa5` suffix guard. The entire 384-byte allocation is retained as lowercase
hex, not merely a selected pixel. The compute output has equivalent 64-byte
guards and retains all 16 payload bytes as hex plus four little-endian words.

| case | pixel format | authored fragment logical output | authored typed compute read |
| --- | --- | --- | --- |
| `rgba8unorm_edges` | RGBA8Unorm | float4(-0.25, 0.5, 1.25, 128/255) | float4 -> IEEE binary32 bits |
| `bgra8unorm_edges` | BGRA8Unorm | same float4 | float4 -> IEEE binary32 bits |
| `rgba8srgb_threshold` | RGBA8Unorm_sRGB | float4(0.0031308, 0.0031309, 0.5, 0.5) | float4 -> IEEE binary32 bits |
| `r16unorm_midpoint` | R16Unorm | float4(0.5,0,0,1) | float4 -> IEEE binary32 bits |
| `rgba16float_edges` | RGBA16Float | float4(-0.0, 1.0, 65504.0, 0.333251953125) | float4 -> IEEE binary32 bits |
| `r32uint_exact` | R32Uint | uint(0xdeadbeef) | uint4 -> exact uint bits |

No format is inferred from a descriptor or a captured command. The MSL uses a
float fragment function only for the five normalized/float cases and a separate
uint fragment function only for `r32uint_exact`; mismatched pipeline creation is
a retained compile/pipeline failure, not a fallback.

## Hypotheses and falsifiers

### H1 — normalized stores clamp and use declared channel order

For the two 8-bit UNorm targets, negative and >1 components yield endpoint
physical bytes, 0.5 yields the format's quantized midpoint, and RGBA/BGRA differ
only by their declared red/blue memory-channel order. The compute float readback
must correspond to the stored normalized texel.

H1 is falsified for a target by public pipeline failure, command failure,
guard change, nonuniform/incorrect full readback, non-endpoint edge byte, an
unexpected RGBA/BGRA relation, or a typed read vector inconsistent with that
case's physical texel. It does not assert an untested rounding rule beyond the
named values.

### H2 — sRGB encode/decode crosses the registered transfer knee

The two red inputs straddling the standard 0.0031308 transfer boundary produce
the public sRGB-store results for their exact binary32 inputs, and the typed
float read is the public sRGB decode of the stored byte. This is falsified by
same-as-UNorm storage at the tested values, a result that violates the explicit
public transfer function/quantization calculation in the analyzer, or a failed
typed readback.

### H3 — R16 conversions preserve selected representable values

R16Unorm 0.5 and RGBA16Float {-0, 1, max finite half, 0.333251953125} store
the expected public 16-bit encodings and typed reads return their defined
expanded values. It is falsified by a nonmatching complete physical row, a
wrong typed-read bit vector, or failure. No NaN/inf/subnormal claim is made.

### H4 — integer render store/read is bit exact

The R32Uint fragment store and uint texture read both preserve `0xdeadbeef`.
H4 is falsified by pipeline/command failure, a different four physical bytes,
or a different compute word. This says nothing about integer blending, filtering,
atomics, or other integer widths.

## Repetition, safety, and stop policy

Two append-only top-level runs are mandatory. Each run creates a fresh process,
device, queue, texture/backings, compute output, pipeline objects, and command
buffer per case: 12 fresh GPU processes total. Every process has a 20-second
parent timeout; compilation and command completion each have their own 10-second
wall-clock cap. Only one command buffer is committed per process.

Any timeout, device-loss/reset indication, GPU fault, failure to create a named
public pipeline, non-completed command buffer, guard corruption, or incomplete
record stops that case and is retained verbatim. A timeout/fault/reset stops all
remaining cases in that top-level run, with no automated retry or recovery. A
normal completed mismatch is repeated only in the other mandatory run. No reboot
or system repair is automated.

## Artifact and analysis requirements

Raw runs live only in a new `raw/m4_YYYYMMDD_runNN/` directory, rejected if it
already exists. Each process must retain: complete source copy/hash; exact public
format/case identity; command/pipeline status/errors; target/OS/tool/repository
identity captured before execution; full 384-byte render backing hex; full
80-byte compute backing hex; decoded physical texel bytes; compute four words;
and guard verdicts. The runner, analyzer, manifest generator, and verifier must
reject symlinks, special files, missing/extra case records, short/extra hex,
or any artifact outside the exact predeclared path/type matrix before opening
payload text.

The final report must distinguish direct public observations from interpretation,
state exact source binary32 constants and test range, reproduce two-run agreement,
and enumerate untested formats/capabilities. All raw results, including errors
and failures, are append-only and remain unstaged until independent audit.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API
Apple binary introspection: NONE
Apple helper/auxiliary-program bytes inspected: NONE
Apple command/state/code/unknown BO bytes inspected: NONE
Compiled code bytes inspected: NONE
```
