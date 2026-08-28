#!/usr/bin/env python3
"""EXP-0110 scan.py -- shared CDM/VDM structural scanner + link-transform
decoder. Imported by run.py (capture time), verify.py (--selftest synthetic
fixtures), and the report generator. Single source of truth for the record
schema so a capture and its verifier can never silently drift apart.

CLEAN ROOM: every byte pattern searched for here is OUR OWN authored data
(the exact grid/threadgroup dims and vertex-count sequence emitted by
harness/cmdprobe.m). This module never interprets opaque Apple-authored
bytes as meaning; it locates our own literal authored values inside BOs
this process itself registered, exactly as EXP-0043/EXP-0049 did (their
"structural scanner"). Unclassified BOs are left unread by callers that
follow the documented allowlist discipline in this file's docstring.

Record shapes (established DATA-TRACE facts, EXP-0011/0019/0024/0043/0049,
reproduced byte-identically on M4 by this experiment's own baseline runs):

  CDM record (0x2c bytes), our authored dispatch is always grid=(64,1,1),
  threadgroup=(32,1,1):
    +0x00 u32 config word (bit19 always set; bit23 = occupancy tier)
    +0x04 u32 (unclassified; observed constant 0x01000000 for this kernel)
    +0x08 u32 code/uniform-window pointer (grows per dispatch in this shape)
    +0x0c u32 (unclassified)
    +0x10 u32 grid.x   +0x14 u32 grid.y   +0x18 u32 grid.z
    +0x1c u32 tg.x     +0x20 u32 tg.y     +0x24 u32 tg.z
    +0x28 u32 (unclassified)
  Segment terminator (4 bytes right after the last record): 0x40000000.
  Segment link (8 bytes in the same position): [hi32, lo32] naming the next
  command BO's GPU VA as `((hi32 & 0x00ffffff) << 32) | lo32`, tag = hi32>>24
  (CDM tag observed = 0x20).

  VDM draw command (4 dwords, non-indexed), our authored draws alternate
  vertexCount 3,6,3,6,...: the pair (vertexCount_u32, instanceCount_u32=1)
  is the stable 8-byte signature this scanner searches for; a genuine
  segment is >=8 consecutive matches reproducing the authored 3,6,3,6,...
  sequence. Segment terminator: 0xc0000000. Segment link: [hi32, lo32],
  same transform, tag = 0x80.
"""
import re
import struct

CDM_RECORD_LEN = 0x2c
CDM_TERMINATOR = 0x40000000
VDM_TERMINATOR = 0xc0000000
CDM_LINK_TAG = 0x20
VDM_LINK_TAG = 0x80

HDR_RE = re.compile(rb"gpu_va=0x([0-9a-fA-F]+) cpu=0x([0-9a-fA-F]+) size=0x([0-9a-fA-F]+) read=0x([0-9a-fA-F]+)")
HEXLINE_RE = re.compile(rb"^([0-9a-f]{8}): (.*)$")


def load_hex_dump(path):
    """Load one iotrace bo_*.hex file into (gpu_va, size, read, bytes)."""
    with open(path, "rb") as f:
        raw = f.read()
    lines = raw.split(b"\n")
    if not lines or not lines[0].startswith(b"#"):
        raise ValueError("not an iotrace BODUMP file: %r" % path)
    m = HDR_RE.search(lines[0])
    if not m:
        raise ValueError("unparseable BODUMP header: %r" % lines[0])
    gpu_va, cpu, size, read = (int(x, 16) for x in m.groups())
    data = bytearray()
    for line in lines[1:]:
        m2 = HEXLINE_RE.match(line)
        if not m2:
            continue
        off = int(m2.group(1), 16)
        hx = m2.group(2).replace(b" ", b"")
        b = bytes.fromhex(hx.decode("ascii"))
        if len(data) < off + len(b):
            data.extend(b"\x00" * (off + len(b) - len(data)))
        data[off:off + len(b)] = b
    return {"gpu_va": gpu_va, "cpu": cpu, "size": size, "read": read, "data": bytes(data)}


