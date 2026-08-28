// EXP-0084: public-API Metal harness for the MEM-20/21/22 dynamic buffer
// addressing probe. Runs EXACTLY ONE case per process (fresh device,
// library, pipeline, buffers, queue, command buffer), prints one complete
// JSON record to stdout, and returns. Single-threaded and synchronous
// (EXP-0072 lesson): the Metal wait, readbacks, and the record printf/fflush
// all execute in main() in program order; main() returns only after stdout
// has been flushed and error-checked.
//
// Clean-room: only public Metal/Foundation API calls. Every dynamic device
// address dereferenced by the compiled kernels comes from our own CPU-side
// harness writing a backing MTLBuffer's public `.gpuAddress` into an
// ordinary data buffer, or from Metal's public implicit-argument-buffer
// (MTLArgumentEncoder) feature. No Apple binary is introspected.
//
// A GPU-address value is NEVER printed by this harness (by design, so the
// gated per-case comparison payload the runner builds can never accidentally
// carry a nondeterministic raw address -- the EXP-0081 quarantine class).
// Only derived TAG words (small compile-time-chosen constants written by us
// into backing buffers, then read back through the dynamic address) are
// printed.
//
// Compile/pipeline REJECTION is a first-class recorded outcome for this
// experiment (MEM-22's direct-argument-count boundary case expects a
// possible compile failure) -- it is NOT treated as a harness/process fault.
// A record is printed and the process exits 0 whenever library/function/
// pipeline creation fails cleanly (an NSError was produced); only a true
// crash, OS-level failure, or watchdog timeout is left for the outer runner
// to classify as proc_fail/watchdog/proc_timeout.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <sys/utsname.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <stdint.h>
#include <time.h>

static int g_exit_code = 0;
static void on_alarm(int sig) { (void)sig; _exit(g_exit_code); }
static void arm_watchdog(int seconds, int code) { g_exit_code = code; signal(SIGALRM, on_alarm); alarm((unsigned)seconds); }
static void disarm_watchdog(void) { alarm(0); }
static double monotonic(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0.0;
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}
static void js(NSString *s) {
    NSData *d = [NSJSONSerialization dataWithJSONObject:(s ?: @"") options:NSJSONWritingFragmentsAllowed error:nil];
    fwrite(d.bytes, 1, d.length, stdout);
}
static void hex_words(const uint32_t *w, NSUInteger n) {
    printf("\"");
    for (NSUInteger i = 0; i < n; i++) printf("%08x", w[i]);
    printf("\"");
}
static uint32_t TAG(uint32_t k) { return 0x5A000000u | (k & 0x00FFFFFFu); }

// ---- record printer: ONE frozen key set for every dispatch-kind case ----
// (mode-inapplicable fields carry a fixed placeholder: -1 for unused ints,
// "" for unused hex-string fields -- never omitted, never renamed).
static void print_record(NSString *mode, NSString *kernel, NSString *function,
                          long n, long grid, long tg, long sel_u, long k_outlier,
                          BOOL use_resource, id<MTLDevice> d,
                          BOOL compile_ok, NSString *compile_error,
                          BOOL dispatch_ok, long cb_status, NSString *run_error,
                          BOOL fast_math, long math_mode_raw, unsigned long lang_raw,
                          double compile_s, double dispatch_s,
                          const uint32_t *out_w, NSUInteger out_n,
                          const uint32_t *outb_w, NSUInteger outb_n,
                          const uint32_t *outsel_w, NSUInteger outsel_n) {
    struct utsname u; uname(&u);
    printf("{\"schema\":1,\"mode\":"); js(mode);
    printf(",\"kernel\":"); js(kernel);
    printf(",\"function\":"); js(function);
    printf(",\"n\":%ld,\"grid\":%ld,\"tg\":%ld,\"sel_u\":%ld,\"k_outlier\":%ld,"
           "\"use_resource\":%s", n, grid, tg, sel_u, k_outlier, use_resource ? "true" : "false");
    printf(",\"device\":"); js(d ? d.name : @"");
    printf(",\"machine\":"); js(@(u.machine));
    printf(",\"os\":"); js(NSProcessInfo.processInfo.operatingSystemVersionString);
    printf(",\"fast_math\":%s,\"math_mode_raw\":%ld,\"language_version_raw\":%lu,"
           "\"library_compile_seconds\":%.6f,\"dispatch_seconds\":%.6f",
           fast_math ? "true" : "false", math_mode_raw, lang_raw, compile_s, dispatch_s);
    printf(",\"compile_ok\":%s,\"compile_error\":", compile_ok ? "true" : "false"); js(compile_error ?: @"");
    printf(",\"dispatch_ok\":%s,\"command_buffer_status\":%ld,\"error\":",
           dispatch_ok ? "true" : "false", cb_status); js(run_error ?: @"");
    printf(",\"out_hex\":"); if (out_w) hex_words(out_w, out_n); else printf("\"\"");
    printf(",\"outb_hex\":"); if (outb_w) hex_words(outb_w, outb_n); else printf("\"\"");
    printf(",\"outsel_hex\":"); if (outsel_w) hex_words(outsel_w, outsel_n); else printf("\"\"");
    printf("}\n");
    fflush(stdout);
}

