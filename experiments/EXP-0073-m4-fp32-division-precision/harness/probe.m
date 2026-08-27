// EXP-0073: public-API Metal harness for the FP32 division precision probe.
// Compiles the authored MSL at runtime with MTLCompileOptions.fastMathEnabled
// explicitly NO, uploads (uint32 a_bits, uint32 b_bits) pairs from a binary
// file into an owned shared buffer, dispatches one compute thread per pair,
// and writes the raw uint32 result bits to a JSONL file. It never inspects
// compiled shader bytes, archives, command streams, or any Apple binary.
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
static BOOL all_bytes(const unsigned char *p, NSUInteger n, unsigned char v) {
    for (NSUInteger i = 0; i < n; i++) if (p[i] != v) return NO;
    return YES;
}

int main(int ac, const char **av) { @autoreleasepool {
    const char *source = NULL, *cases = NULL, *out = NULL; unsigned long n = 0;
    for (int i = 1; i < ac; i++) {
        if (!strcmp(av[i], "--source") && i + 1 < ac) source = av[++i];
        else if (!strcmp(av[i], "--cases") && i + 1 < ac) cases = av[++i];
        else if (!strcmp(av[i], "--out") && i + 1 < ac) out = av[++i];
        else if (!strcmp(av[i], "--n") && i + 1 < ac) n = strtoul(av[++i], NULL, 10);
    }
    if (!source || !cases || !out || n == 0 || n > 1000000) { fprintf(stderr, "ARGS_FAIL\n"); return 2; }
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
    id<MTLFunction> fn = lib ? [lib newFunctionWithName:@"k_fdiv"] : nil;
    id<MTLComputePipelineState> ps = fn ? [d newComputePipelineStateWithFunction:fn error:&e] : nil;
    disarm_watchdog();
    double compile_s = monotonic() - t0;
    if (!lib) { fprintf(stderr, "LIBRARY_FAIL\n"); return 3; }
    if (!fn) { fprintf(stderr, "FUNCTION_FAIL\n"); return 3; }
    if (!ps) { fprintf(stderr, "PIPELINE_FAIL\n"); return 3; }

    NSUInteger pin = 8 * (NSUInteger)n, pout = 4 * (NSUInteger)n;
    id<MTLBuffer> bi = [d newBufferWithLength:64 + pin + 64 options:MTLResourceStorageModeShared];
    id<MTLBuffer> bo = [d newBufferWithLength:64 + pout + 64 options:MTLResourceStorageModeShared];
    if (!bi || !bo) { fprintf(stderr, "BUFFER_FAIL\n"); return 3; }
    unsigned char *pi = bi.contents, *po = bo.contents;
    if (!pi || !po) { fprintf(stderr, "BUFFER_CONTENTS_FAIL\n"); return 3; }
    memset(pi, 0x5a, 64); memset(pi + 64, 0, pin); memset(pi + 64 + pin, 0xa5, 64);
    memset(po, 0x5a, 64); memset(po + 64, 0, pout); memset(po + 64 + pout, 0xa5, 64);
    FILE *cf = fopen(cases, "rb");
    if (!cf || fread(pi + 64, 1, pin, cf) != pin) { if (cf) fclose(cf); fprintf(stderr, "CASES_FAIL\n"); return 3; }
    fclose(cf);

    id<MTLCommandQueue> cq = [d newCommandQueue];
    if (!cq) { fprintf(stderr, "QUEUE_FAIL\n"); return 3; }
    id<MTLCommandBuffer> cb = [cq commandBuffer];
    if (!cb) { fprintf(stderr, "COMMANDBUFFER_FAIL\n"); return 3; }
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    if (!ce) { fprintf(stderr, "ENCODER_FAIL\n"); return 3; }
    [ce setComputePipelineState:ps];
    [ce setBuffer:bi offset:64 atIndex:0];
    [ce setBuffer:bo offset:64 atIndex:1];
    [ce dispatchThreads:MTLSizeMake((NSUInteger)n, 1, 1) threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
    [ce endEncoding];

    double t1 = monotonic();
    arm_watchdog(300, 98);                        // dispatch + completion budget
    [cb commit];
    [cb waitUntilCompleted];
    disarm_watchdog();
    double dispatch_s = monotonic() - t1;

    BOOL gi0 = all_bytes(pi, 64, 0x5a), gi1 = all_bytes(pi + 64 + pin, 64, 0xa5);
    BOOL go0 = all_bytes(po, 64, 0x5a), go1 = all_bytes(po + 64 + pout, 64, 0xa5);

    FILE *of = fopen(out, "w");
    BOOL wrote = of != NULL;
    if (of) {
        const uint32_t *rin = (const uint32_t *)(const void *)(pi + 64);
        const uint32_t *rut = (const uint32_t *)(const void *)(po + 64);
        for (NSUInteger i = 0; i < (NSUInteger)n; i++) {
            if (fprintf(of, "{\"i\":%lu,\"a\":\"0x%08x\",\"b\":\"0x%08x\",\"r\":\"0x%08x\"}\n",
                        (unsigned long)i, (unsigned)rin[2 * i], (unsigned)rin[2 * i + 1],
                        (unsigned)rut[i]) < 0) { wrote = NO; break; }
        }
        if (fclose(of) != 0) wrote = NO;
    }

    struct utsname u; uname(&u);
    printf("{\"schema\":1,\"n\":%lu,\"device\":", (unsigned long)n); js(d.name);
    printf(",\"registry_id\":%llu,\"machine\":", (unsigned long long)d.registryID); js(@(u.machine));
    printf(",\"os\":"); js(NSProcessInfo.processInfo.operatingSystemVersionString);
    printf(",\"fast_math\":%s,\"math_mode_raw\":%ld,\"language_version_raw\":%lu,\"library_compile_seconds\":%.6f,\"dispatch_seconds\":%.6f",
           opts.fastMathEnabled ? "true" : "false", (long)math_raw, (unsigned long)lang_raw, compile_s, dispatch_s);
    printf(",\"command_buffer_status\":%ld,\"error\":", (long)cb.status); js(cb.error.localizedDescription);
    printf(",\"in_prefix_guard\":%s,\"in_suffix_guard\":%s,\"out_prefix_guard\":%s,\"out_suffix_guard\":%s,\"results_written\":%s}\n",
           gi0 ? "true" : "false", gi1 ? "true" : "false", go0 ? "true" : "false",
           go1 ? "true" : "false", wrote ? "true" : "false");
    fflush(stdout);
    return (cb.status == MTLCommandBufferStatusCompleted && gi0 && gi1 && go0 && go1 && wrote) ? 0 : 4;
} }
