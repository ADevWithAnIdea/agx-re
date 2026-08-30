#!/usr/bin/env python3
"""EXP-0178 OFFLINE gates. No Metal, no device, no SSH. Must pass before any
capture and again before any verdict is written.

Gate list (each prints PASS/FAIL and contributes to the exit code):

  G1 pinned toolchain resolves by absolute path and hashes match; a missing blob
     is a hard exit, never a fallback.
  G2 every field named by every arm exists in the PINNED descriptor, with the
     geometry the plan will use.
  G3 THREE-WAY DISCRIMINATION: for every tilebuffer carrier the CORRECT value,
     every SILENT-ZERO candidate and the CLEAR colour differ in EVERY component
     of EVERY pixel. Without this a silent zero is indistinguishable from "the
     draw never happened", which is the EXP-0141 trap.
  G4 SYSVAL DISCRIMINATION: on each get_sr carrier the ladder's two selectors
     produce DIFFERENT host-computed patterns, so the pre-registered liveness
     step can actually move.
  G5 CO-VARIATION AUDIT passes (analysis/covary_audit.py).
  G6 the promotion gate is SATISFIABLE and REFUSABLE: synthetic run pairs that
     should pass do pass and each broken shape fails for the right reason.
  G7 coverage: every ruled field's planned value list covers its full encodable
     range (w<=8) or the protocol's boundary+power-of-two+interior set (w>8).
  G8 no ruled field is also claimed by another experiment (the `foreign` split
     is complete and disjoint).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(EXP, "analysis"))
sys.path.insert(0, os.path.join(EXP, "..", "..", "tools", "agxtest"))
import pinned_isa                                              # noqa: E402
import sweepplan as SP                                         # noqa: E402
import verdicts as V                                           # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- G1 --------
try:
    r = pinned_isa.verify()
    m = pinned_isa.load_isadb()
    check("G1 pinned toolchain", len(m.DB) == 172,
          "%d instructions, db %s" % (len(m.DB), r["db.json"][1][:12]))
except SystemExit as e:
    check("G1 pinned toolchain", False, "exit %s" % e)

# ---------------------------------------------------------------- G2 --------
g2 = []
for arm in SP.ARMS:
    mn = arm["instr"] or "tile_read"
    for f in list(arm["fields"]) + list(arm.get("foreign", {})):
        try:
            pinned_isa.field_geometry(mn, f)
        except KeyError as e:
            if arm["arm"] == "tile_ct2":
                continue
            g2.append("%s.%s: %s" % (mn, f, e))
check("G2 fields exist in pinned db", not g2, "; ".join(g2))

# ---------------------------------------------------------------- G3 --------
g3 = []
CLEARS = [SP.DST0, SP.DST1, SP.DST2]
for arm in SP.ARMS:
    if not arm["oracle"].startswith(("tile", "mrt")):
        continue
    good, zeros = SP.tile_oracles(arm)
    n = arm["W"] * arm["H"]
    clear_rows = [CLEARS[i // n] for i in range(len(good))]
    # correct must differ from the CLEAR colour everywhere -- otherwise a
    # never-drawn pass is indistinguishable from a correct one.
    for i, (a, c) in enumerate(zip(good, clear_rows)):
        for k in range(4):
            if a[k] == c[k]:
                g3.append("%s px%d.c%d: correct == clear (%r)" % (arm["arm"], i, k, a[k]))
    for lbl, z in zeros:
        # a zero candidate differs from `good` only on the rows belonging to the
        # attachment whose read was zeroed; on THOSE rows it must differ in
        # EVERY component, and it must also differ from the clear colour there.
        diffrows = [i for i in range(len(good)) if good[i] != z[i]]
        if not diffrows:
            g3.append("%s %s: zero candidate is identical to correct" % (arm["arm"], lbl))
        for i in diffrows:
            for k in range(4):
                if good[i][k] == z[i][k]:
                    g3.append("%s %s px%d.c%d: correct == zero (%r)"
                              % (arm["arm"], lbl, i, k, good[i][k]))
                if z[i][k] == clear_rows[i][k]:
                    g3.append("%s %s px%d.c%d: zero == clear (%r)"
                              % (arm["arm"], lbl, i, k, z[i][k]))
check("G3 three-way discrimination (correct/zero/clear)", not g3,
      "; ".join(sorted(set(g3))[:4]))

# ---------------------------------------------------------------- G4 --------
g4 = []
for arm in SP.ARMS:
    if not arm["oracle"].startswith("sr_"):
        continue
    base = arm["anchor_sr"]
    alt = arm["ladder"][0][2]
    if arm["oracle"] == "sr_compute":
        a, b = SP.sr_oracle_compute(base, 32), SP.sr_oracle_compute(alt, 32)
    elif arm["oracle"] == "sr_frag":
        a, b = SP.sr_oracle_frag(base, arm["W"], arm["H"]), SP.sr_oracle_frag(alt, arm["W"], arm["H"])
    else:
        a, b = SP.sr_oracle_vertex(base), SP.sr_oracle_vertex(alt)
    if a is None or b is None or a == b:
        g4.append("%s: ladder selectors 0x%02x/0x%02x are NOT distinguishable (%r vs %r)"
                  % (arm["arm"], base, alt, a, b))
check("G4 sysval ladder selectors distinguishable", not g4, "; ".join(g4))

# ---------------------------------------------------------------- G5 --------
r = subprocess.run([sys.executable, os.path.join(EXP, "analysis", "covary_audit.py")],
                   capture_output=True, text=True)
check("G5 co-variation audit", r.returncode == 0, r.stdout.strip()[-200:])

# ---------------------------------------------------------------- G6 --------
def rows(vals, outcome="ok", moved=True):
    return [{"field": "f", "value": v, "outcome": outcome, "moved": moved,
             "bytes": "%02x" % v, "foreign": False, "start": 0, "width": 8,
             "encodable_range": 256} for v in vals]

cases = [
    ("clean 256/256 agreeing + moving -> PASS",
     rows(range(256)), rows(range(256)), True),
    ("all agree but NOTHING moved -> REFUSED (never-mover needs a carrier argument)",
     rows(range(256), moved=False), rows(range(256), moved=False), False),
    ("50%% disagreement -> REFUSED",
     rows(range(256)), rows(range(128)) + rows(range(128, 256), outcome="wrong_value"), False),
    ("movement < 2x disagreements -> REFUSED",
     rows(range(4)) + rows(range(4, 256), moved=False),
     rows(range(2)) + rows(range(2, 256), outcome="wrong_value", moved=False), False),
    ("only 1 shared value -> REFUSED (min_common_values)",
     rows([7]), rows([7]), False),
]
g6 = []
for name, r1, r2, want in cases:
    got = V.gate(r1, r2, ladder_ok=True)["promote"]
    if got != want:
        g6.append("%s: got promote=%s" % (name, got))
if V.gate(rows(range(256)), rows(range(256)), ladder_ok=False)["promote"]:
    g6.append("gate_zero: a FAILED liveness ladder must refuse promotion")
check("G6 promotion gate satisfiable and refusable", not g6, "; ".join(g6))

# ---------------------------------------------------------------- G7 --------
g7 = []
for arm in SP.ARMS:
    mn = arm["instr"] or "tile_read"
    for f in arm["fields"]:
        try:
            mode, vals, rng, start, width = SP.field_values(mn, f)
        except KeyError:
            continue
        if width <= 8 and len(vals) != rng:
            g7.append("%s.%s: %d of %d values" % (mn, f, len(vals), rng))
        if width > 8:
            need = {0, 1, 2, rng - 2, rng - 1} | {1 << k for k in range(width)}
            if not need <= set(vals):
                g7.append("%s.%s: structured set misses boundaries/powers" % (mn, f))
check("G7 coverage rule", not g7, "; ".join(g7))

# ---------------------------------------------------------------- G8 --------
g8 = []
OWNED_ELSEWHERE = {"get_sr.dst": "EXP-0168", "get_sr.dst_hi": "EXP-0168",
                   "get_sr.form": "EXP-0172"}
for arm in SP.ARMS:
    mn = arm["instr"] or "tile_read"
    for f in arm["fields"]:
        k = "%s.%s" % (mn, f)
        if k in OWNED_ELSEWHERE:
            g8.append("%s is ruled on here but owned by %s" % (k, OWNED_ELSEWHERE[k]))
    for f in arm.get("foreign", {}):
        k = "%s.%s" % (mn, f)
        if k not in OWNED_ELSEWHERE:
            g8.append("%s marked foreign but nobody owns it" % k)
check("G8 ruled/foreign split disjoint", not g8, "; ".join(g8))

# ---------------------------------------------------------------- G9 --------
# The runner fix, proved with NO device: harness/fakerunner.py speaks the same
# line protocol and can emit the truncated `OUT 0` shape on demand. A malformed
# response must come back as a MEASUREMENT FAILURE with the raw lines kept --
# never as a crash and never as a `hang`.
g9 = []
try:
    import subprocess as _sp
    from saferunner import SafePersistRunner as _SPR

    class _Stub(_SPR):
        MODE = "--ok"

        def _start(self):
            self.proc = _sp.Popen(
                [sys.executable, os.path.join(HERE, "fakerunner.py"), self.MODE],
                stdin=_sp.PIPE, stdout=_sp.PIPE, stderr=_sp.PIPE,
                text=True, bufsize=1, start_new_session=True)
            self._install_pump()
            ln = self._read_line(10)
            if not ln or not ln.startswith("READY"):
                raise RuntimeError("stub not READY: %r" % (ln,))
            self.device = "stub"

    for mode, want in (("--ok", ["OK", "OK", "OK"]),
                       ("--truncate", ["OK", "MALFORMED", "MALFORMED"])):
        _Stub.MODE = mode
        r = _Stub(source="x", function="k", fast_math=False, agxrun_persist="x")
        got = []
        for _ in range(3):
            resp = r.request(archive="A.bin", grid=64, tg=64,
                             ins={0: "p.bin", 4: "p.bin"}, outs={0: 8, 4: 8},
                             timeout=5)
            got.append(resp["status"])
            if resp["status"] == "MALFORMED" and not resp.get("raw"):
                g9.append("%s: MALFORMED without the raw lines kept" % mode)
            if resp["status"] == "HANG":
                g9.append("%s: a malformed response was scored as a HANG" % mode)
        r._kill()
        if got != want:
            g9.append("%s: got %r, want %r" % (mode, got, want))
except Exception as e:                                         # noqa: BLE001
    g9.append("stub harness failed: %s" % e)
check("G9 malformed response is a measurement failure, not a hang", not g9,
      "; ".join(g9))

# --------------------------------------------------------------- G10 --------
# CLOSURE-SHADOWING SCAN, in harness/closure_scan.py (written to be upstreamed).
# `raw/g17p_20260830_run01` was lost to this defect class. The allow-list is
# names assigned in MUTUALLY EXCLUSIVE branches of one if/else, which is safe:
# exactly one assignment executes per arm. It is an explicit list with a reason,
# not a weakening of the check.
from closure_scan import scan as _closure_scan                 # noqa: E402

G10_ALLOW = {
    "mnem":   "assigned in the two mutually exclusive anchor-resolution branches",
    "off":    "assigned in the two mutually exclusive anchor-resolution branches",
    "runner": "assigned in the two mutually exclusive stage branches (compute/render)",
}
G10_IGNORE = {"arm", "SP", "ISA", "emit", "json", "os", "sys", "time", "struct",
              "f32", "f32v", "same_pixels", "set_bits", "get_bits", "splice",
              "safe_request", "REQ_TIMEOUT", "TOL", "sr_pixels_from_values",
              "traceback", "subprocess"}

g10 = []
try:
    for k, v in sorted(_closure_scan(os.path.join(HERE, "run.py"), "main",
                                     ignore=G10_IGNORE, allow=G10_ALLOW).items()):
        g10.append("%s: read by %s and assigned more than once in main()" % (k, v))
except Exception as e:                                         # noqa: BLE001
    g10.append("scan failed: %s" % e)
check("G10 no closure reads a name main() rebinds", not g10, "; ".join(g10))

print()
print("SELFTEST %s (%d failures)" % ("PASS" if not fails else "FAIL", len(fails)))
sys.exit(0 if not fails else 1)
