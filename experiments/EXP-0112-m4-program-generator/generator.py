#!/usr/bin/env python3
"""EXP-0112 program generator -- THE deliverable this experiment exists to
build and validate.

Given a small dataflow DAG SPEC (a list of typed nodes, each an operation
plus operand references to earlier nodes), this module:
  1. builds the DAG structure (Pass 1: `generate_dag`) from a seeded RNG,
     enforcing a consumption discipline that never leaves the documented,
     HW-VALIDATED rule envelope (see the module docstring's "CONSUMPTION
     DISCIPLINE" section below);
  2. allocates the 14-register DAG value-node pool with REUSE, via a
     provably-bounded linear-scan allocator (Pass 2: `allocate_registers`);
  3. emits real AGX9 instruction bytes for every node from RULES (never by
     copying a whole captured instruction) via `isa_helpers.py` -- which is
     itself a thin wrapper over `tools/agx-isa`'s own `isadb.assemble()`
     (Pass 3: `emit_program`), and simultaneously computes the exact
     expected host-side floating-point value for every stored (leaf) node.

This is a GENERATOR, not a replay tool: no byte string in this file is ever
copied from a captured program. The ONLY verbatim constants used are single
documented FIELD VALUES cited to the experiment that established them
(`isa_helpers.DST_TOKEN_KNOWNGOOD`, the `iadd2_anchor` byte pattern) --
labelled at their point of use, per this project's standing convention
(CLAUDE.md: "copying single documented constants... is fine and must be
labelled as such").

RULES THIS GENERATOR IMPLEMENTS (every one independently re-derivable from
the cited RESULTS.md, none re-discovered here):
  - device_load -> falu2/falu2i bridge: extmode = 2*R (EXP-0101 H1).
  - falu2i mods=0xC0 when srcA is directly load-sourced (EXP-0101 H1).
  - falu2 (register-register) opflags=3 when BOTH operands are real
    computed values (EXP-0090 finding_1).
  - device_store extmode = 2*data_reg (EXP-0090 finding_5).
  - liveness bit0 = 1 on exactly the temporally LAST A-read of a given
    producer register, 0 on every earlier A-read (EXP-0086, EXP-0090 P1).
  - device_load/store address formula idx*scale + idx_off*unit (EXP-0082).
  - falu2i immediate rounding via isadb's own minifloat codec (EXP-0006).

CONSUMPTION DISCIPLINE (why the generator restricts itself this way):
No experiment in this repository has validated a register being read by
BOTH an ALU op AND (afterward) a device_store, nor a register's srcB-only
(falu2 register-form) consumption being followed by a LATER read of any
kind. To stay inside ground actually surveyed, every DAG value node's
consumers must be EXACTLY one of:
  (a) one or more falu2i/falu2-srcA reads ("A-reads"), each carrying its
      own liveness bit, the temporally last one True, and NOTHING else
      reads this node afterward; or
  (b) exactly one falu2-srcB read ("B-read"), and this node had NEVER
      been read before (no prior A-read); or
  (c) exactly one device_store read ("leaf"/output), and this node had
      NEVER been read before.
Mixed A-then-B, A-then-store, or B/store-then-anything are explicitly
OUT of this generator's synthesis envelope -- not silently assumed safe.
See RESULTS.md SS "generation envelope" for what this excludes.
"""
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

# -- shared carrier/slot constants for the whole EXP-0112 corpus (DAG,
# REGBOUNDARY, IADD_ANCHOR, ADVERSARIAL families -- everything spliced over
# kernels/carrier_dag.metal). Re-derived and asserted fresh by baseline.py
# before every capture (never assumed).
DAG_CARRIER_LEN = 1536   # < carrier_dag.metal's own compiled length (1590B)
SLOT_OUT = 0
SLOT_MEM = 1
SLOT_IMEM = 2

