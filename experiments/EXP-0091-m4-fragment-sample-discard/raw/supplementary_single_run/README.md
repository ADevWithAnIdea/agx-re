# Supplementary single-run probe: d_helper_relay

NOT part of the frozen two-run gated matrix (`run.py`/`schema.py`/`verify.py
--crossrun`). Added after the frozen 78-case capture (raw/m4_20260827_run01,
raw/m4_20260827_run02) completed, to attempt closing a GLFS-A03 gap that the frozen
matrix's own GLFS-A06 finding revealed it could not otherwise answer: a demoted lane's
own `simd_is_helper_thread()` value cannot be read from its own buffer write (writes
from demoted lanes are suppressed, EXP-0091 §4), so this kernel relays the value
through `quad_shuffle_xor` into the surviving neighbor, which performs the actual
write.

Two fresh-process captures (`d_helper_relay_capture1.txt`, `d_helper_relay_capture2.txt`)
are byte-identical (see `diff` in PROGRESS.md), i.e. deterministic across repeats, but
this is NOT the same as the formal two-run cross-run gate (different capture
mechanism, not driven by run.py/schema.py, no CAPTURE_CONTRACT.json hash pinning for
this specific file at pre-registration time -- it postdates the freeze). Evidence tier:
HW-PROBE / OWN-SHADER, single design, reproduced twice informally. See RESULTS.md §3
for the exact numeric findings and the explicit PARTIAL/OPEN flag on the 2-of-8
non-uniform "helper_pre" anomaly.
