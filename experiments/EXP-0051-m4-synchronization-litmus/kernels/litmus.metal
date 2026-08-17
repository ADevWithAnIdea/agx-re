#include <metal_stdlib>
using namespace metal;

inline uint asymmetric(uint epoch, uint index) {
    uint x = 0x9e3779b9u * (index + 1u) + 0x85ebca6bu * (epoch + 3u);
    return (x ^ (x >> 13) ^ 0xa5c31f27u) + (index << 16);
}

inline void checked(device atomic_uint *out, uint key, uint want, uint got) {
    atomic_fetch_add_explicit(&out[1], 1u, memory_order_relaxed);
    if (got != want) {
        atomic_fetch_add_explicit(&out[0], 1u, memory_order_relaxed);
        atomic_fetch_min_explicit(&out[2], key, memory_order_relaxed);
        atomic_exchange_explicit(&out[3], got, memory_order_relaxed);
    }
}

kernel void tg_mem_threadgroup(device atomic_uint *out [[buffer(0)]],
                               device uint *unused [[buffer(1)]],
                               uint lid [[thread_position_in_threadgroup]],
                               uint tg [[threadgroup_position_in_grid]]) {
    (void)unused;
    threadgroup uint s[64];
    s[lid] = asymmetric(tg, lid);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint peer = 63u - lid;
    checked(out, tg * 64u + lid, asymmetric(tg, peer), s[peer]);
}

kernel void tg_mem_none(device atomic_uint *out [[buffer(0)]],
                        device uint *unused [[buffer(1)]],
                        uint lid [[thread_position_in_threadgroup]],
                        uint tg [[threadgroup_position_in_grid]]) {
    (void)unused;
    threadgroup uint s[64];
    s[lid] = asymmetric(tg, lid);
    threadgroup_barrier(mem_flags::mem_none);
    uint peer = 63u - lid;
    checked(out, tg * 64u + lid, asymmetric(tg, peer), s[peer]);
}

kernel void simd_mem_threadgroup(device atomic_uint *out [[buffer(0)]],
                                 device uint *unused [[buffer(1)]],
                                 uint lid [[thread_position_in_threadgroup]],
                                 uint tg [[threadgroup_position_in_grid]]) {
    (void)unused;
    threadgroup uint s[64];
    s[lid] = asymmetric(tg, lid);
    simdgroup_barrier(mem_flags::mem_threadgroup);
    uint peer = lid ^ 31u;
    checked(out, tg * 64u + lid, asymmetric(tg, peer), s[peer]);
}

kernel void tg_device_mem_device(device atomic_uint *out [[buffer(0)]],
                                 device uint *scratch [[buffer(1)]],
                                 uint lid [[thread_position_in_threadgroup]],
                                 uint tg [[threadgroup_position_in_grid]]) {
    uint base=tg*64u;scratch[base+lid]=asymmetric(tg,lid);
    threadgroup_barrier(mem_flags::mem_device);
    uint peer=63u-lid;
    checked(out,base+lid,asymmetric(tg,peer),scratch[base+peer]);
}

kernel void tg_device_mem_wrong_class(device atomic_uint *out [[buffer(0)]],
                                      device uint *scratch [[buffer(1)]],
                                      uint lid [[thread_position_in_threadgroup]],
                                      uint tg [[threadgroup_position_in_grid]]) {
    uint base=tg*64u;scratch[base+lid]=asymmetric(tg,lid);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint peer=63u-lid;
    checked(out,base+lid,asymmetric(tg,peer),scratch[base+peer]);
}

kernel void tg_device_mem_both(device atomic_uint *out [[buffer(0)]],
                               device uint *scratch [[buffer(1)]],
                               uint lid [[thread_position_in_threadgroup]],
                               uint tg [[threadgroup_position_in_grid]]) {
    uint base=tg*64u;scratch[base+lid]=asymmetric(tg,lid);
    threadgroup_barrier(mem_flags::mem_device | mem_flags::mem_threadgroup);
    uint peer=63u-lid;
    checked(out,base+lid,asymmetric(tg,peer),scratch[base+peer]);
}

