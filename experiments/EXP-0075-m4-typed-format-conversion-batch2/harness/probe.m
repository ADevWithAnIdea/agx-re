#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dispatch/dispatch.h>
#include <pthread.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

// EXP-0075 public-Metal compute-store + typed-read harness. One case per
// process. Owns every buffer it inspects. Prints exactly one JSON record to
// stdout. Nothing Apple-authored is ever inspected: no archive, no compiled
// bytes, no command stream, no pointer, no private interface.
//
// PROCESS-EXIT DISCIPLINE (the EXP-0072 quarantine fix, fix 1). EXP-0072 died
// because the worker signalled its dispatch semaphore before printing and
// main treated that signal as done, so the process ended mid-print and every
// record was truncated. Here:
//   1. There is exactly one exit call, in finish(), which holds g_exit_lock
//      while it prints the entire record, then flushes stdout and every other
//      stream, and only then terminates the process. Two threads can never
//      interleave partial records; whoever takes the lock first owns the exit.
//   2. No thread signals completion before its record is durably written: the
//      dispatch-phase semaphore is never signalled, so main cannot observe
//      completion at all. The only semaphore signal in this file marks the
//      boundary between the compile phase and the dispatch phase.
//   3. After both semaphore waits, main blocks forever. It never returns and
//      never terminates the process; the worker owns the exit. A watchdog
//      breach in main is the only other path, and it goes through the same
//      locked finish().
// Exit codes: 0 recorded outcome (including a public-API rejection), 2 bad
// arguments, 3 hard resource failure, 5 compile-phase watchdog, 6 dispatch-
// phase watchdog, 7 caught exception.

static const char *g_case = "", *g_format = "", *g_reader = "";
static int g_texel = 0;

static void js(NSString *s) { NSData *d = [NSJSONSerialization dataWithJSONObject:(s ?: @"") options:NSJSONWritingFragmentsAllowed error:nil]; fwrite(d.bytes, 1, d.length, stdout); }
static void jstr(const char *s) { js(@(s ?: "")); }
static void hex(const unsigned char *p, NSUInteger n) { for (NSUInteger i = 0; i < n; i++) printf("%02x", p[i]); }
static BOOL guard(const unsigned char *p, NSUInteger n, unsigned char v) { for (NSUInteger i = 0; i < n; i++) if (p[i] != v) return NO; return YES; }
static void zerohex(int bytes) { for (int i = 0; i < bytes; i++) printf("00"); }

static NSString *errstr(NSError *e) { return e ? [NSString stringWithFormat:@"%@|%ld|%@", e.domain, (long)e.code, e.localizedDescription] : @""; }

static MTLPixelFormat fmt(void) {
    const char *n = g_format;
    if (!strcmp(n, "R8Unorm")) return MTLPixelFormatR8Unorm;
    if (!strcmp(n, "RG8Unorm")) return MTLPixelFormatRG8Unorm;
    if (!strcmp(n, "R8Snorm")) return MTLPixelFormatR8Snorm;
    if (!strcmp(n, "RG8Snorm")) return MTLPixelFormatRG8Snorm;
    if (!strcmp(n, "RGBA8Snorm")) return MTLPixelFormatRGBA8Snorm;
    if (!strcmp(n, "R16Float")) return MTLPixelFormatR16Float;
    if (!strcmp(n, "RG16Float")) return MTLPixelFormatRG16Float;
    if (!strcmp(n, "R32Float")) return MTLPixelFormatR32Float;
    if (!strcmp(n, "RG11B10Float")) return MTLPixelFormatRG11B10Float;
    if (!strcmp(n, "RGB9E5Float")) return MTLPixelFormatRGB9E5Float;
    if (!strcmp(n, "R16Sint")) return MTLPixelFormatR16Sint;
    if (!strcmp(n, "R16Uint")) return MTLPixelFormatR16Uint;
    if (!strcmp(n, "R32Sint")) return MTLPixelFormatR32Sint;
    if (!strcmp(n, "RGBA16Uint")) return MTLPixelFormatRGBA16Uint;
    return MTLPixelFormatInvalid;
}

// Shared record state; filled in as phases complete.
static NSString *S_library_error = @"", *S_store_error = @"", *S_read_error = @"", *S_texture_error = @"";
static BOOL S_library_ok = NO, S_store_ok = NO, S_read_ok = NO, S_texture_ok = NO;
static long S_cb_status = 0; static NSString *S_cb_error = @"";
static NSString *S_device = @"";
static long S_msl_default = 0;
static unsigned char *S_backing = NULL, *S_result = NULL;

