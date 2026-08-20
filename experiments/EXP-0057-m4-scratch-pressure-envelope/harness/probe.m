// EXP-0057: public-Metal execution/readback probe.  No IOKit or BO access.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { TOTAL_THREADS = 32768, GUARD = 64 };

static uint32_t rotl5(uint32_t x) { return (x << 5) | (x >> 27); }
static uint32_t initial(uint32_t gid) { return gid * 0x45d9f3bu + 0x1234567u; }
static uint32_t expected(uint32_t seed, uint32_t words) {
    uint32_t acc = seed ^ 0xa5a5a5a5u;
    if (!words) return acc;
    uint32_t *lanes = calloc(words, sizeof(*lanes));
    if (!lanes) abort();
    for (uint32_t i = 0; i < words; ++i)
        lanes[i] = (seed + i * 0x9e3779b9u) ^ ((i + 1u) * 0x85ebca6bu);
    for (uint32_t pass = 0; pass < 3; ++pass)
        for (uint32_t i = 0; i < words; ++i) {
            uint32_t j = (i * 13u + pass * 7u + 1u) % words;
            lanes[i] = (lanes[i] ^ lanes[j]) + 0x27d4eb2du + pass;
        }
    for (uint32_t i = 0; i < words; ++i) acc = rotl5(acc) ^ lanes[i];
    free(lanes); return acc;
}

static void print_json_string(NSString *value) {
    NSData *d = [NSJSONSerialization dataWithJSONObject:@[value ?: @""] options:0 error:nil];
    const char *s = d.bytes; size_t n = d.length;
    fwrite(s + 1, 1, n - 2, stdout);
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        const char *source_path = NULL; unsigned words = 0, tg = 0;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--source") && i + 1 < argc) source_path = argv[++i];
            else if (!strcmp(argv[i], "--words") && i + 1 < argc) words = (unsigned)strtoul(argv[++i], 0, 10);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) tg = (unsigned)strtoul(argv[++i], 0, 10);
        }
        if (!source_path || (tg != 32 && tg != 256) || words > 4096) return 2;
        NSError *error = nil;
        NSString *source = [NSString stringWithContentsOfFile:@(source_path) encoding:NSUTF8StringEncoding error:&error];
        if (!source) { printf("{\"phase\":\"read\",\"error\":"); print_json_string(error.localizedDescription); puts("}"); return 10; }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { puts("{\"phase\":\"device\",\"error\":\"no-default-device\"}"); return 11; }
        MTLCompileOptions *opts = [MTLCompileOptions new]; opts.fastMathEnabled = NO;
        id<MTLLibrary> lib = [dev newLibraryWithSource:source options:opts error:&error];
        if (!lib) { printf("{\"phase\":\"compile\",\"device\":"); print_json_string(dev.name); printf(",\"error\":"); print_json_string(error.localizedDescription); puts("}"); return 12; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"k_main"];
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&error];
        if (!pso) { printf("{\"phase\":\"pipeline\",\"error\":"); print_json_string(error.localizedDescription); puts("}"); return 13; }
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        NSUInteger payload = TOTAL_THREADS * sizeof(uint32_t), full = GUARD + payload + GUARD;
        id<MTLBuffer> out = [dev newBufferWithLength:full options:MTLResourceStorageModeShared];
        id<MTLBuffer> in = [dev newBufferWithLength:payload options:MTLResourceStorageModeShared];
        if (!out || !in) { puts("{\"phase\":\"allocation\",\"error\":\"public-buffer-allocation\"}"); return 14; }
        memset(out.contents, 0x5a, GUARD); memset((uint8_t *)out.contents + GUARD + payload, 0xa5, GUARD);
        uint32_t *ip = in.contents; for (uint32_t i = 0; i < TOTAL_THREADS; ++i) ip[i] = initial(i);
        id<MTLCommandBuffer> cb = [queue commandBuffer]; id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso]; [enc setBuffer:out offset:GUARD atIndex:0]; [enc setBuffer:in offset:0 atIndex:1];
        [enc dispatchThreads:MTLSizeMake(TOTAL_THREADS, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)]; [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
        BOOL prefix = YES, suffix = YES, exact = cb.status == MTLCommandBufferStatusCompleted;
        uint8_t *op = out.contents; for (unsigned i = 0; i < GUARD; ++i) { prefix &= op[i] == 0x5a; suffix &= op[GUARD + payload + i] == 0xa5; }
        uint32_t *values = (uint32_t *)(op + GUARD);
        for (uint32_t i = 0; i < TOTAL_THREADS && exact; ++i) exact &= values[i] == expected(ip[i], words);
        printf("{\"phase\":\"execution\",\"device\":"); print_json_string(dev.name);
        printf(",\"status\":%ld,\"tg\":%u,\"threads\":%u,\"words\":%u,\"prefix_guard\":%s,\"suffix_guard\":%s,\"exact\":%s,\"error\":", (long)cb.status, tg, TOTAL_THREADS, words, prefix ? "true" : "false", suffix ? "true" : "false", exact ? "true" : "false");
        print_json_string(cb.error.localizedDescription); puts("}");
        return exact && prefix && suffix ? 0 : 15;
    }
}