POOL_SIZE = len(H.POOL)  # 14
# The main-loop generator caps live_count at EFFECTIVE_CAP, not the full
# POOL_SIZE: the finalization pass (closing any still-open, touched node
# with one more A-read) needs a little headroom of its own to bootstrap --
# processing N leftover open nodes sequentially needs at least 1 free
# register to allocate the FIRST finalizer before any of the leftovers can
# be freed (a finalizer's own register is only reclaimed once the NEXT
# node's allocation runs, one step later). 2 registers of headroom is a
# comfortable margin verified empirically by --selftest below, not merely
# assumed.
EFFECTIVE_CAP = POOL_SIZE - 2


# ---------------------------------------------------------------------------
# Pass 1 -- DAG structure
# ---------------------------------------------------------------------------
class _Node:
    __slots__ = ("id", "type", "op", "k", "idx_off", "elem_code",
                 "srcA", "srcB", "a_budget", "touched", "a_reads",
                 "b_read", "is_store", "is_finalizer_of")

    def __init__(self, nid, ntype):
        self.id = nid
        self.type = ntype
        self.op = None
        self.k = None
        self.idx_off = None
        self.elem_code = 3
        self.srcA = None
        self.srcB = None
        self.a_budget = 0
        self.touched = False
        self.a_reads = []      # consumer node ids, in creation order
        self.b_read = None     # consumer node id or None
        self.is_store = False
        self.is_finalizer_of = None  # if this node exists only to close another


def _pick_recency(rng, candidates, window=6):
    """Uniform choice biased toward RECENT node ids (locality, like a real
    compiler's operand selection) -- `candidates` must already be sorted
    ascending by id."""
    if not candidates:
        return None
    tail = candidates[-window:] if len(candidates) > window else candidates
    return rng.choice(tail)


IMM_BOUNDARY_POOL = [0.0, 1.0, -1.0, 0.5, -0.5, 2.0, 30.0, -30.0, 0.125, 100.0, -100.0, 3.5]
IDXOFF_BOUNDARY_POOL = [0, 1, 2, 2047, 2046, 1024, 512]


