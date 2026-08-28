// texpersist.m -- EXP-0142 PERSISTENT compute runner with TEXTURE binding.
//
// Combines two existing repo tools whose union does not yet exist:
//   * tools/agxtest/agxrun_persist.m -- one live MTLDevice for the process
//     lifetime, fresh MTLLibrary loaded from each (spliced) archive's own
//     bytes, log-and-continue past contained command-buffer faults.
//   * experiments/EXP-0114/harness/texsplice.m -- texture binding for a
//     compute pipeline (agxrun*.m bind buffers only).
//
// Neither of those alone can run a multi-thousand-case texture field sweep,
// which is what EXP-0142 needs. This is our own code; it introspects no Apple
// binary and executes only our own compiled+spliced shader bytes.
//
// CLEAN-ROOM: OWN-SHADER + HW-PROBE. Public Metal API only.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -O2 \
//         -o texpersist harness/texpersist.m
//
// Startup:
//   texpersist --source SRC.metal --function NAME [--no-fast-math]
//              [--samp-w 16] [--samp-h 16] [--write-w 8] [--write-h 8]
// Prints: READY <device-name>
//
// Textures created once and reused:
//   texture(0) : R32Float  samp-w x samp-h, READ+SAMPLE, texel(x,y) = x + 100*y
//   texture(1) : RGBA32Float write-w x write-h, WRITE+READ, reset to
//                (-1,-2,-3,-4) in every texel before every dispatch so an
//                untouched texel is distinguishable from a written zero.
//
// Request protocol (one line):
//   <reqid> <archive> <grid> <tg> <nin> [<idx>:<file> ...] <nout> [<idx>:<nbytes> ...] <texflags>
//   texflags bit0 = read back texture(1) after the dispatch.
// Response block, terminated by DONE:
//   REQ <id> / STATUS ... / [GPUTIME_NS n] / [OUT idx hex] / [TEXOUT hex] / [ERROR msg] / DONE <id>

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { OPT_NO_FAST_MATH = 128, OPT_SAMPW, OPT_SAMPH, OPT_WRITEW, OPT_WRITEH };
static const struct option longOpts[] = {
    {"source",       required_argument, NULL, 's'},
    {"function",     required_argument, NULL, 'f'},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {"samp-w",       required_argument, NULL, OPT_SAMPW},
    {"samp-h",       required_argument, NULL, OPT_SAMPH},
    {"write-w",      required_argument, NULL, OPT_WRITEW},
    {"write-h",      required_argument, NULL, OPT_WRITEH},
    {NULL, 0, NULL, 0}
};

static id<MTLDevice>       gDev = nil;
static id<MTLCommandQueue> gQueue = nil;
static const char         *gFuncName = NULL;
static id<MTLTexture>      gTexSamp = nil;
static id<MTLTexture>      gTexWrite = nil;
static int gWW = 8, gWH = 8;

static void respond_fail(const char *reqid, const char *status, const char *msg, NSError *err) {
    printf("REQ %s\n", reqid ? reqid : "?");
    printf("STATUS %s\n", status);
    if (err) {
        // FIELD-SWEEP-PROTOCOL section 7.2: the OS fault CLASSIFICATION, not just the
        // status. ...ErrorInnocentVictim is evidence about the machine, not the encoding.
        printf("ERRDOM %s %ld\n", [[err domain] UTF8String], (long)[err code]);
        printf("ERROR %s: %s\n", msg ? msg : "", [[err localizedDescription] UTF8String]);
    }
    else if (msg) printf("ERROR %s\n", msg);
    printf("DONE %s\n", reqid ? reqid : "?");
    fflush(stdout);
}

static void print_hex(const unsigned char *p, long n) {
    static const char H[] = "0123456789abcdef";
    char *hex = (char *)malloc((size_t)n * 2 + 1);
    for (long j = 0; j < n; j++) { hex[j*2] = H[p[j] >> 4]; hex[j*2+1] = H[p[j] & 0xf]; }
    hex[n*2] = 0;
    fputs(hex, stdout);
    free(hex);
}

