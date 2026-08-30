#!/usr/bin/env python3
"""EXP-0174 FROZEN case matrix + the host oracle.

The whole matrix is generated deterministically from this file, hashed into
`CAPTURE_CONTRACT.json`, and is identical in every gated run. `run.py --order
reverse` changes only the ORDER in which the cases are dispatched.

CLEAN-ROOM: every byte of every case is computed here from `db.json`'s declared
bit geometry. Nothing is copied from a compiled shader.
"""
from __future__ import print_function

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

MOVE_B2 = 0x01          # the canonical MOVE sub-form
REL_B2 = 0x09           # the same, with the release bit set
SRC5 = 0x0A             # byte+1 selecting r5's LOW half  (2*5 + 0)
WIDE = (9, 2.5)         # r9 := 0x40200000

PLANS = ("idx15", "idx7")


# ---------------------------------------------------------------------------
# The frozen model (PRE_REGISTRATION.md section 2)
# ---------------------------------------------------------------------------
def block_state(plan):
    """The HOST-KNOWN register state at the moment the block under test runs.

    It is the seed table with ONE correction: `store_word` re-zeroes the plan's
    index register before every store, and the PRE-sentinel store runs BEFORE
    the block, so r[plan.idx] is 0 when the block executes. Modelling that is
    not a convenience -- arm B reads every register as a source, including the
    index register, and an un-corrected oracle would score that case wrong."""
    st = H.seed_state(plan, WIDE)
    st[plan.idx] = 0
    return st


def dump_of(plan, state):
    """What the 16-word dump must contain given a post-block register state.
    r[plan.idx] always reads 0 (destroyed by the read-back path) and r[plan.pad]
    always reads its own seed (restored by the post-block padding)."""
    out = list(state)
    out[plan.idx] = 0
    out[plan.pad] = H.SEED_I[plan.pad]
    return out


def model_move(plan, dst, b1, b2, b3):
    """Apply the frozen model. Returns (post_state, predicts) where `predicts`
    is "move" when the model applies and "no_model" when it does not."""
    st = block_state(plan)
    if (b2 & 0x03) != 0x01 or (b2 & 0xE0) != 0x00 or b3 not in (0x00, 0x01):
        return st, "no_model"
    S = (b1 >> 1) % 64
    hs = b1 & 1
    hd = b3 & 1
    if S >= H.N_REGS:
        return st, "no_model"          # source above r15: value not host-known
    v = (st[S] >> (16 * hs)) & 0xFFFF
    st[dst] = (st[dst] & ~(0xFFFF << (16 * hd)) & 0xFFFFFFFF) | (v << (16 * hd))
    if (b2 & 0x08) and S != dst:
        st[S] = 0
    return st, "move"


def n3(dst, b1, b2, b3):
    return H.n3_bytes(dst, b1 & 0x7F, (b1 >> 7) & 1, b2, b3)


