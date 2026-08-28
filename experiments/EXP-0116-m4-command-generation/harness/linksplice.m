// linksplice.m -- EXP-0116 hand-constructed CDM segment-link generation and
// hardware-consumer proof.
//
// CLEAN ROOM: public Metal API + OWN-SHADER + DATA-TRACE + HW-PROBE only.
// The only shader executed is the trivial kernel authored below
// (out[i] = tag + i). This program asks the unmodified, read-only
// tools/iotrace/iotrace.c interposer (loaded via DYLD_INSERT_LIBRARIES, never
// edited, never disassembled) to snapshot this process's OWN registered GPU
// buffer objects. It never reads, inspects, or invokes any tool on an Apple
// binary. It never disassembles, decompiles, or introspects Metal/AGX/IOGPU
// code.
//
// New technique vs prior EXP-0043/0049/0110 (which only READ command-stream
// bytes): this program also WRITES a hand-computed 8-byte link value directly
// into a live CDM command segment's CPU-mapped memory, strictly BEFORE that
// command buffer is committed to the GPU (i.e. before any hardware consumes
// it). This is a DATA mutation of our own process's userspace memory that
// Metal itself must already treat as CPU-writable (it is the same mechanism
// Metal's own userspace code uses to build the command stream in the first
// place) -- not an inspection of any Apple binary's code. It is the
// "hardware probing" method CLAUDE.md sanctions explicitly: write a known
// pattern into hardware-visible state, observe what the hardware does with
// it. Calibration (calib0.m, deleted, see PROGRESS.md) proved the CPU
// pointer iotrace's BODUMP reports for a BO is IDENTICAL to
// MTLBuffer.contents for that same BO -- i.e. it is an ordinary, directly
// dereferenceable pointer in this process's own address space.
//
// Two mechanisms are implemented, because calibration (PROGRESS.md) showed
// they answer DIFFERENT questions and neither alone is safe/sufficient:
//
//   --mechanism same_cb (the PRIMARY mechanism for the whole case matrix):
//     ONE command buffer, ONE compute encoder, authored to roll over into
//     the EXACT three-segment shape EXP-0110 already validated naturally
//     occurs at count=1500 (732/732/36 records): seg0 writes buf_A, seg1
//     writes buf_MID (a SEPARATE buffer, so we can tell whether seg1 ever
//     ran), seg2 writes buf_A again. Because source and every candidate
//     target live inside the SAME not-yet-committed command buffer, GPU
//     residency for the target is never in question (the whole buffer set
//     cbM's own encoder referenced will be made resident once cbM commits,
//     regardless of which physical segment the hardware visits), and
//     nothing is ever completed-and-reused mid-experiment (everything is
//     encoded once, spliced once, committed once).
//
//   --mechanism cross_cb (used for exactly one documented negative,
//     "cross_cb_uncommitted"): a SEPARATE, independent command buffer cbR is
//     encoded (giving a second, structurally valid 2-segment chain R0/R1)
//     but deliberately never committed, and A0's link is redirected to R1.
//     This FAULTED on real hardware in calibration
//     (kIOGPUCommandBufferCallbackErrorPageFault) -- see PROGRESS.md and
//     RESULTS.md. A second calibration variant that commits+waits cbR
//     BEFORE encoding cbM was also tried and discarded: waiting for cbR's
//     completion lets its 0x8000-byte segment storage be reused (not
//     zeroed) by cbM's own later allocations, which corrupts the very
//     memory the test depends on and is not a clean probe of anything --
//     recorded as a process/method finding in PROGRESS.md, not promoted as
//     a hardware fact.
//
// Mechanism-neutral procedure (same_cb):
//   1. Build one compute encoder issuing exactly 1500 dispatches with three
//      distinct tag families and two destination buffers (buf_A, buf_MID),
//      call endEncoding -- but do NOT commit yet. Metal must already have
//      written seg0/seg1/seg2's complete byte content, including every
//      natural tail link, into CPU-mapped memory by this point (encoding
//      produces those bytes; commit only hands off references), so
//      everything from here is strictly pre-hardware-consumption.
//   2. Trigger an iotrace BODUMP (SIGUSR1), which snapshots every BO this
//      process has registered via the sel-9 resource-map call.
//   3. This program parses those dump files itself (no external tool),
//      finds the unique CHAIN HEAD (a segment that is nobody else's link
//      target) and follows natural links to identify seg0/seg1/seg2,
//      confirms the natural chain matches the authored shape exactly (the
//      pre-mutation baseline, per CODEX 4), and computes the requested
//      case's new 8-byte link value for seg0's tail.
//   4. Write those 8 bytes directly at seg0's CPU pointer + the discovered
//      tail offset (a plain C memory write in this process's own address
//      space).
//   5. commit cbM under a watchdog (a completion handler + a timed
//      dispatch_semaphore_wait, not a bare waitUntilCompleted, so a genuine
//      hardware hang cannot block this process forever) and record the
//      outcome (completed / command-buffer error / process-level timeout).
//   6. Read back buf_A and buf_MID (both sentinel-stomped beforehand via
//      ordinary CPU writes to our own MTLBuffer.contents) and report exactly
//      which segment(s) executed after seg0.
//
// Build:
//   xcrun clang -fobjc-arc -o linksplice linksplice.m \
//       -framework Metal -framework Foundation

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <dirent.h>
#include <dispatch/dispatch.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