def parse_dump_filename(name):
    """Parse `bo_<reason>_h<handle>_va<hex>_cpu<hex>_sz<hex>.hex` -> dict or None.

    This is pure filename metadata (no file content read) -- the allocation
    catalog this experiment relies on for relocation analysis without
    inspecting unclassified BO bytes.
    """
    m = re.match(r"^bo_([a-zA-Z0-9]+)_h(\d+)_va([0-9a-fA-F]+)_cpu([0-9a-fA-F]+)_sz([0-9a-fA-F]+)\.hex$", name)
    if not m:
        return None
    reason, handle, va, cpu, sz = m.groups()
    return {"reason": reason, "handle": int(handle), "gpu_va": int(va, 16),
            "cpu": int(cpu, 16), "size": int(sz, 16), "filename": name}


def cdm_signature(grid=(64, 1, 1), tg=(32, 1, 1)):
    return struct.pack("<6I", grid[0], grid[1], grid[2], tg[0], tg[1], tg[2])


def find_all(hay, needle):
    out = []
    i = hay.find(needle)
    while i != -1:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out


def scan_cdm_segment(data, grid=(64, 1, 1), tg=(32, 1, 1)):
    """Locate contiguous 0x2c-byte CDM records by our authored grid/tg
    signature (at record +0x10). Returns dict with record offsets (relative
    to `data` start), count, and the 4/8 bytes immediately following the
    last record (terminator-or-link candidate).
    """
    sig = cdm_signature(grid, tg)
    hits = find_all(data, sig)
    records = [h - 0x10 for h in hits]
    records.sort()
    # keep only a maximal contiguous run at fixed 0x2c stride
    runs = []
    cur = []
    for r in records:
        if cur and r - cur[-1] != CDM_RECORD_LEN:
            runs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        runs.append(cur)
    best = max(runs, key=len) if runs else []
    result = {"record_count": len(best), "first_offset": best[0] if best else None,
              "last_offset": best[-1] if best else None, "tail": None, "tail_kind": None,
              "tail_hi": None, "tail_lo": None}
    if best:
        tail_off = best[-1] + CDM_RECORD_LEN
        tail8 = data[tail_off:tail_off + 8]
        result["tail"] = tail8.hex()
        if len(tail8) >= 4:
            w0 = struct.unpack_from("<I", tail8, 0)[0]
            if w0 == CDM_TERMINATOR:
                result["tail_kind"] = "terminator"
            elif len(tail8) == 8:
                w1 = struct.unpack_from("<I", tail8, 4)[0]
                result["tail_kind"] = "link" if (w0 >> 24) == CDM_LINK_TAG else "unknown"
                result["tail_hi"] = w0
                result["tail_lo"] = w1
    return result


def scan_vdm_segment(data, seq_start_parity=0, min_run=8):
    """Locate the alternating vertexCount(3,6,...)+instanceCount(1) 8-byte
    signature sequence. Returns the longest run consistent with the
    authored 3,6,3,6,... (or 6,3,6,3,...) order, plus the tail bytes after
    the last matched draw command.
    """
    def sig(vc):
        return struct.pack("<II", vc, 1)

    hits3 = set(find_all(data, sig(3)))
    hits6 = set(find_all(data, sig(6)))
    all_hits = sorted(hits3 | hits6)
    best_run = []
    cur = []
    expect = None
    for off in all_hits:
        vc = 3 if off in hits3 else 6
        if cur and expect is not None and vc == expect and off - cur[-1][0] > 0:
            cur.append((off, vc))
        elif not cur:
            cur = [(off, vc)]
        else:
            if len(cur) > len(best_run):
                best_run = cur
            cur = [(off, vc)]
        expect = 6 if vc == 3 else 3
    if len(cur) > len(best_run):
        best_run = cur
    if len(best_run) < min_run:
        return {"record_count": len(best_run), "first_offset": None, "last_offset": None,
                "tail": None, "tail_kind": None, "tail_hi": None, "tail_lo": None}
    last_off = best_run[-1][0]
    # The 8-byte (vertexCount, instanceCount) signature sits at the middle of
    # the 4-dword non-indexed draw record [opcode/primitive][vertexCount]
    # [instanceCount][trailing zero] (EXP-0043/EXP-0014); the true tail
    # (terminator or link) begins 4 bytes after instanceCount, i.e. +12 from
    # the matched vertexCount offset. HW-confirmed by this experiment's own
    # baseline dumps (the naive +8 assumption lands mid-terminator).
    tail_off = last_off + 12
    tail8 = data[tail_off:tail_off + 8]
    result = {"record_count": len(best_run), "first_offset": best_run[0][0],
              "last_offset": last_off, "tail": tail8.hex(), "tail_kind": None,
              "tail_hi": None, "tail_lo": None}
    if len(tail8) >= 4:
        w0 = struct.unpack_from("<I", tail8, 0)[0]
        if w0 == VDM_TERMINATOR:
            result["tail_kind"] = "terminator"
        elif len(tail8) == 8:
            w1 = struct.unpack_from("<I", tail8, 4)[0]
            result["tail_kind"] = "link" if (w0 >> 24) == VDM_LINK_TAG else "unknown"
            result["tail_hi"] = w0
            result["tail_lo"] = w1
    return result


