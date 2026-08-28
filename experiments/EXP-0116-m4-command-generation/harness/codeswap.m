// codeswap.m -- EXP-0116 task 3: construct a CDM record ourselves (bytes
// copied from two REAL captured dispatch records of two DIFFERENT compiled
// kernels, hybridized) and see whether the hardware executes it when reached
// only via our own hand-built link splice (never through MTLComputePipeline
// creation / the archive path for the hybrid record itself).
//
// CLEAN ROOM: public Metal API + OWN-SHADER + DATA-TRACE + HW-PROBE only.
// kernel_x/kernel_y are authored MSL below, compiled at runtime
// (newLibraryWithSource:). The unmodified, read-only tools/iotrace/iotrace.c
// interposer is used exactly as in linksplice.m/EXP-0043/49/110 to snapshot
// this process's own registered BOs. No Apple binary is inspected.
//
// Design (see PROGRESS.md/RESULTS.md for the reasoning that led here):
//   - kernel_x writes a fixed constant (0x11111111) to every output element;
//     kernel_y writes a DIFFERENT fixed constant (0x22222222). Two distinct
//     MSL sources -> two genuinely distinct compiled programs (not just two
//     different runtime uniform values against the same code, which EXP-0110
//     already showed is a separate, per-dispatch-varying field).
//   - One command buffer, one compute encoder: first the proven 732/732/36
//     three-segment CDM chain (seg0/seg1/seg2, all running kernel_a, exactly
//     as validated in linksplice.m's same_cb mechanism -- kept byte-identical
//     so residency/placement behavior is the already-HW-VALIDATED shape),
//     THEN two more dispatches appended to seg2 (which has slack: only 36 of
//     up to 732 records used): kernel_x into buf_X, kernel_y into buf_Y.
//     These become seg2's own record[36] and record[37].
//   - endEncoding (not committed). Dump. Locate seg2's record[36] (kernel_x)
//     and record[37] (kernel_y) verbatim, 0x2c bytes each -- this IS a real,
//     Metal-authored, DATA-TRACE-observed pair of CDM records for two
//     genuinely different compiled programs.
//   - Construct hybrid_bytes = record[36] (kernel_x's record) with ONLY its
//     +0x08 "code/uniform-window pointer" 4 bytes REPLACED by record[37]'s
//     (kernel_y's) own +0x08 value. Every other field (config word, the two
//     unclassified words, grid, threadgroup) stays kernel_x's own bytes,
//     verbatim.
//   - Write hybrid_bytes + an 8-byte terminator into a FRESH MTLBuffer we
//     allocate and own outright (ordinary CPU write via .contents -- no
//     live-pointer poke needed to CONSTRUCT it, only to splice a link INTO
//     it, exactly as linksplice.m's proven mechanism does).
//   - Splice seg0's own tail link (the SAME field linksplice.m already
//     HW-VALIDATED as followable) to point at this hybrid buffer instead of
//     seg1, using the identical split-address transform.
//   - Commit under a watchdog. Read back buf_X and buf_Y (both
//     sentinel-stomped beforehand). Neither kernel_x's nor kernel_y's OWN
//     natural dispatch (seg2 records 36/37) ever runs in this configuration
//     (the redirect skips seg1 AND seg2 entirely), so ANY change to buf_X or
//     buf_Y is attributable only to the hybrid record's own execution.
//
// Interpretation key:
//   buf_X changed, buf_Y sentinel  -> hybrid record ran AS kernel_x (the
//     +0x08 swap had no effect; code/context is NOT selected by that field,
//     or our copy did not take).
//   buf_Y changed, buf_X sentinel  -> hybrid record ran AS kernel_y (the
//     +0x08 field alone selects both the executed code AND its resource
//     context) -- proves code selection is a distinct, copyable/movable
//     field, though the VALUE itself was copied from a capture, not
//     independently computed (see RESULTS.md's GENERATED-vs-COPIED table).
//   neither changed / fault / hang -> negative result, reported as such.
//
// Build:
//   xcrun clang -fobjc-arc -o codeswap codeswap.m -framework Metal -framework Foundation

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

#define CDM_RECORD_LEN 0x2c
#define CDM_TERMINATOR 0x40000000u
#define CDM_LINK_TAG 0x20u

static uint64_t decode_link_target(uint32_t hi, uint32_t lo) {
    return (((uint64_t)(hi & 0x00ffffffu)) << 32) | (uint64_t)lo;
}
static void encode_link(uint8_t tag, uint64_t target, uint32_t *hi, uint32_t *lo) {
    *hi = ((uint32_t)tag << 24) | (uint32_t)((target >> 32) & 0x00ffffffu);
    *lo = (uint32_t)(target & 0xffffffffu);
}

