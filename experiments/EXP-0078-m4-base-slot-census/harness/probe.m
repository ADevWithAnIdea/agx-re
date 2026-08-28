// EXP-0078: public-API Metal harness for the device-buffer base-slot census.
// Runs EXACTLY ONE case per process (fresh device, library, pipeline, buffers,
// queue, command buffer), prints one complete JSON record to stdout, and
// returns. It never inspects compiled shader bytes, archives, command streams,
// or any Apple binary; only public Metal/Foundation API is touched. The
// archive it loads was serialized by tools/shdump from OUR OWN MSL and may
// have one byte spliced out-of-band by the runner (our own bytes).
//
// Exit discipline (lesson from the quarantined EXP-0072, whose worker thread
// signaled completion before printing its record): this harness is
// deliberately single-threaded and synchronous. The Metal wait, the readbacks,
// the record printf, and the fflush all execute in main() in program order,
// and main() returns only after stdout has been flushed and error-checked.
// There is no worker thread and no completion semaphore, so the process
// cannot exit while the JSON record is still in flight.
//
// Binding layout (the harness IS the binding-layout capture: it constructs
// the index -> contents mapping itself and echoes it in every record):
//   MSL buffer index k in 0..30 is bound to a 64-byte shared MTLBuffer whose
//   word w holds the frozen fill P(k,w) = 0xC0DE0000 | (k<<8) | w, EXCEPT
//   buffer 30 (idxbuf), whose word 0 is the frozen probe element index 5
//   (words 1..15 still P(30,w)). The kernel writes results into buffer 0.
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

#define NBIND 31          /* MSL buffer indices 0..30 */
#define WORDS 16          /* 64 bytes per bound buffer */
#define OUTBYTES 128      /* out buffer dump: 32 words */

static long g_idxbuf = 30;   /* MSL index of this kernel's idxbuf binding */
static uint32_t fillword(int k, int w) {
    if (k == g_idxbuf && w == 0) return 5u;      /* frozen probe element index */
    return (uint32_t)(0xC0DE0000u | ((uint32_t)k << 8) | (uint32_t)w);
}

static void js(NSString *s) {
    NSData *d = [NSJSONSerialization dataWithJSONObject:(s ?: @"") options:NSJSONWritingFragmentsAllowed error:nil];
    fwrite(d.bytes, 1, d.length, stdout);
}
static void hex_out(const unsigned char *p, NSUInteger n) {
    for (NSUInteger i = 0; i < n; i++) printf("%02x", (unsigned)p[i]);
}

static void die(int code, const char *stage, NSError *err) {
    // Infrastructure failure (not a GPU-behavior observation): print a
    // minimal non-record marker; the runner maps it to proc_fail.
    fprintf(stderr, "HARNESS_FAIL %s", stage);
    if (err) fprintf(stderr, ": %s", [[err localizedDescription] UTF8String]);
    fprintf(stderr, "\n");
    fflush(stderr);
    exit(code);
}

