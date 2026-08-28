#!/usr/bin/env python3
"""EXP-0116 casematrix.py -- the FROZEN case list for both harnesses.

Order matters: cases are listed roughly in increasing risk (a clean
completion before a page fault before the one case that produced a genuine
GPU Hang error in calibration), per the finite-resource-mandate discipline
and CLAUDE.md's "one change per run" safety posture. See PRE_REGISTRATION.md
for the predicted outcome table this list reproduces the case NAMES of.
"""

# (case_name, mechanism, extra_cli_args)
LINKSPLICE_CASES = [
    ("baseline_check", "same_cb", []),
    ("skip_seg1", "same_cb", []),
    ("mid_segment_offset", "same_cb", []),
    ("misaligned_byte1", "same_cb", []),
    ("misaligned_word2", "same_cb", []),
    ("misaligned_word4", "same_cb", []),
    ("misaligned_word8", "same_cb", []),
    ("at_capacity_boundary", "same_cb", []),
    ("one_past_capacity", "same_cb", []),
    ("tag_zero", "same_cb", []),
    ("tag_vdm", "same_cb", []),
    ("out_of_range_beyond_bo", "same_cb", []),
    ("out_of_range_null", "same_cb", []),
    ("out_of_range_bit40", "same_cb", []),
    ("out_of_range_bit44", "same_cb", []),
    ("out_of_range_far", "same_cb", []),
    ("encoding_max", "same_cb", []),
    ("cross_cb_uncommitted", "cross_cb", []),
]

# codeswap.m has no case matrix (one fixed configuration); represented here
# as a single pseudo-case for run.py's uniform loop.
CODESWAP_CASES = [
    ("codeswap_task3", None, []),
]
