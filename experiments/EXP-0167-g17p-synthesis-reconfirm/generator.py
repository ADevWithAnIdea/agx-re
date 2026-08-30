#!/usr/bin/env python3
"""EXP-0158 dataflow-DAG generator (G17P).

Passes 1 (DAG structure) and 2 (linear-scan register allocation) are carried
over UNCHANGED from `experiments/EXP-0112-m4-program-generator/generator.py`
(our own code; EXP-0112 is committed, read-only evidence and is not modified),
INCLUDING its RNG seed string -- so the 100 MAIN_DAG programs have exactly the
DAG SHAPES EXP-0112 ran.  Holding the shapes constant is deliberate: it makes
field provenance and target the only variables between the two experiments.

Pass 3 -- instruction emission -- is REWRITTEN on top of `synth.py`, so that
every field value is tagged RULE / FREE / PILOT / CARRIER / COPIED and the
experiment can report how many programs contain zero COPIED fields.

Pass 3 also gains an `imm_mode`:
  "falu2i"  -- a constant costs one falu2i with a packed minifloat immediate
               (what EXP-0112 did);
  "inline"  -- a constant rides in the CONSUMING instruction's own srcB
               operand field as EXP-0138's inline 8-bit float immediate, so a
               `const` leaf needs no separate seed instruction at all and an
               `add_imm`/`mul_imm` needs no minifloat encode.  Values are
               snapped onto the inline grid so the oracle stays exact.
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth as S  # noqa: E402

DAG_CARRIER_LEN = 1536   # < carrier_dag.metal's own compiled length (asserted by baseline.py)
SLOT_OUT = 0
SLOT_MEM = 1
SLOT_IMEM = 2

POOL_SIZE = len(S.POOL)  # 14
EFFECTIVE_CAP = POOL_SIZE - 2


# ---------------------------------------------------------------------------
# Pass 1 -- DAG structure  (verbatim from EXP-0112)
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
        self.a_reads = []
        self.b_read = None
        self.is_store = False
        self.is_finalizer_of = None


def _pick_recency(rng, candidates, window=6):
    if not candidates:
        return None
    tail = candidates[-window:] if len(candidates) > window else candidates
    return rng.choice(tail)


IMM_BOUNDARY_POOL = [0.0, 1.0, -1.0, 0.5, -0.5, 2.0, 30.0, -30.0, 0.125, 100.0, -100.0, 3.5]
IDXOFF_BOUNDARY_POOL = [0, 1, 2, 2047, 2046, 1024, 512]


def generate_dag(seed, n_nodes, allow_boundary_immediates=True):
    rng = random.Random("EXP-0112-dag-%r" % (seed,))   # SAME stream as EXP-0112, deliberately:
                                                        # the DAG shapes are held constant so the
                                                        # ONLY variable is field provenance.
    nodes = []
    open_ids = []
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
        else:
            n.idx_off = rng.choice(IDXOFF_BOUNDARY_POOL) if rng.random() < 0.25 \
                else rng.randrange(0, 2048)
            n.elem_code = 3
        n.a_budget = rng.choices([1, 2], weights=[0.75, 0.25])[0]
        nodes.append(n)
        open_ids.append(nid)
        live_count += 1
        return nid

    def consume_a(producer_id, consumer_id):
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

        srcA = _pick_recency(rng, sorted(ac))
        fc2 = [x for x in fc if x != srcA]
        if not fc2:
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
# Pass 2 -- register allocation (verbatim from EXP-0112)
# ---------------------------------------------------------------------------
def allocate_registers(nodes):
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

    free = list(S.POOL)
    reg_of = {}
    holder_of = {}
    for n in nodes:
        for reg, p_id in list(holder_of.items()):
            if last_event[p_id] < n.id:
                del holder_of[reg]
                free.append(reg)
        free.sort()
        if not free:
            raise RuntimeError("register allocator ran out of free registers at node %d" % n.id)
        reg = free.pop(0)
        reg_of[n.id] = reg
        holder_of[reg] = n.id
    return reg_of


# ---------------------------------------------------------------------------
# Pass 3 -- SYNTHESISED emission + host oracle
# ---------------------------------------------------------------------------
def snap_to_inline_grid(k):
    """Nearest EXACTLY representable inline-immediate value to k, taking the
    sign convention frozen from the pilot into account.  Returns
    (code, srcB_neg, exact_value)."""
    import frozen_pilot as FP
    best = None
    negs = (0, 1) if FP.INLINE_NEG_WORKS else (0,)
    for code in range(64):
        for neg in negs:
            v = S.inline_srcB_value(code, neg)
            d = abs(v - k)
            if best is None or d < best[0]:
                best = (d, code, neg, v)
    return best[1], best[2], best[3]


def emit_program(led, nodes, leaves, reg_of, base_slot_out, base_slot_in,
                 salt, offnatural, out_idx_off_start=0, imm_mode="falu2i"):
    instrs = []
    val = {}
    oracle_words = {}
    next_out_idx = out_idx_off_start

    for n in nodes:
        reg = reg_of[n.id]
        cs = "%s#%d" % (salt, n.id)
        if n.type == "const":
            if imm_mode == "inline":
                code, neg, kv = snap_to_inline_grid(n.k)
                instrs.append(S.falu2_imm(led, reg, "fadd", S.R_UNWRITTEN, None,
                                          last_use_srcA=True, salt=cs,
                                          offnatural=offnatural, srcB_neg=neg,
                                          imm_code_override=code,
                                          load_sourced=False))
            else:
                kv = S.imm_value(n.k)
                instrs.append(S.falu2i(led, reg, "fadd", S.R_UNWRITTEN, n.k,
                                       last_use_srcA=True, load_sourced=False, salt=cs))
            val[n.id] = S.f32(0.0 + kv)
        elif n.type == "load":
            instrs.append(S.device_load(led, S.R_IDX, n.idx_off, n.elem_code, base_slot_in,
                                        R=reg, salt=cs, offnatural=offnatural))
            byte_off = S.load_byte_offset(0, n.idx_off, n.elem_code)
            word_idx = byte_off // 4
            val[n.id] = MEM_WORDS[word_idx % len(MEM_WORDS)]
        elif n.type in ("add_imm", "mul_imm"):
            srcA = n.srcA
            last = nodes[srcA].a_reads[-1] == n.id
            producer_is_load = (nodes[srcA].type == "load")
            if imm_mode == "inline" and not producer_is_load:
                # NOT used when srcA is load-sourced: EXP-0101 H1's bridge rule
                # is only established for the falu2i `mods` form, and this
                # experiment does not assume it transfers to the inline-imm
                # class.  Named, not silently assumed.
                code, neg, kv = snap_to_inline_grid(n.k)
                instrs.append(S.falu2_imm(led, reg, n.op, reg_of[srcA], None,
                                          last_use_srcA=last, salt=cs,
                                          offnatural=offnatural, srcB_neg=neg,
                                          imm_code_override=code,
                                          load_sourced=False))
            else:
                instrs.append(S.falu2i(led, reg, n.op, reg_of[srcA], n.k, last_use_srcA=last,
                                       load_sourced=producer_is_load, salt=cs))
                kv = S.imm_value(n.k)
            a = val[srcA]
            val[n.id] = S.f32(a + kv) if n.op == "fadd" else S.f32(a * kv)
        elif n.type in ("add_reg", "mul_reg"):
            srcA, srcB = n.srcA, n.srcB
            last = nodes[srcA].a_reads[-1] == n.id
            # EXP-0158 pilot P2: if EITHER operand came from a device_load,
            # mod_hi = 0xC is the only value of sixteen that delivers it.  The
            # srcB half is not separately established, so the conservative
            # reading (either operand load-sourced -> 0xC) is used and stated.
            ls = (nodes[srcA].type == "load") or (nodes[srcB].type == "load")
            instrs.append(S.falu2(led, reg, n.op, reg_of[srcA], reg_of[srcB],
                                  last_use_srcA=last, salt=cs, offnatural=offnatural,
                                  load_sourced=ls))
            a, b = val[srcA], val[srcB]
            val[n.id] = S.f32(a + b) if n.op == "fadd" else S.f32(a * b)
        else:
            raise AssertionError("unknown node type %r" % n.type)

        if n.is_store:
            instrs.append(S.device_store(led, S.R_IDX, next_out_idx, base_slot_out,
                                         data_reg=reg, salt=cs, offnatural=offnatural))
            byte_off = S.store_byte_offset(0, next_out_idx)
            oracle_words[byte_off // 4] = val[n.id]
            next_out_idx += 1

    return instrs, oracle_words, next_out_idx


def _make_mem_words(n=2048):
    vals = []
    specials = [0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 3.14159, -2.71828]
    for i in range(n):
        if i < len(specials):
            vals.append(specials[i])
        else:
            vals.append(S.f32((i - n / 2) * 0.015625))
    return vals


MEM_WORDS = _make_mem_words()


def _make_imem_words(n=64):
    return [(i * 37 + 5) % 5000 for i in range(n)]


IMEM_WORDS = _make_imem_words()


def build_dag_program(seed, n_nodes, carrier_len, base_slot_out, base_slot_in,
                      offnatural=True, imm_mode="falu2i"):
    """seed -> DAG -> registers -> SYNTHESISED bytes + oracle + provenance."""
    led = S.Ledger()
    nodes, leaves = generate_dag(seed, n_nodes)
    reg_of = allocate_registers(nodes)
    salt = "dag%d" % seed
    setup = [S.mov_imm(led, S.R_IDX, 0, salt=salt)]
    setup += S.sentinel_instrs(led, base_slot_out, salt)
    body, oracle, n_stores = emit_program(led, nodes, leaves, reg_of, base_slot_out,
                                          base_slot_in, salt, offnatural,
                                          imm_mode=imm_mode)
    instrs = setup + body + [S.stop(led)]
    prog = S.build_program(led, instrs, carrier_len)
    S.assert_round_trip(prog)
    meta = {"n_nodes": len(nodes), "n_leaves": len(leaves), "n_stores": n_stores,
            "max_live_registers": _max_concurrent_live(nodes),
            "byte_length": len(prog),
            "prov_counts": led.counts(), "copied_fields": led.copied_fields(),
            "carrier_fields": led.carrier_fields(), "pilot_fields": led.pilot_fields(),
            "imm_mode": imm_mode,
            "n_offnatural": len(led.offnatural())}
    return prog.hex(), oracle, meta


def _max_concurrent_live(nodes):
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
