#!/usr/bin/env python3
"""predictor.py -- EXP-0199 AMENDMENT-01: the case matrix, the GATE A ledger check,
and the GATE C independent semantic predictor.

Frozen with AMENDMENT-01 before the first confirmation dispatch.  Every prediction
here is computed from the MODEL ALONE -- it never reads a GPU result -- and
`conf.py` writes the whole prediction table to disk before it reads any output.

Buckets (RE_EXPERIMENT_PROCESS_CORRECTIONS Gate C):
  correct_effect | coherent_alternative | silent_zero_or_no_write | rejected | invalid
A model that makes no commitment for a case emits None for that case; a case where
NO model commits contributes to liveness and geometry only, never to semantics.

CLEAN-ROOM: pure host-side arithmetic over our own authored carriers.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.expanduser("~/agxre/tools/agx-isa"),
           os.path.join(_HERE, "..", "..", "..", "tools", "agx-isa")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
try:
    import isadb
except Exception:                                     # pragma: no cover
    isadb = None

BOUND = [38, 52, 62, 74, 84, 94, 104]
# Discovery (raw/g17p_run01*, run02*) found these; the models below are stated so
# that the confirmation capture can select among them, and so that each model's
# prediction for EVERY case is fixed before the confirmation runs.
FDS_BYTES = "d71454000003"          # frag_depth_store, both depth carriers
VS_BYTES = "000c4000"               # vary_slot in c_vary4's vertex shader


# ------------------------------------------------------------- case matrix ---
def build_cases(M3, off3, FD, cd, FD2, cd2, VX, cv):
    C = []

    def add(**kw):
        kw.setdefault("role", None)
        C.append(kw)

    def ins(B, hx):
        return [(off3 + B, hx + M3[B:].hex())]

    # ---------------- ARM A : frag_depth_store, on TWO carriers -------------
    for carrier, MAIN, moff, aoff, kind in (("c_depth", FD, cd, 168, "depth"),
                                            ("c_depth2", FD2, cd2, 186, "depth2")):
        A = moff + aoff
        add(arm="A", case="A_%s_baseline" % carrier, kind=kind, carrier=carrier,
            splice=[], instr="frag_depth_store", field="_baseline", value=None,
            anchor=A, req_bytes=FDS_BYTES)
        add(arm="A", case="A_%s_identity" % carrier, kind=kind, carrier=carrier,
            splice=[(moff, MAIN.hex())], instr="frag_depth_store",
            field="_identity", value=None, anchor=A, req_bytes=FDS_BYTES,
            role="falsifier_F1")
        for name, bo in (("b3", 3), ("b4", 4), ("b5", 5), ("byte1", 1), ("byte2", 2)):
            if carrier == "c_depth2" and name == "b4":
                continue                      # second carrier runs the 4 decisive bytes
            for v in range(256):
                rb = bytearray(bytes.fromhex(FDS_BYTES))
                rb[bo] = v
                add(arm="A", case="A_%s_%s_%02x" % (carrier, name, v), kind=kind,
                    carrier=carrier, splice=[(A + bo, "%02x" % v)],
                    instr="frag_depth_store", field=name, value=v, anchor=A,
                    req_bytes=bytes(rb).hex())
        for lbl, hx in (("barrier_depth", "070254010000"),
                        ("barrier_color", "0702540c0200"),
                        ("six_pads", "000000000000")):
            add(arm="A", case="A_%s_null_%s" % (carrier, lbl), kind=kind,
                carrier=carrier, splice=[(A, hx)], instr="frag_depth_store",
                field="_null", value=lbl, anchor=A, req_bytes=hx)

    # ---------------- ARM B : vary_slot ------------------------------------
    V = cv + 28
    add(arm="B", case="B_baseline", kind="vary", carrier="c_vary4", splice=[],
        instr="vary_slot", field="_baseline", value=None, anchor=V, req_bytes=VS_BYTES)
    add(arm="B", case="B_identity", kind="vary", carrier="c_vary4",
        splice=[(cv, VX.hex())], instr="vary_slot", field="_identity", value=None,
        anchor=V, req_bytes=VS_BYTES, role="falsifier_F1")
    for name, bo in (("slot", 3), ("sel", 1), ("byte0", 0), ("byte2", 2)):
        for v in range(256):
            rb = bytearray(bytes.fromhex(VS_BYTES))
            rb[bo] = v
            add(arm="B", case="B_%s_%02x" % (name, v), kind="vary", carrier="c_vary4",
                splice=[(V + bo, "%02x" % v)], instr="vary_slot", field=name,
                value=v, anchor=V, req_bytes=bytes(rb).hex())
    for j, so in enumerate((136, 144, 152, 160)):        # the four varying stores
        for v in (0x00, 0x20, 0x40, 0x60, 0x80, 0xa0, 0xc0, 0xe0):
            add(arm="B", case="B_posctl_store%d_%02x" % (j + 4, v), kind="vary",
                carrier="c_vary4", splice=[(cv + so + 4, "%02x" % v)],
                instr="vary_store", field="out_slot", value=v, site=j + 4,
                anchor=cv + so, req_bytes=None, role="positive_control")
    add(arm="B", case="B_null_4pad", kind="vary", carrier="c_vary4",
        splice=[(V, "00000000")], instr="vary_slot", field="_null", value="4pad",
        anchor=V, req_bytes="00000000")

    # ---------------- ARMS C / D : marker framing by INSERTION --------------
    add(arm="C", case="C_baseline", kind="comp", carrier="k_line3", splice=[],
        instr="sfu_marker", field="_baseline", value=None, anchor=off3 + 74,
        req_bytes=None)
    add(arm="C", case="C_identity", kind="comp", carrier="k_line3",
        splice=[(off3, M3.hex())], instr="sfu_marker", field="_identity", value=None,
        anchor=off3 + 74, req_bytes=None, role="falsifier_F1")
    for B in BOUND:
        add(arm="C", case="C_sfu0602@%d" % B, kind="comp", carrier="k_line3",
            splice=ins(B, "0602"), instr="sfu_marker", field="_insert2",
            value="0602", site=B, anchor=off3 + B, req_bytes="0602",
            role="positive_control")
        for lbl, hx in (("pad0000", "0000"), ("ffff", "ffff")):
            add(arm="C", case="C_ctl_%s@%d" % (lbl, B), kind="comp", carrier="k_line3",
                splice=ins(B, hx), instr="_control", field="_insert2", value=hx,
                site=B, anchor=off3 + B, req_bytes=hx, role="falsifier_F6")
        add(arm="C", case="C_del2@%d" % B, kind="comp", carrier="k_line3",
            splice=[(off3 + B, M3[B + 2:].hex())], instr="_control", field="_delete2",
            value="del2", site=B, anchor=off3 + B, req_bytes=None,
            role="falsifier_F2")
        add(arm="D", case="D_fmc4@%d" % B, kind="comp", carrier="k_line3",
            splice=ins(B, "60010000"), instr="frame_marker_compact",
            field="_insert4", value="60010000", site=B, anchor=off3 + B,
            req_bytes="60010000")
        add(arm="D", case="D_fmc2@%d" % B, kind="comp", carrier="k_line3",
            splice=ins(B, "6001"), instr="frame_marker_compact", field="_insert2",
            value="6001", site=B, anchor=off3 + B, req_bytes="6001")
        add(arm="D", case="D_ctl_4pad@%d" % B, kind="comp", carrier="k_line3",
            splice=ins(B, "00000000"), instr="_control", field="_insert4",
            value="00000000", site=B, anchor=off3 + B, req_bytes="00000000",
            role="falsifier_F6")
    for B in (74, 94):
        for v in range(256):
            add(arm="C", case="C_b0_%02x@%d" % (v, B), kind="comp", carrier="k_line3",
                splice=ins(B, "%02x02" % v), instr="sfu_marker",
                field="match_byte0", value=v, site=B, anchor=off3 + B,
                req_bytes="%02x02" % v)
            add(arm="C", case="C_b1_%02x@%d" % (v, B), kind="comp", carrier="k_line3",
                splice=ins(B, "06%02x" % v), instr="sfu_marker",
                field="match_byte1", value=v, site=B, anchor=off3 + B,
                req_bytes="06%02x" % v)
            if v not in (3, 7):
                add(arm="D", case="D_b1x4_%02x@%d" % (v, B), kind="comp",
                    carrier="k_line3", splice=ins(B, "60%02x0000" % v),
                    instr="frame_marker_compact", field="b1_in_4byte", value=v,
                    site=B, anchor=off3 + B, req_bytes="60%02x0000" % v)
    for v in range(256):
        if v not in (3, 7):
            add(arm="D", case="D_b1x2_%02x@74" % v, kind="comp", carrier="k_line3",
                splice=ins(74, "60%02x" % v), instr="frame_marker_compact",
                field="b1_in_2byte", value=v, site=74, anchor=off3 + 74,
                req_bytes="60%02x" % v)
        add(arm="D", case="D_b2x4_%02x@74" % v, kind="comp", carrier="k_line3",
            splice=ins(74, "6001%02x00" % v), instr="frame_marker_compact",
            field="byte2_in_4byte", value=v, site=74, anchor=off3 + 74,
            req_bytes="6001%02x00" % v)
        add(arm="D", case="D_b3x4_%02x@74" % v, kind="comp", carrier="k_line3",
            splice=ins(74, "600100%02x" % v), instr="frame_marker_compact",
            field="byte3_in_4byte", value=v, site=74, anchor=off3 + 74,
            req_bytes="600100%02x" % v)
    for v in (0x60, 0x61, 0x62, 0x64, 0x68, 0x70, 0x40, 0x20, 0xe0, 0x00,
              0x50, 0x63, 0x6f, 0x30, 0xa0, 0xc0):
        add(arm="D", case="D_byte0_%02x@74" % v, kind="comp", carrier="k_line3",
            splice=ins(74, "%02x010000" % v), instr="frame_marker_compact",
            field="match_byte0", value=v, site=74, anchor=off3 + 74,
            req_bytes="%02x010000" % v)

    # ---------------- ARM E : n2_op6 (geometry + liveness only) -------------
    N = cd + 48
    add(arm="E", case="E_baseline", kind="depth", carrier="c_depth", splice=[],
        instr="n2_op6", field="_baseline", value=None, anchor=N,
        req_bytes="023e00000004")
    for name, bo in (("byte0", 0), ("opsel", 2), ("imm_sel", 5)):
        for v in range(256):
            rb = bytearray(bytes.fromhex("023e00000004"))
            rb[bo] = v
            add(arm="E", case="E_%s_%02x" % (name, v), kind="depth", carrier="c_depth",
                splice=[(N + bo, "%02x" % v)], instr="n2_op6", field=name, value=v,
                site=48, anchor=N, req_bytes=bytes(rb).hex())
    return C


# ------------------------------------------------------------ GATE A ledger --
def check_ledger(c, actual):
    """requested value == value decoded INDEPENDENTLY out of the ACTUAL bytes the
    runner read back from the dispatched file.  Returns a dict; ok=False makes the
    case `invalid_ledger` and it is excluded from every tally."""
    a = c.get("anchor")
    rb = c.get("req_bytes")
    if a is None or rb is None:
        return {"ok": True, "checked": False, "why": "no anchor/req_bytes for this case"}
    got = actual.get(str(a))
    if got is None:
        return {"ok": True, "checked": False, "why": "anchor outside the ledger windows"}
    if not got.startswith(rb):
        return {"ok": False, "checked": True, "why": "actual != requested",
                "req": rb, "actual": got}
    out = {"ok": True, "checked": True, "actual_prefix": got[:len(rb)]}
    # independent decode of the swept BYTE out of the actual bytes
    f, v = c.get("field"), c.get("value")
    boff = {"b3": 3, "b4": 4, "b5": 5, "byte1": 1, "byte2": 2, "byte0": 0,
            "slot": 3, "sel": 1, "opsel": 2, "imm_sel": 5,
            "match_byte0": 0, "match_byte1": 1,
            "b1_in_2byte": 1, "b1_in_4byte": 1,
            "byte2_in_4byte": 2, "byte3_in_4byte": 3}.get(f)
    if boff is not None and isinstance(v, int):
        dec = int(got[boff * 2:boff * 2 + 2], 16)
        out["decoded_value"] = dec
        out["ok"] = (dec == v)
        if not out["ok"]:
            out["why"] = "decoded byte != requested value"
    if isadb is not None:
        try:
            b = bytes.fromhex(got)
            L = isadb.instr_length(b, 0)
            out["decoded_len"] = L
            if L:
                rec, _ = isadb.decode_one(b, 0)
                out["decoded_mnemonic"] = rec["mnemonic"]
        except Exception as e:
            out["decoded_mnemonic"] = "NO_DESC(%s)" % str(e)[:60]
    return out


# ------------------------------------------------------- GATE C predictions --
def predict(c):
    """Per-case prediction from every pre-registered competing model.  Computed
    from the model alone; never reads a GPU result."""
    arm, f, v = c["arm"], c.get("field"), c.get("value")
    P = {}

    if arm == "A":
        # M_A1: this instruction writes the shader depth output to the DEPTH
        # attachment.  Consequences that are predictions, not observations:
        if f == "_baseline" or f == "_identity" or (f == "byte2" and v == 0x54):
            P["M_A1"] = "correct_effect"        # DEPTH == host oracle, colour baseline
            P["M_A2"] = "coherent_alternative"  # DEPTH == 0.0 (position.z)
        elif f == "_null":
            P["M_A1"] = "silent_zero_or_no_write"   # depth attachment keeps the CLEAR
            P["M_A2"] = "coherent_alternative"      # DEPTH == 0.0 (position.z)
        else:
            # domain-wide prediction: the colour surface is unreachable from this
            # instruction, so no mutation of its bytes may move colour alone.
            P["M_A1"] = "not_color_moved"
            P["M_A3"] = "some_case_is_color_moved"
        P["M_A4"] = ("second_carrier_reproduces"
                     if c.get("carrier") == "c_depth2" else None)

    elif arm == "B":
        if c.get("role") == "positive_control":
            j, k = c["site"], v >> 5
            P["M_PC"] = ("draw_gone" if k < 4 else
                         ("ok" if k == j else "relocated:ch%d=%0.1f" %
                          (k - 4, 1000.0 * (j - 3))))
        elif f == "slot":
            P["M_B1"] = "some_value_relocates"
            P["M_B2"] = "ok" if (v & 0x04) == 0 else "draw_gone"
            P["M_B3"] = "ok"
        elif f == "_baseline" or f == "_identity":
            P["M_B1"] = P["M_B2"] = P["M_B3"] = "ok"

    elif arm in ("C", "D"):
        w = c.get("field")
        if w == "_insert2":
            P["M_len2"] = "correct_effect"
            P["M_len4"] = "rejected"
            P["M_notinstr"] = "rejected"
        elif w == "_insert4":
            P["M_len2"] = "depends_on_trailing_word"
            P["M_len4"] = "correct_effect"
            P["M_notinstr"] = "rejected"
        elif w == "_delete2":
            P["M_len2"] = P["M_len4"] = P["M_notinstr"] = "rejected"
        elif w in ("match_byte0", "match_byte1"):
            # db.json's declared match for sfu_marker: (b0 & 0x07)==6, (b1 & 0x03)==2
            m = ((v & 0x07) == 6) if w == "match_byte0" else ((v & 0x03) == 2)
            P["M_db_match"] = "correct_effect" if m else "rejected"
        elif w in ("b1_in_4byte", "byte2_in_4byte", "byte3_in_4byte"):
            P["M_len4"] = "correct_effect"      # 4-byte form should stay framed
        elif w == "b1_in_2byte":
            P["M_len2"] = "correct_effect"
            P["M_len4"] = "rejected"
        elif w == "_baseline" or w == "_identity":
            P["M_len2"] = P["M_len4"] = P["M_notinstr"] = "correct_effect"

    elif arm == "E":
        P["none"] = None                       # semantics declared unknown in advance
    return P