def generate_dag(seed, n_nodes, allow_boundary_immediates=True):
    """Deterministic (seed -> identical DAG, always) structural generator.
    Returns the list of `_Node` objects, fully resolved (every consumer
    edge recorded, every leaf/finalizer decided). No register or byte-level
    decision is made here -- see `allocate_registers`/`emit_program`."""
    rng = random.Random("EXP-0112-dag-%r" % (seed,))
    nodes = []
    open_ids = []          # node ids with a_budget > 0 (may also be untouched)
    live_count = 0

    def a_candidates():
        return [i for i in open_ids if nodes[i].a_budget > 0]

    def fresh_candidates():
        return [i for i in open_ids if not nodes[i].touched]

    def close_if_exhausted(nid):
        nonlocal live_count
        n = nodes[nid]
        if n.a_budget <= 0 and n.b_read is None and not n.is_store:
            open_ids.remove(nid)
            live_count -= 1

    def new_leaf(ntype):
        nonlocal live_count
        nid = len(nodes)
        n = _Node(nid, ntype)
        if ntype == "const":
            n.k = rng.choice(IMM_BOUNDARY_POOL) if (allow_boundary_immediates and rng.random() < 0.35) \
                else rng.uniform(-25.0, 25.0)
        else:  # load
            n.idx_off = rng.choice(IDXOFF_BOUNDARY_POOL) if rng.random() < 0.25 \
                else rng.randrange(0, 2048)
            n.elem_code = 3
        n.a_budget = rng.choices([1, 2], weights=[0.75, 0.25])[0]
        nodes.append(n)
        open_ids.append(nid)
        live_count += 1
        return nid

    def consume_a(producer_id, consumer_id):
        nonlocal live_count
        p = nodes[producer_id]
        p.a_reads.append(consumer_id)
        p.touched = True
        p.a_budget -= 1
        close_if_exhausted(producer_id)

    def consume_b(producer_id, consumer_id):
        nonlocal live_count
        p = nodes[producer_id]
        assert not p.touched, "B-read requires an untouched node"
        p.b_read = consumer_id
        p.touched = True
        open_ids.remove(producer_id)
        live_count -= 1

    for i in range(n_nodes):
        at_cap = live_count >= EFFECTIVE_CAP
        ac = a_candidates()
        fc = fresh_candidates()
        if not ac and not fc:
            t = rng.choice(["const", "load"])
        elif at_cap:
            # Provably-bounded forced closure: pick the OLDEST open node,
            # clamp its remaining budget to 1 so THIS read is guaranteed
            # terminal, then consume it via a single-operand op. Net live
            # count change is exactly 0 (one closes, one opens) -- live_count
            # can never exceed POOL_SIZE by induction (starts at 0, every
            # non-forced step's net change is <= +1 only while
            # live_count < POOL_SIZE, and every forced step's net change is
            # exactly 0), so the Pass-2 allocator's POOL_SIZE-sized free list
            # never underflows.
            oldest = min(ac) if ac else min(fc)
            nodes[oldest].a_budget = 1
            new_op_type = rng.choice(["add_imm", "mul_imm"])
            nid = len(nodes)
            n = _Node(nid, new_op_type)
            n.op = "fadd" if new_op_type == "add_imm" else "fmul"
            n.k = rng.choice(IMM_BOUNDARY_POOL) if rng.random() < 0.3 else rng.uniform(-10, 10)
            n.srcA = oldest
            n.a_budget = rng.choices([1, 2], weights=[0.75, 0.25])[0]
            nodes.append(n)
            consume_a(oldest, nid)
            open_ids.append(nid)
            live_count += 1
            continue
        else:
            weights = {"const": 0.16, "load": 0.24, "add_imm": 0.22, "mul_imm": 0.10,
                       "add_reg": 0.16, "mul_reg": 0.12}
            choices, wts = [], []
            for k, w in weights.items():
                if k in ("const", "load"):
                    choices.append(k); wts.append(w)
                elif k in ("add_imm", "mul_imm") and ac:
                    choices.append(k); wts.append(w)
                elif k in ("add_reg", "mul_reg") and ac and len(fc) >= 1:
                    choices.append(k); wts.append(w)
            t = rng.choices(choices, weights=wts)[0]

        if t in ("const", "load"):
            new_leaf(t)
            continue

        if t in ("add_imm", "mul_imm"):
            srcA = _pick_recency(rng, sorted(ac))
            nid = len(nodes)
            n = _Node(nid, t)
            n.op = "fadd" if t == "add_imm" else "fmul"
            n.k = rng.choice(IMM_BOUNDARY_POOL) if rng.random() < 0.3 else rng.uniform(-10, 10)
            n.srcA = srcA
            n.a_budget = rng.choices([1, 2], weights=[0.75, 0.25])[0]
            nodes.append(n)
            consume_a(srcA, nid)
            open_ids.append(nid)
            live_count += 1
            continue

        # add_reg / mul_reg
        srcA = _pick_recency(rng, sorted(ac))
        fc2 = [x for x in fc if x != srcA]
        if not fc2:
            # fall back to single-operand form
            nid = len(nodes)
            fallback = "add_imm" if t == "add_reg" else "mul_imm"
            n = _Node(nid, fallback)
            n.op = "fadd" if fallback == "add_imm" else "fmul"
            n.k = rng.uniform(-10, 10)
            n.srcA = srcA
            n.a_budget = rng.choices([1, 2], weights=[0.75, 0.25])[0]
            nodes.append(n)
            consume_a(srcA, nid)
            open_ids.append(nid)
            live_count += 1
            continue
        srcB = _pick_recency(rng, sorted(fc2))
        nid = len(nodes)
        n = _Node(nid, t)
        n.op = "fadd" if t == "add_reg" else "fmul"
        n.srcA = srcA
        n.srcB = srcB
        nodes.append(n)
        consume_a(srcA, nid)
        consume_b(srcB, nid)
        open_ids.append(nid)
        live_count += 1

    # -- finalization: every still-open node must become either a direct
    # store (never touched) or get one trivial +0.0 finalizer A-read that
    # becomes its guaranteed last use, whose OWN result (untouched) is what
    # actually gets stored -- keeps every store strictly single-consumer
    # (rule (c) above), never mixed with a prior A-read on the SAME node.
    # IMPORTANT SCOPE NOTE (found by this generator's own dry-run validation,
    # not asserted a priori): a `load` node must NEVER be stored directly
    # (device_store reading its extmode-bridged register with no ALU op in
    # between). EXP-0101's extmode=2*R rule was validated ONLY for
    # falu2/falu2i CONSUMPTION of a bridged load register -- it says
    # nothing about a device_store reading that same register directly.
    # EXP-0090's OWN validated load->store path (finding_3) is a
    # STRUCTURALLY DIFFERENT mechanism: addr_mode=0x56 on an IMMEDIATELY
    # ADJACENT store, extmode=0 fixed, bypassing the GPR file entirely
    # (not indexed by "which register" at all) -- it cannot be mixed
    # in-place with this generator's general, register-addressed DAG
    # model. Rather than half-implement a second, structurally distinct
    # bridging mechanism, this generator stays inside the validated
    # ALU-bridge envelope: every `load` node ALWAYS gets at least one
    # trivial +0.0 A-read finalizer before being stored, exactly like a
    # "touched but not fully closed" node below -- so every stored load
    # value has passed through a real falu2i consumption (EXP-0101's own
    # validated shape) first. See RESULTS.md "generation envelope".
    leaves = []
    for nid in list(open_ids):
        n = nodes[nid]
        if not n.touched and n.type != "load":
            leaves.append(nid)
        else:
            fin_id = len(nodes)
            fin = _Node(fin_id, "add_imm")
            fin.op = "fadd"
            fin.k = 0.0
            fin.srcA = nid
            nodes.append(fin)
            n.a_reads.append(fin_id)
            leaves.append(fin_id)
    for nid in leaves:
        nodes[nid].is_store = True

    return nodes, leaves