typedef struct { char path[1024]; uint64_t gpu_va, cpu, size, read_len; uint8_t *data; } BODump;

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
    struct dirent *e; int n = 0;
    while ((e = readdir(d)) != NULL && n < max) {
        if (strncmp(e->d_name, "bo_", 3) != 0) continue;
        size_t l = strlen(e->d_name);
        if (l < 4 || strcmp(e->d_name + l - 4, ".hex") != 0) continue;
        char path[1200]; snprintf(path, sizeof(path), "%s/%s", dir, e->d_name);
        if (load_one_bodump(path, &out[n])) n++;
    }
    closedir(d);
    return n;
}

typedef struct {
    int found; int64_t first_off, last_off; int count;
    int has_tail, tail_is_link, tail_is_term;
    uint32_t tail_hi, tail_lo; uint64_t tail_off;
} CDMScan;

static CDMScan scan_cdm(const uint8_t *data, size_t len) {
    CDMScan r; memset(&r, 0, sizeof(r));
    uint8_t sig[24]; uint32_t grid[3] = {64,1,1}, tg[3] = {32,1,1};
    memcpy(sig+0, grid, 12); memcpy(sig+12, tg, 12);
    if (len < 24) return r;
    int64_t hits[4096]; int nh = 0;
    for (size_t i = 0; i + 24 <= len && nh < 4096; i++)
        if (memcmp(data+i, sig, 24) == 0) { int64_t rec = (int64_t)i - 0x10; if (rec >= 0) hits[nh++] = rec; }
    if (nh == 0) return r;
    int64_t best_first=hits[0], best_last=hits[0]; int best_count=1;
    int64_t cur_first=hits[0], cur_last=hits[0]; int cur_count=1;
    for (int i = 1; i < nh; i++) {
        if (hits[i]-cur_last == CDM_RECORD_LEN) { cur_last=hits[i]; cur_count++; }
        else if (hits[i] != cur_last) {
            if (cur_count > best_count) { best_first=cur_first; best_last=cur_last; best_count=cur_count; }
            cur_first=hits[i]; cur_last=hits[i]; cur_count=1;
        }
    }
    if (cur_count > best_count) { best_first=cur_first; best_last=cur_last; best_count=cur_count; }
    r.found=1; r.first_off=best_first; r.last_off=best_last; r.count=best_count;
    uint64_t tail_off = (uint64_t)(best_last + CDM_RECORD_LEN);
    if (tail_off + 4 <= len) {
        r.has_tail = 1;
        uint32_t w0; memcpy(&w0, data+tail_off, 4);
        if (w0 == CDM_TERMINATOR) r.tail_is_term = 1;
        else if (tail_off + 8 <= len) {
            uint32_t w1; memcpy(&w1, data+tail_off+4, 4);
            r.tail_hi=w0; r.tail_lo=w1; r.tail_off=tail_off;
            if ((w0>>24) == CDM_LINK_TAG) r.tail_is_link = 1;
        }
    }
    return r;
}

