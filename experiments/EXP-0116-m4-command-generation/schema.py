#!/usr/bin/env python3
"""EXP-0116 schema.py -- frozen GATED/NON-GATED key split for both harness
programs (linksplice.m mechanism=same_cb|cross_cb, codeswap.m). Single source
of truth so a capture (run.py) and its verifier (verify.py) can never drift.

CLEAN ROOM: pure data-shape bookkeeping over our own harnesses' JSON output.
Inspects no Apple binary.

Design (see PRE_REGISTRATION.md "Raw-record schema"): every field that names
or embeds a live GPU virtual address varies run to run and must NEVER appear
in the byte-compared GATED file. Only case identity, structural counts,
booleans, status codes, the link TAG byte (not its address-bearing hi/lo
words), and our own deterministic tag-derived readback content are gated.

POST-CAPTURE SCHEMA CORRECTION (disclosed, see PROGRESS.md): the FIRST
official pair of runs (m4_20260828_run01/02) used a version of this module
that treated `readback_A_word0`/`readback_A` as always gate-safe. The
`--captured` gate correctly caught 3/19 cases (`misaligned_word8`,
`out_of_range_bit40`, `codeswap_task3` -- all cases where the command buffer
FAULTED, i.e. `final_status != 4`) where that field genuinely differed
between the two runs: e.g. `misaligned_word8` read back pure sentinel
(`0x5eed0000`, meaning zero of seg0's 732 legitimate dispatches were visible)
in run01 but `0xc0000002` (partial progress into seg2!) in run02. This is a
REAL hardware finding -- how much of a faulted command buffer's earlier,
perfectly legitimate work is visible in memory by the time the fault is
reported is racy, not deterministic -- not a bug in either capture. Both
run01 and run02 remain valid, immutable raw evidence for that finding
(reported in RESULTS.md). Per CODEX's "no nondeterministic field in
byte-compared records", THIS schema is corrected (a tooling fix, not a
raw-data repair -- raw/m4_20260828_run01 and run02 are untouched) to exclude
readback content from the gate whenever `final_status` != 4 (Completed);
a fresh, superseding pair of captures (m4_20260828_run03/04) was then taken
under this corrected schema for the row that actually gates closure claims.
This correction is proven by `--selftest`'s new fixture pair below.
"""
import re

COMPLETED_STATUS = 4  # MTLCommandBufferStatusCompleted

# Fields safe to compare byte-for-byte across runs (linksplice.m, both
# mechanisms share this superset; missing keys are simply absent per-record).
# NOTE: "readback_A_word0"/"readback_MID_word0" are handled SEPARATELY below
# (RACY_ON_FAULT_LINKSPLICE), not listed here -- see the module docstring's
# POST-CAPTURE SCHEMA CORRECTION.
LINKSPLICE_GATED_FIELDS = [
    "case", "mechanism", "redirect_mode", "redirect_committed",
    "found_seg0", "seg0_count",
    "found_seg1", "seg1_count",
    "found_seg2", "seg2_count",
    "natural_chain_ok", "case_valid_setup", "wrote",
    "new_link_tag",
    "hang", "final_status",
    "expect_seg0_last", "expect_seg1_last", "expect_seg2_last",
    "sentinel_A", "sentinel_MID",
    "fault_only_after_seg0",
]
# "final_error" (the raw NSError localizedDescription string) is handled
# SEPARATELY: gated only as a coarse CATEGORY (see _classify_final_error),
# never verbatim. HW-observed (run03 vs run04 of `encoding_max`): the SAME
# case, same final_status==5, reported "Caused GPU Hang Error
# (...ErrorHang)" in one run and "Discarded (victim of GPU error/recovery)
# (...ErrorInnocentVictim)" in the other -- GPU-level hang/TDR recovery can
# label any one of several affected in-flight command buffers as either the
# hang itself or an "innocent victim" of it, depending on timing. Both
# strings are collapsed to the same category for gating; the verbatim
# string remains in the addrs/non-gated sibling.
# Content fields that are DETERMINISTIC only when the command buffer reached
# MTLCommandBufferStatusCompleted (final_status==4). On a fault/hang, how
# much of a command buffer's earlier, legitimate work is memory-visible by
# the time the fault is reported is racy (HW-observed: run01/run02 of
# `misaligned_word8` differed between pure-sentinel and partial-progress-into-
# seg2 with every OTHER field identical). Gated only when final_status==4;
# otherwise routed to the addrs/non-gated sibling.
RACY_ON_FAULT_LINKSPLICE = ["readback_A_word0", "readback_MID_word0"]
RACY_ON_FAULT_CODESWAP = ["readback_A", "readback_MID", "readback_X", "readback_Y"]

# Address-bearing / location-dependent fields (never gated): pre_link_hi/lo,
# new_link_hi/lo (the split-address encodes a real GPU VA), raw_addrs.*, and
# the verbatim final_error string (see above; only its category is gated).
LINKSPLICE_ADDR_FIELDS = [
    "pre_link_hi", "pre_link_lo", "new_link_hi", "new_link_lo", "raw_addrs",
    "final_error",
] + RACY_ON_FAULT_LINKSPLICE  # present when final_status!=4; see build_addrs_linksplice

