#!/usr/bin/env python3
"""EXP-0127 schema.py -- frozen GATED/NON-GATED key split for every raw
record this experiment produces (vstoken varied/uniform/pad/extraqueues
sub-tests, fsredirect case matrix). Single source of truth so run.py and
verify.py can never drift (mirrors EXP-0116's schema.py design).

CLEAN ROOM: pure data-shape bookkeeping over our own harnesses' JSON/text
output. Inspects no Apple binary.

Design principle (CODEX / dispatch "STANDING GATES"): GPU addresses are
central to this experiment (a code-window base address, a growth-region
base address, per-BO VAs) and MUST NOT appear in the byte-compared gated
file, because they are allocator-order-dependent and legitimately differ
run to run even when every architectural fact they support is identical.
Everything else this experiment measures -- the VS token's own numeric
value, the FS pool+0x08 selector's own numeric value, structural booleans
(did the code window's own registered VA change under padding?), status
codes, and colour classifications -- has been empirically shown
PROCESS-INVARIANT across more than a dozen independent pilot invocations
during calibration (see PROGRESS.md) and is therefore safe and meaningful
to gate directly: reproducing it byte-identically across two independent
official runs is itself evidence for architectural (not incidental)
stability, exactly the point of the cross-run gate.
"""
import re

COMPLETED_STATUS = 4  # MTLCommandBufferStatusCompleted

# ---------------------------------------------------------------------------
# vstoken sub-tests: gated summary keys (see run.py's build_vstoken_summary).
# Every raw per-draw GPU VA (code BO VA, pool VA, growth-region VA, per-BO
# cpu pointers) lives ONLY in the *_addrs sibling.
VSTOKEN_VARIED_GATED_FIELDS = [
    "mode", "order", "n", "tokens", "deltas", "readback_status_all_completed",
]
VSTOKEN_UNIFORM_GATED_FIELDS = [
    "mode", "count", "schedule", "tokens", "deltas",
    "linear_base", "linear_step", "first_step_anomaly_token",
    "boundary_index", "boundary_delta", "post_boundary_step_ok",
    "readback_status_all_completed", "new_region_appeared",
    "new_region_size",  # a size (0x40000), not a VA -- structurally safe
]
VSTOKEN_PERTURB_GATED_FIELDS = [
    "mode", "pad_mb", "extra_queues", "n",
    "code_bo_base_unchanged_vs_pad0_baseline",
    "pool_base_unchanged_vs_pad0_baseline",
    "vdm_base_unchanged_vs_pad0_baseline",
    "readback_status_all_completed",
]
VSTOKEN_ADDR_FIELDS = [
    "code_bo_va", "pool_va", "vdm_va", "new_region_va", "per_dump_bo_vas",
]

# ---------------------------------------------------------------------------
# fsredirect case matrix: every field the C harness emits is already
# non-address (see harness/fsredirect.m -- S_RED/S_GREEN/S_BLUE and the
# pool selector are small code-window-relative integers, empirically
# process-invariant across every pilot run in PROGRESS.md, never a raw
# 48-bit GPU VA). final_error is still routed through the same
# category-only treatment EXP-0116 established, out of caution (a verbatim
# NSError string is not a value this experiment wants to assert byte-exact
# forever).
FSREDIRECT_GATED_FIELDS = [
    "case", "bind", "discovery_ok",
    "S_RED", "S_GREEN", "S_BLUE",
    "discover_colour_red", "discover_colour_green", "discover_colour_blue",
    "pool_found", "natural_selector", "case_valid_setup",
    "do_mutate", "mutate_desc", "mutate_value",
    "wrote", "hang", "final_status",
    "post_pool_found", "post_selector",
]
# `result_colour` is a content readback.
#
# POST-CAPTURE SCHEMA CORRECTION (disclosed, see PROGRESS.md): the FIRST
# official pair (m4_20260828_run02/run03) found `result_colour` genuinely
# DIFFERED between the two runs for 2/25 records (`misalign_plus4`:
# black vs red; `misalign_minus1`: black vs red) despite BOTH runs
# reporting `final_status == 4` (Completed) -- i.e. this is racy even on a
# clean, unfaulted completion, not only on a faulted one (which was the
# only case this field was originally guarded for, mirroring EXP-0116's
# `RACY_ON_FAULT_LINKSPLICE`). Both run02 and run03 are retained, valid,
# immutable raw evidence for this new finding (not repaired or discarded);
# a fresh pair (run04/run05) was captured under this corrected schema for
# the row that gates closure claims. Per CODEX ("no nondeterministic field
# in byte-compared records"), the schema is corrected here (a tooling fix,
# not a raw-data repair) to exclude `result_colour` from the gate whenever
# the case wrote a selector value that is NOT one of the three
# independently-discovered exact natural values (`S_RED`/`S_GREEN`/
# `S_BLUE`) -- i.e. every misalignment/zero/far-OOR/top-bit/ceiling/
# near-but-invalid probe, which is exactly the class of case built to land
# on or near an unstable boundary. `result_colour` remains gated for every
# baseline (`do_mutate=False`) and exact-redirect (`mutate_value` equal to
# a discovered natural selector) case, all of which reproduced
# byte-identically between run02 and run03.
RACY_ON_FAULT_FSREDIRECT = ["result_colour"]
FSREDIRECT_ADDR_FIELDS = ["final_error"]  # verbatim string -> category only


