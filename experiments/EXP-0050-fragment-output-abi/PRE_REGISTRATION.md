# EXP-0050 pre-registration: M4 fragment-output compiler ABI

Date: 2026-08-17

Target: the local Apple M4 (`G16G`) only. A18 Pro is not available for this
experiment, so no result may be promoted to an A18 fact.

This file is frozen before the first live run. Its SHA-256 is checked before
building or invoking Metal and is copied into every append-only raw run.

## Clean-room boundary

The only executable shader input is `kernels/output_matrix.metal`, authored in
this experiment. The probe may inspect only:

- that complete MSL source;
- the exact fragment `_agc.main` bytes compiled from the selected function in
  that source through the public Metal API;
- authored color/depth/counter readbacks; and
- public target/tool identity and process exit/error output.

It must never inspect, scan, disassemble, trace, or dump any Apple binary,
framework code, compiler code, system cache, firmware, auxiliary/helper program,
or unknown buffer object. The temporary binary archive exists only to carry our
own compiled pipeline between our authored tools. It is never committed. Only
the exact `_agc.main` region attributed by our repository-authored parser to the
selected fragment function is retained.

No command/state BO capture is in scope. No generic pointer scan, BO scan,
framework inspection, or auxiliary-program inspection is permitted.

## Bounded question

Across a controlled fragment-output matrix, what stable compiler-emitted
`_agc.main` structure and live output behavior correlate with:

1. asymmetric MRT indices and source declaration order;
2. shader depth output versus fixed interpolated depth;
3. fragment sample-mask output;
4. discard; and
5. an authored device-atomic side effect placed before or after discard?

The purpose is to bound the fragment-output portion of P0.8. Compiler-emitted
correlation does not establish a complete native fragment ABI, prolog/epilog
linkage, independent code generation, or Linux UAPI packing.

## Controlled matrix

All color attachments are 4 x 1 RGBA8Unorm targets. Defined outputs use distinct
byte-exact colors: RT0=`11 22 33 44`, RT1=`55 66 77 88`, and
RT2=`99 aa bb cc`. Each absent/unwritten attachment has a distinct clear color.

### Color/MRT

1. `c0`: only `[[color(0)]]`, only RT0 attached.
2. `c1-only`: only `[[color(1)]]`, only RT1 attached.
3. `c2-only`: only `[[color(2)]]`, only RT2 attached.
4. `c0-c2-decl02`: RT0 and RT2, members declared 0 then 2.
5. `c0-c2-decl20`: same values/attachments, members declared 2 then 0.
6. `mrt3-decl012`: RT0/1/2, members declared 0/1/2.
7. `mrt3-decl210`: same values/attachments, members declared 2/1/0.
8. `mrt3-swap12`: same declaration/config as case 6, but the authored values
   assigned to RT1 and RT2 are swapped.

H1: each live attachment receives the value assigned to its semantic color index,
independent of declaration order. A stable per-index compiler correlation should
survive declaration reordering, although register allocation or scheduling may
prevent byte-identical whole programs. A wrong target, declaration-order routing,
or run-to-run change falsifies H1.

### Depth

9. `color-depth`: RT0 plus `[[depth(any)]] = 0.25`, color declared first.
10. `depth-color-decl`: same output/config, depth declared first.
11. `depth-only`: no color attachment, `[[depth(any)]] = 0.625`.
12. `color-fixed-depth`: RT0 plus a depth attachment but no shader depth output;
    the full-screen vertex depth is 0.75.

All use Depth32Float, depth compare Always, and depth writes enabled.

H2: shader depth replaces interpolated depth in cases 9--11; case 12 writes the
interpolated 0.75 control. Field declaration order must not alter case 9/10
readback. A clear-only depth result, wrong depth, or order-dependent output
falsifies H2. Exact code correlation remains compiler-path evidence unless a
safe independent mutation validates it.

### Sample mask

Cases 13--17 use four samples and force per-sample execution through
`[[sample_id]]`. Sample `s` writes red `(s+1)/4`, with green/blue zero and alpha
one, so masks `0x5` and `0xa` have different resolved red values despite equal
population.

13. `mask-f`: mask `0xf`.
14. `mask-5`: mask `0x5`, color declared before mask.
15. `mask-a`: mask `0xa`.
16. `mask-0`: mask zero.
17. `mask-5-declfirst`: same as 14, mask declared before color.

H3: resolved outputs distinguish all/none and distinguish `0x5` from `0xa`;
declaration order does not alter the `0x5` result. Equal `0x5`/`0xa` red,
non-clear mask-zero output, or order-dependent output falsifies H3. The exact
native bit convention is not claimed from source compilation alone.

### Discard and side effect

18. `discard-half`: discard pixels with `position.x < 2`, otherwise RT0 color.
19. `atomic-all`: increment an authored counter and write RT0 for every pixel.
20. `atomic-before-discard`: increment, then discard the left two pixels.
21. `atomic-after-discard`: discard the left two pixels, then increment.

H4: discarded pixels preserve clear color and surviving pixels receive RT0.
The counter should be four for `atomic-all` and `atomic-before-discard`, but two
for `atomic-after-discard`, distinguishing program-order side effects from the
eventual output kill. Any unstable count or incorrect color mask falsifies H4.

## Narrow splice control

Only after an intact `mrt3-decl012` archive completes, the runner may search that
own fragment `_agc.main` for the previously established exact store signature
`e7 06 54` and require exactly one store whose byte `+5` is `0x02`. If and only
if those checks pass, it changes that byte to `0x04`, rerouting the RT1 store to
the already-valid RT2 attachment. No length, opcode, source register, pointer,
or other byte may change. The archive is forced with
`MTLPipelineOptionFailOnBinaryArchiveMiss` and a hard timeout.

H5: RT1 remains at clear and RT2 receives the RT1-authored value (assuming the
later RT1 store overwrites the earlier RT2 store, as the intact byte order
predicts). Pipeline miss, fault, any other changed byte, RT1 write, or a result
inconsistent with the recorded store order falsifies H5. If the signature is
not unique, the splice is skipped and preserved as a bounded failure, never
generalized.

## Repetition, stop conditions, and evidence level

The complete matrix and optional safe splice run twice in fresh run directories.
Every build, extraction, and render process has a hard timeout. A failure,
compile rejection, pipeline miss, command-buffer error, timeout, or missing own
main is retained in `failures.json`; it is not retried in place or overwritten.

Evidence labels are limited to:

- `OWN-SHADER-DIFF` for compiler-emitted byte correlations;
- `HW-PROBE` for authored readbacks; and
- `HW-VALIDATED` only for the single checked splice if both repeats change live
  behavior exactly as predicted.

P0.8 remains open regardless: no full FS input/output register ABI, prolog,
epilog, tilebuffer ABI, helper linkage, arbitrary-format generation, or A18
validation is provided here.

