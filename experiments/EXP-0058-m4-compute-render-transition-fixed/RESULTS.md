# EXP-0058 results — corrected M4 compute-to-render transition framing

## Verdict

**PUBLIC DEPENDENCY VALIDATED; PAYLOAD ANALYSIS STOPPED. P0.5 remains open.**
All six fresh M4 processes completed with Metal status 4/no error and their
exact authored readbacks: compute-only reported `0.25,0.5,0.75`; both
CPU-render and compute-render reported center BGRA `bf8040ff` and identical
image FNV `4e6294d9841a3583`. Thus the corrected authored CPU/MSL `Scene`
layout and the public compute-to-render data dependency are accepted for this
small matrix.

No command-BO payload conclusion is permitted. Before any `.bin` byte was
opened, hashed, or compared, complete-matrix metadata preflight stopped at
`plain_compute-only`: required exact EXP-0043 `CDM0` start `0x100000b8000` was
absent. This makes the aggregate dependency/control comparison invalid under
the frozen policy. The corresponding padded compute-only process did expose
that exact mapping, but that does not authorize selective analysis or an
alternative-mapping search.

The other retained fixed-VA files are opaque, unopened raw evidence. Their
path presence and metadata are retained for audit only. No captured word has
been decoded, treated as a pointer, or used as a packing claim.

## Exact scope and limitations

- Target: local Apple M4/G16G only; no A18 Pro or M5 claim.
- One append-only run, six processes, no timeout/device loss/retry.
- The two public producer paths produce the same expected rendered image; this
  proves neither an explicit hardware barrier packet nor any VDM/CDM encoding.
- The missing fixed mapping is a bounded process negative, not evidence that a
  new mapping contains the transition state.
- A follow-up must preregister a matrix whose every required mapping is shown
  metadata-first to be stable before any payload comparison. It must keep an
  explicit allowlist and never widen it because of this absence.

Clean-room provenance: HW-PROBE / DATA-TRACE. Apple binary introspection: NONE.
Unknown BO/auxiliary-program byte inspection: NONE. Pointer following,
command mutation, and replay: NONE.
