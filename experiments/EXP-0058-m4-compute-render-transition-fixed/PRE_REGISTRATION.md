# EXP-0058 pre-registration — corrected M4 compute-to-render transition framing

Frozen before any EXP-0058 source build or live GPU process. This local Apple
M4/G16G experiment addresses P0.5 only. It makes no A18 Pro or M5 claim.

EXP-0056 is retained and superseded only as a probe implementation: its first
compute-only process falsified its own CPU readback because a CPU `float2[3]`
prefix did not include the 16-byte alignment padding used by the authored MSL
struct's subsequent `float4`. This successor corrects that authored CPU layout
with exactly two floats of explicit padding before its first build. It does not
edit, erase, reinterpret, or retry EXP-0056.

## Question, boundary, and matrix

The question and six fresh-process matrix are unchanged: compare an authored
compute-produced `Scene` consumed immediately by an authored render encoder
with a compute-only producer control and a CPU-initialized render control, each
under `plain` and one authored 64 KiB padding schedule. A correct dependency
must produce BGRA `bf8040ff`; a compute-only control must observe its authored
scene values.

Only exact EXP-0043-preclassified allocation starts `0x100000b8000`,
`0x10000158000`, `0x18000`, and `0x88000` may ever be retained/opened, each
capped at 0x10000. Their roles and provenance are exactly EXP-0049's frozen
four-VA bridge. Nonallowlisted BOs have metadata only; their CPU mappings and
contents are never retained or inspected. No payload is opened before exact
regular-path, metadata, trace grammar, role, size, and trace/meta linkage
preflight. If a required command mapping is absent, the run is a bounded stop:
no alternate mapping may be found or inspected.

The interposer rejects no mappings itself except by compile-time inability to
remember nonallowlisted CPU addresses. It never follows encoded values,
captures shaders or Apple helper bytes, modifies command memory, or replays a
capture. Apple binary/framework/kernel/firmware introspection is forbidden.

## Hypotheses and falsifiers

H1: all six fresh processes complete with correct status/readback. A wrong
scene/image, command error, or timeout is a retained stop.

H2: where required fixed payloads occur, same-VA dependency/control byte
differences repeat across two append-only top-level runs and both schedules.
Any matching result is structural only, not proof of a barrier encoding or
hardware consumption. A no-difference result is a bounded negative.

H3: padding does not change any matching candidate. Schedule-only bytes are
opaque allocation correlation and are neither decoded nor followed.

Builds/processes/analysis time out at 60/45/15 seconds. The preregistration
commit includes all sources and this exact plan before its first build.

Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER source. Apple binary
introspection: NONE. Unknown BO or auxiliary-program byte inspection: NONE.