// ---- shared compile helper ----
static id<MTLComputePipelineState> build_pipeline(id<MTLDevice> d, NSString *source_path,
                                                   NSString *fn_name, MTLCompileOptions *opts,
                                                   double *compile_s_out, BOOL *ok_out, NSString **err_out) {
    NSError *e = nil;
    NSString *msl = [NSString stringWithContentsOfFile:source_path encoding:NSUTF8StringEncoding error:&e];
    if (!msl) { *ok_out = NO; *err_out = @"SOURCE_READ_FAIL"; return nil; }
    double t0 = monotonic();
    arm_watchdog(120, 97);
    id<MTLLibrary> lib = [d newLibraryWithSource:msl options:opts error:&e];
    id<MTLFunction> fn = lib ? [lib newFunctionWithName:fn_name] : nil;
    id<MTLComputePipelineState> ps = fn ? [d newComputePipelineStateWithFunction:fn error:&e] : nil;
    disarm_watchdog();
    *compile_s_out = monotonic() - t0;
    if (!ps) {
        *ok_out = NO;
        *err_out = e ? e.localizedDescription : (lib ? (fn ? @"PIPELINE_FAIL" : @"FUNCTION_FAIL") : @"LIBRARY_FAIL");
        return nil;
    }
    *ok_out = YES; *err_out = @"";
    return ps;
}

static id<MTLBuffer> mk_buf(id<MTLDevice> d, NSUInteger len) {
    return [d newBufferWithLength:len options:MTLResourceStorageModeShared];
}

