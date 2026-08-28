#!/usr/bin/env python3
"""EXP-0084 frozen case matrix -- ONE authoritative definition, imported by
run.py, verify.py, and every analysis script. Never redefine this list or
any of its fields anywhere else.

Three case kinds:
  dispatch -- harness/probe (compile our MSL, dispatch on the real GPU,
              read back). Behavioral (HW-PROBE + OWN-SHADER) evidence for
              MEM-20/21/22.
  decode   -- analysis/decode_case.py (tools/shdump compile + extract,
              tools/agx-isa tokenize/disasm; no dispatch). Static
              instruction-encoding evidence (OWN-SHADER, structural).
  splice   -- analysis/splice_case.py (tools/shdump + harness/splice_run;
              hand-perturb one identified byte in our own compiled bytes and
              execute on the real GPU). Independent-encoding-synthesis
              evidence (OWN-SHADER + HW-VALIDATED), the strongest tier.

Every dynamic device address dereferenced anywhere in this matrix is
obtained through public Metal API only (`MTLBuffer.gpuAddress`, implicit
argument buffers via `MTLArgumentEncoder`) -- see kernels/probes.metal.
"""

KERNELS_DIR = "kernels"
PROBES_SRC = "probes.metal"
CAP_SRC = "cap_kernels.metal"

CASES = [
    # --- sanity control --------------------------------------------------
    {"i": 0, "name": "ctrl_direct_baseline", "kind": "dispatch",
     "mode": "ctrl_direct", "source": PROBES_SRC, "function": "ctrl_direct",
     "n": -1, "sel": -1, "k": -1, "use_resource": 1},

    # --- MEM-20: dynamic device address, no static base slot -------------
    {"i": 1, "name": "mem20_uniform_single", "kind": "dispatch",
     "mode": "mem21_uniform", "source": PROBES_SRC, "function": "mem21_uniform",
     "n": 1, "sel": 0, "k": -1, "use_resource": 1},
    {"i": 2, "name": "mem20_implicit_ab", "kind": "dispatch",
     "mode": "mem20_implicit_ab", "source": PROBES_SRC, "function": "mem20_implicit_ab",
     "n": -1, "sel": -1, "k": -1, "use_resource": 1},
    {"i": 3, "name": "mem20_chained_indirection", "kind": "dispatch",
     "mode": "mem20_chained", "source": PROBES_SRC, "function": "mem20_chained",
     "n": -1, "sel": -1, "k": -1, "use_resource": 1},
    {"i": 4, "name": "mem20_no_useresource", "kind": "dispatch",
     "mode": "mem21_uniform", "source": PROBES_SRC, "function": "mem21_uniform",
     "n": 1, "sel": 0, "k": -1, "use_resource": 0},

    # --- MEM-21: per-lane divergent base-address selection ---------------
    {"i": 5, "name": "mem21_uniform_ctrl", "kind": "dispatch",
     "mode": "mem21_uniform", "source": PROBES_SRC, "function": "mem21_uniform",
     "n": 2, "sel": 1, "k": -1, "use_resource": 1},
    {"i": 6, "name": "mem21_perlane_divergent_32", "kind": "dispatch",
     "mode": "mem21_perlane", "source": PROBES_SRC, "function": "mem21_perlane",
     "n": 32, "sel": -1, "k": -1, "use_resource": 1},
    {"i": 7, "name": "mem21_outlier_lane17", "kind": "dispatch",
     "mode": "mem21_outlier", "source": PROBES_SRC, "function": "mem21_outlier",
     "n": 2, "sel": -1, "k": 17, "use_resource": 1},

    # --- MEM-22: exceeding the direct-slot path ---------------------------
    {"i": 8, "name": "mem22_direct_cap_31", "kind": "dispatch",
     "mode": "cap_direct", "source": CAP_SRC, "function": "cap31",
     "n": 30, "sel": -1, "k": -1, "use_resource": 1},
    {"i": 9, "name": "mem22_direct_cap_32", "kind": "dispatch",
     "mode": "cap_direct", "source": CAP_SRC, "function": "cap32",
     "n": 31, "sel": -1, "k": -1, "use_resource": 1},
    {"i": 10, "name": "mem22_dynamic_64", "kind": "dispatch",
     "mode": "mem21_perlane", "source": PROBES_SRC, "function": "mem21_perlane",
     "n": 64, "sel": -1, "k": -1, "use_resource": 1},
    {"i": 11, "name": "mem22_dynamic_256", "kind": "dispatch",
     "mode": "mem21_perlane", "source": PROBES_SRC, "function": "mem21_perlane",
     "n": 256, "sel": -1, "k": -1, "use_resource": 1},

    # --- static decode (OWN-SHADER, compile-only, no dispatch) -----------
    # "mode" is a dispatch-only concept (selects a harness/probe.m code
    # path); decode/splice cases carry the frozen placeholder None so every
    # case dict in this matrix shares EXACTLY the same key set (gate (a)).
    {"i": 12, "name": "decode_dynamic_addressing_mechanism", "kind": "decode",
     "mode": None, "source": PROBES_SRC, "function": "splice_target",
     "n": -1, "sel": -1, "k": -1, "use_resource": -1},

    # --- splice validation (OWN-SHADER + HW-VALIDATED) --------------------
    {"i": 13, "name": "splice_swap_indirect_pointer", "kind": "splice",
     "mode": None, "source": PROBES_SRC, "function": "splice_target",
     "n": -1, "sel": -1, "k": -1, "use_resource": -1},
]

TOTAL = len(CASES)
assert TOTAL == 14
assert [c["i"] for c in CASES] == list(range(TOTAL))
assert len({c["name"] for c in CASES}) == TOTAL

SMOKE_CASE_NAME = "ctrl_direct_baseline"

DISPATCH_CASES = [c for c in CASES if c["kind"] == "dispatch"]
DECODE_CASES = [c for c in CASES if c["kind"] == "decode"]
SPLICE_CASES = [c for c in CASES if c["kind"] == "splice"]


def by_name(name):
    for c in CASES:
        if c["name"] == name:
            return c
    raise KeyError(name)
