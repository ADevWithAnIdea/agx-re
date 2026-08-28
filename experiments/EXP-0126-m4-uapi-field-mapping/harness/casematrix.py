#!/usr/bin/env python3
"""EXP-0126 frozen case matrix.

Two probe families:
  sampos     -- render.ppp_multisamplectl / sample-position grid+rounding+boundary probe
                (harness/sampos126.m under tools/iotrace DATA-TRACE, unmodified read-only
                tool per SUBAGENT_BRIEF.md)
  sampcount  -- render.samples valid-range boundary probe (harness/sampcount.m, plain
                public-Metal HW-PROBE, no iotrace needed)

This module is imported by both run.py and verify.py so the matrix is defined exactly
once and frozen at pre-registration time. Do not edit case content after freezing;
capture validity is judged against the authored_file_sha256 of this file in
CAPTURE_CONTRACT.json.
"""

REF_X = 0.5625  # 9/16, an on-grid reference distinct from every swept grid point's
                 # neighbourhood, used to hold the non-tested axis fixed.

def _sampos_cases():
    cases = []

    # (A) exhaustive 1/16-grid coverage on X, Y fixed on-grid.
    for k in range(16):
        x = k / 16.0
        cases.append({
            "case_id": f"sp_gridx_{k:02d}",
            "family": "sp_gridx",
            "kind": "sampos",
            "params": {"samples": 4, "p0x": x, "p0y": REF_X},
        })

    # (B) partial 1/16-grid coverage on Y (every other point), X fixed on-grid.
    for k in (0, 2, 4, 6, 8, 10, 12, 14):
        y = k / 16.0
        cases.append({
            "case_id": f"sp_gridy_{k:02d}",
            "family": "sp_gridy",
            "kind": "sampos",
            "params": {"samples": 4, "p0x": REF_X, "p0y": y},
        })

    # (C) off-grid rounding ladder around the two lowest half-way boundaries
    # (1/32 = 0.03125 between grid points 0/16 and 1/16; 3/32 = 0.09375 between 1/16
    # and 2/16), fine enough to bracket the exact flip point.
    ladder = [0.01, 0.02, 0.03, 0.031, 0.03124, 0.03125, 0.03126, 0.032, 0.04,
              0.05, 0.07, 0.08, 0.09374, 0.09375, 0.09376, 0.10, 0.11]
    for x in ladder:
        tag = str(x).replace(".", "p").replace("-", "n")
        cases.append({
            "case_id": f"sp_ladder_{tag}",
            "family": "sp_ladder",
            "kind": "sampos",
            "params": {"samples": 4, "p0x": x, "p0y": REF_X},
        })

    # (D) boundary / out-of-documented-range values. Metal documents valid custom
    # sample positions as [0.0, 0.9375]; these probe at and past that limit.
    for x in (-0.001, 0.94, 0.99, 1.0):
        tag = str(x).replace(".", "p").replace("-", "n")
        cases.append({
            "case_id": f"sp_boundx_{tag}",
            "family": "sp_boundary",
            "kind": "sampos",
            "params": {"samples": 4, "p0x": x, "p0y": REF_X},
        })
    for y in (-0.001, 1.0):
        tag = str(y).replace(".", "p").replace("-", "n")
        cases.append({
            "case_id": f"sp_boundy_{tag}",
            "family": "sp_boundary",
            "kind": "sampos",
            "params": {"samples": 4, "p0x": REF_X, "p0y": y},
        })

    # (E) cross-count check: same encoding family at samples=2 (VA 0x100000e0000, not
    # 0x100000e8000) -- one on-grid, one off-grid rounding case.
    for x in (0.375, 0.10):
        tag = str(x).replace(".", "p")
        cases.append({
            "case_id": f"sp_count2_{tag}",
            "family": "sp_count2",
            "kind": "sampos",
            "params": {"samples": 2, "p0x": x, "p0y": REF_X},
        })

    return cases


def _sampcount_cases():
    cases = []
    for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 16):
        cases.append({
            "case_id": f"sc_count_{n:02d}",
            "family": "sc_count",
            "kind": "sampcount",
            "params": {"count": n},
        })
    return cases


def all_cases():
    return _sampos_cases() + _sampcount_cases()


def smoke_case():
    """One fast, representative, NON-RECORDED case used for the pre-raw smoke gate."""
    return {
        "case_id": "smoke_sp_grid0",
        "family": "sp_gridx",
        "kind": "sampos",
        "params": {"samples": 4, "p0x": 0.0, "p0y": REF_X},
    }


SAMPOS_VA_4X = "0x100000e8000"
SAMPOS_VA_2X = "0x100000e0000"
SAMPOS_OFFSET_X0 = 0x40
SAMPOS_OFFSET_Y0 = 0x44

# Keys present in a completed case record that MUST be byte-identical across two
# independent runs (gate d). GPU virtual addresses are allocator-dependent and
# EXCLUDED here, not because they are uninteresting, but because this project's
# standing gates forbid gating on them; see verify.py gate_captured() and its
# selftest proof that the exclusion is real (a deliberately-injected VA difference
# does not fail the gate) and does not also hide a semantic difference (a deliberately
# injected 'observed' difference still fails it).
GATED_KEYS = ["case_id", "family", "kind", "params", "status", "observed"]
NONGATED_KEYS = ["case_id", "va_vtxbuf", "va_resbuf", "hex_path", "raw_stdout", "wall_ms"]

if __name__ == "__main__":
    cs = all_cases()
    print(f"{len(cs)} cases")
    from collections import Counter
    print(Counter(c["family"] for c in cs))
