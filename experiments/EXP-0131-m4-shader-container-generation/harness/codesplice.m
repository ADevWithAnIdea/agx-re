// codesplice.m -- EXP-0131 M4 shader container generation: live code-BO
// field mapping, splice-and-execute hardware-consumer proof, and
// extent/boundary mutation matrix.
//
// CLEAN ROOM: public Metal API + OWN-SHADER + DATA-TRACE + HW-PROBE only.
// The only shader compiled/executed here is our own authored MSL
// (render_min.metal, verbatim as in EXP-0008-fragment-extraction/kernels/
// render_min.metal, and identical inline below). This program asks the
// unmodified, read-only tools/iotrace/iotrace.c interposer (loaded via
// DYLD_INSERT_LIBRARIES, never edited, never disassembled) to snapshot this
// process's OWN registered GPU buffer objects. It never reads, inspects, or
// runs any introspection tool on an Apple binary.
//
// New technique this experiment adds vs EXP-0042 (which only READ/matched
// live code-BO bytes) and vs EXP-0116 (which wrote into CDM/compute command
// segments): this program WRITES directly into the live, POST-PIPELINE-
// CREATION graphics shader CODE record itself (the 0x10000000000-family BO
// EXP-0042 located), strictly before a FRESH command buffer that reuses the
// ALREADY-CREATED MTLRenderPipelineState is committed. Calibration
// (work/calib0.m, work/calib2.m; see PROGRESS.md) proved the BODUMP `cpu=`
// pointer for this BO is an ordinary, directly-dereferenceable pointer in
// this process's own address space (mirrors EXP-0116's finding for CDM
// segment BOs, extended here to the graphics code-container BO specifically
// -- this had NOT been previously tested).
//
// The core case (`splice_green_field`) reuses a byte-level fact ALREADY
// hardware-validated at the archive/pre-creation level by EXP-0008
// (`tools/agxtest/agxrender.m`, `render_min` fragment `_agc.main[0x06]`:
// 0x80->0x40 flips the rendered green channel 0.502->0.251, a single-byte
// value we obtain here by decoding the existing `frag_color_pack`
// instruction's `val` field with tools/agx-isa and writing our own chosen
// replacement value into that exact same field, i.e. genuinely "our own
// assembled bytes", not a value copied from any other Apple-authored
// record). This experiment's contribution is proving that same fact holds
// for the LIVE, POST-CREATION container -- i.e. that hardware actually
// fetches code from the exact 0x10000000000-family location EXP-0042
// found, not from some macOS-private shadow copy -- by mutating that live
// memory in place and observing the predicted pixel change on a FRESH draw.
//
// Build:
//   xcrun clang -fobjc-arc -o codesplice codesplice.m \
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
// Frozen authored source (byte-identical to
// experiments/EXP-0008-fragment-extraction/kernels/render_min.metal; hash
// recorded in CAPTURE_CONTRACT.json). Compiling this at runtime, in-process,
// reproduces the exact 54-byte fragment _agc.main body verified offline via
// tools/shdump + tools/agx-isa during calibration.
static const char *RENDER_MIN_SRC =
"#include <metal_stdlib>\n"
"using namespace metal;\n"
"\n"
"struct VOut {\n"
"    float4 pos [[position]];\n"
"};\n"
"\n"
"vertex VOut v_main(uint vid [[vertex_id]]) {\n"
"    float2 p = float2(float((vid << 1) & 2), float(vid & 2));\n"
"    VOut o;\n"
"    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);\n"
"    return o;\n"
"}\n"
"\n"
"fragment float4 f_main() {\n"
"    return float4(1.0, 0.5, 0.25, 1.0);\n"
"}\n";

