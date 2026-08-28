#!/usr/bin/env python3
"""EXP-0110 schema.py -- the ONE frozen GATED record schema per case kind,
imported by both run.py (capture) and verify.py (--selftest and cross-run
gate). No GPU address, allocation-schedule byte, timing value, or pid may
ever be written into a GATED record -- see `assert_no_address_leak` below,
exercised by verify.py --selftest against every KEYS set in this file.

Design (per the EXP-0110 dispatch's explicit instruction): "keep raw
addresses OUT of the gated payload ... or normalize them explicitly and
prove the normalization in the selftest." This module does BOTH:
  - CDM/VDM segment facts are stored as record counts, tail/link tags, and
    *deltas* relative to that run's own zero-padding baseline case (an
    address DIFFERENCE, not a raw address -- and expected to reproduce
    run-to-run because it is exactly what the relocation hypothesis
    predicts is invariant).
  - the one raw structure this experiment must compare byte-for-byte (the
    CDM launch record, for the P0.7 firmware-vs-archive check) has its one
    known address-derived field (+0x08, a code/uniform-window pointer that
    tracks unrelated per-dispatch allocation) explicitly zeroed before
    hex-encoding -- `normalize_cdm_record`.
"""
import re

ADDRESS_KEY_DENY_TOKENS = {"va", "addr", "address", "gpu", "base", "cpu", "pointer", "ptr", "target"}

CDM_SEGMENT_KEYS = {"index", "record_count", "tail_kind", "link_tag", "delta_from_baseline", "transform_ok"}
CDM_CASE_KEYS = {"case", "kind", "params", "status", "cb_status", "segment_count", "total_records", "segments"}

VDM_SEGMENT_KEYS = CDM_SEGMENT_KEYS
VDM_CASE_KEYS = CDM_CASE_KEYS

STATE_CASE_KEYS = {"case", "kind", "params", "status", "cb_status", "pool_fields", "pairs"}
STATE_PAIR_KEYS = {"control", "delta_from_pool"}

CONTAINER_CASE_KEYS = {"case", "kind", "function", "meta_len", "fields", "sections_present"}

CONTAINER_LIVE_CASE_KEYS = {"case", "kind", "function", "nbuf", "status", "cb_status",
                            "cdm_record_hex_normalized", "arg_table_entry_count",
                            "preamble_nonzero_len"}

ALL_KEY_SETS = {
    "CDM_SEGMENT_KEYS": CDM_SEGMENT_KEYS, "CDM_CASE_KEYS": CDM_CASE_KEYS,
    "STATE_CASE_KEYS": STATE_CASE_KEYS, "STATE_PAIR_KEYS": STATE_PAIR_KEYS,
    "CONTAINER_CASE_KEYS": CONTAINER_CASE_KEYS,
    "CONTAINER_LIVE_CASE_KEYS": CONTAINER_LIVE_CASE_KEYS,
}


def assert_no_address_leak():
    """Every frozen key name in this module must be address-shape-free.
    Exercised by verify.py --selftest; also callable directly.
    """
    bad = []
    for setname, keys in ALL_KEY_SETS.items():
        for k in keys:
            tokens = set(k.lower().split("_"))
            if tokens & ADDRESS_KEY_DENY_TOKENS:
                bad.append((setname, k))
    if bad:
        raise AssertionError("address-shaped key name(s) in frozen schema: %r" % (bad,))
    return True


CDM_RECORD_LEN = 0x2c
CDM_OFFSET8_LEN = 4  # the one field this experiment observed varying independent of
                     # buffer count/content within a single process run (a per-dispatch
                     # code/uniform-window pointer, EXP-0011); zeroed before hex-encode.


def normalize_cdm_record(record_bytes):
    """Zero the +0x08..+0x0b field of a raw 0x2c-byte CDM record before
    hex-encoding it into a GATED payload. Idempotent: normalizing twice
    equals normalizing once (checked by verify.py --selftest).
    """
    if len(record_bytes) != CDM_RECORD_LEN:
        raise ValueError("expected a %d-byte CDM record, got %d" % (CDM_RECORD_LEN, len(record_bytes)))
    b = bytearray(record_bytes)
    b[8:8 + CDM_OFFSET8_LEN] = b"\x00" * CDM_OFFSET8_LEN
    return bytes(b)


def build_segment_records(segments_in_order, baseline_segments):
    """segments_in_order / baseline_segments: list of dicts with keys
    {gpu_va, record_count, tail_kind, tail_hi, tail_lo, decoded_target_va,
    decoded_ok (bool: does the decoded target equal the ACTUAL next
    segment's gpu_va, or None if there is no next segment / no link)}.
    Returns a list of GATED segment dicts (schema CDM_SEGMENT_KEYS), never
    touching gpu_va directly except via subtraction into `delta_from_baseline`.
    """
    out = []
    for i, seg in enumerate(segments_in_order):
        base_va = baseline_segments[i]["gpu_va"] if i < len(baseline_segments) else None
        delta = (seg["gpu_va"] - base_va) if base_va is not None else None
        link_tag = None
        if seg["tail_kind"] == "link" and seg.get("tail_hi") is not None:
            link_tag = (seg["tail_hi"] >> 24) & 0xff
        rec = {"index": i, "record_count": seg["record_count"], "tail_kind": seg["tail_kind"],
               "link_tag": link_tag, "delta_from_baseline": delta,
               "transform_ok": seg.get("decoded_ok")}
        assert set(rec.keys()) == CDM_SEGMENT_KEYS
        out.append(rec)
    return out