def raw4(b0, b1, b2, b3):
    return bytes([b0, b1, b2, b3])


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------
def build_cases():
    C = []

    def add(arm, field, value, blk, plan, dst=None, b1=None, b2=None, b3=None,
            predicts=None, expect=None, note="", start=None, width=None,
            enc_range=None, falsifier=False, undecidable=False):
        C.append({
            "arm": arm, "field": field, "value": value, "bytes": blk.hex(),
            "plan": plan, "dst": dst, "b1": b1, "b2": b2, "b3": b3,
            "predicts": predicts, "expect": expect, "note": note,
            "start": start, "width": width, "encodable_range": enc_range,
            "falsifier": falsifier, "undecidable": undecidable,
        })

    def moved(arm, field, value, dst, b1, b2, b3, plan, **kw):
        P = H.PLANS[plan]
        st, pr = model_move(P, dst, b1, b2, b3)
        add(arm, field, value, n3(dst, b1, b2, b3), plan, dst, b1, b2, b3,
            pr, dump_of(P, st), **kw)

    # -- A/dstmap : n3_mov.dst, dense 0..15, both plans -------------------
    for plan in PLANS:
        for dst in range(16):
            P = H.PLANS[plan]
            und = (dst in P.blind) or (dst in P.masked) or (dst == 5)
            moved("A/dstmap", "n3_mov.dst", dst, dst, SRC5, MOVE_B2, 0x00, plan,
                  start=4, width=4, enc_range=16, undecidable=und,
                  note=("blind/masked/self in this plan" if und else ""))

    # -- B/srcmap : byte+1 dense 0..255, both plans ------------------------
    for plan in PLANS:
        for b1 in range(256):
            moved("B/srcmap", "n3_mov.srcA_reg", b1, 2, b1, MOVE_B2, 0x00, plan,
                  start=8, width=8, enc_range=256,
                  note="whole byte+1: db.json splits it 7+1, the model splits it 1+7")

    # -- C/half : source-half x destination-half, wide src AND wide dst ----
    for plan in PLANS:
        for hs in (0, 1):
            for hd in (0, 1):
                moved("C/half", "n3_mov.srcA_uni", hs, 2, 2 * 9 + hs, MOVE_B2, hd,
                      plan, start=15, width=1, enc_range=2,
                      note="wide SOURCE r9=0x40200000, hs=%d hd=%d" % (hs, hd))
                moved("C/half", "n3_mov.srcA_uni", hs, 9, 2 * 5 + hs, MOVE_B2, hd,
                      plan, start=15, width=1, enc_range=2,
                      note="wide DEST r9, src r5, hs=%d hd=%d" % (hs, hd))

    # -- D/subform : byte+2 dense 0..255 x b3 in {0,1} ---------------------
    for plan in PLANS:
        for b3 in (0x00, 0x01):
            for b2 in range(256):
                moved("D/subform", "n3_mov.subform", b2, 9, SRC5, b2, b3, plan,
                      start=16, width=8, enc_range=256,
                      note="wide DEST r9 so a half-write is visible; b3=%02x" % b3)

    # -- E/companion : byte+3 dense 0..255 x b2 in {move, move+release} ----
    for plan in PLANS:
        for b2 in (MOVE_B2, REL_B2):
            for b3 in range(256):
                moved("E/companion", "n3_mov.companion", b3, 9, SRC5, b2, b3, plan,
                      start=24, width=8, enc_range=256,
                      note="wide DEST r9; b2=%02x" % b2)

    # -- F/gen32 : GENERATED full 32-bit copy, all 240 ordered pairs -------
    for plan in PLANS:
        P = H.PLANS[plan]
        for dst in range(16):
            for src in range(16):
                if dst == src:
                    continue
                for order in ("hi_lo", "lo_hi"):
                    hi = n3(dst, 2 * src + 1, MOVE_B2, 0x01)
                    lo = n3(dst, 2 * src + 0, MOVE_B2, 0x00)
                    blk = (hi + lo) if order == "hi_lo" else (lo + hi)
                    st = block_state(P)
                    st[dst] = st[src]
                    und = (dst in P.blind) or (dst in P.masked)
                    add("F/gen32", "n3_mov.GENERATED32", dst * 16 + src, blk, plan,
                        dst, 2 * src, MOVE_B2, 0x00, "move", dump_of(P, st),
                        note="r%d = r%d, %s, ZERO copied fields" % (dst, src, order),
                        undecidable=und)

    # -- G/genhalf : GENERATED half moves, dst x src x hs x hd -------------
    for plan in PLANS:
        for dst in range(16):
            for src in range(16):
                for hs in (0, 1):
                    for hd in (0, 1):
                        und = (dst in H.PLANS[plan].blind) or \
                              (dst in H.PLANS[plan].masked) or (dst == src)
                        moved("G/genhalf", "n3_mov.GENERATEDHALF",
                              ((dst * 16 + src) * 2 + hs) * 2 + hd,
                              dst, 2 * src + hs, MOVE_B2, hd, plan,
                              undecidable=und,
                              note="r%d.h%d = r%d.h%d" % (dst, hd, src, hs))

    # -- H/release : byte+2 bit 3, incl. a wide source and S == dst --------
    for plan in PLANS:
        for b2 in (MOVE_B2, REL_B2, 0x05, 0x0D, 0x11, 0x19):
            for (dst, src) in ((2, 5), (2, 9), (9, 5), (5, 5), (2, 14)):
                moved("H/release", "n3_mov.subform", b2, dst, 2 * src, b2, 0x00,
                      plan, undecidable=(dst == src),
                      note="release probe b2=%02x r%d <- r%d" % (b2, dst, src))

    # -- X/alternate : STALE-PIPELINE CONTROL ------------------------------
    # This experiment dispatches ~1400 cases/second, far faster than any earlier
    # sweep in this repository. That is fast enough that "the child cached a
    # pipeline and re-ran an earlier program" is a live alternative explanation
    # for every result. So: two DISTINCT blocks are dispatched alternately 20
    # times each. If any pipeline caching were happening the two would converge;
    # they must alternate perfectly, every time, in both plans.
    for plan in PLANS:
        for k in range(20):
            for (tag, b1) in ((0, 2 * 5), (1, 2 * 0)):
                moved("X/alternate", "STALE_PIPELINE_CONTROL", tag, 2, b1,
                      MOVE_B2, 0x00, plan,
                      note="alternation %d: r2 <- r%d (must never converge)"
                           % (k, b1 // 2))

    # -- X/falsify ---------------------------------------------------------
    for plan in PLANS:
        P = H.PLANS[plan]
        base = block_state(P)
        for lo in range(16):
            if lo == 3:
                continue
            blk = raw4((2 << 4) | lo, SRC5, MOVE_B2, 0x00)
            add("X/lownib", "FALSIFIER", lo, blk, plan, 2, SRC5, MOVE_B2, 0x00,
                "no_move", dump_of(P, base), falsifier=True,
                note="byte0 low nibble %x must NOT perform the n3 move" % lo)
        # narrow member: r[dst] &= 0xFFFF, source NOT copied
        for dst in (2, 9):
            st = block_state(P)
            st[dst] = st[dst] & 0xFFFF
            blk = n3(dst, SRC5, 0x00, 0x01)
            add("X/narrow", "FALSIFIER", dst, blk, plan, dst, SRC5, 0x00, 0x01,
                "narrow", dump_of(P, st), falsifier=True,
                note="byte+2=0x00 is the in-place narrow, NOT a move (EXP-0161)")
        for b3 in (0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80):
            add("X/b3hi", "FALSIFIER", b3, n3(2, SRC5, MOVE_B2, b3), plan,
                2, SRC5, MOVE_B2, b3, "no_move", dump_of(P, base), falsifier=True,
                note="byte+3 = %02x must not write" % b3)
        for b2 in (0x21, 0x41, 0x81, 0xA1, 0xC1, 0xE1):
            add("X/b2hi", "FALSIFIER", b2, n3(2, SRC5, b2, 0x00), plan,
                2, SRC5, b2, 0x00, "no_move", dump_of(P, base), falsifier=True,
                note="byte+2 mask bit set: %02x must not move" % b2)
        for dst in (2, 9, 14):
            moved("X/selfmove", "FALSIFIER", dst, dst, 2 * dst, MOVE_B2, 0x00,
                  plan, undecidable=True,
                  note="dst == src: a correct self-move and a no-op are "
                       "INDISTINGUISHABLE here. Scored undecidable, never ok.")
    return C


def matrix_sha256(cases):
    return hashlib.sha256(
        json.dumps(cases, sort_keys=True).encode()).hexdigest()


if __name__ == "__main__":
    cs = build_cases()
    import collections
    c = collections.Counter(x["arm"] for x in cs)
    for k in sorted(c):
        print("%-14s %d" % (k, c[k]))
    print("TOTAL", len(cs))
    print("sha256", matrix_sha256(cs))