def _result_colour_is_racy(result):
    """True if this case's `result_colour` is not asserted gate-stable:
    either the command buffer did not cleanly complete, or the spliced
    value is not exactly one of the three independently-discovered natural
    selectors (see the POST-CAPTURE SCHEMA CORRECTION note above)."""
    if result.get("final_status") != COMPLETED_STATUS:
        return True
    if not result.get("do_mutate"):
        return False
    mv = result.get("mutate_value")
    naturals = {result.get("S_RED"), result.get("S_GREEN"), result.get("S_BLUE")}
    return mv not in naturals


def _classify_final_error(final_error):
    if final_error is None:
        return "None"
    s = final_error
    if "PageFault" in s or "AddressFault" in s or "Address Fault" in s:
        return "PageFault"
    if "ErrorHang" in s or "InnocentVictim" in s or "Hang Error" in s or "victim of GPU error" in s:
        return "GPU_RECOVERY_EVENT"
    if "PROCESS_WATCHDOG_TIMEOUT" in s:
        return "PROCESS_WATCHDOG_TIMEOUT"
    return "Other"


def build_gated_fsredirect(result):
    out = {k: result[k] for k in FSREDIRECT_GATED_FIELDS if k in result}
    out["final_error_category"] = _classify_final_error(result.get("final_error"))
    if not _result_colour_is_racy(result):
        for k in RACY_ON_FAULT_FSREDIRECT:
            if k in result:
                out[k] = result[k]
    return out


def build_addrs_fsredirect(result):
    out = {k: result[k] for k in FSREDIRECT_ADDR_FIELDS if k in result}
    if _result_colour_is_racy(result):
        for k in RACY_ON_FAULT_FSREDIRECT:
            if k in result:
                out[k] = result[k]
    return out


def build_gated_vstoken(summary, kind):
    fields = {
        "varied": VSTOKEN_VARIED_GATED_FIELDS,
        "uniform": VSTOKEN_UNIFORM_GATED_FIELDS,
        "perturb": VSTOKEN_PERTURB_GATED_FIELDS,
    }[kind]
    return {k: summary[k] for k in fields if k in summary}


def build_addrs_vstoken(summary):
    return {k: summary[k] for k in VSTOKEN_ADDR_FIELDS if k in summary}


# Deny-list of substrings that must never appear as a KEY in a gated record
# (defence in depth beyond the explicit field lists above).
_ADDR_KEY_DENYLIST = {"va", "cpu", "addr", "address", "pointer", "ptr"}


def assert_no_address_leak(gated_record):
    """Raise AssertionError if any key in `gated_record` looks address-shaped,
    OR if any integer/string value looks like a bare GPU VA (this
    experiment's own addresses are >= 0x18000 and, for the 4GiB-aligned code
    window, >= 2**32; small selector/token values stay well under 0x10000
    for the tested range except the uniform sweep's own token, which is
    EXPECTED to grow past 0x10000 (see RESULTS.md) -- so this check flags
    only values >= 2**32, which no legitimate gated field in this schema
    ever produces).
    """
    for k, v in gated_record.items():
        kl = k.lower()
        tokens = kl.split("_")
        for bad in _ADDR_KEY_DENYLIST:
            if bad in tokens:
                raise AssertionError(f"address-shaped key {k!r} in gated record")
        if isinstance(v, int) and v >= (1 << 32):
            raise AssertionError(f"address-shaped integer value {v!r} for key {k!r}")
        if isinstance(v, str) and re.fullmatch(r"0x[0-9a-f]{9,16}", v):
            raise AssertionError(f"address-shaped string value {v!r} for key {k!r}")
        if isinstance(v, list):
            for item in v:
                if isinstance(item, int) and item >= (1 << 32):
                    raise AssertionError(f"address-shaped list item {item!r} for key {k!r}")
    return True
