#!/usr/bin/env python3
"""cases199.py -- EXP-0199 case matrix.

Every case is a (arm, case_id, splice-list, meta) tuple.  The splice offsets are
ABSOLUTE file offsets into the base binary archive; they are computed from the
per-carrier `main_off` reported by tools/shdump/agxparse.py --locate, which is
frozen in CAPTURE_CONTRACT.json.  Nothing here is hand-computed.

CLEAN-ROOM: manipulates only bytes compiled from our own MSL.
"""

# ---------------------------------------------------------------- carriers ---
# Frozen at pre-registration.  `main_hex` is the extracted _agc.main of OUR OWN
# compiled shader; `main_off` is its absolute offset in the archive container;
# `slack` is the number of alignment-pad bytes that follow it (verified to be
# zero-valued), which bounds how far an INSERTION may shift the tail.
CARRIERS = {}

# ------------------------------------------------------------- helpers ------
def h(b):
    return bytes(b).hex()


def insert_at(main, off, B, ins):
    """One splice that INSERTS `ins` at byte B of `main`, shifting the tail down.
    Total written = len(ins) + len(main) - B, ending at off+len(main)+len(ins).
    The caller must have checked len(ins) <= slack."""
    return [(off + B, h(bytes(ins) + main[B:]))]


def delete_at(main, off, B, n):
    """One splice that DELETES n bytes at byte B of `main`, shifting the tail up.
    The last n bytes of the region keep whatever they held; execution stops at
    the (relocated) `stop`, so those bytes are never reached."""
    return [(off + B, h(main[B + n:]))]


def poke(off, B, byts):
    """In-place overwrite of len(byts) bytes at byte B of a shader."""
    return [(off + B, h(bytes(byts)))]
