// fsredirect.m -- EXP-0127 task 2/3: FS selector (0x58000+0x08) redirect
// generation and hardware-consumer proof, plus boundary/alias sweep.
//
// CLEAN ROOM: public Metal API + OWN-SHADER + DATA-TRACE + HW-PROBE only.
// The only shaders executed are our own committed kernels/fsredirect.metal
// (fs_red/fs_green/fs_blue, vs_main). This program asks the unmodified,
// read-only tools/iotrace/iotrace.c interposer (DYLD_INSERT_LIBRARIES,
// never edited, never disassembled) to snapshot this process's OWN
// registered GPU buffer objects, then WRITES a computed 4-byte value into
// the live FF-state pool BO's CPU-mapped memory (fixed queue-context VA
// 0x58000, established DATA-TRACE fact from EXP-0042/EXP-0110/this
// experiment's own work/calib_fs.m calibration) strictly BEFORE the owning
// command buffer is committed. Calibration (PROGRESS.md) proved this write
// happens at ENCODE time, not commit time: pool+0x08 already reads the
// bound pipeline's own natural selector immediately after endEncoding, and
// is byte-identical pre- vs post-commit for an unmutated draw. This is the
// same "write a known pattern into hardware-visible state, observe what the
// hardware does with it" HW-PROBE method EXP-0116 already validated for the
// CDM segment link.
//
// Discovery, never hand-copied: every run independently discovers this
// run's own S_RED/S_GREEN/S_BLUE (the natural pool+0x08 selector value Metal
// assigns to each of our three fragment functions) via three ordinary solo
// draws (own command buffer each, commit+wait, post-commit dump), BEFORE
// the one mutation case this process invocation tests. All boundary deltas
// (+-1/2/4/8, 0, the field's own 0xffffffff ceiling, the top-bit mask, a
// far out-of-range offset) are protocol constants, not captured addresses.
//
// One case per process (SUBAGENT_BRIEF.md): `--case NAME` selects which
// pipeline is bound for the 4th (test) draw and what value (if any) is
// spliced into pool+0x08 before that draw's command buffer commits. A
// baseline_*_solo case performs no mutation (case_valid_setup sanity only).
//
// Safety: a per-draw watchdog (completion handler + timed semaphore, never
// a bare waitUntilCompleted) bounds every commit; the Python driver adds a
// process-level hard timeout on top (mirrors EXP-0116, whose `encoding_max`
// case produced a genuine GPU hang, not just a fault -- CONTAINED, no host
// wedge, but requiring exactly this two-layer guard).
//
// Build:
//   xcrun clang -fobjc-arc -o fsredirect fsredirect.m -framework Metal -framework Foundation

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

#define POOL_VA 0x58000ULL
#define POOL_SELECTOR_OFF 0x08

// ---------------------------------------------------------------------------
// Minimal BODUMP (.hex) reader, matching tools/iotrace/iotrace.c
// dump_all_bos() output format (unmodified, read-only tool). Adapted from
// this experiment's own harness/vstoken.m analysis pattern and
// EXP-0116/harness/linksplice.m's independently-authored in-process reader
// (same public log format, our own re-implementation here).
typedef struct {
    uint64_t gpu_va, cpu, size, read_len;
} BODump;

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int load_bodump_header(const char *path, BODump *out) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[8192];
    if (!fgets(line, sizeof(line), f)) { fclose(f); return 0; }
    fclose(f);
    unsigned long long gpu_va = 0, cpu = 0, size = 0, read_len = 0;
    char *p;
    if ((p = strstr(line, "gpu_va=0x"))) gpu_va = strtoull(p + 9, NULL, 16);
    if ((p = strstr(line, "cpu=0x"))) cpu = strtoull(p + 6, NULL, 16);
    if ((p = strstr(line, "size=0x"))) size = strtoull(p + 7, NULL, 16);
    if ((p = strstr(line, "read=0x"))) read_len = strtoull(p + 7, NULL, 16);
    out->gpu_va = gpu_va; out->cpu = cpu; out->size = size; out->read_len = read_len;
    return 1;
}