static void die(const char *m) { fprintf(stderr, "FATAL %s\n", m); exit(2); }

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *dump_dir = "work/dumps";
        const char *out_json = NULL;
        long watchdog_sec = 15;
        long dump_wait_us = 1200000;
        long seg0_n = 732, seg1_n = 732, seg2_n = 36; // proven shape

        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--dump-dir") && i+1 < argc) dump_dir = argv[++i];
            else if (!strcmp(argv[i], "--out") && i+1 < argc) out_json = argv[++i];
            else if (!strcmp(argv[i], "--watchdog-sec") && i+1 < argc) watchdog_sec = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump-wait-us") && i+1 < argc) dump_wait_us = strtol(argv[++i], NULL, 0);
            else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
        }
        if (!out_json) die("--out required");
        FILE *jf = fopen(out_json, "w");
        if (!jf) die("cannot open --out");

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device");
        fprintf(stderr, "DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        NSString *srcA =
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "kernel void kernel_a(device uint *out [[buffer(0)]],\n"
             "                     constant uint &tag [[buffer(1)]],\n"
             "                     uint i [[thread_position_in_grid]]) {\n"
             "  out[i] = tag + i;\n"
             "}\n";
        NSString *srcX =
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "kernel void kernel_x(device uint *out [[buffer(0)]],\n"
             "                     uint i [[thread_position_in_grid]]) {\n"
             "  out[i] = 0x11111111u;\n"
             "}\n";
        NSString *srcY =
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "kernel void kernel_y(device uint *out [[buffer(0)]],\n"
             "                     uint i [[thread_position_in_grid]]) {\n"
             "  out[i] = 0x22222222u;\n"
             "}\n";
        id<MTLLibrary> libA = [dev newLibraryWithSource:srcA options:nil error:&err];
        id<MTLLibrary> libX = [dev newLibraryWithSource:srcX options:nil error:&err];
        id<MTLLibrary> libY = [dev newLibraryWithSource:srcY options:nil error:&err];
        if (!libA || !libX || !libY) die("compile failed");
        id<MTLComputePipelineState> cpA = [dev newComputePipelineStateWithFunction:[libA newFunctionWithName:@"kernel_a"] error:&err];
        id<MTLComputePipelineState> cpX = [dev newComputePipelineStateWithFunction:[libX newFunctionWithName:@"kernel_x"] error:&err];
        id<MTLComputePipelineState> cpY = [dev newComputePipelineStateWithFunction:[libY newFunctionWithName:@"kernel_y"] error:&err];
        if (!cpA || !cpX || !cpY) die("pso failed");

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLBuffer> buf_A = [dev newBufferWithLength:64*sizeof(uint32_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> buf_MID = [dev newBufferWithLength:64*sizeof(uint32_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> buf_X = [dev newBufferWithLength:64*sizeof(uint32_t) options:MTLResourceStorageModeShared];
        id<MTLBuffer> buf_Y = [dev newBufferWithLength:64*sizeof(uint32_t) options:MTLResourceStorageModeShared];
        for (int i = 0; i < 64; i++) {
            ((uint32_t*)buf_A.contents)[i] = 0x5eed0000u + i;
            ((uint32_t*)buf_MID.contents)[i] = 0x5eed1000u + i;
            ((uint32_t*)buf_X.contents)[i] = 0x5eed2000u + i;
            ((uint32_t*)buf_Y.contents)[i] = 0x5eed3000u + i;
        }
        // hybrid target buffer: fully ours, plain CPU-writable, allocated
        // now so it has a stable identity for the whole encode.
        id<MTLBuffer> hybrid_buf = [dev newBufferWithLength:0x8000 options:MTLResourceStorageModeShared];
        memset(hybrid_buf.contents, 0, 0x8000);

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        long total = seg0_n + seg1_n + seg2_n;
        for (long j = 0; j < total; j++) {
            id<MTLBuffer> dst; uint32_t tag;
            if (j < seg0_n) { dst = buf_A; tag = 0xa0000000u | ((uint32_t)j & 0xffffu); }
            else if (j < seg0_n + seg1_n) { dst = buf_MID; tag = 0xb0000000u | ((uint32_t)(j - seg0_n) & 0xffffu); }
            else { dst = buf_A; tag = 0xc0000000u | ((uint32_t)(j - seg0_n - seg1_n) & 0xffffu); }
            [enc setComputePipelineState:cpA];
            [enc setBuffer:dst offset:0 atIndex:0];
            [enc setBytes:&tag length:sizeof(tag) atIndex:1];
            [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        }
        // seg2 record[36]: kernel_x -> buf_X
        [enc setComputePipelineState:cpX];
        [enc setBuffer:buf_X offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        // seg2 record[37]: kernel_y -> buf_Y
        [enc setComputePipelineState:cpY];
        [enc setBuffer:buf_Y offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        [enc endEncoding];
        // NOT committed yet.

        kill(getpid(), SIGUSR1);
        usleep((useconds_t)dump_wait_us);

        static BODump dumps[MAX_DUMPS];
        int n = load_all_bodumps(dump_dir, dumps, MAX_DUMPS);
        fprintf(stderr, "predump: loaded %d BO files from %s\n", n, dump_dir);

        // find chain head (seg0): a link head that is nobody's target
        BODump *heads[8]; CDMScan hscans[8]; int nh = 0;
        for (int i = 0; i < n && nh < 8; i++) {
            CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len);
            if (!s.found || !s.tail_is_link) continue;
            uint64_t t = decode_link_target(s.tail_hi, s.tail_lo);
            int exists = 0; for (int k = 0; k < n; k++) if (dumps[k].gpu_va == t) { exists = 1; break; }
            if (!exists) continue;
            heads[nh] = &dumps[i]; hscans[nh] = s; nh++;
        }
        BODump *seg0d = NULL; CDMScan seg0s = {0};
        for (int i = 0; i < nh; i++) {
            int is_target = 0;
            for (int k = 0; k < nh; k++) { if (k==i) continue; if (decode_link_target(hscans[k].tail_hi, hscans[k].tail_lo) == heads[i]->gpu_va) { is_target = 1; break; } }
            if (!is_target) { seg0d = heads[i]; seg0s = hscans[i]; break; }
        }
        int found_seg0 = (seg0d != NULL);
        fprintf(stderr, "seg0 found=%d va=0x%llx count=%d\n", found_seg0, found_seg0 ? (unsigned long long)seg0d->gpu_va : 0, seg0s.count);

        BODump *seg1d = NULL; CDMScan seg1s = {0};
        if (found_seg0 && seg0s.tail_is_link) {
            uint64_t t = decode_link_target(seg0s.tail_hi, seg0s.tail_lo);
            for (int i = 0; i < n; i++) if (dumps[i].gpu_va == t) { CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len); if (s.found) { seg1d = &dumps[i]; seg1s = s; } break; }
        }
        int found_seg1 = (seg1d != NULL);

        BODump *seg2d = NULL; CDMScan seg2s = {0};
        if (found_seg1 && seg1s.tail_is_link) {
            uint64_t t = decode_link_target(seg1s.tail_hi, seg1s.tail_lo);
            for (int i = 0; i < n; i++) if (dumps[i].gpu_va == t) { CDMScan s = scan_cdm(dumps[i].data, dumps[i].read_len); if (s.found) { seg2d = &dumps[i]; seg2s = s; } break; }
        }
        int found_seg2 = (seg2d != NULL);
        fprintf(stderr, "seg1 found=%d seg2 found=%d seg2_count=%d (expect >=38: 36 kernel_a + kernel_x + kernel_y)\n", found_seg1, found_seg2, seg2s.count);

        int setup_ok = found_seg0 && found_seg1 && found_seg2 &&
            seg0s.count == seg0_n && seg1s.count == seg1_n && seg2s.count >= seg2_n + 2 &&
            seg0s.tail_is_link && seg1s.tail_is_link;

        uint8_t record_x[CDM_RECORD_LEN], record_y[CDM_RECORD_LEN], hybrid[CDM_RECORD_LEN];
        memset(record_x, 0, sizeof(record_x)); memset(record_y, 0, sizeof(record_y)); memset(hybrid, 0, sizeof(hybrid));
        int extracted_ok = 0;
        uint32_t x_ptr = 0, y_ptr = 0;
        if (setup_ok) {
            // seg2's records are at first_off + k*0x2c for k=0..count-1, in
            // encode order: 0..seg2_n-1 = kernel_a (tag 0xc...), seg2_n =
            // kernel_x, seg2_n+1 = kernel_y.
            int64_t off_x = seg2s.first_off + seg2_n * CDM_RECORD_LEN;
            int64_t off_y = seg2s.first_off + (seg2_n + 1) * CDM_RECORD_LEN;
            if (off_x + CDM_RECORD_LEN <= (int64_t)seg2d->read_len && off_y + CDM_RECORD_LEN <= (int64_t)seg2d->read_len) {
                memcpy(record_x, seg2d->data + off_x, CDM_RECORD_LEN);
                memcpy(record_y, seg2d->data + off_y, CDM_RECORD_LEN);
                memcpy(&x_ptr, record_x + 0x08, 4);
                memcpy(&y_ptr, record_y + 0x08, 4);
                extracted_ok = 1;
            }
        }
        fprintf(stderr, "extracted_ok=%d x_ptr=0x%08x y_ptr=0x%08x record_x_config=0x%08x record_y_config=0x%08x record_x==record_y(except+08..+0c)=%d\n",
                extracted_ok, x_ptr, y_ptr,
                extracted_ok ? *(uint32_t*)record_x : 0, extracted_ok ? *(uint32_t*)record_y : 0,
                extracted_ok ? (memcmp(record_x, record_y, 0x08) == 0 && memcmp(record_x+0x0c, record_y+0x0c, CDM_RECORD_LEN-0x0c) == 0) : -1);

        int wrote = 0;
        uint64_t hybrid_va = hybrid_buf.gpuAddress;
        if (extracted_ok) {
            memcpy(hybrid, record_x, CDM_RECORD_LEN);
            memcpy(hybrid + 0x08, &y_ptr, 4); // ONLY the code/uniform pointer swapped
            uint8_t *h = (uint8_t*)hybrid_buf.contents;
            memcpy(h, hybrid, CDM_RECORD_LEN);
            uint32_t term[2] = { CDM_TERMINATOR, 0 };
            memcpy(h + CDM_RECORD_LEN, term, 8);
            wrote = 1;

            uint32_t new_hi, new_lo;
            encode_link(CDM_LINK_TAG, hybrid_va, &new_hi, &new_lo);
            uint8_t *seg0cpu = (uint8_t*)(uintptr_t)seg0d->cpu;
            uint32_t linkbuf[2] = { new_hi, new_lo };
            memcpy(seg0cpu + seg0s.tail_off, linkbuf, 8);
            fprintf(stderr, "SPLICE hybrid_va=0x%llx new_link=%08x:%08x\n", (unsigned long long)hybrid_va, new_hi, new_lo);
        } else {
            fprintf(stderr, "SPLICE SKIPPED (setup_ok=%d extracted_ok=%d)\n", setup_ok, extracted_ok);
        }

        dispatch_semaphore_t sem = dispatch_semaphore_create(0);
        __block MTLCommandBufferStatus fs = MTLCommandBufferStatusNotEnqueued;
        __block NSString *fe = nil;
        [cb addCompletedHandler:^(id<MTLCommandBuffer> b) { fs = b.status; fe = b.error ? [b.error localizedDescription] : nil; dispatch_semaphore_signal(sem); }];
        [cb commit];
        long timed_out = dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, watchdog_sec * 1000000000LL));
        int hang = (timed_out != 0);
        fprintf(stderr, "COMMIT_RESULT hang=%d status=%ld error=%s\n", hang, (long)fs, fe ? [fe UTF8String] : "NONE");

        uint32_t rb_A = ((uint32_t*)buf_A.contents)[0];
        uint32_t rb_MID = ((uint32_t*)buf_MID.contents)[0];
        uint32_t rb_X = ((uint32_t*)buf_X.contents)[0];
        uint32_t rb_Y = ((uint32_t*)buf_Y.contents)[0];

        fprintf(jf, "{\n");
        fprintf(jf, "  \"setup_ok\": %s, \"extracted_ok\": %s, \"wrote\": %s,\n", setup_ok?"true":"false", extracted_ok?"true":"false", wrote?"true":"false");
        fprintf(jf, "  \"seg0_count\": %d, \"seg1_count\": %d, \"seg2_count\": %d,\n", seg0s.count, seg1s.count, seg2s.count);
        fprintf(jf, "  \"x_ptr\": \"0x%08x\", \"y_ptr\": \"0x%08x\",\n", x_ptr, y_ptr);
        fprintf(jf, "  \"record_x_hex\": \"");
        for (int i = 0; i < CDM_RECORD_LEN; i++) fprintf(jf, "%02x", record_x[i]);
        fprintf(jf, "\",\n  \"record_y_hex\": \"");
        for (int i = 0; i < CDM_RECORD_LEN; i++) fprintf(jf, "%02x", record_y[i]);
        fprintf(jf, "\",\n  \"hybrid_hex\": \"");
        for (int i = 0; i < CDM_RECORD_LEN; i++) fprintf(jf, "%02x", hybrid[i]);
        fprintf(jf, "\",\n");
        fprintf(jf, "  \"hang\": %s, \"final_status\": %ld, \"final_error\": %s,\n", hang?"true":"false", (long)fs, fe ? [[NSString stringWithFormat:@"\"%@\"", fe] UTF8String] : "null");
        fprintf(jf, "  \"readback_A\": \"0x%08x\", \"readback_MID\": \"0x%08x\", \"readback_X\": \"0x%08x\", \"readback_Y\": \"0x%08x\",\n", rb_A, rb_MID, rb_X, rb_Y);
        fprintf(jf, "  \"sentinel_X\": \"0x5eed2000\", \"sentinel_Y\": \"0x5eed3000\",\n");
        fprintf(jf, "  \"expect_kernel_x_value\": \"0x11111111\", \"expect_kernel_y_value\": \"0x22222222\",\n");
        fprintf(jf, "  \"hybrid_va\": \"0x%llx\", \"seg0_va\": \"0x%llx\"\n", (unsigned long long)hybrid_va, found_seg0 ? (unsigned long long)seg0d->gpu_va : 0);
        fprintf(jf, "}\n");
        fclose(jf);
        printf("VERDICT wrote=%d hang=%d status=%ld rb_X=0x%08x rb_Y=0x%08x\n", wrote, hang, (long)fs, rb_X, rb_Y);
        return 0;
    }
}
