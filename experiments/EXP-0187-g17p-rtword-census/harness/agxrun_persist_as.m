// agxrun_persist_as.m -- EXP-0157. clean-room OWN-SHADER PERSISTENT hardware
// runner WITH an MTLAccelerationStructure binding path.
//
// DERIVED FROM tools/agxtest/agxrun_persist.m (EXP-0005), byte-for-byte except
// for the additions marked "EXP-0157 ADDITION" below. The upstream file is NOT
// modified: sibling G17P experiments (EXP-0153/0154/0155/0156) rebuild it
// concurrently from tools/, and editing a shared tool mid-wave would break
// them. The diff is small and self-contained so the orchestrator can upstream
// it (see RESULTS.md, "the testbed gap").
//
// WHY THIS EXISTS. EXP-0146 could not sweep a single field of `sr_read_wide`
// (nor of the rtq_*/ray_move* cluster) because `agxrun_persist` binds
// MTLBuffers only. Our own intersection_query kernel therefore compiled and
// executed, but `q.next()` never entered the loop -- the acceleration
// structure argument was unbound -- so every ray-query getter returned zero
// and the field was not live on the observed output path
// (FIELD-SWEEP-PROTOCOL section 3.2). That is a TESTBED gap, not a hardware
// fact. This runner closes it.
//
// CLEAN-ROOM: identical technique to agxrun_persist.m. Only our own compiled
// shader bytes are executed; only public Metal API is called. No Apple binary
// is disassembled. The acceleration structure is built from OUR OWN authored
// triangle vertices (below), so its contents are our data.
//
// Build (on the neo, CLT/Xcode present):
//   clang -fobjc-arc -framework Metal -framework Foundation -O2 \
//         -o agxrun_persist_as agxrun_persist_as.m
//
// Startup args:
//   agxrun_persist_as --source SRC.metal --function NAME [--no-fast-math]
//                     [--accel IDX] [--accel-kind primitive|instance]
// Prints:  ACCEL <kind> <status> <ntris>     (once, if --accel was given)
//          READY <device-name>
//
// Request protocol and response block: UNCHANGED from agxrun_persist.m.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { OPT_NO_FAST_MATH = 128, OPT_ACCEL = 129, OPT_ACCEL_KIND = 130 };
static const struct option longOpts[] = {
    {"source",       required_argument, NULL, 's'},
    {"function",     required_argument, NULL, 'f'},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {"accel",        required_argument, NULL, OPT_ACCEL},
    {"accel-kind",   required_argument, NULL, OPT_ACCEL_KIND},
    {NULL, 0, NULL, 0}
};

static id<MTLDevice>       gDev  = nil;
static id<MTLCommandQueue> gQueue = nil;
static NSString           *gSrc  = nil;
static const char         *gFuncName = NULL;
static BOOL                gFastMath = YES;

// ---------------------------------------------------- EXP-0157 ADDITION
// Our own authored geometry. THREE non-opaque triangles, each a large quad-ish
// triangle in the z = 1, 2, 3 planes, all straddling the +z axis, so a ray
// with origin (0,0,0), direction (0,0,1), t in [0,100] hits all three at
// t = 1, 2, 3 with primitive_id 0, 1, 2 and geometry_id 0.
//
// `opaque = NO` is load-bearing: an OPAQUE triangle hit is committed by the
// hardware without ever surfacing as a candidate, so `q.next()` would return
// false immediately and the CANDIDATE getters would still be dead. Non-opaque
// geometry forces every hit through the candidate path.
static const float kTrisG0[] = {          // geometry 0: primitive ids 0,1,2
    -8.0f, -8.0f, 3.0f,   8.0f, -8.0f, 3.0f,   0.0f,  8.0f, 3.0f,
    -8.0f, -8.0f, 2.0f,   8.0f, -8.0f, 2.0f,   0.0f,  8.0f, 2.0f,
    -8.0f, -8.0f, 1.0f,   8.0f, -8.0f, 1.0f,   0.0f,  8.0f, 1.0f,
};
static const float kTrisG1[] = {          // geometry 1: primitive id 0
    -8.0f, -8.0f, 4.0f,   8.0f, -8.0f, 4.0f,   0.0f,  8.0f, 4.0f,
};
// EXP-0157 ADDITION (post-freeze, recorded as a deviation): BOUNDING-BOX
// geometry. The reachability probe showed that a triangle-only query never
// executes the code containing `rtq_pred` and `rtq_dualsrc` -- erasing 256
// contiguous bytes at those offsets leaves the result exactly correct. Custom
// (bounding-box) geometry drives the OTHER traversal path, where a candidate
// is a box the shader must range-test and commit explicitly.
// Three axis-aligned boxes straddling the +z axis at z in [1,1.5], [2,2.5],
// [3,3.5] -- so the same ray hits all three, with primitive ids 0, 1, 2.
static const float kBoxes[] = {
    -8.0f, -8.0f, 1.0f,   8.0f, 8.0f, 1.5f,
    -8.0f, -8.0f, 2.0f,   8.0f, 8.0f, 2.5f,
    -8.0f, -8.0f, 3.0f,   8.0f, 8.0f, 3.5f,
};
static const int kNBoxes = 3;