// Find the most-recently-written dump file for gpu_va `want_va` inside
// directory `dir`. Returns 1 and fills *out on success.
static int find_bo_by_va(const char *dir, uint64_t want_va, BODump *out) {
    DIR *d = opendir(dir);
    if (!d) return 0;
    struct dirent *e;
    int found = 0;
    time_t best_mtime = 0;
    char best_path[1200];
    while ((e = readdir(d)) != NULL) {
        if (strncmp(e->d_name, "bo_", 3) != 0) continue;
        size_t l = strlen(e->d_name);
        if (l < 4 || strcmp(e->d_name + l - 4, ".hex") != 0) continue;
        char path[1200];
        snprintf(path, sizeof(path), "%s/%s", dir, e->d_name);
        BODump tmp;
        if (!load_bodump_header(path, &tmp)) continue;
        if (tmp.gpu_va != want_va) continue;
        struct stat st;
        if (stat(path, &st) != 0) continue;
        if (!found || st.st_mtime >= best_mtime) {
            found = 1; best_mtime = st.st_mtime;
            strncpy(best_path, path, sizeof(best_path) - 1);
        }
    }
    closedir(d);
    if (!found) return 0;
    return load_bodump_header(best_path, out);
}

static uint32_t rd_u32(uint64_t cpu_addr, uint64_t off) {
    return *(volatile uint32_t *)(uintptr_t)(cpu_addr + off);
}
static void wr_u32(uint64_t cpu_addr, uint64_t off, uint32_t v) {
    *(volatile uint32_t *)(uintptr_t)(cpu_addr + off) = v;
}

// ---------------------------------------------------------------------------
typedef struct {
    __block MTLCommandBufferStatus status;
    __block NSString *errdesc;
} Watched;

static Watched watch_commit(id<MTLCommandBuffer> cb, double timeout_sec) {
    Watched w; w.status = 0; w.errdesc = nil;
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);
    __block MTLCommandBufferStatus st = 0;
    __block NSString *ed = nil;
    [cb addCompletedHandler:^(id<MTLCommandBuffer> c) {
        st = c.status; ed = c.error ? c.error.localizedDescription : nil;
        dispatch_semaphore_signal(sem);
    }];
    [cb commit];
    long timed_out = dispatch_semaphore_wait(
        sem, dispatch_time(DISPATCH_TIME_NOW, (int64_t)(timeout_sec * NSEC_PER_SEC)));
    if (timed_out != 0) { w.status = (MTLCommandBufferStatus)-1; w.errdesc = @"PROCESS_WATCHDOG_TIMEOUT"; }
    else { w.status = st; w.errdesc = ed; }
    return w;
}

static id<MTLRenderPipelineState> mk_pipeline(id<MTLDevice> dev, id<MTLLibrary> lib,
                                              NSString *fs, NSString *label) {
    MTLRenderPipelineDescriptor *d = [MTLRenderPipelineDescriptor new];
    d.label = label;
    d.vertexFunction = [lib newFunctionWithName:@"vs_main"];
    d.fragmentFunction = [lib newFunctionWithName:fs];
    d.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    NSError *e = nil;
    id<MTLRenderPipelineState> s = [dev newRenderPipelineStateWithDescriptor:d error:&e];
    if (!s) {
        fprintf(stderr, "FAIL pipeline %s: %s\n", label.UTF8String,
                e ? e.localizedDescription.UTF8String : "unknown");
        exit(2);
    }
    return s;
}

// Sanitize a possibly-NSString error description into a JSON-safe C string
// (strip quotes/backslashes/newlines; truncate). Static buffer, single-
// threaded use only (this program is single-threaded aside from Metal's own
// completion-handler dispatch, which always completes before this is read).
static char g_errbuf[512];
static const char *sanitize_error(NSString *s) {
    if (!s) return NULL;
    const char *raw = s.UTF8String;
    size_t j = 0;
    for (size_t i = 0; raw[i] && j + 1 < sizeof(g_errbuf); ++i) {
        char c = raw[i];
        if (c == '"' || c == '\\') c = '\'';
        if (c == '\n' || c == '\r') c = ' ';
        g_errbuf[j++] = c;
    }
    g_errbuf[j] = 0;
    return g_errbuf;
}

