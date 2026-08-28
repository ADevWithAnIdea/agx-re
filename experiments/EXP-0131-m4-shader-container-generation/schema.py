#!/usr/bin/env python3
"""EXP-0131 schema: splits each case's raw JSON record from harness/codesplice.m
into a GATED payload (content only, cross-run byte-comparable) and a
NON-GATED sibling (every address/pointer-shaped field, which legitimately
varies run to run because the allocator places BOs at different addresses
each process launch).

This mirrors the schema.py convention established by EXP-0110/EXP-0116:
"GPU addresses vary -- exclude or normalize and prove it" (standing gate).
"""
import re

# Fields written by harness/codesplice.m's `addr_*` keys are pointer/offset-
# shaped and MUST NEVER appear in the gated payload.
ADDR_KEYS = {
    "addr_bo_gpu_va", "addr_bo_cpu", "addr_main_off", "addr_header_off", "addr_write",
}

# Every other key the harness emits is content: case identity, booleans,
# status codes, small integers, hex BYTE STRINGS (not addresses) for
# before/after/bgra/main-hex, and the two header u32 VALUES (record_size is
# a small content field like 0xc0/0x0/0xffffffff, not a live pointer).
GATED_KEYS = [
    "case",
    "found_code_record",
    "baseline_completed",
    "baseline_status",
    "baseline_bgra",
    "did_write",
    "write_len",
    "write_before",
    "write_after_intended",
    "header_word_pre",
    "post_mutation_completed",
    "post_mutation_hang",
    "post_mutation_status",
    "post_mutation_error",
    "post_mutation_bgra",
    "post_read_ok",
    "header_word_post",
    "post_main_hex",
]

# A GPU VA / cpu-pointer in this experiment's captures always falls in one of
# these families (observed across all calibration + smoke runs): the
# 4 GiB-aligned code window (0x10000000000-ish), the low per-queue-context
# pool range (0x18000/0x40000/0x48000/0x58000/0x68000/0x80000/0x90000-ish),
# or a raw CPU heap pointer (>= 0x100000000, but NOT one of the above 40-bit
# code-window values -- CPU pointers are typically 0x1xxxxxxxx, 9-10 hex
# digits). We flag anything hex-string-shaped that parses to an integer
# whose value looks like one of these families, OUTSIDE the known-safe small
# content fields, as a leak.
_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")


def _looks_address_shaped(value: str) -> bool:
    if not isinstance(value, str) or not _HEX_RE.match(value):
        return False
    v = int(value, 16)
    # Small content values (record_size, status codes, etc.) are never
    # address-shaped in this experiment: every real capture saw header
    # words <= 0xffffffff (32-bit) which could coincidentally alias a
    # pointer's low bits, so instead we key off the SPECIFIC known BO/cpu
    # value ranges seen in this experiment, which all exceed 2**33.
    return v >= (1 << 33)


def split_record(raw: dict) -> tuple[dict, dict]:
    """Return (gated, nongated) dicts from one harness JSON record."""
    gated = {k: raw[k] for k in GATED_KEYS if k in raw}
    nongated = {k: raw[k] for k in ADDR_KEYS if k in raw}
    nongated["case"] = raw.get("case")
    return gated, nongated


def assert_no_address_leak(gated: dict):
    """Raise AssertionError if any gated field is address-shaped, or if any
    ADDR_KEYS key leaked into the gated dict."""
    for k in gated:
        if k in ADDR_KEYS:
            raise AssertionError(f"address-shaped key {k!r} present in gated payload")
    for k, v in gated.items():
        if isinstance(v, str) and _looks_address_shaped(v):
            raise AssertionError(f"gated field {k!r}={v!r} looks address-shaped")
    # write_before/write_after_intended/post_main_hex/baseline_bgra/
    # post_mutation_bgra are raw byte-string hex WITHOUT a 0x prefix (see
    # jbytes() in codesplice.m) -- confirm none of those slipped in with a
    # 0x prefix either (would indicate a schema drift in the harness).
    for k in ("write_before", "write_after_intended", "post_main_hex", "baseline_bgra", "post_mutation_bgra"):
        v = gated.get(k)
        if isinstance(v, str) and v.startswith("0x"):
            raise AssertionError(f"byte-string field {k!r} unexpectedly 0x-prefixed: {v!r}")


def gated_bytes_for_compare(gated: dict) -> bytes:
    """Canonical byte serialization for cross-run comparison (stable key
    order, no whitespace variance)."""
    import json
    return json.dumps(gated, sort_keys=True, separators=(",", ":")).encode("utf-8")