static const int kNTrisG0 = 3;
static const int kNTrisG1 = 1;
static const int kNTris   = 4;

static int                        gAccelIdx  = -1;
static const char                *gAccelKind = "primitive";
static id<MTLAccelerationStructure> gAccel   = nil;
static id<MTLAccelerationStructure> gPrimAccel = nil;   // kept resident for the instance case
static id<MTLBuffer>              gInstBuf   = nil;

static id<MTLAccelerationStructure> build_accel(MTLAccelerationStructureDescriptor *desc,
                                                 NSString **err) {
    MTLAccelerationStructureSizes sizes =
        [gDev accelerationStructureSizesWithDescriptor:desc];
    id<MTLAccelerationStructure> as =
        [gDev newAccelerationStructureWithSize:sizes.accelerationStructureSize];
    if (!as) { *err = @"newAccelerationStructureWithSize failed"; return nil; }
    id<MTLBuffer> scratch =
        [gDev newBufferWithLength:(sizes.buildScratchBufferSize > 0
                                    ? sizes.buildScratchBufferSize : 16)
                          options:MTLResourceStorageModePrivate];
    // The build is submitted with bounded retries. On a busy device the
    // build command buffer is routinely discarded as
    // `kIOGPUCommandBufferCallbackErrorInnocentVictim` -- a sibling
    // experiment's contained fault triggering a device reset that kills every
    // in-flight command buffer, ours included (NEO-TARGET-BRIEF, "Concurrency").
    // That is evidence about the MACHINE, not about the descriptor, so it is
    // retried rather than reported as a build failure; a genuinely bad
    // descriptor fails all ACCEL_BUILD_TRIES attempts.
    const int ACCEL_BUILD_TRIES = 30;
    for (int attempt = 1; attempt <= ACCEL_BUILD_TRIES; attempt++) {
        id<MTLCommandBuffer> cb = [gQueue commandBuffer];
        id<MTLAccelerationStructureCommandEncoder> aenc = [cb accelerationStructureCommandEncoder];
        [aenc buildAccelerationStructure:as descriptor:desc scratchBuffer:scratch
                     scratchBufferOffset:0];
        [aenc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] != MTLCommandBufferStatusError) return as;
        *err = [NSString stringWithFormat:@"attempt %d/%d: %@", attempt,
                         ACCEL_BUILD_TRIES, [[cb error] localizedDescription]];
        fprintf(stderr, "accel build retry %d: %s\n", attempt, [*err UTF8String]);
        gQueue = [gDev newCommandQueue];
        usleep(200000 * (attempt < 10 ? attempt : 10));
    }
    return nil;
}