static void prefix(const char *status) {
    printf("{\"case\":"); jstr(g_case);
    printf(",\"format\":"); jstr(g_format);
    printf(",\"texel_bytes\":%d,\"reader\":", g_texel); jstr(g_reader);
    printf(",\"usage_flags\":\"MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead\"");
    printf(",\"storage_mode\":\"MTLStorageModeShared\",\"fast_math_enabled\":false");
    printf(",\"msl_language_version\":%ld", S_msl_default);
    printf(",\"status\":"); jstr(status);
    printf(",\"library_ok\":%s,\"library_error\":", S_library_ok ? "true" : "false"); js(S_library_error);
    printf(",\"store_pipeline_ok\":%s,\"store_pipeline_error\":", S_store_ok ? "true" : "false"); js(S_store_error);
    printf(",\"read_pipeline_ok\":%s,\"read_pipeline_error\":", S_read_ok ? "true" : "false"); js(S_read_error);
    printf(",\"texture_ok\":%s,\"texture_error\":", S_texture_ok ? "true" : "false"); js(S_texture_error);
    printf(",\"command_buffer_status\":%ld,\"command_buffer_error\":", S_cb_status); js(S_cb_error);
    printf(",\"device\":"); js(S_device);
}
static void tail(void) {
    struct utsname u; uname(&u);
    printf(",\"machine\":"); js(@(u.machine));
    printf(",\"os\":"); js(NSProcessInfo.processInfo.operatingSystemVersionString);
    if (S_backing && S_texture_ok) {
        printf(",\"physical_texel_hex\":\""); hex(S_backing + 64, g_texel); printf("\"");
        printf(",\"backing_hex\":\""); hex(S_backing, 384); printf("\"");
        const unsigned char *c = S_result;
        const uint32_t *w = (const uint32_t *)(c + 64);
        printf(",\"result_hex\":\""); hex(c, 144); printf("\"");
        printf(",\"read_words_le\":[%u,%u,%u,%u]", w[0], w[1], w[2], w[3]);
        printf(",\"backing_prefix_guard\":%s,\"backing_suffix_guard\":%s", guard(S_backing, 64, 0x5a) ? "true" : "false", guard(S_backing + 320, 64, 0xa5) ? "true" : "false");
        printf(",\"result_prefix_guard\":%s,\"result_suffix_guard\":%s", guard(c, 64, 0x5a) ? "true" : "false", guard(c + 80, 64, 0xa5) ? "true" : "false");
    } else {
        printf(",\"physical_texel_hex\":\""); zerohex(g_texel); printf("\"");
        printf(",\"backing_hex\":\"");
        for (int i = 0; i < 64; i++) printf("5a");
        for (int i = 0; i < 256; i++) printf("00");
        for (int i = 0; i < 64; i++) printf("a5");
        printf("\",\"result_hex\":\"");
        for (int i = 0; i < 64; i++) printf("5a");
        for (int i = 0; i < 16; i++) printf("00");
        for (int i = 0; i < 64; i++) printf("a5");
        printf("\",\"read_words_le\":[0,0,0,0]");
        printf(",\"backing_prefix_guard\":true,\"backing_suffix_guard\":true,\"result_prefix_guard\":true,\"result_suffix_guard\":true");
    }
    printf("}\n");
}

static pthread_mutex_t g_exit_lock = PTHREAD_MUTEX_INITIALIZER;

static void finish(const char *status, int code) {
    pthread_mutex_lock(&g_exit_lock); // the sole printer from here on
    prefix(status);
    tail();
    fflush(stdout);                   // the record leaves this thread first
    fflush(NULL);
    exit(code);                       // the sole process exit; the lock is intentionally never released
}

static dispatch_semaphore_t sem_compile, sem_dispatch;

