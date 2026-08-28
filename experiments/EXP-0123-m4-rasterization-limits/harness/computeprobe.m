// computeprobe.m -- EXP-0123 compute-side limit probe (threadgroup size,
// dynamic threadgroup memory, SIMD/subgroup width). Companion to
// rasterprobe.m; same JSON-in-file / JSON-out-stdout protocol and the same
// clean-room posture (OWN-SHADER + HW-PROBE, public Metal API only).
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -O1 -o computeprobe computeprobe.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static NSMutableDictionary *gResult;
static void setStatus(NSString *s) { gResult[@"status"] = s; }
static void setErrFromNSError(NSError *err) {
    if (err) {
        NSString *flat = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        gResult[@"error"] = flat;
    }
}
static void emitAndExit(int code) {
    NSError *jerr = nil;
    NSData *d = [NSJSONSerialization dataWithJSONObject:gResult options:0 error:&jerr];
    if (!d) fprintf(stdout, "{\"status\":\"HARNESS_JSON_FAIL\"}\n");
    else { fwrite([d bytes], 1, [d length], stdout); fprintf(stdout, "\n"); }
    fflush(stdout);
    exit(code);
}

static void opDispatch(NSDictionary *c, id<MTLDevice> dev) {
    NSString *src = c[@"metal_source"];
    NSError *err = nil;
    NSString *msl = [NSString stringWithContentsOfFile:src encoding:NSUTF8StringEncoding error:&err];
    if (!msl) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err); emitAndExit(1); }
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:msl options:co error:&err];
    if (!lib) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err); emitAndExit(1); }
    id<MTLFunction> fn = [lib newFunctionWithName:c[@"kernel_fn"]];
    if (!fn) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }

    id<MTLComputePipelineState> pso = nil;
    @try {
        pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    } @catch (NSException *ex) {
        setStatus(@"EXCEPTION"); gResult[@"error"] = [ex reason] ?: @"?"; emitAndExit(1);
    }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }
    gResult[@"max_total_threads_per_threadgroup"] = @(pso.maxTotalThreadsPerThreadgroup);
    gResult[@"thread_execution_width"] = @(pso.threadExecutionWidth);
    gResult[@"static_threadgroup_memory_length"] = @(pso.staticThreadgroupMemoryLength);

    NSUInteger tgx = [c[@"tg_x"] unsignedIntegerValue], tgy = c[@"tg_y"] ? [c[@"tg_y"] unsignedIntegerValue] : 1,
               tgz = c[@"tg_z"] ? [c[@"tg_z"] unsignedIntegerValue] : 1;
    NSUInteger gx = c[@"grid_x"] ? [c[@"grid_x"] unsignedIntegerValue] : 1,
               gy = c[@"grid_y"] ? [c[@"grid_y"] unsignedIntegerValue] : 1,
               gz = c[@"grid_z"] ? [c[@"grid_z"] unsignedIntegerValue] : 1;
    NSUInteger dynTgMem = c[@"dyn_tg_mem_bytes"] ? [c[@"dyn_tg_mem_bytes"] unsignedIntegerValue] : 0;
    NSUInteger outCount = c[@"out_count"] ? [c[@"out_count"] unsignedIntegerValue] : 64;

    id<MTLBuffer> outBuf = [dev newBufferWithLength:sizeof(uint32_t) * outCount options:MTLResourceStorageModeShared];
    memset([outBuf contents], 0xEE, sizeof(uint32_t) * outCount);

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    @try {
        [enc setComputePipelineState:pso];
        [enc setBuffer:outBuf offset:0 atIndex:0];
        if (dynTgMem > 0) [enc setThreadgroupMemoryLength:dynTgMem atIndex:0];
        MTLSize tgSize = MTLSizeMake(tgx, tgy, tgz);
        MTLSize gridSize = MTLSizeMake(gx, gy, gz);
        if ([c[@"dispatch_mode"] isEqualToString:@"threads"])
            [enc dispatchThreads:gridSize threadsPerThreadgroup:tgSize];
        else
            [enc dispatchThreadgroups:gridSize threadsPerThreadgroup:tgSize];
    } @catch (NSException *ex) {
        gResult[@"dispatch_exception"] = [ex reason] ?: @"?";
    }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) {
        setStatus(@"CMDBUF_ERROR"); setErrFromNSError([cb error]); emitAndExit(1);
    }
    uint32_t *op = (uint32_t *)[outBuf contents];
    NSMutableArray *out = [NSMutableArray array];
    for (NSUInteger i = 0; i < outCount; i++) [out addObject:@(op[i])];
    gResult[@"out"] = out;
    setStatus(@"OK");
    emitAndExit(0);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        gResult = [NSMutableDictionary dictionary];
        if (argc < 2) { fprintf(stderr, "usage: computeprobe CASE.json\n"); return 2; }
        NSData *cd = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]];
        if (!cd) { fprintf(stderr, "cannot read %s\n", argv[1]); return 2; }
        NSError *jerr = nil;
        NSDictionary *c = [NSJSONSerialization JSONObjectWithData:cd options:0 error:&jerr];
        if (!c) { fprintf(stderr, "bad json\n"); return 2; }
        gResult[@"op"] = c[@"op"] ?: @"?";
        gResult[@"case_id"] = c[@"case_id"] ?: @"?";
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { setStatus(@"NO_DEVICE"); emitAndExit(1); }
        NSString *op = c[@"op"];
        if ([op isEqualToString:@"dispatch"]) opDispatch(c, dev);
        else { setStatus(@"UNKNOWN_OP"); emitAndExit(2); }
    }
    return 0;
}