# ---------------------------------------------------------------------------
# Pass 2 -- register allocation (linear scan, smallest-first free list)
# ---------------------------------------------------------------------------
def allocate_registers(nodes):
    """Assign each node a register from H.POOL, freeing a producer's
    register the moment its LAST consumer event (in creation/program order)
    has been issued. Program order == node creation order (every operand
    references a strictly earlier node id, so creation order is already a
    valid topological/emission order)."""
    last_event = {}   # node id -> index of its last consumption (in nodes[] order), or -1 if a leaf/store
    for n in nodes:
        if n.is_store:
            last_event[n.id] = n.id  # consumed by "itself" (its own store, emitted right after it)
        elif n.b_read is not None:
            last_event[n.id] = n.b_read
        elif n.a_reads:
            last_event[n.id] = n.a_reads[-1]
        else:
            # produced but never consumed and never marked a store (should
            # not happen after finalization) -- treat as immediately dead.
            last_event[n.id] = n.id

    free = list(H.POOL)          # ascending; smallest-first pop
    reg_of = {}                  # PERMANENT node id -> register assignment (never deleted --
                                  # emit_program needs this even after the register is reused)
    holder_of = {}                # register -> node id CURRENTLY occupying it (freed separately)
    # process nodes in id order; consumer events for node j fire exactly
    # when node j itself is emitted (since srcA/srcB always reference
    # strictly earlier ids, and a "self" consumption for a leaf/store fires
    # right after the producer's own creation, i.e. effectively immediately)
    for n in nodes:
        # free any producer registers whose last event has already fired
        # strictly BEFORE this node (n.id > last_event[p] means p's final
        # read already happened)
        for reg, p_id in list(holder_of.items()):
            if last_event[p_id] < n.id:
                del holder_of[reg]
                free.append(reg)
        free.sort()
        if not free:
            raise RuntimeError("register allocator ran out of free registers at node %d "
                                "(live-count invariant violated -- generator bug)" % n.id)
        reg = free.pop(0)
        reg_of[n.id] = reg
        holder_of[reg] = n.id
    return reg_of