int main(int ac, const char **av) { @autoreleasepool {
    const char *source = NULL, *fnname = NULL, *archive = NULL, *op = NULL;
    long slot = -1, splice_abs_off = -1, idxbuf = 30;
    for (int i = 1; i < ac; i++) {
        if (!strcmp(av[i], "--source") && i + 1 < ac) source = av[++i];
        else if (!strcmp(av[i], "--function") && i + 1 < ac) fnname = av[++i];
        else if (!strcmp(av[i], "--archive") && i + 1 < ac) archive = av[++i];
        else if (!strcmp(av[i], "--op") && i + 1 < ac) op = av[++i];
        else if (!strcmp(av[i], "--slot") && i + 1 < ac) slot = strtol(av[++i], NULL, 0);
        else if (!strcmp(av[i], "--splice-abs-off") && i + 1 < ac) splice_abs_off = strtol(av[++i], NULL, 0);
        else if (!strcmp(av[i], "--idxbuf") && i + 1 < ac) idxbuf = strtol(av[++i], NULL, 0);
        else { fprintf(stderr, "bad arg %s\n", av[i]); return 2; }
    }
    if (!source || !fnname || !archive || !op) { fprintf(stderr, "need --source --function --archive --op\n"); return 2; }

    struct utsname u;
    NSString *os = @"?";
    if (uname(&u) == 0) os = [NSString stringWithFormat:@"%s %s", u.sysname, u.release];

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) die(3, "no-device", nil);

    NSError *err = nil;
    double t0 = monotonic();

    // --- 1. Compile OUR source (identity for the archive lookup). ----------
    arm_watchdog(120, 97);
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:source]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) die(3, "read-source", err);
    MTLCompileOptions *opts = [MTLCompileOptions new];
    [opts setFastMathEnabled:YES];       // matches the shdump default that built the archive
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
    if (!lib) die(3, "library", err);
    id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:fnname]];
    if (!fn) die(3, "function", nil);

    // --- 2. Load the (runner-spliced) serialized archive. -------------------
    MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
    [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archive]]];
    id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
    if (!arc) die(3, "archive", err);

    // --- 3. Force the pipeline from the archived machine code. -------------
    MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
    [pdesc setComputeFunction:fn];
    [pdesc setBinaryArchives:@[arc]];
    id<MTLComputePipelineState> pso =
        [dev newComputePipelineStateWithDescriptor:pdesc
                                           options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                        reflection:nil
                                             error:&err];
    if (!pso) die(4, "pipeline-miss", err);
    double compile_s = monotonic() - t0;
    disarm_watchdog();

    // --- 4. Buffers: the binding layout, filled with the frozen pattern. ---
    id<MTLBuffer> bufs[NBIND];
    uint32_t model[NBIND][WORDS];
    BOOL pre_ok = YES;
    g_idxbuf = idxbuf;
    for (int k = 0; k < NBIND; k++) {
        for (int w = 0; w < WORDS; w++) model[k][w] = fillword(k, w);
        bufs[k] = [dev newBufferWithBytes:model[k] length:sizeof(model[k])
                                   options:MTLResourceStorageModeShared];
        if (!bufs[k]) die(3, "buffer", nil);
        if (memcmp([bufs[k] contents], model[k], sizeof(model[k])) != 0) pre_ok = NO;
    }

    // --- 5. Dispatch one thread, synchronously. ----------------------------
    id<MTLCommandQueue> queue = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    for (int k = 0; k < NBIND; k++) [enc setBuffer:bufs[k] offset:0 atIndex:(NSUInteger)k];
    [enc dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [enc endEncoding];
    double t1 = monotonic();
    arm_watchdog(100, 98);
    [cb commit];
    [cb waitUntilCompleted];
    disarm_watchdog();
    double dispatch_s = monotonic() - t1;

    long cb_status = (long)[cb status];
    NSString *cb_err = @"";
    if (cb_status == MTLCommandBufferStatusError && [cb error] != nil)
        cb_err = [NSString stringWithFormat:@"%@", [cb error]];

    // --- 6. One complete JSON record (witness + every bound buffer). --------
    printf("{");
    printf("\"schema\":1,");
    printf("\"kernel\":\"%s\",", fnname);
    printf("\"op\":\"%s\",", op);
    printf("\"slot\":%ld,", slot);
    printf("\"splice_abs_off\":%ld,", splice_abs_off);
    printf("\"idxbuf\":%ld,", idxbuf);
    printf("\"device\":\"%s\",", [[dev name] UTF8String]);
    printf("\"registry_id\":%llu,", (unsigned long long)[dev registryID]);
    printf("\"machine\":\"arm64\",");
    printf("\"os\":\"%s\",", [os UTF8String]);
    printf("\"fast_math\":true,");
    printf("\"math_mode_raw\":%ld,", (long)opts.mathMode);
    printf("\"language_version_raw\":%lu,", (unsigned long)opts.languageVersion);
    printf("\"library_compile_seconds\":%.6f,", compile_s);
    printf("\"dispatch_seconds\":%.6f,", dispatch_s);
    printf("\"command_buffer_status\":%ld,", cb_status);
    printf("\"error\":");
    js(cb_err);
    printf(",\"pre_ok\":%s,", pre_ok ? "true" : "false");
    printf("\"out_hex\":\"");
    hex_out((const unsigned char *)[bufs[0] contents], OUTBYTES);
    printf("\",\"bufs_hex\":{");
    for (int k = 0; k < NBIND; k++) {
        printf("\"%d\":\"", k);
        hex_out((const unsigned char *)[bufs[k] contents], sizeof(model[k]));
        printf("\"%s", k + 1 < NBIND ? "," : "");
    }
    printf("}}\n");

    if (fflush(stdout) != 0 || ferror(stdout)) { fprintf(stderr, "STDOUT_FLUSH_FAIL\n"); return 5; }
    return 0;
}}