struct Mailbox {
    uint payload[4];
    atomic_uint ready;
    atomic_uint ack;
};

inline void payload_write(device Mailbox *m, uint iteration, uint salt) {
    m->payload[0]=asymmetric(iteration,salt+0u);
    m->payload[1]=asymmetric(iteration,salt+7u);
    m->payload[2]=asymmetric(iteration,salt+19u);
    m->payload[3]=asymmetric(iteration,salt+41u);
}

inline uint payload_mismatch(device Mailbox *m, uint iteration, uint salt) {
    uint n=0;
    n += m->payload[0] != asymmetric(iteration,salt+0u);
    n += m->payload[1] != asymmetric(iteration,salt+7u);
    n += m->payload[2] != asymmetric(iteration,salt+19u);
    n += m->payload[3] != asymmetric(iteration,salt+41u);
    return n;
}

inline bool wait_value(device atomic_uint *p, uint want) {
    for (uint spin=0;spin<1000000u;++spin)
        if (atomic_load_explicit(p,memory_order_relaxed)==want) return true;
    return false;
}

inline void record_timeout(device atomic_uint *out, uint which) {
    atomic_fetch_add_explicit(&out[which],1u,memory_order_relaxed);
}

kernel void msg_tg_relaxed(device Mailbox *boxes [[buffer(0)]],
                           device atomic_uint *out [[buffer(1)]],
                           constant uint &iterations [[buffer(2)]],
                           uint lid [[thread_position_in_threadgroup]],
                           uint tg [[threadgroup_position_in_grid]]) {
    device Mailbox *m=&boxes[tg];uint salt=tg*53u;
    if(lid==0){for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ack,i-1u)){record_timeout(out,1);return;}payload_write(m,i,salt);atomic_store_explicit(&m->ready,i,memory_order_relaxed);if(!wait_value(&m->ack,i)){record_timeout(out,1);return;}}}
    else if(lid==32){uint bad=0,done=0;for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ready,i)){record_timeout(out,2);break;}bad+=payload_mismatch(m,i,salt);atomic_store_explicit(&m->ack,i,memory_order_relaxed);++done;}atomic_fetch_add_explicit(&out[0],bad,memory_order_relaxed);atomic_fetch_add_explicit(&out[3],done,memory_order_relaxed);}
}

kernel void msg_tg_fence_device(device Mailbox *boxes [[buffer(0)]],
                                device atomic_uint *out [[buffer(1)]],
                                constant uint &iterations [[buffer(2)]],
                                uint lid [[thread_position_in_threadgroup]],
                                uint tg [[threadgroup_position_in_grid]]) {
    device Mailbox *m=&boxes[tg];uint salt=tg*53u;
    if(lid==0){for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ack,i-1u)){record_timeout(out,1);return;}payload_write(m,i,salt);atomic_thread_fence(mem_flags::mem_device,memory_order_seq_cst,thread_scope_device);atomic_store_explicit(&m->ready,i,memory_order_relaxed);if(!wait_value(&m->ack,i)){record_timeout(out,1);return;}}}
    else if(lid==32){uint bad=0,done=0;for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ready,i)){record_timeout(out,2);break;}atomic_thread_fence(mem_flags::mem_device,memory_order_seq_cst,thread_scope_device);bad+=payload_mismatch(m,i,salt);atomic_store_explicit(&m->ack,i,memory_order_relaxed);++done;}atomic_fetch_add_explicit(&out[0],bad,memory_order_relaxed);atomic_fetch_add_explicit(&out[3],done,memory_order_relaxed);}
}

