// EXP-0103: generic public-API Metal harness.
// Loads kernels/probe.metal at runtime (newLibraryWithSource:), picks ONE
// named kernel (--fn), uploads N fixed-shape 16-byte input records
// (struct Rec { uint r0,r1,r2,r3; }) from a binary file, dispatches one
// compute thread per record, waits for completion, and writes one JSONL
// line per record with the four raw output words as hex. Never inspects
// compiled shader bytes, archives, command streams, or any Apple binary.
//
// Design pattern (guard bytes, watchdog alarms, single-threaded synchronous
// exit discipline, JSON string escaping via NSJSONSerialization) adopted
// unchanged from experiments/EXP-0074-m4-fp32-division-precision/harness/probe.m.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <sys/utsname.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <stdint.h>
#include <time.h>

typedef struct { uint32_t r0, r1, r2, r3; } Rec;

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
    const char *source = NULL, *fn = NULL, *cases = NULL, *out = NULL;
    unsigned long n = 0;
    BOOL fastmath = NO;
    for (int i = 1; i < ac; i++) {
        if (!strcmp(av[i], "--source") && i + 1 < ac) source = av[++i];
        else if (!strcmp(av[i], "--fn") && i + 1 < ac) fn = av[++i];
        else if (!strcmp(av[i], "--cases") && i + 1 < ac) cases = av[++i];
        else if (!strcmp(av[i], "--out") && i + 1 < ac) out = av[++i];
        else if (!strcmp(av[i], "--n") && i + 1 < ac) n = strtoul(av[++i], NULL, 10);
        else if (!strcmp(av[i], "--fastmath") && i + 1 < ac) fastmath = !strcmp(av[++i], "yes");
    }
    if (!source || !fn || !cases || !out || n == 0 || n > 2000000) { fprintf(stderr, "ARGS_FAIL\n"); return 2; }
    NSError *e = nil;
    NSString *msl = [NSString stringWithContentsOfFile:@(source) encoding:NSUTF8StringEncoding error:&e];
    if (!msl) { fprintf(stderr, "SOURCE_FAIL\n"); return 3; }
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { fprintf(stderr, "DEVICE_FAIL\n"); return 3; }

    MTLCompileOptions *opts = [[MTLCompileOptions alloc] init];
    opts.mathMode = fastmath ? MTLMathModeFast : MTLMathModeSafe;
    opts.fastMathEnabled = fastmath;
    NSUInteger lang_raw = opts.languageVersion;
    NSInteger math_raw = opts.mathMode;

    double t0 = monotonic();
    arm_watchdog(120, 97);
    id<MTLLibrary> lib = [d newLibraryWithSource:msl options:opts error:&e];
    id<MTLFunction> fnobj = lib ? [lib newFunctionWithName:@(fn)] : nil;
    id<MTLComputePipelineState> ps = fnobj ? [d newComputePipelineStateWithFunction:fnobj error:&e] : nil;
    disarm_watchdog();
    double compile_s = monotonic() - t0;
    if (!lib) { fprintf(stderr, "LIBRARY_FAIL: %s\n", e.localizedDescription.UTF8String ?: ""); return 3; }
    if (!fnobj) { fprintf(stderr, "FUNCTION_FAIL: %s\n", fn); return 3; }
    if (!ps) { fprintf(stderr, "PIPELINE_FAIL\n"); return 3; }

    NSUInteger pin = sizeof(Rec) * (NSUInteger)n, pout = sizeof(Rec) * (NSUInteger)n;
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
    NSUInteger tg = ps.maxTotalThreadsPerThreadgroup < 64 ? ps.maxTotalThreadsPerThreadgroup : 64;
    if (tg == 0) tg = 1;
    [ce dispatchThreads:MTLSizeMake((NSUInteger)n, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
    [ce endEncoding];

    double t1 = monotonic();
    arm_watchdog(300, 98);
    [cb commit];
    [cb waitUntilCompleted];
    disarm_watchdog();
    double dispatch_s = monotonic() - t1;

    BOOL gi0 = all_bytes(pi, 64, 0x5a), gi1 = all_bytes(pi + 64 + pin, 64, 0xa5);
    BOOL go0 = all_bytes(po, 64, 0x5a), go1 = all_bytes(po + 64 + pout, 64, 0xa5);

    FILE *of = fopen(out, "w");
    BOOL wrote = of != NULL;
    if (of) {
        const Rec *rout = (const Rec *)(const void *)(po + 64);
        for (NSUInteger i = 0; i < (NSUInteger)n; i++) {
            if (fprintf(of, "{\"i\":%lu,\"r0\":\"0x%08x\",\"r1\":\"0x%08x\",\"r2\":\"0x%08x\",\"r3\":\"0x%08x\"}\n",
                        (unsigned long)i, rout[i].r0, rout[i].r1, rout[i].r2, rout[i].r3) < 0) { wrote = NO; break; }
        }
        if (fclose(of) != 0) wrote = NO;
    }

    struct utsname u; uname(&u);
    printf("{\"schema\":1,\"fn\":"); js(@(fn));
    printf(",\"n\":%lu,\"device\":", (unsigned long)n); js(d.name);
    printf(",\"registry_id\":%llu,\"machine\":", (unsigned long long)d.registryID); js(@(u.machine));
    printf(",\"os\":"); js(NSProcessInfo.processInfo.operatingSystemVersionString);
    printf(",\"fast_math\":%s,\"math_mode_raw\":%ld,\"language_version_raw\":%lu,\"library_compile_seconds\":%.6f,\"dispatch_seconds\":%.6f",
           opts.fastMathEnabled ? "true" : "false", (long)math_raw, (unsigned long)lang_raw, compile_s, dispatch_s);
    printf(",\"command_buffer_status\":%ld,\"error\":", (long)cb.status); js(cb.error.localizedDescription);
    printf(",\"in_prefix_guard\":%s,\"in_suffix_guard\":%s,\"out_prefix_guard\":%s,\"out_suffix_guard\":%s,\"results_written\":%s}\n",
           gi0 ? "true" : "false", gi1 ? "true" : "false", go0 ? "true" : "false",
           go1 ? "true" : "false", wrote ? "true" : "false");
    fflush(stdout);
    if (fflush(stdout) != 0 || ferror(stdout)) { fprintf(stderr, "STDOUT_FLUSH_FAIL\n"); return 5; }
    return (cb.status == MTLCommandBufferStatusCompleted && gi0 && gi1 && go0 && go1 && wrote) ? 0 : 4;
} }