static void reset_write_texture(void) {
    if (!gTexWrite) return;
    size_t n = (size_t)gWW * (size_t)gWH * 4;
    float *tmp = (float *)malloc(n * sizeof(float));
    for (size_t i = 0; i < n; i += 4) {
        tmp[i+0] = -1.0f; tmp[i+1] = -2.0f; tmp[i+2] = -3.0f; tmp[i+3] = -4.0f;
    }
    [gTexWrite replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gWW, (NSUInteger)gWH)
                 mipmapLevel:0 withBytes:tmp bytesPerRow:(NSUInteger)gWW * 16];
    free(tmp);
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
            respond_fail(reqid, "BAD_REQUEST", "want: id archive grid tg nin ... nout ... texflags", nil);
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
            if (idx < 0 || idx >= 64) { respond_fail(reqid, "BAD_REQUEST", "input idx range", nil); return; }
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
            if (outIdx[i] < 0 || outIdx[i] >= 64) { respond_fail(reqid, "BAD_REQUEST", "output idx range", nil); return; }
            if (!bufs[outIdx[i]]) {
                bufs[outIdx[i]] = [gDev newBufferWithLength:outSz[i] options:MTLResourceStorageModeShared];
                // FIELD-SWEEP-PROTOCOL section 7: poison the read-back buffer so an
                // untouched word is unmistakable (0xDEADBEEF, little-endian).
                unsigned char *pz = (unsigned char *)[bufs[outIdx[i]] contents];
                for (long z = 0; z < outSz[i]; z++) pz[z] = (unsigned char)"\xef\xbe\xad\xde"[z & 3];
            }
        }
        char *sflags = strtok_r(NULL, " \t\r\n", &save);
        int texflags = sflags ? (int)strtol(sflags, NULL, 0) : 0;

        NSError *err = nil;
        NSURL *archiveURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive]];
        // Fresh library from the SPLICED archive's own bytes each request --
        // the crux documented in tools/agxtest/README.md: a source-compiled
        // library's native code is memoized in-process, which would silently
        // run the ORIGINAL code for every request after the first.
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

        reset_write_texture();

        id<MTLCommandBuffer> cb = [gQueue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for (int i = 0; i < 64; i++) if (bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        if (gTexSamp)  [enc setTexture:gTexSamp  atIndex:0];
        if (gTexWrite) [enc setTexture:gTexWrite atIndex:1];
        [enc dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(reqid, "CMDBUF_ERROR", "command buffer failed", [cb error]);
            gQueue = [gDev newCommandQueue];   // a faulted submission can poison the queue
            return;
        }

        printf("REQ %s\n", reqid);
        printf("STATUS OK\n");
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));
        for (int i = 0; i < nout; i++) {
            printf("OUT %d ", outIdx[i]);
            print_hex((const unsigned char *)[bufs[outIdx[i]] contents], outSz[i]);
            printf("\n");
        }
        if ((texflags & 1) && gTexWrite) {
            size_t nbytes = (size_t)gWW * (size_t)gWH * 16;
            unsigned char *tmp = (unsigned char *)malloc(nbytes);
            [gTexWrite getBytes:tmp bytesPerRow:(NSUInteger)gWW * 16
                     fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gWW, (NSUInteger)gWH)
                    mipmapLevel:0];
            printf("TEXOUT ");
            print_hex(tmp, (long)nbytes);
            printf("\n");
            free(tmp);
        }
        printf("DONE %s\n", reqid);
        fflush(stdout);
    }
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *funcName = NULL;
        BOOL fastMath = YES;
        int sw = 16, sh = 16;
        int c;
        while ((c = getopt_long(argc, argv, "s:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'f': funcName = optarg; break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                case OPT_SAMPW: sw = (int)strtol(optarg, NULL, 0); break;
                case OPT_SAMPH: sh = (int)strtol(optarg, NULL, 0); break;
                case OPT_WRITEW: gWW = (int)strtol(optarg, NULL, 0); break;
                case OPT_WRITEH: gWH = (int)strtol(optarg, NULL, 0); break;
                default: fprintf(stderr, "bad option\n"); return 2;
            }
        }
        if (!sourcePath || !funcName) {
            fprintf(stderr, "usage: texpersist --source SRC --function NAME [--no-fast-math]\n");
            return 2;
        }
        gDev = MTLCreateSystemDefaultDevice();
        if (!gDev) { fprintf(stderr, "no Metal device\n"); return 1; }
        gQueue = [gDev newCommandQueue];
        gFuncName = funcName;

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) { fprintf(stderr, "read source failed\n"); return 1; }
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [gDev newLibraryWithSource:src options:copts error:&err];
        if (!lib) { fprintf(stderr, "compile failed: %s\n", [[err localizedDescription] UTF8String]); return 1; }
        if (![lib newFunctionWithName:[NSString stringWithUTF8String:funcName]]) {
            fprintf(stderr, "function %s missing\n", funcName); return 1;
        }

        // texture(0): sampled source, texel(x,y) = x + 100*y
        MTLTextureDescriptor *sd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                                                      width:(NSUInteger)sw
                                                                                     height:(NSUInteger)sh
                                                                                  mipmapped:NO];
        sd.usage = MTLTextureUsageShaderRead;
        sd.storageMode = MTLStorageModeShared;
        gTexSamp = [gDev newTextureWithDescriptor:sd];
        {
            float *tmp = (float *)malloc((size_t)sw * (size_t)sh * sizeof(float));
            for (int y = 0; y < sh; y++)
                for (int x = 0; x < sw; x++)
                    tmp[y * sw + x] = (float)x + 100.0f * (float)y;
            [gTexSamp replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)sw, (NSUInteger)sh)
                        mipmapLevel:0 withBytes:tmp bytesPerRow:(NSUInteger)sw * 4];
            free(tmp);
        }

        // texture(1): write target
        MTLTextureDescriptor *wd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                      width:(NSUInteger)gWW
                                                                                     height:(NSUInteger)gWH
                                                                                  mipmapped:NO];
        wd.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
        wd.storageMode = MTLStorageModeShared;
        gTexWrite = [gDev newTextureWithDescriptor:wd];
        reset_write_texture();

        printf("READY %s\n", [[gDev name] UTF8String]);
        fflush(stdout);

        char *line = NULL; size_t cap = 0; ssize_t len;
        while ((len = getline(&line, &cap, stdin)) > 0) {
            char *copy = strdup(line);
            handle_request(copy);
            free(copy);
        }
        free(line);
        return 0;
    }
}