# ---------------------------------------------------------------------------
# Pass 3 -- instruction emission + host oracle
# ---------------------------------------------------------------------------
def emit_program(nodes, leaves, reg_of, base_slot_out, base_slot_in, out_idx_off_start=0):
    """Emit isa_helpers-built instruction bytes for the whole DAG in node-id
    order, plus a device_store immediately after every node with
    `is_store=True`. Returns (instr_list, oracle_words, out_words_used,
    max_load_idx_off_used). `oracle_words` maps output-buffer word index ->
    expected float32 value, computed with the SAME arithmetic the hardware
    is documented to use (isadb's own minifloat round-trip for immediates,
    plain IEEE-754 binary32 for add/mul)."""
    instrs = []
    val = {}            # node id -> host-computed float value
    oracle_words = {}
    next_out_idx = out_idx_off_start

    for n in nodes:
        reg = reg_of[n.id]
        if n.type == "const":
            kv = H.imm_value(n.k)
            instrs.append(H.falu2i(reg, "fadd", H.R_UNWRITTEN, n.k, last_use_srcA=True, mods=0))
            val[n.id] = H.f32(0.0 + kv)
        elif n.type == "load":
            instrs.append(H.device_load(H.R_IDX, n.idx_off, n.elem_code, base_slot_in,
                                          extmode=(reg << 1) & 0xFF))
            byte_off = H.load_byte_offset(0, n.idx_off, n.elem_code)
            word_idx = byte_off // 4
            val[n.id] = MEM_WORDS[word_idx % len(MEM_WORDS)]
        elif n.type in ("add_imm", "mul_imm"):
            srcA = n.srcA
            last = nodes[srcA].a_reads[-1] == n.id
            producer_is_load = (nodes[srcA].type == "load")
            mods = 0xC0 if producer_is_load else 0
            instrs.append(H.falu2i(reg, n.op, reg_of[srcA], n.k, last_use_srcA=last, mods=mods))
            kv = H.imm_value(n.k)
            a = val[srcA]
            val[n.id] = H.f32(a + kv) if n.op == "fadd" else H.f32(a * kv)
        elif n.type in ("add_reg", "mul_reg"):
            srcA, srcB = n.srcA, n.srcB
            last = nodes[srcA].a_reads[-1] == n.id
            instrs.append(H.falu2(reg, n.op, reg_of[srcA], reg_of[srcB], last_use_srcA=last))
            a, b = val[srcA], val[srcB]
            val[n.id] = H.f32(a + b) if n.op == "fadd" else H.f32(a * b)
        else:
            raise AssertionError("unknown node type %r" % n.type)

        if n.is_store:
            instrs.append(H.device_store(H.R_IDX, next_out_idx, base_slot_out, data_reg=reg))
            byte_off = H.store_byte_offset(0, next_out_idx)
            oracle_words[byte_off // 4] = val[n.id]
            next_out_idx += 1

    return instrs, oracle_words, next_out_idx


# input buffer contents -- fixed, deterministic, reused by EVERY generated
# case (idx_off selects WHICH word; the buffer itself never varies). 2048
# float32 words = 8192 bytes, matching idx_off's full 11-bit range at the
# native 4-byte element scale (EXP-0082's own MEM-03 dense-sweep envelope).
def _make_mem_words(n=2048):
    vals = []
    # deterministic "interesting" pattern: a mix of small integers,
    # fractional values, negatives, and a few IEEE-754 special/boundary
    # bit patterns at fixed low indices for the boundary sub-family.
    # Deliberately NOT including extreme-magnitude values (e.g. 1e30): a
    # random DAG can chain several multiplications, and an early overflow
    # to +-Inf combined with a LATER multiply-by-0.0 (0.0 is in
    # IMM_BOUNDARY_POOL) produces NaN, which breaks the harness's exact
    # IEEE-754 `==` oracle comparison for a reason having nothing to do
    # with hardware correctness. Keeping every input word's magnitude
    # small enough that no plausible generated chain (immediates bounded
    # to roughly +-100, depth <=~15) can overflow float32 avoids this
    # confound entirely; float32 special-value/overflow semantics are
    # already characterized elsewhere (EXP-0102 PACK-09/10).
    specials = [0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 3.14159, -2.71828]
    for i in range(n):
        if i < len(specials):
            vals.append(specials[i])
        else:
            # a smooth, exactly-float32-representable, easy-to-eyeball sequence
            vals.append(H.f32((i - n / 2) * 0.015625))  # 1/64, exact in binary32
    return vals


MEM_WORDS = _make_mem_words()


def _make_imem_words(n=64):
    """IADD_ANCHOR's dedicated int32 buffer (buffer(2), SLOT_IMEM). Kept
    small, non-negative, and far from 2**31 so that (raw_int + addend)
    (addend in 0..127, see families.py) never wraps into a negative
    two's-complement bit pattern -- a negative int32's bit pattern
    reinterpreted as float32 is frequently a NaN encoding (sign+exponent
    all-ones), which would break the harness's exact IEEE-754 `==` oracle
    comparison for a reason having nothing to do with hardware
    correctness (see generator.py's MEM_WORDS comment for the same
    concern on the float side)."""
    return [(i * 37 + 5) % 5000 for i in range(n)]


IMEM_WORDS = _make_imem_words()


def build_dag_program(seed, n_nodes, carrier_len, base_slot_out, base_slot_in):
    """Full pipeline: seed -> DAG -> registers -> bytes+oracle -> padded
    program. Returns (hexstring, oracle_words dict[int->float], meta)."""
    nodes, leaves = generate_dag(seed, n_nodes)
    reg_of = allocate_registers(nodes)
    setup = [H.mov_imm(H.R_IDX, 0)]
    body, oracle, n_stores = emit_program(nodes, leaves, reg_of, base_slot_out, base_slot_in)
    instrs = setup + body + [H.stop()]
    prog = H.build_program(instrs, carrier_len)
    H.assert_round_trip(prog)
    max_live = _max_concurrent_live(nodes)
    meta = {"n_nodes": len(nodes), "n_leaves": len(leaves), "n_stores": n_stores,
            "max_live_registers": max_live, "byte_length": len(prog)}
    return prog.hex(), oracle, meta


def _max_concurrent_live(nodes):
    """Diagnostic re-derivation of peak live-node count, independent of the
    allocator's own bookkeeping -- used by --selftest to cross-check the
    POOL_SIZE invariant a second, independent way."""
    last_event = {}
    for n in nodes:
        if n.is_store:
            last_event[n.id] = n.id
        elif n.b_read is not None:
            last_event[n.id] = n.b_read
        elif n.a_reads:
            last_event[n.id] = n.a_reads[-1]
        else:
            last_event[n.id] = n.id
    peak = 0
    alive = set()
    for n in nodes:
        alive.add(n.id)
        alive = {p for p in alive if last_event[p] >= n.id}
        peak = max(peak, len(alive))
    return peak


if __name__ == "__main__":
    # standalone self-check: no GPU, pure structural + round-trip validation
    # over a wide seed range -- this is what --selftest (verify.py) also
    # calls, kept runnable directly for interactive debugging.
    import json
    bad = 0
    for seed in range(0, 40):
        for n in (3, 8, 14, 20, 30, 45):
            hexstr, oracle, meta = build_dag_program(seed, n, 2048, base_slot_out=0, base_slot_in=1)
            if meta["max_live_registers"] > POOL_SIZE:
                print("VIOLATION seed=%d n=%d max_live=%d" % (seed, n, meta["max_live_registers"]))
                bad += 1
    print("checked %d (seed,n) pairs, %d violations" % (40 * 6, bad))
    sys.exit(1 if bad else 0)
