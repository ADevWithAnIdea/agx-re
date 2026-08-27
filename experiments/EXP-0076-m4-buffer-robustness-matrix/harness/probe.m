// EXP-0076: public-API Metal harness for the buffer robustness matrix probe.
// Runs EXACTLY ONE case per process (fresh device, library, pipeline, buffers,
// queue, command buffer), prints one complete JSON record to stdout, and
// returns. It never inspects compiled shader bytes, archives, command streams,
// or any Apple binary; only public Metal/Foundation API is touched.
//
// Exit discipline (lesson from the quarantined EXP-0072, whose worker thread
// signaled completion before printing its record): this harness is
// deliberately single-threaded and synchronous. The Metal wait, the readbacks,
// the guard checks, the record printf, and the fflush all execute in main()
// in program order, and main() returns only after stdout has been flushed and
// error-checked. There is no worker thread and no completion semaphore, so the
// process cannot exit while the JSON record is still in flight.
//
// Owned-buffer geometry per case (created in this exact order):
//   G1     256 bytes, 0x5A  (guard allocation BEFORE the case buffer)
//   MAIN    64 bytes, F(i) = (0xA5 + 0x1B*i) & 0xFF  (the case buffer)
//   RESULT 160 bytes: [0..64) 0x5A guard, [64..96) zeroed payload,
//                    [96..160) 0xA5 guard
//   G2     256 bytes, 0xC3  (guard allocation AFTER the case buffer)
//   PARAMS  32 bytes (8 uint words)
//
// In-process watchdogs: 120 s library+pipeline compile (exit 97), 100 s
// dispatch+completion (exit 98). Both exits skip the record by design: the
// outer runner owns the timeout/fault record for those cases.
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
static void hex_out(const unsigned char *p, NSUInteger n) {
    for (NSUInteger i = 0; i < n; i++) printf("%02x", (unsigned)p[i]);
}
static BOOL all_bytes(const unsigned char *p, NSUInteger n, unsigned char v) {
    for (NSUInteger i = 0; i < n; i++) if (p[i] != v) return NO;
    return YES;
}
static unsigned char fill_byte(NSUInteger i) { return (unsigned char)((0xA5 + 0x1B * (unsigned long)i) & 0xFF); }