// ---------------------------------------------------------------------------
// CDM record shape (0x2c bytes), established DATA-TRACE fact (EXP-0011/0043/
// 0049/0110), reproduced structurally here for OUR OWN authored dispatch
// shape: grid=(64,1,1), threadgroup=(32,1,1). See those experiments'
// analysis/scan.py for the original documentation of this layout; this is
// our own independent re-implementation in C for this experiment.
//   +0x00 u32 config word
//   +0x04 u32 unclassified
//   +0x08 u32 code/uniform-window pointer (varies per dispatch)
//   +0x0c u32 unclassified
//   +0x10 u32 grid.x  +0x14 grid.y  +0x18 grid.z
//   +0x1c u32 tg.x    +0x20 tg.y    +0x24 tg.z
//   +0x28 u32 unclassified
// Segment terminator (4 bytes right after the last record): 0x40000000.
// Segment link (8 bytes in the same position): [hi32, lo32] naming the next
// command BO's GPU VA as ((hi32 & 0x00ffffff) << 32) | lo32, tag = hi32>>24
// (CDM tag observed 0x20, EXP-0043/49/110).
#define CDM_RECORD_LEN 0x2c
#define CDM_TERMINATOR 0x40000000u
#define CDM_LINK_TAG 0x20u
#define SEG_CAPACITY 732

static uint64_t decode_link_target(uint32_t hi, uint32_t lo) {
    return (((uint64_t)(hi & 0x00ffffffu)) << 32) | (uint64_t)lo;
}
static void encode_link(uint8_t tag, uint64_t target, uint32_t *hi, uint32_t *lo) {
    *hi = ((uint32_t)tag << 24) | (uint32_t)((target >> 32) & 0x00ffffffu);
    *lo = (uint32_t)(target & 0xffffffffu);
}

// ---------------------------------------------------------------------------
// Minimal, self-contained BODUMP (.hex) reader. Format written by
// tools/iotrace/iotrace.c dump_all_bos() (unmodified, read-only):
//   filename: bo_<reason>_h<handle>_va<hex>_cpu<hex>_sz<hex>.hex
//   line 0:   "# BODUMP reason=%s handle=%u gpu_va=0x%llx cpu=0x%llx
//              size=0x%llx read=0x%llx\n"
//   lines 1..:"%08llx: xx xx xx xx ...\n" (16 bytes/line, space every 4)
typedef struct {
    char path[1024];
    uint64_t gpu_va, cpu, size, read_len;
    uint8_t *data; // length read_len, malloc'd
} BODump;

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int load_one_bodump(const char *path, BODump *out) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[8192];
    if (!fgets(line, sizeof(line), f)) { fclose(f); return 0; }
    unsigned long long gpu_va = 0, cpu = 0, size = 0, read_len = 0;
    char *p;
    if ((p = strstr(line, "gpu_va=0x"))) gpu_va = strtoull(p + 9, NULL, 16);
    if ((p = strstr(line, "cpu=0x"))) cpu = strtoull(p + 6, NULL, 16);
    if ((p = strstr(line, "size=0x"))) size = strtoull(p + 7, NULL, 16);
    if ((p = strstr(line, "read=0x"))) read_len = strtoull(p + 7, NULL, 16);
    if (read_len == 0) { fclose(f); return 0; }
    uint8_t *buf = calloc(1, read_len);
    while (fgets(line, sizeof(line), f)) {
        char *colon = strchr(line, ':');
        if (!colon) continue;
        unsigned long long off = strtoull(line, NULL, 16);
        const char *q = colon + 1;
        uint64_t idx = off;
        while (*q) {
            while (*q == ' ') q++;
            int h1 = hexval(*q); if (h1 < 0) break; q++;
            int h2 = hexval(*q); if (h2 < 0) break; q++;
            if (idx < read_len) buf[idx] = (uint8_t)((h1 << 4) | h2);
            idx++;
        }
    }
    fclose(f);
    strncpy(out->path, path, sizeof(out->path) - 1);
    out->gpu_va = gpu_va; out->cpu = cpu; out->size = size; out->read_len = read_len;
    out->data = buf;
    return 1;
}