// Returns nil and sets *err on failure. Builds the primitive AS always; wraps
// it in a single-instance instance-AS when --accel-kind instance was asked for
// (our own intersection_query<instancing> kernels need that flavour).
static id<MTLAccelerationStructure> make_accel(NSString **err) {
    if (strcmp(gAccelKind, "bbox") == 0) {
        id<MTLBuffer> bb = [gDev newBufferWithBytes:kBoxes length:sizeof(kBoxes)
                                            options:MTLResourceStorageModeShared];
        MTLAccelerationStructureBoundingBoxGeometryDescriptor *gb =
            [MTLAccelerationStructureBoundingBoxGeometryDescriptor descriptor];
        [gb setBoundingBoxBuffer:bb];
        [gb setBoundingBoxBufferOffset:0];
        [gb setBoundingBoxStride:6 * sizeof(float)];
        [gb setBoundingBoxCount:kNBoxes];
        [gb setOpaque:NO];
        MTLPrimitiveAccelerationStructureDescriptor *pdb =
            [MTLPrimitiveAccelerationStructureDescriptor descriptor];
        [pdb setGeometryDescriptors:@[gb]];
        gPrimAccel = build_accel((MTLAccelerationStructureDescriptor *)pdb, err);
        return gPrimAccel;
    }
    id<MTLBuffer> v0 = [gDev newBufferWithBytes:kTrisG0 length:sizeof(kTrisG0)
                                        options:MTLResourceStorageModeShared];
    id<MTLBuffer> v1 = [gDev newBufferWithBytes:kTrisG1 length:sizeof(kTrisG1)
                                        options:MTLResourceStorageModeShared];
    MTLAccelerationStructureTriangleGeometryDescriptor *g0 =
        [MTLAccelerationStructureTriangleGeometryDescriptor descriptor];
    [g0 setVertexBuffer:v0]; [g0 setVertexBufferOffset:0];
    [g0 setVertexStride:3 * sizeof(float)];
    [g0 setTriangleCount:kNTrisG0]; [g0 setOpaque:NO];
    MTLAccelerationStructureTriangleGeometryDescriptor *g1 =
        [MTLAccelerationStructureTriangleGeometryDescriptor descriptor];
    [g1 setVertexBuffer:v1]; [g1 setVertexBufferOffset:0];
    [g1 setVertexStride:3 * sizeof(float)];
    [g1 setTriangleCount:kNTrisG1]; [g1 setOpaque:NO];
    MTLPrimitiveAccelerationStructureDescriptor *pd =
        [MTLPrimitiveAccelerationStructureDescriptor descriptor];
    [pd setGeometryDescriptors:@[g0, g1]];
    gPrimAccel = build_accel((MTLAccelerationStructureDescriptor *)pd, err);
    if (!gPrimAccel) return nil;
    if (strcmp(gAccelKind, "instance") != 0) return gPrimAccel;

    MTLAccelerationStructureInstanceDescriptor inst;
    memset(&inst, 0, sizeof(inst));
    // identity transform (3x4, column-major)
    inst.transformationMatrix.columns[0] = (MTLPackedFloat3){1.0f, 0.0f, 0.0f};
    inst.transformationMatrix.columns[1] = (MTLPackedFloat3){0.0f, 1.0f, 0.0f};
    inst.transformationMatrix.columns[2] = (MTLPackedFloat3){0.0f, 0.0f, 1.0f};
    inst.transformationMatrix.columns[3] = (MTLPackedFloat3){0.0f, 0.0f, 0.0f};
    inst.options = MTLAccelerationStructureInstanceOptionNonOpaque;
    inst.mask = 0xFF;
    inst.intersectionFunctionTableOffset = 0;
    inst.accelerationStructureIndex = 0;
    gInstBuf = [gDev newBufferWithBytes:&inst length:sizeof(inst)
                                options:MTLResourceStorageModeShared];
    MTLInstanceAccelerationStructureDescriptor *idesc =
        [MTLInstanceAccelerationStructureDescriptor descriptor];
    [idesc setInstancedAccelerationStructures:@[gPrimAccel]];
    [idesc setInstanceCount:1];
    [idesc setInstanceDescriptorBuffer:gInstBuf];
    [idesc setInstanceDescriptorBufferOffset:0];
    [idesc setInstanceDescriptorStride:sizeof(MTLAccelerationStructureInstanceDescriptor)];
    return build_accel((MTLAccelerationStructureDescriptor *)idesc, err);
}
// -------------------------------------------------- end EXP-0157 ADDITION