kernel void msg_tg_fence_tgscope(device Mailbox *boxes [[buffer(0)]],
                                 device atomic_uint *out [[buffer(1)]],
                                 constant uint &iterations [[buffer(2)]],
                                 uint lid [[thread_position_in_threadgroup]],
                                 uint tg [[threadgroup_position_in_grid]]) {
    device Mailbox *m=&boxes[tg];uint salt=tg*53u;
    if(lid==0){for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ack,i-1u)){record_timeout(out,1);return;}payload_write(m,i,salt);atomic_thread_fence(mem_flags::mem_device,memory_order_seq_cst,thread_scope_threadgroup);atomic_store_explicit(&m->ready,i,memory_order_relaxed);if(!wait_value(&m->ack,i)){record_timeout(out,1);return;}}}
    else if(lid==32){uint bad=0,done=0;for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ready,i)){record_timeout(out,2);break;}atomic_thread_fence(mem_flags::mem_device,memory_order_seq_cst,thread_scope_threadgroup);bad+=payload_mismatch(m,i,salt);atomic_store_explicit(&m->ack,i,memory_order_relaxed);++done;}atomic_fetch_add_explicit(&out[0],bad,memory_order_relaxed);atomic_fetch_add_explicit(&out[3],done,memory_order_relaxed);}
}

kernel void msg_cross_relaxed(device Mailbox *boxes [[buffer(0)]],
                              device atomic_uint *out [[buffer(1)]],
                              constant uint &iterations [[buffer(2)]],
                              uint lid [[thread_position_in_threadgroup]],
                              uint tg [[threadgroup_position_in_grid]]) {
    if(lid!=0||tg>1)return;device Mailbox*m=&boxes[0];uint salt=0x611u;
    if(tg==0){for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ack,i-1u)){record_timeout(out,1);return;}payload_write(m,i,salt);atomic_store_explicit(&m->ready,i,memory_order_relaxed);if(!wait_value(&m->ack,i)){record_timeout(out,1);return;}}}
    else {uint bad=0,done=0;for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ready,i)){record_timeout(out,2);break;}bad+=payload_mismatch(m,i,salt);atomic_store_explicit(&m->ack,i,memory_order_relaxed);++done;}atomic_fetch_add_explicit(&out[0],bad,memory_order_relaxed);atomic_fetch_add_explicit(&out[3],done,memory_order_relaxed);}
}

kernel void msg_cross_fence_device(device Mailbox *boxes [[buffer(0)]],
                                   device atomic_uint *out [[buffer(1)]],
                                   constant uint &iterations [[buffer(2)]],
                                   uint lid [[thread_position_in_threadgroup]],
                                   uint tg [[threadgroup_position_in_grid]]) {
    if(lid!=0||tg>1)return;device Mailbox*m=&boxes[0];uint salt=0x611u;
    if(tg==0){for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ack,i-1u)){record_timeout(out,1);return;}payload_write(m,i,salt);atomic_thread_fence(mem_flags::mem_device,memory_order_seq_cst,thread_scope_device);atomic_store_explicit(&m->ready,i,memory_order_relaxed);if(!wait_value(&m->ack,i)){record_timeout(out,1);return;}}}
    else {uint bad=0,done=0;for(uint i=1;i<=iterations;++i){if(!wait_value(&m->ready,i)){record_timeout(out,2);break;}atomic_thread_fence(mem_flags::mem_device,memory_order_seq_cst,thread_scope_device);bad+=payload_mismatch(m,i,salt);atomic_store_explicit(&m->ack,i,memory_order_relaxed);++done;}atomic_fetch_add_explicit(&out[0],bad,memory_order_relaxed);atomic_fetch_add_explicit(&out[3],done,memory_order_relaxed);}
}

kernel void ordered_producer(device uint *data [[buffer(0)]],
                             constant uint &epoch [[buffer(1)]],
                             uint gid [[thread_position_in_grid]]) {
    data[gid]=asymmetric(epoch,gid);
}

kernel void ordered_consumer(device const uint *data [[buffer(0)]],
                             device uint *copy [[buffer(1)]],
                             uint gid [[thread_position_in_grid]]) {
    copy[gid]=data[gid];
}