#define MAX_DUMPS 256
static int load_all_bodumps(const char *dir, BODump *out, int max) {
    DIR *d = opendir(dir);
    if (!d) return 0;
    struct dirent *e;
    int n = 0;
    while ((e = readdir(d)) != NULL && n < max) {
        if (strncmp(e->d_name, "bo_", 3) != 0) continue;
        size_t l = strlen(e->d_name);
        if (l < 4 || strcmp(e->d_name + l - 4, ".hex") != 0) continue;
        char path[1200];
        snprintf(path, sizeof(path), "%s/%s", dir, e->d_name);
        if (load_one_bodump(path, &out[n])) n++;
    }
    closedir(d);
    return n;
}

// ---------------------------------------------------------------------------
// Our own authored CDM structural scan: locate the longest contiguous run of
// 0x2c-byte records whose grid/tg dwords (at record+0x10) equal our exact
// authored dispatch shape (64,1,1 / 32,1,1). This is OUR OWN literal byte
// pattern -- it never interprets any opaque/unclassified Apple-authored data.
typedef struct {
    int found;
    int64_t first_off, last_off;
    int count;
    int has_tail;
    int tail_is_link;
    int tail_is_term;
    uint32_t tail_hi, tail_lo;
    uint64_t tail_off;
} CDMScan;

static CDMScan scan_cdm(const uint8_t *data, size_t len) {
    CDMScan r; memset(&r, 0, sizeof(r));
    uint8_t sig[24];
    uint32_t grid[3] = {64, 1, 1}, tg[3] = {32, 1, 1};
    memcpy(sig + 0, grid, 12);
    memcpy(sig + 12, tg, 12);
    if (len < 24) return r;
    int64_t hits[4096]; int nh = 0;
    for (size_t i = 0; i + 24 <= len && nh < 4096; i++) {
        if (memcmp(data + i, sig, 24) == 0) {
            int64_t rec = (int64_t)i - 0x10;
            if (rec >= 0) hits[nh++] = rec;
        }
    }
    if (nh == 0) return r;
    int64_t best_first = hits[0], best_last = hits[0]; int best_count = 1;
    int64_t cur_first = hits[0], cur_last = hits[0]; int cur_count = 1;
    for (int i = 1; i < nh; i++) {
        if (hits[i] - cur_last == CDM_RECORD_LEN) {
            cur_last = hits[i]; cur_count++;
        } else if (hits[i] != cur_last) {
            if (cur_count > best_count) { best_first = cur_first; best_last = cur_last; best_count = cur_count; }
            cur_first = hits[i]; cur_last = hits[i]; cur_count = 1;
        }
    }
    if (cur_count > best_count) { best_first = cur_first; best_last = cur_last; best_count = cur_count; }
    r.found = 1; r.first_off = best_first; r.last_off = best_last; r.count = best_count;
    uint64_t tail_off = (uint64_t)(best_last + CDM_RECORD_LEN);
    if (tail_off + 4 <= len) {
        r.has_tail = 1;
        uint32_t w0; memcpy(&w0, data + tail_off, 4);
        if (w0 == CDM_TERMINATOR) {
            r.tail_is_term = 1;
        } else if (tail_off + 8 <= len) {
            uint32_t w1; memcpy(&w1, data + tail_off + 4, 4);
            r.tail_hi = w0; r.tail_lo = w1; r.tail_off = tail_off;
            if ((w0 >> 24) == CDM_LINK_TAG) r.tail_is_link = 1;
        }
    }
    return r;
}