def decode_link(tail_hi, tail_lo):
    """Decode the hypothesized split-address link encoding:
       target_va = ((hi32 & 0x00ffffff) << 32) | lo32 ; tag = hi32 >> 24.
    Returns (tag, target_va).
    """
    tag = (tail_hi >> 24) & 0xff
    target_va = ((tail_hi & 0x00ffffff) << 32) | tail_lo
    return tag, target_va


def encode_link(tag, target_va):
    hi = ((tag & 0xff) << 24) | ((target_va >> 32) & 0x00ffffff)
    lo = target_va & 0xffffffff
    return hi, lo


VDM_HEADER_START = 0x08
VDM_CONTROL_SET = (0x0200, 0x0300, 0x0500, 0x0700, 0x0a00)


def scan_vdm_bindpairs(data, first_draw_record_offset):
    """Extract the (control, address) bind pairs in the VDM header region
    (EXP-0019 grammar), from VDM_HEADER_START up to just before the first
    draw record's opcode word (4 bytes before the matched vertexCount
    offset). A pair is any consecutive (u32, u32) where the first word's
    value is in VDM_CONTROL_SET and the second is nonzero. Returns a list of
    {offset, control, address} in file order.
    """
    end = max(first_draw_record_offset - 4, VDM_HEADER_START)
    pairs = []
    off = VDM_HEADER_START
    while off + 8 <= end:
        w0, w1 = struct.unpack_from("<II", data, off)
        if w0 in VDM_CONTROL_SET and w1 != 0:
            pairs.append({"offset": off, "control": w0, "address": w1})
            off += 8
        else:
            off += 4
    return pairs


def find_pool_base(pairs):
    """Cluster bind-pair addresses by 4 KiB page; the densest cluster's
    minimum address is the FF-state pool base (EXP-0019: 5-6 of ~8-9 pairs
    land in a contiguous <=0x400-byte pool region). Returns (pool_base,
    cluster_addresses) or (None, []) if no cluster of size >= 2 exists.
    """
    from collections import defaultdict
    buckets = defaultdict(list)
    for p in pairs:
        buckets[p["address"] & ~0xfff].append(p["address"])
    if not buckets:
        return None, []
    best_page = max(buckets, key=lambda k: len(buckets[k]))
    if len(buckets[best_page]) < 2:
        return None, []
    cluster = sorted(set(buckets[best_page]))
    return cluster[0], cluster


def find_chain(matched):
    """matched: {gpu_va: scan_result} for every BO whose content structurally
    matched our authored CDM/VDM signature (>=1 record). Finds the head (the
    VA no other matched segment's decoded link targets) and follows tail
    links until termination, an unmatched/dangling target, or a cycle.

    Returns (chain, anomalies) where `chain` is an ordered list of gpu_va and
    `anomalies` lists any dangling/cyclic condition found (never silently
    dropped).
    """
    targets = {}
    for va, r in matched.items():
        if r.get("tail_kind") == "link":
            tag, tgt = decode_link(r["tail_hi"], r["tail_lo"])
            targets[va] = tgt
    heads = [va for va in matched if va not in targets.values()]
    anomalies = []
    if len(heads) != 1:
        anomalies.append({"kind": "ambiguous_or_missing_head", "heads": sorted(heads)})
        if not heads:
            return [], anomalies
    head = sorted(heads)[0]
    chain = [head]
    seen = {head}
    cur = head
    while cur in targets:
        nxt = targets[cur]
        if nxt in seen:
            anomalies.append({"kind": "cycle", "at": nxt})
            break
        if nxt not in matched:
            anomalies.append({"kind": "dangling_link", "from": cur, "target": nxt})
            break
        chain.append(nxt)
        seen.add(nxt)
        cur = nxt
    return chain, anomalies
