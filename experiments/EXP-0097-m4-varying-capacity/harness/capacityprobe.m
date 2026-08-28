// capacityprobe.m -- EXP-0097 GLIO-A01 capacity probe.
//
// Compiles OUR OWN MSL at runtime (newLibraryWithSource:) and attempts to
// create a render pipeline state from the named vertex/fragment functions.
// Reports, in order, exactly which stage first fails: MSL frontend compile
// (AIR), function lookup, or MTLRenderPipelineState creation (the backend
// AGX compile + IO-linkage validation). This directly distinguishes
// "frontend/compiler rejection" from "API object-creation failure" per the
// finite-resource mandate (APPLE9_RE_IMPLEMENTATION_GAPS.md).
//
// Clean-room: OWN-SHADER. Only our own MSL source (given as a file path) is
// compiled through the public Metal runtime API. No Apple binary is
// introspected; only the public MTLLibrary/MTLRenderPipelineState error
// objects (diagnostic text Apple's public API returns to any caller) are
// read.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o capacityprobe capacityprobe.m
//
// Usage:
//   capacityprobe --source SRC.metal --vertex VFN --fragment FFN
//                 [--topology triangle|point] [--color-format N]
//
// Stdout protocol (text; one field per line), always terminated by STATUS:
//   STATUS COMPILE_OK|COMPILE_FAIL|FUNCTION_MISSING|PIPELINE_OK|PIPELINE_FAIL
//   ERROR <message>          (present iff STATUS is a *_FAIL/*_MISSING line)
// Exit status: 0 iff STATUS PIPELINE_OK, 1 otherwise.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { OPT_TOPOLOGY = 128, OPT_COLORFMT };
static const struct option longOpts[] = {
    {"source",   required_argument, NULL, 's'},
    {"vertex",   required_argument, NULL, 'v'},
    {"fragment", required_argument, NULL, 'f'},
    {"topology", required_argument, NULL, OPT_TOPOLOGY},
    {"color-format", required_argument, NULL, OPT_COLORFMT},
    {NULL, 0, NULL, 0}
};

static void done(const char *status, NSError *err, int exitcode) {
    printf("STATUS %s\n", status);
    if (err) {
        NSString *d = [err localizedDescription];
        // Flatten to one line; strip newlines so the line protocol stays 1-field-per-line.
        NSString *flat = [d stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        printf("ERROR %s\n", [flat UTF8String]);
    }
    fflush(stdout);
    exit(exitcode);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *vName = NULL, *fName = NULL;
        const char *topology = "triangle";
        MTLPixelFormat colorFmt = MTLPixelFormatBGRA8Unorm;
        int c;
        while ((c = getopt_long(argc, argv, "s:v:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'v': vName = optarg; break;
                case 'f': fName = optarg; break;
                case OPT_TOPOLOGY: topology = optarg; break;
                case OPT_COLORFMT: colorFmt = (MTLPixelFormat)strtol(optarg, NULL, 0); break;
                default: fprintf(stderr, "usage: see header\n"); return 2;
            }
        }
        if (!sourcePath || !vName || !fName) {
            fprintf(stderr, "need --source --vertex --fragment\n");
            return 2;
        }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) done("PIPELINE_FAIL", nil, 1);

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                    encoding:NSUTF8StringEncoding error:&err];
        if (!src) done("COMPILE_FAIL", err, 1);

        MTLCompileOptions *co = [MTLCompileOptions new];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
        if (!lib) done("COMPILE_FAIL", err, 1);
        // Frontend compiled OK even if `err` carries warnings (Metal returns
        // both a library AND a non-nil err for warnings-only compiles).

        id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
        id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!vf || !ff) done("FUNCTION_MISSING", nil, 1);

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vf;
        pd.fragmentFunction = ff;
        pd.colorAttachments[0].pixelFormat = colorFmt;
        if (strcmp(topology, "point") == 0) {
            pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassPoint;
        } else {
            pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassTriangle;
        }
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) done("PIPELINE_FAIL", err, 1);

        done("PIPELINE_OK", nil, 0);
        return 0;
    }
}