// ---------------------------------------------------------------------------
static void die(const char *msg) { fprintf(stderr, "FATAL %s\n", msg); exit(2); }

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *case_name = "baseline_check";
        const char *dump_dir = "work/dumps";
        const char *mechanism = "same_cb";
        long watchdog_sec = 15;
        long dump_wait_us = 1200000;
        const char *out_json = NULL;
        // same_cb authored shape (defaults reproduce EXP-0110's validated
        // 732/732/36 3-segment CDM chain exactly).
        long seg0_n = 732, seg1_n = 732, seg2_n = 36;
        // cross_cb authored shape
        long cross_main_count = 733, cross_redirect_count = 737;

        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--case") && i + 1 < argc) case_name = argv[++i];
            else if (!strcmp(argv[i], "--dump-dir") && i + 1 < argc) dump_dir = argv[++i];
            else if (!strcmp(argv[i], "--mechanism") && i + 1 < argc) mechanism = argv[++i];
            else if (!strcmp(argv[i], "--watchdog-sec") && i + 1 < argc) watchdog_sec = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump-wait-us") && i + 1 < argc) dump_wait_us = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--out") && i + 1 < argc) out_json = argv[++i];
            else if (!strcmp(argv[i], "--seg0-n") && i + 1 < argc) seg0_n = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--seg1-n") && i + 1 < argc) seg1_n = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--seg2-n") && i + 1 < argc) seg2_n = strtol(argv[++i], NULL, 0);
            else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
        }
        if (!out_json) die("--out required");
        if (strcmp(mechanism, "same_cb") != 0 && strcmp(mechanism, "cross_cb") != 0) die("--mechanism must be same_cb or cross_cb");

        FILE *jf = fopen(out_json, "w");
        if (!jf) die("cannot open --out for writing");

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device");
        fprintf(stderr, "DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        NSString *src =
            @"#include <metal_stdlib>\n"
             "using namespace metal;\n"
             "kernel void kernel_a(device uint *out [[buffer(0)]],\n"
             "                     constant uint &tag [[buffer(1)]],\n"
             "                     uint i [[thread_position_in_grid]]) {\n"
             "  out[i] = tag + i;\n"
             "}\n";
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) die("compile failed");
        id<MTLFunction> fn = [lib newFunctionWithName:@"kernel_a"];
        id<MTLComputePipelineState> cp = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!cp) die("pso failed");

        id<MTLCommandQueue> q = [dev newCommandQueue];

        int wrote = 0, hang = 0, case_valid_setup = 0, natural_chain_ok = 0;
        MTLCommandBufferStatus final_status = MTLCommandBufferStatusNotEnqueued;
        NSString *final_error = nil;
        uint32_t pre_hi = 0, pre_lo = 0, new_hi = 0, new_lo = 0;
        uint8_t new_tag = CDM_LINK_TAG; uint64_t new_target = 0;
        uint32_t readback_A = 0, readback_MID = 0;
        uint32_t expect_seg0_last = 0xa0000000u | ((uint32_t)(seg0_n - 1) & 0xffffu);
        uint32_t expect_seg1_last = 0xb0000000u | ((uint32_t)(seg1_n - 1) & 0xffffu);
        uint32_t expect_seg2_last = 0xc0000000u | ((uint32_t)(seg2_n - 1) & 0xffffu);
        uint64_t seg0_va = 0, seg1_va = 0, seg2_va = 0;
        int seg0_count = 0, seg1_count = 0, seg2_count = 0;
        int found_seg0 = 0, found_seg1 = 0, found_seg2 = 0;
        int fault_only_after_seg0 = 0; // cross_cb-specific note

        if (!strcmp(mechanism, "same_cb")) {
            // ---- Author buf_A (segments 0 and 2) and buf_MID (segment 1) ----
            id<MTLBuffer> buf_A = [dev newBufferWithLength:64 * sizeof(uint32_t) options:MTLResourceStorageModeShared];
            id<MTLBuffer> buf_MID = [dev newBufferWithLength:64 * sizeof(uint32_t) options:MTLResourceStorageModeShared];
            for (int i = 0; i < 64; i++) { ((uint32_t*)buf_A.contents)[i] = 0x5eed0000u + i; ((uint32_t*)buf_MID.contents)[i] = 0x5eed1000u + i; }

            id<MTLCommandBuffer> cbM = [q commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cbM computeCommandEncoder];
            long total = seg0_n + seg1_n + seg2_n;
            for (long j = 0; j < total; j++) {
                id<MTLBuffer> dst; uint32_t tag;
                if (j < seg0_n) { dst = buf_A; tag = 0xa0000000u | ((uint32_t)j & 0xffffu); }
                else if (j < seg0_n + seg1_n) { dst = buf_MID; tag = 0xb0000000u | ((uint32_t)(j - seg0_n) & 0xffffu); }
                else { dst = buf_A; tag = 0xc0000000u | ((uint32_t)(j - seg0_n - seg1_n) & 0xffffu); }
                [enc setComputePipelineState:cp];
                [enc setBuffer:dst offset:0 atIndex:0];
                [enc setBytes:&tag length:sizeof(tag) atIndex:1];
                [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
            }
            [enc endEncoding];
            // NOT committed yet.

            kill(getpid(), SIGUSR1);
            usleep((useconds_t)dump_wait_us);

            static BODump dumps[MAX_DUMPS];
            int n = load_all_bodumps(dump_dir, dumps, MAX_DUMPS);
            fprintf(stderr, "predump: loaded %d BO files from %s\n", n, dump_dir);

            // Find the unique chain head: a segment with tail_is_link, whose
            // target is among the dumped BOs, and which is NOT itself the
            // target of any other such segment.
            BODump *heads[8]; CDMScan hscans[8]; int nh = 0;
            for (int i = 0; i < n && nh < 8; i++) {
                CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len);
                if (!s.found || !s.tail_is_link) continue;
                uint64_t target = decode_link_target(s.tail_hi, s.tail_lo);
                int target_exists = 0;
                for (int k = 0; k < n; k++) if (dumps[k].gpu_va == target) { target_exists = 1; break; }
                if (!target_exists) continue;
                heads[nh] = &dumps[i]; hscans[nh] = s; nh++;
            }
            BODump *seg0d = NULL; CDMScan seg0s = {0};
            for (int i = 0; i < nh; i++) {
                int is_target_of_other = 0;
                for (int k = 0; k < nh; k++) {
                    if (k == i) continue;
                    uint64_t t = decode_link_target(hscans[k].tail_hi, hscans[k].tail_lo);
                    if (t == heads[i]->gpu_va) { is_target_of_other = 1; break; }
                }
                if (!is_target_of_other) { seg0d = heads[i]; seg0s = hscans[i]; break; }
            }
            found_seg0 = (seg0d != NULL);
            if (found_seg0) { seg0_va = seg0d->gpu_va; seg0_count = seg0s.count; }
            fprintf(stderr, "seg0 found=%d va=0x%llx count=%d tail_link=%d\n", found_seg0,
                    (unsigned long long)seg0_va, seg0_count, seg0s.tail_is_link);

            BODump *seg1d = NULL; CDMScan seg1s = {0};
            if (found_seg0 && seg0s.tail_is_link) {
                uint64_t t1 = decode_link_target(seg0s.tail_hi, seg0s.tail_lo);
                for (int i = 0; i < n; i++) if (dumps[i].gpu_va == t1) {
                    CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len);
                    if (s.found) { seg1d = &dumps[i]; seg1s = s; }
                    break;
                }
            }
            found_seg1 = (seg1d != NULL);
            if (found_seg1) { seg1_va = seg1d->gpu_va; seg1_count = seg1s.count; }
            fprintf(stderr, "seg1 found=%d va=0x%llx count=%d tail_link=%d tail_term=%d\n", found_seg1,
                    (unsigned long long)seg1_va, seg1_count, seg1s.tail_is_link, seg1s.tail_is_term);

            BODump *seg2d = NULL; CDMScan seg2s = {0};
            if (found_seg1 && seg1s.tail_is_link) {
                uint64_t t2 = decode_link_target(seg1s.tail_hi, seg1s.tail_lo);
                for (int i = 0; i < n; i++) if (dumps[i].gpu_va == t2) {
                    CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len);
                    if (s.found) { seg2d = &dumps[i]; seg2s = s; }
                    break;
                }
            }
            found_seg2 = (seg2d != NULL);
            if (found_seg2) { seg2_va = seg2d->gpu_va; seg2_count = seg2s.count; }
            fprintf(stderr, "seg2 found=%d va=0x%llx count=%d tail_term=%d has_tail=%d tail_off=0x%llx first_off=%lld last_off=%lld read_len=0x%llx\n",
                    found_seg2, (unsigned long long)seg2_va, seg2_count, seg2s.tail_is_term, seg2s.has_tail,
                    (unsigned long long)seg2s.tail_off, (long long)seg2s.first_off, (long long)seg2s.last_off,
                    found_seg2 ? (unsigned long long)seg2d->read_len : 0);
            if (found_seg2) {
                uint32_t direct_w0; memcpy(&direct_w0, seg2d->data + seg2s.tail_off, 4);
                fprintf(stderr, "seg2 DIRECT re-read at tail_off: 0x%08x (path=%s)\n", direct_w0, seg2d->path);
            }

            // NOTE (calibration finding, see PROGRESS.md): seg2's OWN tail
            // word (the true stream terminator, 0x40000000) is reliably
            // observed as 0x00000000 in a PRE-COMMIT dump, becoming
            // 0x40000000 only in a POST-COMMIT dump of the identical BO --
            // i.e. Metal defers finalizing the very last segment's
            // terminator sentinel past endEncoding (to commit/schedule
            // time), unlike an intermediate segment's forward LINK (seg0's
            // and seg1's own tails), which this experiment confirmed
            // reliable pre-commit across 5+ repeated calibration runs. This
            // is a genuine, reportable finding, not a bug worked around:
            // it means a hand-built terminator cannot be assumed present at
            // the tail of an in-flight command buffer's own last segment.
            // It does not affect this splice (which only ever reads/writes
            // seg0's and seg1's LINK words, both confirmed reliable), so
            // natural_chain_ok intentionally does not require seg2's tail.
            natural_chain_ok = found_seg0 && found_seg1 && found_seg2 &&
                seg0_count == seg0_n && seg1_count == seg1_n && seg2_count == seg2_n &&
                seg0s.tail_is_link && seg1s.tail_is_link;
            fprintf(stderr, "NATURAL_CHAIN_OK=%d (baseline: seg0->seg1->seg2, authored record counts match exactly)\n", natural_chain_ok);

            pre_hi = seg0s.tail_hi; pre_lo = seg0s.tail_lo;

            case_valid_setup = natural_chain_ok;
            int do_write = 1;
            if (!strcmp(case_name, "baseline_check")) {
                do_write = 0;
            } else if (!strcmp(case_name, "skip_seg1")) {
                new_target = seg2_va;
            } else if (!strcmp(case_name, "mid_segment_offset")) {
                new_target = seg2_va + 2 * CDM_RECORD_LEN; case_valid_setup &= (seg2_count > 2);
            } else if (!strcmp(case_name, "at_capacity_boundary")) {
                new_target = seg1_va + (uint64_t)SEG_CAPACITY * CDM_RECORD_LEN;
            } else if (!strcmp(case_name, "one_past_capacity")) {
                new_target = seg1_va + (uint64_t)(SEG_CAPACITY + 1) * CDM_RECORD_LEN;
            } else if (!strcmp(case_name, "misaligned_word4")) {
                new_target = seg2_va + 4;
            } else if (!strcmp(case_name, "misaligned_byte1")) {
                new_target = seg2_va + 1;
            } else if (!strcmp(case_name, "misaligned_word2")) {
                new_target = seg2_va + 2;
            } else if (!strcmp(case_name, "misaligned_word8")) {
                new_target = seg2_va + 8;
            } else if (!strcmp(case_name, "out_of_range_beyond_bo")) {
                new_target = seg1_va + (seg1d ? seg1d->size : 0x8000) + 0x1000;
            } else if (!strcmp(case_name, "out_of_range_null")) {
                new_target = 0;
            } else if (!strcmp(case_name, "out_of_range_far")) {
                new_target = (seg2_va + 0x0000400000000000ull) & 0x00ffffffffffffffull;
            } else if (!strcmp(case_name, "out_of_range_bit40")) {
                new_target = (seg2_va + 0x0000010000000000ull) & 0x00ffffffffffffffull;
            } else if (!strcmp(case_name, "out_of_range_bit44")) {
                new_target = (seg2_va + 0x0000100000000000ull) & 0x00ffffffffffffffull;
            } else if (!strcmp(case_name, "encoding_max")) {
                new_tag = 0xff; new_target = 0x00ffffffffffffffull;
            } else if (!strcmp(case_name, "tag_zero")) {
                new_tag = 0x00; new_target = seg2_va;
            } else if (!strcmp(case_name, "tag_vdm")) {
                new_tag = 0x80; new_target = seg2_va;
            } else {
                die("unknown --case");
            }

            if (do_write && case_valid_setup) {
                encode_link(new_tag, new_target, &new_hi, &new_lo);
                uint8_t *cpu = (uint8_t *)(uintptr_t)seg0d->cpu;
                uint8_t *dst = cpu + seg0s.tail_off;
                uint32_t buf2[2] = { new_hi, new_lo };
                memcpy(dst, buf2, 8);
                wrote = 1;
                fprintf(stderr, "SPLICE case=%s pre=%08x:%08x new=%08x:%08x tail_off=0x%llx seg0_cpu=%p\n",
                        case_name, pre_hi, pre_lo, new_hi, new_lo, (unsigned long long)seg0s.tail_off, (void*)cpu);
            } else {
                fprintf(stderr, "SPLICE SKIPPED case=%s do_write=%d case_valid_setup=%d\n", case_name, do_write, case_valid_setup);
            }

            dispatch_semaphore_t sem = dispatch_semaphore_create(0);
            __block MTLCommandBufferStatus fs = MTLCommandBufferStatusNotEnqueued;
            __block NSString *fe = nil;
            [cbM addCompletedHandler:^(id<MTLCommandBuffer> b) {
                fs = b.status; fe = b.error ? [b.error localizedDescription] : nil;
                dispatch_semaphore_signal(sem);
            }];
            [cbM commit];
            long timed_out = dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, watchdog_sec * 1000000000LL));
            hang = (timed_out != 0);
            final_status = fs; final_error = fe;
            fprintf(stderr, "COMMIT_RESULT hang=%d status=%ld error=%s\n", hang, (long)final_status,
                    final_error ? [final_error UTF8String] : "NONE");

            readback_A = ((uint32_t*)buf_A.contents)[0];
            readback_MID = ((uint32_t*)buf_MID.contents)[0];
            if (!hang) { kill(getpid(), SIGUSR1); usleep((useconds_t)dump_wait_us); }
        } else {
            // ---- cross_cb: documented negative only (kIOGPUCommandBufferCallbackErrorPageFault) ----
            id<MTLBuffer> out_A = [dev newBufferWithLength:64 * sizeof(uint32_t) options:MTLResourceStorageModeShared];
            id<MTLBuffer> out_R = [dev newBufferWithLength:64 * sizeof(uint32_t) options:MTLResourceStorageModeShared];
            for (int i = 0; i < 64; i++) { ((uint32_t*)out_A.contents)[i] = 0x5eed0000u + i; ((uint32_t*)out_R.contents)[i] = 0x5eed1000u + i; }

            id<MTLCommandBuffer> cbR = [q commandBuffer];
            id<MTLComputeCommandEncoder> encR = [cbR computeCommandEncoder];
            for (long j = 0; j < cross_redirect_count; j++) {
                [encR setComputePipelineState:cp];
                [encR setBuffer:out_R offset:0 atIndex:0];
                uint32_t tag = 0xb0000000u | ((uint32_t)j & 0xffffu);
                [encR setBytes:&tag length:sizeof(tag) atIndex:1];
                [encR dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
            }
            [encR endEncoding];
            // deliberately never committed (see PROGRESS.md)

            id<MTLCommandBuffer> cbM = [q commandBuffer];
            id<MTLComputeCommandEncoder> encM = [cbM computeCommandEncoder];
            for (long j = 0; j < cross_main_count; j++) {
                [encM setComputePipelineState:cp];
                [encM setBuffer:out_A offset:0 atIndex:0];
                uint32_t tag = 0xa0000000u | ((uint32_t)j & 0xffffu);
                [encM setBytes:&tag length:sizeof(tag) atIndex:1];
                [encM dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
            }
            [encM endEncoding];

            kill(getpid(), SIGUSR1);
            usleep((useconds_t)dump_wait_us);
            static BODump dumps[MAX_DUMPS];
            int n = load_all_bodumps(dump_dir, dumps, MAX_DUMPS);
            fprintf(stderr, "predump: loaded %d BO files from %s\n", n, dump_dir);

            BODump *heads[8]; CDMScan hscans[8]; int nh = 0;
            for (int i = 0; i < n && nh < 8; i++) {
                CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len);
                if (!s.found || !s.tail_is_link) continue;
                uint64_t target = decode_link_target(s.tail_hi, s.tail_lo);
                int target_exists = 0;
                for (int k = 0; k < n; k++) if (dumps[k].gpu_va == target) { target_exists = 1; break; }
                if (!target_exists) continue;
                heads[nh] = &dumps[i]; hscans[nh] = s; nh++;
            }
            // sort heads by va ascending; lowest = R0 (encoded first), highest = A0
            for (int i = 1; i < nh; i++) {
                BODump *hb = heads[i]; CDMScan hs = hscans[i]; int j = i - 1;
                while (j >= 0 && heads[j]->gpu_va > hb->gpu_va) { heads[j+1]=heads[j]; hscans[j+1]=hscans[j]; j--; }
                heads[j+1] = hb; hscans[j+1] = hs;
            }
            BODump *a0d = NULL, *r0d = NULL; CDMScan a0s = {0}, r0s = {0};
            if (nh >= 2) { r0d = heads[0]; r0s = hscans[0]; a0d = heads[nh-1]; a0s = hscans[nh-1]; }
            else if (nh == 1) { a0d = heads[0]; a0s = hscans[0]; }
            BODump *a1d = NULL; CDMScan a1s = {0};
            if (a0d && a0s.tail_is_link) {
                uint64_t t = decode_link_target(a0s.tail_hi, a0s.tail_lo);
                for (int i = 0; i < n; i++) if (dumps[i].gpu_va == t) { CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len); if (s.found) { a1d = &dumps[i]; a1s = s; } break; }
            }
            BODump *r1d = NULL; CDMScan r1s = {0};
            if (r0d && r0s.tail_is_link) {
                uint64_t t = decode_link_target(r0s.tail_hi, r0s.tail_lo);
                for (int i = 0; i < n; i++) if (dumps[i].gpu_va == t) { CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len); if (s.found) { r1d = &dumps[i]; r1s = s; } break; }
            }
            found_seg0 = (a0d != NULL); found_seg1 = (a1d != NULL);
            int found_r0 = (r0d != NULL), found_r1 = (r1d != NULL);
            if (a0d) { seg0_va = a0d->gpu_va; seg0_count = a0s.count; }
            if (a1d) { seg1_va = a1d->gpu_va; seg1_count = a1s.count; }
            if (r1d) { seg2_va = r1d->gpu_va; seg2_count = r1s.count; } // reuse seg2_* fields to report R1
            natural_chain_ok = found_seg0 && found_seg1 && found_r0 && found_r1 &&
                a0s.count == 732 && a1s.count == 1 && r0s.count == 732 && r1s.count == 5 &&
                decode_link_target(a0s.tail_hi, a0s.tail_lo) == a1d->gpu_va;
            pre_hi = a0s.tail_hi; pre_lo = a0s.tail_lo;
            expect_seg0_last = 0xa0000000u | ((uint32_t)(cross_main_count - 1) & 0xffffu);
            expect_seg1_last = 0xa0000000u | ((uint32_t)(732 - 1) & 0xffffu); // seg0-only completion
            expect_seg2_last = 0xb0000000u | ((uint32_t)(cross_redirect_count - 1) & 0xffffu); // "R1 executed" tag

            case_valid_setup = natural_chain_ok && found_r1;
            if (!strcmp(case_name, "cross_cb_uncommitted")) {
                new_tag = CDM_LINK_TAG; new_target = found_r1 ? r1d->gpu_va : 0;
            } else {
                die("unknown --case for --mechanism cross_cb");
            }
            if (case_valid_setup) {
                encode_link(new_tag, new_target, &new_hi, &new_lo);
                uint8_t *cpu = (uint8_t *)(uintptr_t)a0d->cpu;
                uint8_t *dst = cpu + a0s.tail_off;
                uint32_t buf2[2] = { new_hi, new_lo };
                memcpy(dst, buf2, 8);
                wrote = 1;
                fprintf(stderr, "SPLICE case=%s pre=%08x:%08x new=%08x:%08x\n", case_name, pre_hi, pre_lo, new_hi, new_lo);
            } else {
                fprintf(stderr, "SPLICE SKIPPED case=%s case_valid_setup=%d\n", case_name, case_valid_setup);
            }

            dispatch_semaphore_t sem = dispatch_semaphore_create(0);
            __block MTLCommandBufferStatus fs = MTLCommandBufferStatusNotEnqueued;
            __block NSString *fe = nil;
            [cbM addCompletedHandler:^(id<MTLCommandBuffer> b) { fs = b.status; fe = b.error ? [b.error localizedDescription] : nil; dispatch_semaphore_signal(sem); }];
            [cbM commit];
            long timed_out = dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, watchdog_sec * 1000000000LL));
            hang = (timed_out != 0);
            final_status = fs; final_error = fe;
            fprintf(stderr, "COMMIT_RESULT hang=%d status=%ld error=%s\n", hang, (long)final_status, final_error ? [final_error UTF8String] : "NONE");
            readback_A = ((uint32_t*)out_A.contents)[0];
            readback_MID = ((uint32_t*)out_R.contents)[0];
            fault_only_after_seg0 = (final_status == MTLCommandBufferStatusError) && (readback_A == 0x5eed0000u);
        }

        fprintf(jf, "{\n");
        fprintf(jf, "  \"case\": \"%s\", \"mechanism\": \"%s\",\n", case_name, mechanism);
        fprintf(jf, "  \"found_seg0\": %s, \"seg0_count\": %d,\n", found_seg0 ? "true" : "false", seg0_count);
        fprintf(jf, "  \"found_seg1\": %s, \"seg1_count\": %d,\n", found_seg1 ? "true" : "false", seg1_count);
        fprintf(jf, "  \"found_seg2\": %s, \"seg2_count\": %d,\n", found_seg2 ? "true" : "false", seg2_count);
        fprintf(jf, "  \"natural_chain_ok\": %s,\n", natural_chain_ok ? "true" : "false");
        fprintf(jf, "  \"case_valid_setup\": %s,\n", case_valid_setup ? "true" : "false");
        fprintf(jf, "  \"wrote\": %s,\n", wrote ? "true" : "false");
        fprintf(jf, "  \"pre_link_hi\": \"0x%08x\", \"pre_link_lo\": \"0x%08x\",\n", pre_hi, pre_lo);
        fprintf(jf, "  \"new_link_hi\": \"0x%08x\", \"new_link_lo\": \"0x%08x\", \"new_link_tag\": \"0x%02x\",\n", new_hi, new_lo, new_tag);
        fprintf(jf, "  \"hang\": %s,\n", hang ? "true" : "false");
        fprintf(jf, "  \"final_status\": %ld,\n", (long)final_status);
        fprintf(jf, "  \"final_error\": %s,\n", final_error ? [[NSString stringWithFormat:@"\"%@\"", final_error] UTF8String] : "null");
        fprintf(jf, "  \"readback_A_word0\": \"0x%08x\",\n", readback_A);
        fprintf(jf, "  \"readback_MID_word0\": \"0x%08x\",\n", readback_MID);
        fprintf(jf, "  \"expect_seg0_last\": \"0x%08x\",\n", expect_seg0_last);
        fprintf(jf, "  \"expect_seg1_last\": \"0x%08x\",\n", expect_seg1_last);
        fprintf(jf, "  \"expect_seg2_last\": \"0x%08x\",\n", expect_seg2_last);
        fprintf(jf, "  \"sentinel_A\": \"0x5eed0000\", \"sentinel_MID\": \"0x5eed1000\",\n");
        fprintf(jf, "  \"fault_only_after_seg0\": %s,\n", fault_only_after_seg0 ? "true" : "false");
        fprintf(jf, "  \"raw_addrs\": {\n");
        fprintf(jf, "    \"seg0_va\": \"0x%llx\",\n", (unsigned long long)seg0_va);
        fprintf(jf, "    \"seg1_va\": \"0x%llx\",\n", (unsigned long long)seg1_va);
        fprintf(jf, "    \"seg2_va\": \"0x%llx\",\n", (unsigned long long)seg2_va);
        fprintf(jf, "    \"new_target\": \"0x%llx\"\n", (unsigned long long)new_target);
        fprintf(jf, "  }\n");
        fprintf(jf, "}\n");
        fclose(jf);

        printf("VERDICT case=%s mechanism=%s wrote=%d hang=%d status=%ld\n", case_name, mechanism, wrote, hang, (long)final_status);
        return 0;
    }
}