static void respond_fail(const char *reqid, const char *status, const char *msg, NSError *err) {
    printf("REQ %s\n", reqid);
    printf("STATUS %s\n", status);
    if (err)      printf("ERROR %s: %s\n", msg ? msg : "", [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    printf("DONE %s\n", reqid);
    fflush(stdout);
}

static void handle_request(char *line) {
    @autoreleasepool {
        char *save = NULL;
        char *reqid = strtok_r(line, " \t\r\n", &save);
        if (!reqid) return;
        char *archive = strtok_r(NULL, " \t\r\n", &save);
        char *sgrid   = strtok_r(NULL, " \t\r\n", &save);
        char *stg     = strtok_r(NULL, " \t\r\n", &save);
        char *snin    = strtok_r(NULL, " \t\r\n", &save);
        if (!archive || !sgrid || !stg || !snin) {
            respond_fail(reqid, "BAD_REQUEST", "want: id archive grid tg nin ... nout ...", nil);
            return;
        }
        long grid = strtol(sgrid, NULL, 0);
        long tg   = strtol(stg,   NULL, 0);
        int  nin  = (int)strtol(snin, NULL, 0);

        id<MTLBuffer> bufs[64] = {0};
        for (int i = 0; i < nin; i++) {
            char *spec = strtok_r(NULL, " \t\r\n", &save);
            if (!spec) { respond_fail(reqid, "BAD_REQUEST", "missing input spec", nil); return; }
            char *colon = strchr(spec, ':');
            if (!colon) { respond_fail(reqid, "BAD_REQUEST", "input want IDX:FILE", nil); return; }
            *colon = 0;
            int idx = (int)strtol(spec, NULL, 0);
            NSData *d = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:colon + 1]];
            if (!d) { respond_fail(reqid, "BAD_REQUEST", "cannot read input file", nil); return; }
            bufs[idx] = [gDev newBufferWithBytes:[d bytes] length:[d length]
                                        options:MTLResourceStorageModeShared];
        }
        char *snout = strtok_r(NULL, " \t\r\n", &save);
        int nout = snout ? (int)strtol(snout, NULL, 0) : 0;
        int outIdx[64]; long outSz[64];
        for (int i = 0; i < nout; i++) {
            char *spec = strtok_r(NULL, " \t\r\n", &save);
            if (!spec) { respond_fail(reqid, "BAD_REQUEST", "missing output spec", nil); return; }
            char *colon = strchr(spec, ':');
            if (!colon) { respond_fail(reqid, "BAD_REQUEST", "output want IDX:NBYTES", nil); return; }
            *colon = 0;
            outIdx[i] = (int)strtol(spec, NULL, 0);
            outSz[i]  = strtol(colon + 1, NULL, 0);
            if (!bufs[outIdx[i]])
                bufs[outIdx[i]] = [gDev newBufferWithLength:outSz[i]
                                                   options:MTLResourceStorageModeShared];
        }

        NSError *err = nil;
        NSURL *archiveURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive]];
        id<MTLLibrary> lib = [gDev newLibraryWithURL:archiveURL error:&err];
        if (!lib) { respond_fail(reqid, "COMPILE_FAIL", "newLibraryWithURL(archive)", err); return; }
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:gFuncName]];
        if (!fn) { respond_fail(reqid, "FUNCTION_MISSING", "newFunctionWithName", nil); return; }

        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        [adesc setUrl:archiveURL];
        id<MTLBinaryArchive> arc = [gDev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) { respond_fail(reqid, "ARCHIVE_FAIL", "newBinaryArchive", err); return; }

        MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
        [pdesc setComputeFunction:fn];
        [pdesc setBinaryArchives:@[arc]];
        id<MTLComputePipelineState> pso =
            [gDev newComputePipelineStateWithDescriptor:pdesc
                                                options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                             reflection:nil error:&err];
        if (!pso) { respond_fail(reqid, "PIPELINE_MISS", "pipeline (FailOnBinaryArchiveMiss)", err); return; }

        id<MTLCommandBuffer> cb = [gQueue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for (int i = 0; i < 64; i++) if (bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        // ------------------------------------------ EXP-0157 ADDITION
        if (gAccel && gAccelIdx >= 0) {
            [enc setAccelerationStructure:gAccel atBufferIndex:gAccelIdx];
            if (gPrimAccel && gPrimAccel != gAccel)
                [enc useResource:gPrimAccel usage:MTLResourceUsageRead];
        }
        // -------------------------------------- end EXP-0157 ADDITION
        [enc dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(reqid, "CMDBUF_ERROR", "command buffer failed", [cb error]);
            gQueue = [gDev newCommandQueue];
            return;
        }

        printf("REQ %s\n", reqid);
        printf("STATUS OK\n");
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));
        for (int i = 0; i < nout; i++) {
            const unsigned char *p = (const unsigned char *)[bufs[outIdx[i]] contents];
            long n = outSz[i];
            char *hex = (char *)malloc(n * 2 + 1);
            static const char H[] = "0123456789abcdef";
            for (long j = 0; j < n; j++) { hex[j*2] = H[p[j] >> 4]; hex[j*2+1] = H[p[j] & 0xf]; }
            hex[n*2] = 0;
            printf("OUT %d %s\n", outIdx[i], hex);
            free(hex);
        }
        printf("DONE %s\n", reqid);
        fflush(stdout);
    }
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *funcName = NULL;
        BOOL fastMath = YES;
        int c;
        while ((c = getopt_long(argc, argv, "s:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'f': funcName = optarg; break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                case OPT_ACCEL: gAccelIdx = (int)strtol(optarg, NULL, 0); break;
                case OPT_ACCEL_KIND: gAccelKind = optarg; break;
            }
        }
        if (!sourcePath || !funcName) {
            fprintf(stderr, "usage: agxrun_persist_as --source SRC --function NAME "
                            "[--no-fast-math] [--accel IDX] [--accel-kind primitive|instance]\n");
            return 2;
        }
        gDev = MTLCreateSystemDefaultDevice();
        if (!gDev) { fprintf(stderr, "no Metal device\n"); return 1; }
        gQueue = [gDev newCommandQueue];
        gFuncName = funcName;
        gFastMath = fastMath;

        NSError *err = nil;
        gSrc = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                         encoding:NSUTF8StringEncoding error:&err];
        if (!gSrc) { fprintf(stderr, "read source failed\n"); return 1; }
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [gDev newLibraryWithSource:gSrc options:copts error:&err];
        if (!lib) { fprintf(stderr, "compile failed: %s\n", [[err localizedDescription] UTF8String]); return 1; }
        if (![lib newFunctionWithName:[NSString stringWithUTF8String:funcName]]) {
            fprintf(stderr, "function %s missing\n", funcName); return 1;
        }

        // ---------------------------------------- EXP-0157 ADDITION
        if (gAccelIdx >= 0) {
            if (![gDev supportsRaytracing]) {
                fprintf(stderr, "device reports supportsRaytracing = NO\n");
                printf("ACCEL %s UNSUPPORTED 0\n", gAccelKind);
            } else {
                NSString *aerr = nil;
                gAccel = make_accel(&aerr);
                if (!gAccel) {
                    fprintf(stderr, "acceleration structure build failed: %s\n",
                            aerr ? [aerr UTF8String] : "?");
                    printf("ACCEL %s BUILD_FAIL 0\n", gAccelKind);
                } else {
                    printf("ACCEL %s OK %d\n", gAccelKind,
                           strcmp(gAccelKind, "bbox") == 0 ? kNBoxes : kNTris);
                }
            }
            fflush(stdout);
        }
        // ------------------------------------ end EXP-0157 ADDITION

        printf("READY %s\n", [[gDev name] UTF8String]);
        fflush(stdout);

        char *line = NULL;
        size_t cap = 0;
        ssize_t len;
        while ((len = getline(&line, &cap, stdin)) > 0) {
            char *copy = strdup(line);
            handle_request(copy);
            free(copy);
        }
        free(line);
        return 0;
    }
}