static const char *classify_bgra(unsigned char *px) {
    // px = B,G,R,A bytes.
    int b = px[0] > 0x80, g = px[1] > 0x80, r = px[2] > 0x80;
    if (r && !g && !b) return "red";
    if (!r && g && !b) return "green";
    if (!r && !g && b) return "blue";
    if (!r && !g && !b) return "black";
    return "other";
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *case_name = "baseline_red_solo";
        const char *source_path = "kernels/fsredirect.metal";
        const char *dump_dir = "work/rt_dumps"; // overridden by run.py per case
        double watchdog_sec = 10.0;
        unsigned proc_alarm = 60;

        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--case") && i + 1 < argc) case_name = argv[++i];
            else if (!strcmp(argv[i], "--source") && i + 1 < argc) source_path = argv[++i];
            else if (!strcmp(argv[i], "--dump-dir") && i + 1 < argc) dump_dir = argv[++i];
            else if (!strcmp(argv[i], "--watchdog-sec") && i + 1 < argc) watchdog_sec = atof(argv[++i]);
            else if (!strcmp(argv[i], "--alarm") && i + 1 < argc) proc_alarm = (unsigned)atoi(argv[++i]);
            else { fprintf(stderr, "usage: %s --case NAME [--dump-dir DIR] "
                           "[--watchdog-sec S] [--alarm SEC]\n", argv[0]); return 2; }
        }
        alarm(proc_alarm);
        mkdir(dump_dir, 0755);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "FAIL no Metal device\n"); return 2; }
        NSError *e = nil;
        NSString *src = [NSString stringWithContentsOfFile:@(source_path)
                                                    encoding:NSUTF8StringEncoding error:&e];
        if (!src) { fprintf(stderr, "FAIL read source: %s\n", e.localizedDescription.UTF8String); return 2; }
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        if (!lib) { fprintf(stderr, "FAIL compile: %s\n", e.localizedDescription.UTF8String); return 2; }

        id<MTLRenderPipelineState> red = mk_pipeline(dev, lib, @"fs_red", @"red");
        id<MTLRenderPipelineState> green = mk_pipeline(dev, lib, @"fs_green", @"green");
        id<MTLRenderPipelineState> blue = mk_pipeline(dev, lib, @"fs_blue", @"blue");

        static const float tri[6] = {-1.0f, -1.0f, 3.0f, -1.0f, -1.0f, 3.0f};
        id<MTLBuffer> verts = [dev newBufferWithBytes:tri length:sizeof(tri)
                                              options:MTLResourceStorageModeShared];
        id<MTLBuffer> params = [dev newBufferWithLength:0x100 options:MTLResourceStorageModeShared];
        float *p = params.contents; p[0] = 1; p[1] = 1; p[2] = 0; p[3] = 1;

        const NSUInteger w = 16, h = 16, bpr = 64;
        id<MTLBuffer> tb = [dev newBufferWithLength:bpr * h options:MTLResourceStorageModeShared];
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:w height:h mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [tb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
        if (!tex) { fprintf(stderr, "FAIL target\n"); return 2; }

        id<MTLCommandQueue> queue = [dev newCommandQueue];

        // ---- Discovery phase: three solo draws, own CB each. ----
        id<MTLRenderPipelineState> discovery_order[3] = {red, green, blue};
        const char *discovery_names[3] = {"red", "green", "blue"};
        uint32_t sel[3] = {0, 0, 0};
        const char *discover_colour[3] = {NULL, NULL, NULL};
        int discovery_ok = 1;

        for (int i = 0; i < 3; ++i) {
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = tex;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
            id<MTLCommandBuffer> cb = [queue commandBuffer];
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:discovery_order[i]];
            [enc setVertexBuffer:verts offset:0 atIndex:0];
            [enc setVertexBuffer:params offset:0 atIndex:1];
            [enc setFragmentBuffer:params offset:0 atIndex:0];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            Watched w1 = watch_commit(cb, watchdog_sec);
            if (w1.status != MTLCommandBufferStatusCompleted) { discovery_ok = 0; }
            unsigned char *px = (unsigned char *)tb.contents + 8 * bpr + 8 * 4;
            discover_colour[i] = classify_bgra(px);

            char dpath[1200];
            snprintf(dpath, sizeof(dpath), "%s/discover_%d", dump_dir, i);
            mkdir(dpath, 0755);
            kill(getpid(), SIGUSR1);
            usleep(400000);
            BODump pool;
            if (find_bo_by_va("iotrace_maps", POOL_VA, &pool)) {
                sel[i] = rd_u32(pool.cpu, POOL_SELECTOR_OFF);
            } else {
                discovery_ok = 0;
            }
        }
        uint32_t S_RED = sel[0], S_GREEN = sel[1], S_BLUE = sel[2];

        // ---- Case dispatch: choose bound pipeline + mutation for test draw. ----
        id<MTLRenderPipelineState> bind = red;
        const char *bind_name = "red";
        int do_mutate = 0;
        uint32_t mutate_value = 0;
        const char *mutate_desc = "none";

        if (!strcmp(case_name, "baseline_red_solo")) { bind = red; bind_name = "red"; }
        else if (!strcmp(case_name, "baseline_green_solo")) { bind = green; bind_name = "green"; }
        else if (!strcmp(case_name, "baseline_blue_solo")) { bind = blue; bind_name = "blue"; }
        else if (!strcmp(case_name, "redirect_red_to_green")) { bind = red; bind_name = "red"; do_mutate = 1; mutate_value = S_GREEN; mutate_desc = "S_GREEN"; }
        else if (!strcmp(case_name, "redirect_red_to_blue")) { bind = red; bind_name = "red"; do_mutate = 1; mutate_value = S_BLUE; mutate_desc = "S_BLUE"; }
        else if (!strcmp(case_name, "redirect_green_to_red")) { bind = green; bind_name = "green"; do_mutate = 1; mutate_value = S_RED; mutate_desc = "S_RED"; }
        else if (!strcmp(case_name, "redirect_blue_to_red")) { bind = blue; bind_name = "blue"; do_mutate = 1; mutate_value = S_RED; mutate_desc = "S_RED"; }
        else if (!strcmp(case_name, "misalign_plus1")) { bind = red; do_mutate = 1; mutate_value = S_GREEN + 1; mutate_desc = "S_GREEN+1"; }
        else if (!strcmp(case_name, "misalign_plus2")) { bind = red; do_mutate = 1; mutate_value = S_GREEN + 2; mutate_desc = "S_GREEN+2"; }
        else if (!strcmp(case_name, "misalign_plus4")) { bind = red; do_mutate = 1; mutate_value = S_GREEN + 4; mutate_desc = "S_GREEN+4"; }
        else if (!strcmp(case_name, "misalign_plus8")) { bind = red; do_mutate = 1; mutate_value = S_GREEN + 8; mutate_desc = "S_GREEN+8"; }
        else if (!strcmp(case_name, "misalign_minus1")) { bind = red; do_mutate = 1; mutate_value = S_GREEN - 1; mutate_desc = "S_GREEN-1"; }
        else if (!strcmp(case_name, "misalign_minus2")) { bind = red; do_mutate = 1; mutate_value = S_GREEN - 2; mutate_desc = "S_GREEN-2"; }
        else if (!strcmp(case_name, "misalign_minus4")) { bind = red; do_mutate = 1; mutate_value = S_GREEN - 4; mutate_desc = "S_GREEN-4"; }
        else if (!strcmp(case_name, "misalign_minus8")) { bind = red; do_mutate = 1; mutate_value = S_GREEN - 8; mutate_desc = "S_GREEN-8"; }
        else if (!strcmp(case_name, "boundary_zero")) { bind = red; do_mutate = 1; mutate_value = 0; mutate_desc = "0"; }
        else if (!strcmp(case_name, "boundary_far_oor")) { bind = red; do_mutate = 1; mutate_value = S_GREEN + 0x2000000u; mutate_desc = "S_GREEN+0x2000000"; }
        else if (!strcmp(case_name, "boundary_top_bit")) { bind = red; do_mutate = 1; mutate_value = S_GREEN | 0x80000000u; mutate_desc = "S_GREEN|0x80000000"; }
        else if (!strcmp(case_name, "boundary_max")) { bind = red; do_mutate = 1; mutate_value = 0xFFFFFFFFu; mutate_desc = "0xFFFFFFFF"; }
        else if (!strcmp(case_name, "boundary_near_but_invalid")) { bind = red; do_mutate = 1; mutate_value = S_RED - 0x40; mutate_desc = "S_RED-0x40"; }
        else { fprintf(stderr, "FAIL unknown case %s\n", case_name); return 2; }

        // ---- Test draw: encode, dump PRE-commit, mutate, commit, readback. ----
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:bind];
        [enc setVertexBuffer:verts offset:0 atIndex:0];
        [enc setVertexBuffer:params offset:0 atIndex:1];
        [enc setFragmentBuffer:params offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];

        char dpath[1200];
        snprintf(dpath, sizeof(dpath), "%s/test", dump_dir);
        mkdir(dpath, 0755);
        kill(getpid(), SIGUSR1);
        usleep(400000);
        BODump pool;
        int pool_found = find_bo_by_va("iotrace_maps", POOL_VA, &pool);
        uint32_t natural_selector = 0;
        int case_valid_setup = 0;
        if (pool_found) {
            natural_selector = rd_u32(pool.cpu, POOL_SELECTOR_OFF);
            uint32_t expect_natural = !strcmp(bind_name, "red") ? S_RED :
                                       (!strcmp(bind_name, "green") ? S_GREEN : S_BLUE);
            case_valid_setup = (natural_selector == expect_natural);
        }

        int wrote = 0;
        if (do_mutate && pool_found) {
            wr_u32(pool.cpu, POOL_SELECTOR_OFF, mutate_value);
            wrote = 1;
        }

        Watched w2 = watch_commit(cb, watchdog_sec);
        int hang = (w2.status == (MTLCommandBufferStatus)-1);
        int completed = (w2.status == MTLCommandBufferStatusCompleted);
        unsigned char *px = (unsigned char *)tb.contents + 8 * bpr + 8 * 4;
        const char *result_colour = classify_bgra(px);
        const char *err_sanitized = sanitize_error(w2.errdesc);

        // Post-commit diagnostic read of the SAME field: does the splice
        // survive through commit, or does Metal re-finalize/overwrite it at
        // commit time (as EXP-0116 found for a CDM chain's own LAST-segment
        // terminator)? Purely diagnostic; not used to gate the result.
        char dpath2[1200];
        snprintf(dpath2, sizeof(dpath2), "%s/test_post", dump_dir);
        mkdir(dpath2, 0755);
        kill(getpid(), SIGUSR1);
        usleep(400000);
        uint32_t post_selector = 0;
        int post_pool_found = 0;
        BODump pool2;
        if (find_bo_by_va("iotrace_maps", POOL_VA, &pool2)) {
            post_selector = rd_u32(pool2.cpu, POOL_SELECTOR_OFF);
            post_pool_found = 1;
        }

        // JSON output (single line).
        printf("{\"case\":\"%s\",\"bind\":\"%s\",\"discovery_ok\":%s,"
               "\"S_RED\":%u,\"S_GREEN\":%u,\"S_BLUE\":%u,"
               "\"discover_colour_red\":\"%s\",\"discover_colour_green\":\"%s\","
               "\"discover_colour_blue\":\"%s\","
               "\"pool_found\":%s,\"natural_selector\":%u,\"case_valid_setup\":%s,"
               "\"do_mutate\":%s,\"mutate_desc\":\"%s\",\"mutate_value\":%u,"
               "\"wrote\":%s,\"hang\":%s,\"final_status\":%ld,"
               "\"final_error\":%s%s%s,\"result_colour\":\"%s\","
               "\"post_pool_found\":%s,\"post_selector\":%u}\n",
               case_name, bind_name, discovery_ok ? "true" : "false",
               S_RED, S_GREEN, S_BLUE,
               discover_colour[0], discover_colour[1], discover_colour[2],
               pool_found ? "true" : "false", natural_selector,
               case_valid_setup ? "true" : "false",
               do_mutate ? "true" : "false", mutate_desc, mutate_value,
               wrote ? "true" : "false", hang ? "true" : "false",
               (long)w2.status,
               err_sanitized ? "\"" : "", err_sanitized ? err_sanitized : "null",
               err_sanitized ? "\"" : "",
               result_colour,
               post_pool_found ? "true" : "false", post_selector);
        fflush(stdout);
        alarm(0);
        return 0;
    }
}