// Frozen expected 54-byte fragment _agc.main, extracted OFFLINE via
// tools/shdump/shdump.m + tools/shdump/agxparse.py on the byte-identical
// source above (see PRE_REGISTRATION.md "Calibration"). Used only as a
// search NEEDLE to locate our own code inside the live code BO -- this
// value is never itself written anywhere; it's the pre-mutation pattern we
// look for.
static const uint8_t ORIG_MAIN[54] = {
    0x97,0x0c,0x54,0x00,0x02,0x60,0x80,0x50,0x04,0xc8,
    0x97,0x04,0x54,0x01,0x02,0x20,0xc0,0x50,0x04,0xc8,
    0x87,0x02,0x54,0x00,0x06,0x00,
    0x87,0x02,0x54,0x0c,0x08,0x00,
    0xe7,0x06,0x54,0x00,0x00,0x00,0x01,0x4e,0x00,0x00,0x00,0x00,
    0x07,0x02,0x54,0x0c,0x02,0x00,
    0x0e,0x00,0x00,0x00
};
#define ORIG_MAIN_LEN 54
#define HEADER_BACK_OFFSET 0x80  // header = main_offset - 0x40 (header pad) - 0x40 (const_program)

// ---------------------------------------------------------------------------
// Minimal, self-contained BODUMP (.hex) reader (own reimplementation of the
// documented tools/iotrace/iotrace.c dump_all_bos() text format; that file
// is used unmodified and read-only -- this is our own parser for its
// disclosed, non-Apple output format, not a copy of any Apple code).
typedef struct {
    char path[1024];
    uint64_t gpu_va, cpu, size, read_len;
    uint8_t *data;
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

static void free_dumps(BODump *d, int n) { for (int i = 0; i < n; i++) free(d[i].data); }

// Find the code-BO family (gpu_va in [0x10000000000, 0x10000010000)) whose
// content contains ORIG_MAIN verbatim. Returns 1 and fills *out on success.
static int find_code_record(BODump *dumps, int n, BODump **out_bo, int64_t *out_main_off) {
    for (int i = 0; i < n; i++) {
        if (dumps[i].gpu_va < 0x10000000000ULL || dumps[i].gpu_va >= 0x10000010000ULL) continue;
        for (uint64_t off = 0; off + ORIG_MAIN_LEN <= dumps[i].read_len; off++) {
            if (memcmp(dumps[i].data + off, ORIG_MAIN, ORIG_MAIN_LEN) == 0) {
                *out_bo = &dumps[i];
                *out_main_off = (int64_t)off;
                return 1;
            }
        }
    }
    return 0;
}

static uint32_t rd_u32(const uint8_t *data, size_t len, int64_t off) {
    if (off < 0 || (uint64_t)off + 4 > len) return 0xdeadbeefu;
    uint32_t v; memcpy(&v, data + off, 4); return v;
}

// ---------------------------------------------------------------------------
// JSON output helpers (minimal, no external dep).
static FILE *g_out;
static void jstr(const char *k, const char *v) { fprintf(g_out, "\"%s\":\"%s\",", k, v); }
static void jint(const char *k, long long v) { fprintf(g_out, "\"%s\":%lld,", k, v); }
static void jbool(const char *k, int v) { fprintf(g_out, "\"%s\":%s,", k, v ? "true" : "false"); }
static void jhex(const char *k, uint64_t v) { fprintf(g_out, "\"%s\":\"0x%llx\",", k, (unsigned long long)v); }
static void jbytes(const char *k, const uint8_t *b, int n) {
    fprintf(g_out, "\"%s\":\"", k);
    for (int i = 0; i < n; i++) fprintf(g_out, "%02x", b[i]);
    fprintf(g_out, "\",");
}

// ---------------------------------------------------------------------------
static void die(const char *msg) { fprintf(stderr, "FATAL %s\n", msg); exit(2); }

// Commit a command buffer and wait with a hard watchdog (completion handler +
// timed dispatch_semaphore_wait), never a bare waitUntilCompleted, so a true
// GPU hang cannot block this process forever (mirrors EXP-0116's mechanism).
static int commit_and_wait(id<MTLCommandBuffer> cb, long watchdog_sec,
                            MTLCommandBufferStatus *out_status, NSString **out_err) {
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);
    __block MTLCommandBufferStatus st = MTLCommandBufferStatusNotEnqueued;
    __block NSString *errStr = nil;
    [cb addCompletedHandler:^(id<MTLCommandBuffer> b) {
        st = b.status;
        if (b.error) errStr = [b.error localizedDescription];
        dispatch_semaphore_signal(sem);
    }];
    [cb commit];
    long rc = dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, watchdog_sec * NSEC_PER_SEC));
    *out_status = st;
    *out_err = errStr;
    return (rc == 0) ? 1 : 0; // 1 = completed within watchdog, 0 = timed out (hang)
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *case_name = "baseline_check";
        const char *dump_dir = "work/dumps";
        long watchdog_sec = 15;
        long dump_wait_us = 1000000;
        const char *out_json = NULL;

        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--case") && i + 1 < argc) case_name = argv[++i];
            else if (!strcmp(argv[i], "--dump-dir") && i + 1 < argc) dump_dir = argv[++i];
            else if (!strcmp(argv[i], "--watchdog-sec") && i + 1 < argc) watchdog_sec = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump-wait-us") && i + 1 < argc) dump_wait_us = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--out") && i + 1 < argc) out_json = argv[++i];
            else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
        }
        if (!out_json) die("--out required");
        g_out = fopen(out_json, "w");
        if (!g_out) die("cannot open --out");

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device");
        fprintf(stderr, "DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:[NSString stringWithUTF8String:RENDER_MIN_SRC]
                                                options:nil error:&err];
        if (!lib) die("compile failed");
        id<MTLFunction> vfn = [lib newFunctionWithName:@"v_main"];
        id<MTLFunction> ffn = [lib newFunctionWithName:@"f_main"];
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vfn; pd.fragmentFunction = ffn;
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) die("pso failed");

        id<MTLCommandQueue> q = [dev newCommandQueue];
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                 width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;

        // ---- Baseline draw ----
        id<MTLCommandBuffer> cb0 = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc0 = [cb0 renderCommandEncoderWithDescriptor:rp];
        [enc0 setRenderPipelineState:pso];
        [enc0 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc0 endEncoding];
        MTLCommandBufferStatus st0; NSString *e0;
        int ok0 = commit_and_wait(cb0, watchdog_sec, &st0, &e0);
        uint8_t px0[64] = {0};
        if (ok0) [target getBytes:px0 bytesPerRow:16 fromRegion:MTLRegionMake2D(0, 0, 4, 4) mipmapLevel:0];
        fprintf(stderr, "baseline: completed=%d status=%ld bgra=%02x%02x%02x%02x\n",
                ok0, (long)st0, px0[0], px0[1], px0[2], px0[3]);

        // ---- Pre-mutation dump ----
        kill(getpid(), SIGUSR1);
        usleep((useconds_t)dump_wait_us);
        static BODump dumps1[MAX_DUMPS];
        int n1 = load_all_bodumps(dump_dir, dumps1, MAX_DUMPS);
        BODump *bo1 = NULL; int64_t main_off1 = -1;
        int found1 = find_code_record(dumps1, n1, &bo1, &main_off1);
        int64_t header_off1 = found1 ? (main_off1 - HEADER_BACK_OFFSET) : -1;
        uint32_t header_word1 = found1 ? rd_u32(bo1->data, bo1->read_len, header_off1) : 0;
        fprintf(stderr, "predump: n=%d found=%d main_off=0x%llx header_off=0x%llx header_word=0x%08x\n",
                n1, found1, (unsigned long long)main_off1, (unsigned long long)header_off1, header_word1);

        // ---- Apply the case's mutation (if any) directly into the live BO ----
        int did_write = 0;
        uint8_t write_before[16] = {0}, write_after_intended[16] = {0};
        int write_len = 0;
        uint64_t write_addr = 0;

        if (found1) {
            uint8_t *cpu_main = (uint8_t *)(uintptr_t)(bo1->cpu + (uint64_t)main_off1);
            uint8_t *cpu_header = (uint8_t *)(uintptr_t)(bo1->cpu + (uint64_t)header_off1);

            if (!strcmp(case_name, "baseline_check")) {
                // no mutation
            } else if (!strcmp(case_name, "splice_green_field")) {
                // Decode-modify-encode result (tools/agx-isa `val` field of the
                // first frag_color_pack instruction, byte offset +0x06 within
                // main): 0x80 -> 0x40. Matches EXP-0008's archive-level
                // hardware-validated mapping of this exact byte.
                write_addr = (uint64_t)(uintptr_t)(cpu_main + 6);
                write_before[0] = *(uint8_t *)(uintptr_t)write_addr;
                *(uint8_t *)(uintptr_t)write_addr = 0x40;
                write_after_intended[0] = 0x40;
                write_len = 1; did_write = 1;
            } else if (!strcmp(case_name, "splice_wrong_field")) {
                // Adjacent byte (+0x07, src_present_mask): a "misaligned by one
                // field" negative/boundary control -- same instruction, wrong
                // field.
                write_addr = (uint64_t)(uintptr_t)(cpu_main + 7);
                write_before[0] = *(uint8_t *)(uintptr_t)write_addr;
                *(uint8_t *)(uintptr_t)write_addr = 0x40;
                write_after_intended[0] = 0x40;
                write_len = 1; did_write = 1;
            } else if (!strcmp(case_name, "header_size_zero")) {
                write_addr = (uint64_t)(uintptr_t)cpu_header;
                memcpy(write_before, cpu_header, 4);
                uint32_t z = 0; memcpy(cpu_header, &z, 4);
                memcpy(write_after_intended, &z, 4);
                write_len = 4; did_write = 1;
            } else if (!strcmp(case_name, "header_size_max")) {
                write_addr = (uint64_t)(uintptr_t)cpu_header;
                memcpy(write_before, cpu_header, 4);
                uint32_t m = 0xFFFFFFFFu; memcpy(cpu_header, &m, 4);
                memcpy(write_after_intended, &m, 4);
                write_len = 4; did_write = 1;
            } else if (!strcmp(case_name, "truncate_main_early")) {
                // Keep the first frag_color_pack instruction (10 bytes) intact,
                // then place `stop` (0e000000) immediately after it and zero
                // the remainder of the original 54-byte main (44 bytes),
                // producing a well-formed but deliberately truncated program
                // that never reaches frag_tile_setup/frag_color_store.
                write_addr = (uint64_t)(uintptr_t)(cpu_main + 10);
                write_len = ORIG_MAIN_LEN - 10; // 44
                if (write_len > 16) write_len = 16; // cap what we log before/after
                memcpy(write_before, cpu_main + 10, write_len);
                uint8_t stopbuf[44];
                memset(stopbuf, 0, sizeof(stopbuf));
                stopbuf[0] = 0x0e; stopbuf[1] = 0x00; stopbuf[2] = 0x00; stopbuf[3] = 0x00;
                memcpy(cpu_main + 10, stopbuf, ORIG_MAIN_LEN - 10);
                memcpy(write_after_intended, cpu_main + 10, write_len);
                did_write = 1;
            } else if (!strcmp(case_name, "corrupt_next_record_header")) {
                // header_off1 + header_word1 (the record's OWN declared size)
                // is where the NEXT code record begins (structurally
                // identified in calibration as the vertex shader's own
                // header, not independent FS metadata -- see RESULTS.md).
                // Corrupt only its leading 4-byte header/size field.
                int64_t next_hdr_off = header_off1 + (int64_t)header_word1;
                uint8_t *cpu_next = (uint8_t *)(uintptr_t)(bo1->cpu + (uint64_t)next_hdr_off);
                write_addr = (uint64_t)(uintptr_t)cpu_next;
                memcpy(write_before, cpu_next, 4);
                uint32_t m = 0xFFFFFFFFu; memcpy(cpu_next, &m, 4);
                memcpy(write_after_intended, &m, 4);
                write_len = 4; did_write = 1;
            } else {
                die("unknown --case");
            }
        }

        // ---- Second draw (fresh command buffer, SAME pso, post-mutation) ----
        id<MTLCommandBuffer> cb1 = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc1 = [cb1 renderCommandEncoderWithDescriptor:rp];
        [enc1 setRenderPipelineState:pso];
        [enc1 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc1 endEncoding];
        MTLCommandBufferStatus st1; NSString *e1;
        int ok1 = commit_and_wait(cb1, watchdog_sec, &st1, &e1);
        uint8_t px1[64] = {0};
        if (ok1) [target getBytes:px1 bytesPerRow:16 fromRegion:MTLRegionMake2D(0, 0, 4, 4) mipmapLevel:0];
        fprintf(stderr, "post-mutation: completed=%d status=%ld err=%s bgra=%02x%02x%02x%02x\n",
                ok1, (long)st1, e1 ? [e1 UTF8String] : "(none)", px1[0], px1[1], px1[2], px1[3]);

        // ---- Post-draw dump (persistence + post-state) ----
        kill(getpid(), SIGUSR1);
        usleep((useconds_t)dump_wait_us);
        static BODump dumps2[MAX_DUMPS];
        int n2 = load_all_bodumps(dump_dir, dumps2, MAX_DUMPS);
        BODump *bo2 = NULL; int64_t main_off2 = -1;
        // For a corrupted-header case ORIG_MAIN itself is untouched (we only
        // ever corrupt bytes outside [main_off, main_off+54) except in
        // splice_green_field/splice_wrong_field/truncate_main_early, where
        // main content differs from ORIG_MAIN by design -- so re-locating by
        // the ORIGINAL needle only works for the cases that never touch main
        // bytes. For those that do, locate by matching bo1's own gpu_va/cpu
        // instead (same physical BO, since nothing here reallocates it).
        for (int i = 0; i < n2; i++) {
            if (bo1 && dumps2[i].cpu == bo1->cpu && dumps2[i].gpu_va == bo1->gpu_va) { bo2 = &dumps2[i]; break; }
        }
        if (bo2) main_off2 = main_off1; // same BO, same offset by construction

        uint8_t post_main[ORIG_MAIN_LEN]; memset(post_main, 0, sizeof(post_main));
        uint32_t post_header_word = 0;
        int post_read_ok = 0;
        if (bo2 && main_off2 >= 0 && (uint64_t)main_off2 + ORIG_MAIN_LEN <= bo2->read_len) {
            memcpy(post_main, bo2->data + main_off2, ORIG_MAIN_LEN);
            post_header_word = rd_u32(bo2->data, bo2->read_len, header_off1);
            post_read_ok = 1;
        }

        // ---- Emit JSON ----
        fprintf(g_out, "{");
        jstr("case", case_name);
        jbool("found_code_record", found1);
        jbool("baseline_completed", ok0);
        jint("baseline_status", (long long)st0);
        jbytes("baseline_bgra", px0, 4);
        jbool("did_write", did_write);
        jint("write_len", write_len);
        jbytes("write_before", write_before, write_len > 16 ? 16 : write_len);
        jbytes("write_after_intended", write_after_intended, write_len > 16 ? 16 : write_len);
        jhex("header_word_pre", header_word1);
        jbool("post_mutation_completed", ok1);
        jbool("post_mutation_hang", !ok1);
        jint("post_mutation_status", (long long)st1);
        jstr("post_mutation_error", e1 ? [e1 UTF8String] : "");
        jbytes("post_mutation_bgra", px1, 4);
        jbool("post_read_ok", post_read_ok);
        jhex("header_word_post", post_header_word);
        jbytes("post_main_hex", post_main, ORIG_MAIN_LEN);
        // Non-gated address-shaped fields (still emitted here; the Python
        // driver splits gated vs non-gated on write, per schema.py).
        jhex("addr_bo_gpu_va", bo1 ? bo1->gpu_va : 0);
        jhex("addr_bo_cpu", bo1 ? bo1->cpu : 0);
        jhex("addr_main_off", (uint64_t)main_off1);
        jhex("addr_header_off", (uint64_t)header_off1);
        jhex("addr_write", write_addr);
        fprintf(g_out, "\"_end\":true}\n");
        fclose(g_out);

        free_dumps(dumps1, n1);
        free_dumps(dumps2, n2);
        return 0;
    }
}