CODESWAP_GATED_FIELDS = [
    "setup_ok", "extracted_ok", "wrote",
    "seg0_count", "seg1_count", "seg2_count",
    "hang", "final_status",
    "sentinel_X", "sentinel_Y",
    "expect_kernel_x_value", "expect_kernel_y_value",
    # record hex is gated ONLY after redacting the +0x08 field (bytes 8..12,
    # hex chars 16..24), which is itself a location-dependent pointer.
    "record_x_hex_redacted", "record_y_hex_redacted", "hybrid_hex_redacted",
]
CODESWAP_ADDR_FIELDS = [
    "x_ptr", "y_ptr", "record_x_hex", "record_y_hex", "hybrid_hex",
    "hybrid_va", "seg0_va", "final_error",
] + RACY_ON_FAULT_CODESWAP  # present when final_status!=4; see build_addrs_codeswap


def _classify_final_error(final_error):
    """Collapse a verbatim NSError localizedDescription string to a stable
    category. See the RACY final_error note above for why the verbatim
    string is not gate-safe for hang-class events."""
    if final_error is None:
        return "None"
    s = final_error
    if "PageFault" in s or "AddressFault" in s or "Address Fault" in s:
        return "PageFault"
    if "ErrorHang" in s or "InnocentVictim" in s or "Hang Error" in s or "victim of GPU error" in s:
        return "GPU_RECOVERY_EVENT"
    return "Other"

# Deny-list of substrings that must never appear as a KEY in a gated record
# (defence in depth beyond the explicit whitelist above).
_ADDR_KEY_DENYLIST = {"va", "cpu", "addr", "address", "pointer", "ptr",
                       "hi", "lo", "target"}


def _redact_record_hex(hex_str):
    """Redact the CDM record's +0x08 4-byte field (hex chars [16:24)) which
    is a location-dependent code/uniform-window pointer, not a stable fact.
    """
    if not hex_str or len(hex_str) < 24:
        return hex_str
    return hex_str[:16] + "????????" + hex_str[24:]


def build_gated_linksplice(result):
    """result: parsed JSON dict from linksplice.m --out. Returns a dict
    containing LINKSPLICE_GATED_FIELDS, PLUS the readback fields only when
    final_status==COMPLETED_STATUS (otherwise they are racy -- see module
    docstring -- and belong only in the addrs/non-gated sibling), PLUS a
    normalized final_error_category (never the verbatim string)."""
    out = {k: result[k] for k in LINKSPLICE_GATED_FIELDS if k in result}
    if "final_error" in result:
        out["final_error_category"] = _classify_final_error(result["final_error"])
    if result.get("final_status") == COMPLETED_STATUS:
        for k in RACY_ON_FAULT_LINKSPLICE:
            if k in result:
                out[k] = result[k]
    return out


def build_addrs_linksplice(result):
    out = {k: result[k] for k in LINKSPLICE_ADDR_FIELDS
           if k in result and k not in RACY_ON_FAULT_LINKSPLICE}
    if result.get("final_status") != COMPLETED_STATUS:
        for k in RACY_ON_FAULT_LINKSPLICE:
            if k in result:
                out[k] = result[k]
    return out


def build_gated_codeswap(result):
    out = {k: result[k] for k in CODESWAP_GATED_FIELDS
           if k in result and not k.endswith("_redacted")}
    for src, dst in (("record_x_hex", "record_x_hex_redacted"),
                      ("record_y_hex", "record_y_hex_redacted"),
                      ("hybrid_hex", "hybrid_hex_redacted")):
        if src in result:
            out[dst] = _redact_record_hex(result[src])
    if "final_error" in result:
        out["final_error_category"] = _classify_final_error(result["final_error"])
    if result.get("final_status") == COMPLETED_STATUS:
        for k in RACY_ON_FAULT_CODESWAP:
            if k in result:
                out[k] = result[k]
    return out


def build_addrs_codeswap(result):
    out = {k: result[k] for k in CODESWAP_ADDR_FIELDS
           if k in result and k not in RACY_ON_FAULT_CODESWAP}
    if result.get("final_status") != COMPLETED_STATUS:
        for k in RACY_ON_FAULT_CODESWAP:
            if k in result:
                out[k] = result[k]
    return out


def assert_no_address_leak(gated_record):
    """Raise AssertionError if any key in `gated_record` looks address-shaped
    per the deny-list, OR if any string value looks like a bare 64-bit-ish
    hex GPU VA (a long run of hex digits with no surrounding structure other
    than the expected 0x-prefixed short status codes / tag bytes we know are
    safe). This is exercised synthetically by --selftest.
    """
    for k, v in gated_record.items():
        kl = k.lower()
        for bad in _ADDR_KEY_DENYLIST:
            # whole-token match only (split on underscore) to avoid false
            # positives like "expect_seg0_last" containing no denied token,
            # but catching "pre_link_hi" style names outright.
            tokens = kl.split("_")
            if bad in tokens:
                raise AssertionError(f"address-shaped key {k!r} in gated record")
        if isinstance(v, str) and re.fullmatch(r"0x[0-9a-f]{9,16}", v):
            # a long hex value (9-16 digits, i.e. >=36 bits) is address-shaped;
            # known-safe short codes (status ints, 2-digit tag hex like
            # "0x20") never match this width.
            raise AssertionError(f"address-shaped value {v!r} for key {k!r}")
    return True