int main(int ac, const char **av) { @autoreleasepool {
    const char *source = NULL, *kernel = NULL, *op = NULL, *store_hex = NULL;
    long width = 0, offset = 0;
    for (int i = 1; i < ac; i++) {
        if (!strcmp(av[i], "--source") && i + 1 < ac) source = av[++i];
        else if (!strcmp(av[i], "--kernel") && i + 1 < ac) kernel = av[++i];
        else if (!strcmp(av[i], "--op") && i + 1 < ac) op = av[++i];
        else if (!strcmp(av[i], "--width") && i + 1 < ac) width = strtol(av[++i], NULL, 10);
        else if (!strcmp(av[i], "--offset") && i + 1 < ac) offset = strtol(av[++i], NULL, 10);
        else if (!strcmp(av[i], "--store-hex") && i + 1 < ac) store_hex = av[++i];
    }
    if (!source || !kernel || !op || !store_hex || width <= 0 || width > 16
        || offset < 0 || offset > 65536 || strlen(store_hex) != 32
        || strspn(store_hex, "0123456789abcdef") != 32) {
        fprintf(stderr, "ARGS_FAIL\n");
        return 2;
    }
    uint32_t words[4] = {0, 0, 0, 0};
    for (int j = 0; j < 4; j++) {
        char w[9];
        memcpy(w, store_hex + 8 * j, 8);   // store_hex is store-value bytes 0..15 in order
        w[8] = 0;
        words[j] = (uint32_t)strtoul(w, NULL, 16);
    }
    NSError *e = nil;
    NSString *msl = [NSString stringWithContentsOfFile:@(source) encoding:NSUTF8StringEncoding error:&e];
    if (!msl) { fprintf(stderr, "SOURCE_FAIL\n"); return 3; }
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { fprintf(stderr, "DEVICE_FAIL\n"); return 3; }

    MTLCompileOptions *opts = [[MTLCompileOptions alloc] init];
    opts.mathMode = MTLMathModeSafe;              // modern precise setting, echoed below
    opts.fastMathEnabled = NO;                    // explicit precise configuration, echoed below
    NSUInteger lang_raw = opts.languageVersion;   // not pinned; default recorded verbatim
    NSInteger math_raw = opts.mathMode;

    double t0 = monotonic();
    arm_watchdog(120, 97);                        // library + compute pipeline compile budget
    id<MTLLibrary> lib = [d newLibraryWithSource:msl options:opts error:&e];
    id<MTLFunction> fn = lib ? [lib newFunctionWithName:@(kernel)] : nil;
    id<MTLComputePipelineState> ps = fn ? [d newComputePipelineStateWithFunction:fn error:&e] : nil;
    disarm_watchdog();
    double compile_s = monotonic() - t0;
    if (!lib) { fprintf(stderr, "LIBRARY_FAIL\n"); return 3; }
    if (!fn) { fprintf(stderr, "FUNCTION_FAIL\n"); return 3; }
    if (!ps) { fprintf(stderr, "PIPELINE_FAIL\n"); return 3; }

    // Owned buffers, exact lengths, created in the frozen guard order.
    id<MTLBuffer> g1 = [d newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLBuffer> main = [d newBufferWithLength:64 options:MTLResourceStorageModeShared];
    id<MTLBuffer> res = [d newBufferWithLength:160 options:MTLResourceStorageModeShared];
    id<MTLBuffer> g2 = [d newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLBuffer> par = [d newBufferWithLength:32 options:MTLResourceStorageModeShared];
    if (!g1 || !main || !res || !g2 || !par) { fprintf(stderr, "BUFFER_FAIL\n"); return 3; }
    unsigned char *pg1 = g1.contents, *pm = main.contents, *pr = res.contents,
                  *pg2 = g2.contents, *pp = par.contents;
    if (!pg1 || !pm || !pr || !pg2 || !pp) { fprintf(stderr, "BUFFER_CONTENTS_FAIL\n"); return 3; }
    memset(pg1, 0x5a, 256);
    for (NSUInteger i = 0; i < 64; i++) pm[i] = fill_byte(i);
    memset(pr, 0x5a, 64); memset(pr + 64, 0, 32); memset(pr + 96, 0xa5, 64);
    memset(pg2, 0xc3, 256);
    uint32_t pw[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    pw[0] = (uint32_t)offset;
    pw[2] = words[0]; pw[3] = words[1]; pw[4] = words[2]; pw[5] = words[3];
    memcpy(pp, pw, 32);

    // Pre-dispatch integrity: what we wrote is what the GPU will see.
    BOOL pre_ok = all_bytes(pg1, 256, 0x5a) && all_bytes(pg2, 256, 0xc3);
    for (NSUInteger i = 0; i < 64 && pre_ok; i++) if (pm[i] != fill_byte(i)) pre_ok = NO;
    pre_ok = pre_ok && all_bytes(pr, 64, 0x5a) && all_bytes(pr + 64, 32, 0x00)
             && all_bytes(pr + 96, 64, 0xa5) && memcmp(pp, pw, 32) == 0;

    id<MTLCommandQueue> cq = [d newCommandQueue];
    if (!cq) { fprintf(stderr, "QUEUE_FAIL\n"); return 3; }
    id<MTLCommandBuffer> cb = [cq commandBuffer];
    if (!cb) { fprintf(stderr, "COMMANDBUFFER_FAIL\n"); return 3; }
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    if (!ce) { fprintf(stderr, "ENCODER_FAIL\n"); return 3; }
    [ce setComputePipelineState:ps];
    [ce setBuffer:main offset:0 atIndex:0];
    [ce setBuffer:par offset:0 atIndex:1];
    [ce setBuffer:res offset:64 atIndex:2];
    [ce dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [ce endEncoding];

    double t1 = monotonic();
    arm_watchdog(100, 98);                        // dispatch + completion budget
    [cb commit];
    [cb waitUntilCompleted];
    disarm_watchdog();
    double dispatch_s = monotonic() - t1;

    BOOL gi1 = all_bytes(pg1, 256, 0x5a), gi2 = all_bytes(pg2, 256, 0xc3);
    BOOL rg0 = all_bytes(pr, 64, 0x5a), rg1 = all_bytes(pr + 96, 64, 0xa5);

    struct utsname u; uname(&u);
    printf("{\"schema\":1,\"kernel\":"); js(@(kernel));
    printf(",\"op\":"); js(@(op));
    printf(",\"width\":%ld,\"off\":%ld,\"device\":", width, offset); js(d.name);
    printf(",\"registry_id\":%llu,\"machine\":", (unsigned long long)d.registryID); js(@(u.machine));
    printf(",\"os\":"); js(NSProcessInfo.processInfo.operatingSystemVersionString);
    printf(",\"fast_math\":%s,\"math_mode_raw\":%ld,\"language_version_raw\":%lu,"
           "\"library_compile_seconds\":%.6f,\"dispatch_seconds\":%.6f",
           opts.fastMathEnabled ? "true" : "false", (long)math_raw, (unsigned long)lang_raw,
           compile_s, dispatch_s);
    printf(",\"command_buffer_status\":%ld,\"error\":", (long)cb.status); js(cb.error.localizedDescription);
    printf(",\"obs\":");
    if (strcmp(op, "store") == 0) {
        printf("\"\"");
    } else {
        NSUInteger ol = width < 4 ? 4 : (NSUInteger)width;
        printf("\"");
        hex_out(pr + 64, ol);
        printf("\"");
    }
    printf(",\"buf_after\":\"");
    hex_out(pm, 64);
    printf("\",\"pre_ok\":%s,\"g1_ok\":%s,\"g2_ok\":%s,\"res_g0_ok\":%s,\"res_g1_ok\":%s}\n",
           pre_ok ? "true" : "false", gi1 ? "true" : "false", gi2 ? "true" : "false",
           rg0 ? "true" : "false", rg1 ? "true" : "false");
    fflush(stdout);
    // the ONLY return path: the record above is fully printed and flushed
    if (fflush(stdout) != 0 || ferror(stdout)) { fprintf(stderr, "STDOUT_FLUSH_FAIL\n"); return 5; }
    return 0;
} }