static void worker(NSString *msl) {
    NSError *e = nil;
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { S_device = @""; finish("device_failed", 3); }
    S_device = d.name;
    // Public environment read: the compile options this host hands out before
    // anything is set. Recorded per case as the MSL language-version datum.
    MTLCompileOptions *peek = [MTLCompileOptions new];
    S_msl_default = (long)peek.languageVersion;
    MTLCompileOptions *opt = [MTLCompileOptions new];
    opt.fastMathEnabled = NO; // frozen: fast math disabled
    id<MTLLibrary> lib = [d newLibraryWithSource:msl options:opt error:&e];
    S_library_ok = lib != nil; S_library_error = errstr(e);
    if (!lib) finish("library_failed", 3);
    NSString *storeName = [@"s_" stringByAppendingString:@(g_case)];
    NSString *readName = [@"k_read_" stringByAppendingString:@(g_reader)];
    id<MTLFunction> sf = [lib newFunctionWithName:storeName];
    id<MTLFunction> rf = [lib newFunctionWithName:readName];
    if (!sf || !rf) { S_store_ok = NO; S_read_ok = NO; finish("function_missing", 3); }
    e = nil; id<MTLComputePipelineState> sp = [d newComputePipelineStateWithFunction:sf error:&e];
    S_store_ok = sp != nil; S_store_error = errstr(e);
    if (!sp) finish("store_pipeline_rejected", 0);
    e = nil; id<MTLComputePipelineState> rp = [d newComputePipelineStateWithFunction:rf error:&e];
    S_read_ok = rp != nil; S_read_error = errstr(e);
    if (!rp) finish("read_pipeline_rejected", 0);
    id<MTLBuffer> rb = [d newBufferWithLength:384 options:MTLResourceStorageModeShared];
    id<MTLBuffer> rres = [d newBufferWithLength:144 options:MTLResourceStorageModeShared];
    if (!rb || !rres) finish("buffer_failed", 3);
    unsigned char *r = rb.contents, *c = rres.contents;
    if (!r || !c) finish("buffer_failed", 3);
    memset(r, 0x5a, 64); memset(r + 64, 0, 256); memset(r + 320, 0xa5, 64);
    memset(c, 0x5a, 64); memset(c + 64, 0, 16); memset(c + 80, 0xa5, 64);
    S_backing = r; S_result = c;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt() width:1 height:1 mipmapped:NO];
    if (!td) finish("texture_failed", 3);
    td.storageMode = MTLStorageModeShared;
    td.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
    id<MTLTexture> t = [rb newTextureWithDescriptor:td offset:64 bytesPerRow:256];
    S_texture_ok = t != nil;
    if (!t) finish("texture_rejected", 0);
    dispatch_semaphore_signal(sem_compile); // compile phase complete; NOT a completion signal

    id<MTLCommandQueue> cq = [d newCommandQueue];
    if (!cq) finish("queue_failed", 3);
    id<MTLCommandBuffer> q = [cq commandBuffer];
    if (!q) finish("command_resource_failed", 3);
    id<MTLComputeCommandEncoder> we = [q computeCommandEncoder];
    [we setComputePipelineState:sp]; [we setTexture:t atIndex:0];
    [we dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [we endEncoding];
    id<MTLComputeCommandEncoder> re = [q computeCommandEncoder];
    [re setComputePipelineState:rp]; [re setTexture:t atIndex:0]; [re setBuffer:rres offset:64 atIndex:0];
    [re dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [re endEncoding];
    [q commit]; [q waitUntilCompleted];
    S_cb_status = (long)q.status; S_cb_error = q.error.localizedDescription;
    if (q.status != MTLCommandBufferStatusCompleted) finish("command_buffer_error", 0);
    // No dispatch-phase signal exists: the record below, printed and flushed
    // inside finish, is the only completion evidence, and the exit inside
    // finish is the only way this process ends.
    finish("ok", 0);
}

int main(int ac, const char **av) { @autoreleasepool {
    const char *source = NULL;
    for (int i = 1; i < ac; i++) {
        if (!strcmp(av[i], "--source") && i + 1 < ac) source = av[++i];
        else if (!strcmp(av[i], "--case") && i + 1 < ac) g_case = av[++i];
        else if (!strcmp(av[i], "--format") && i + 1 < ac) g_format = av[++i];
        else if (!strcmp(av[i], "--texel-bytes") && i + 1 < ac) g_texel = atoi(av[++i]);
        else if (!strcmp(av[i], "--reader") && i + 1 < ac) g_reader = av[++i];
    }
    if (!source || !g_case[0] || !g_format[0] || g_texel <= 0 || g_texel > 8) return 2;
    if (strcmp(g_reader, "float") && strcmp(g_reader, "int") && strcmp(g_reader, "uint")) return 2;
    if (fmt() == MTLPixelFormatInvalid) return 2;
    NSError *e = nil;
    NSString *msl = [NSString stringWithContentsOfFile:@(source) encoding:NSUTF8StringEncoding error:&e];
    if (!msl) { fprintf(stderr, "SOURCE_FAIL\n"); return 3; }
    sem_compile = dispatch_semaphore_create(0);
    sem_dispatch = dispatch_semaphore_create(0);
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        @try { worker(msl); }
        @catch (NSException *ex) { finish("exception", 7); }
    });
    if (dispatch_semaphore_wait(sem_compile, dispatch_time(DISPATCH_TIME_NOW, 120LL * NSEC_PER_SEC))) {
        fprintf(stderr, "compile-phase watchdog fired\n");
        finish("compile_timeout", 5);
    }
    if (dispatch_semaphore_wait(sem_dispatch, dispatch_time(DISPATCH_TIME_NOW, 300LL * NSEC_PER_SEC))) {
        fprintf(stderr, "dispatch-phase watchdog fired\n");
        finish("dispatch_timeout", 6);
    }
    // Both phase waits returned without a watchdog breach. main must never
    // end the process: block forever and let the worker finish it.
    for (;;) pause();
} }