int main(int ac, const char **av) { @autoreleasepool {
    const char *mode = NULL, *source = NULL, *function = NULL;
    // grid/tg are NOT accepted as CLI input: every mode below computes its
    // own effective dispatch geometry deterministically from --mode/--n (so
    // that geometry can never silently disagree with the buffers the same
    // mode branch allocates). What gets RECORDED in the JSON output is that
    // effective geometry (eff_grid/eff_tg), not a caller-supplied value.
    long n = -1, sel_u = -1, k_outlier = -1, use_resource = 1;
    for (int i = 1; i < ac; i++) {
        if (!strcmp(av[i], "--mode") && i + 1 < ac) mode = av[++i];
        else if (!strcmp(av[i], "--source") && i + 1 < ac) source = av[++i];
        else if (!strcmp(av[i], "--function") && i + 1 < ac) function = av[++i];
        else if (!strcmp(av[i], "--n") && i + 1 < ac) n = strtol(av[++i], NULL, 10);
        else if (!strcmp(av[i], "--sel") && i + 1 < ac) sel_u = strtol(av[++i], NULL, 10);
        else if (!strcmp(av[i], "--k") && i + 1 < ac) k_outlier = strtol(av[++i], NULL, 10);
        else if (!strcmp(av[i], "--use-resource") && i + 1 < ac) use_resource = strtol(av[++i], NULL, 10);
    }
    if (!mode || !source || !function) { fprintf(stderr, "ARGS_FAIL\n"); return 2; }
    NSString *nsSource = @(source), *nsFunction = @(function), *nsMode = @(mode);

    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { fprintf(stderr, "DEVICE_FAIL\n"); return 3; }
    MTLCompileOptions *opts = [[MTLCompileOptions alloc] init];
    opts.mathMode = MTLMathModeSafe;
    opts.fastMathEnabled = NO;

    double compile_s = 0.0; BOOL compile_ok = NO; NSString *compile_err = @"";
    id<MTLComputePipelineState> ps = build_pipeline(d, nsSource, nsFunction, opts, &compile_s, &compile_ok, &compile_err);
    if (!ps) {
        // Recorded outcome (e.g. MEM-22 direct-argument-count rejection), not a process fault.
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, -1, -1, sel_u, k_outlier,
                     use_resource != 0, d, NO, compile_err, NO, -1, @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, 0.0, NULL, 0, NULL, 0, NULL, 0);
        if (fflush(stdout) != 0 || ferror(stdout)) { fprintf(stderr, "STDOUT_FLUSH_FAIL\n"); return 5; }
        return 0;
    }

    id<MTLCommandQueue> cq = [d newCommandQueue];
    if (!cq) { fprintf(stderr, "QUEUE_FAIL\n"); return 3; }
    id<MTLCommandBuffer> cb = [cq commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    if (!cb || !ce) { fprintf(stderr, "ENCODER_FAIL\n"); return 3; }
    [ce setComputePipelineState:ps];

    uint32_t out_w[256]; memset(out_w, 0, sizeof(out_w));
    uint32_t outb_w[256]; memset(outb_w, 0, sizeof(outb_w));
    uint32_t outsel_w[256]; memset(outsel_w, 0, sizeof(outsel_w));
    NSUInteger out_n = 0, outb_n = 0, outsel_n = 0;
    (void)outb_n;  // reserved: no dispatch-kind mode currently populates outb (splice_target
                    // is exercised only by analysis/splice_case.py, not this harness)
    long eff_grid = 1, eff_tg = 1;  // every mode branch below overwrites both explicitly

    if (!strcmp(mode, "ctrl_direct")) {
        eff_grid = 32; eff_tg = 32;
        id<MTLBuffer> a = mk_buf(d, 32 * 4), out = mk_buf(d, 32 * 4);
        uint32_t *pa = a.contents;
        for (int i = 0; i < 32; i++) pa[i] = 1000u + (uint32_t)i;
        [ce setBuffer:a offset:0 atIndex:0];
        [ce setBuffer:out offset:0 atIndex:1];
        [ce dispatchThreads:MTLSizeMake(32, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, 32 * 4); out_n = 32;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, NULL, 0);
    } else if (!strcmp(mode, "mem21_uniform")) {
        // n backing buffers, each 1 word, tagged TAG(k). addrs[k]=backing[k].gpuAddress.
        // sel_u selects ONE address, used by every thread (uniform).
        eff_grid = 32; eff_tg = 32;
        NSMutableArray *backing = [NSMutableArray array];
        for (long k = 0; k < n; k++) {
            id<MTLBuffer> b = mk_buf(d, 4);
            *((uint32_t *)b.contents) = TAG((uint32_t)k);
            [backing addObject:b];
        }
        id<MTLBuffer> addrs = mk_buf(d, (NSUInteger)n * 8);
        uint64_t *pAddrs = addrs.contents;
        for (long k = 0; k < n; k++) pAddrs[k] = [(id<MTLBuffer>)backing[(NSUInteger)k] gpuAddress];
        id<MTLBuffer> selBuf = mk_buf(d, 4); *((uint32_t *)selBuf.contents) = (uint32_t)sel_u;
        id<MTLBuffer> out = mk_buf(d, 32 * 4);
        if (use_resource) for (id<MTLBuffer> b in backing) [ce useResource:b usage:MTLResourceUsageRead];
        [ce setBuffer:addrs offset:0 atIndex:0];
        [ce setBuffer:selBuf offset:0 atIndex:1];
        [ce setBuffer:out offset:0 atIndex:2];
        [ce dispatchThreads:MTLSizeMake(32, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, 32 * 4); out_n = 32;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, NULL, 0);
    } else if (!strcmp(mode, "mem21_perlane")) {
        // n backing buffers == grid size; each thread gid selects addrs[gid % n].
        eff_grid = n; eff_tg = (n < 32) ? n : 32;
        NSMutableArray *backing = [NSMutableArray array];
        for (long k = 0; k < n; k++) {
            id<MTLBuffer> b = mk_buf(d, 4);
            *((uint32_t *)b.contents) = TAG((uint32_t)k);
            [backing addObject:b];
        }
        id<MTLBuffer> addrs = mk_buf(d, (NSUInteger)n * 8);
        uint64_t *pAddrs = addrs.contents;
        for (long k = 0; k < n; k++) pAddrs[k] = [(id<MTLBuffer>)backing[(NSUInteger)k] gpuAddress];
        id<MTLBuffer> nBuf = mk_buf(d, 4); *((uint32_t *)nBuf.contents) = (uint32_t)n;
        id<MTLBuffer> out = mk_buf(d, (NSUInteger)n * 4);
        id<MTLBuffer> outsel = mk_buf(d, (NSUInteger)n * 4);
        if (use_resource) for (id<MTLBuffer> b in backing) [ce useResource:b usage:MTLResourceUsageRead];
        [ce setBuffer:addrs offset:0 atIndex:0];
        [ce setBuffer:nBuf offset:0 atIndex:1];
        [ce setBuffer:out offset:0 atIndex:2];
        [ce setBuffer:outsel offset:0 atIndex:3];
        [ce dispatchThreads:MTLSizeMake((NSUInteger)n, 1, 1) threadsPerThreadgroup:MTLSizeMake((NSUInteger)eff_tg, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, (size_t)n * 4); out_n = (NSUInteger)n;
        memcpy(outsel_w, outsel.contents, (size_t)n * 4); outsel_n = (NSUInteger)n;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, outsel_w, outsel_n);
    } else if (!strcmp(mode, "mem21_outlier")) {
        // n=2 backing buffers; every lane selects addrs[0] except gid==k_outlier -> addrs[1].
        eff_grid = 32; eff_tg = 32;
        NSMutableArray *backing = [NSMutableArray array];
        for (long k = 0; k < n; k++) {
            id<MTLBuffer> b = mk_buf(d, 4);
            *((uint32_t *)b.contents) = TAG((uint32_t)k);
            [backing addObject:b];
        }
        id<MTLBuffer> addrs = mk_buf(d, (NSUInteger)n * 8);
        uint64_t *pAddrs = addrs.contents;
        for (long k = 0; k < n; k++) pAddrs[k] = [(id<MTLBuffer>)backing[(NSUInteger)k] gpuAddress];
        id<MTLBuffer> kBuf = mk_buf(d, 4); *((uint32_t *)kBuf.contents) = (uint32_t)k_outlier;
        id<MTLBuffer> out = mk_buf(d, 32 * 4);
        if (use_resource) for (id<MTLBuffer> b in backing) [ce useResource:b usage:MTLResourceUsageRead];
        [ce setBuffer:addrs offset:0 atIndex:0];
        [ce setBuffer:kBuf offset:0 atIndex:1];
        [ce setBuffer:out offset:0 atIndex:2];
        [ce dispatchThreads:MTLSizeMake(32, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, 32 * 4); out_n = 32;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, NULL, 0);
    } else if (!strcmp(mode, "mem20_implicit_ab")) {
        eff_grid = 32; eff_tg = 32;
        id<MTLLibrary> lib = [d newLibraryWithSource:[NSString stringWithContentsOfFile:nsSource encoding:NSUTF8StringEncoding error:nil] options:opts error:nil];
        id<MTLFunction> fn = [lib newFunctionWithName:nsFunction];
        id<MTLArgumentEncoder> ae = [fn newArgumentEncoderWithBufferIndex:0];
        id<MTLBuffer> ab = mk_buf(d, ae.encodedLength);
        id<MTLBuffer> target = mk_buf(d, 32 * 4);
        uint32_t *pt = target.contents;
        for (int i = 0; i < 32; i++) pt[i] = TAG((uint32_t)(0x300000 + i));
        [ae setArgumentBuffer:ab offset:0];
        [ae setBuffer:target offset:0 atIndex:0];
        id<MTLBuffer> out = mk_buf(d, 32 * 4);
        if (use_resource) [ce useResource:target usage:MTLResourceUsageRead];
        [ce setBuffer:ab offset:0 atIndex:0];
        [ce setBuffer:out offset:0 atIndex:1];
        [ce dispatchThreads:MTLSizeMake(32, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, 32 * 4); out_n = 32;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, NULL, 0);
    } else if (!strcmp(mode, "mem20_chained")) {
        eff_grid = 32; eff_tg = 32;
        id<MTLBuffer> final = mk_buf(d, 32 * 4);
        uint32_t *pf = final.contents;
        for (int i = 0; i < 32; i++) pf[i] = TAG((uint32_t)(0x700000 + i));
        id<MTLBuffer> mid = mk_buf(d, 8);
        *((uint64_t *)mid.contents) = final.gpuAddress;
        id<MTLBuffer> addrs2 = mk_buf(d, 8);
        *((uint64_t *)addrs2.contents) = mid.gpuAddress;
        id<MTLBuffer> out = mk_buf(d, 32 * 4);
        if (use_resource) { [ce useResource:mid usage:MTLResourceUsageRead]; [ce useResource:final usage:MTLResourceUsageRead]; }
        [ce setBuffer:addrs2 offset:0 atIndex:0];
        [ce setBuffer:out offset:0 atIndex:1];
        [ce dispatchThreads:MTLSizeMake(32, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, 32 * 4); out_n = 32;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, NULL, 0);
    } else if (!strcmp(mode, "cap_direct")) {
        // n data buffers (b1..bn) at indices 1..n, out at index 0; grid=1 (single thread, no gid dependency).
        eff_grid = 1; eff_tg = 1;
        NSMutableArray *backing = [NSMutableArray array];
        for (long k = 1; k <= n; k++) {
            id<MTLBuffer> b = mk_buf(d, 4);
            *((uint32_t *)b.contents) = TAG((uint32_t)k);
            [backing addObject:b];
        }
        id<MTLBuffer> out = mk_buf(d, (NSUInteger)n * 4);
        [ce setBuffer:out offset:0 atIndex:0];
        for (long k = 1; k <= n; k++) [ce setBuffer:backing[(NSUInteger)(k - 1)] offset:0 atIndex:(NSUInteger)k];
        [ce dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
        [ce endEncoding];
        double t1 = monotonic(); arm_watchdog(100, 98);
        [cb commit]; [cb waitUntilCompleted]; disarm_watchdog();
        double dispatch_s = monotonic() - t1;
        memcpy(out_w, out.contents, (size_t)n * 4); out_n = (NSUInteger)n;
        print_record(nsMode, [nsSource lastPathComponent], nsFunction, n, eff_grid, eff_tg, sel_u, k_outlier,
                     use_resource != 0, d, YES, @"", YES, (long)cb.status, cb.error.localizedDescription ?: @"",
                     opts.fastMathEnabled, (long)opts.mathMode, (unsigned long)opts.languageVersion,
                     compile_s, dispatch_s, out_w, out_n, NULL, 0, NULL, 0);
    } else {
        fprintf(stderr, "UNKNOWN_MODE\n");
        return 2;
    }
    if (fflush(stdout) != 0 || ferror(stdout)) { fprintf(stderr, "STDOUT_FLUSH_FAIL\n"); return 5; }
    return 0;
} }
