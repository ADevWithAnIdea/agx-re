// mrt_extract.m — EXP-0109 structural fragment-input/output extractor (OWN-SHADER).
//
// Compiles OUR OWN MSL (kernels/mrt_interp.metal), builds a render pipeline
// with a configurable number of color attachments (and optional depth
// attachment / preprocessor macros), validates it on the real device, and
// serializes the archive so agxparse.py (read-only, unmodified) can extract
// the fragment-stage AGX bytes. Also captures compile/pipeline-creation
// *failure* text verbatim for negative-result probes (e.g. the fragment-
// stencil-output attempt) — a rejection is itself the evidence.
//
// CLEAN-ROOM: public Metal API only, on our own MSL source. Never disassembles
// or introspects any Apple binary.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o mrt_extract mrt_extract.m
// Usage: mrt_extract -o out.bin --source S.metal --vertex v_persp --fragment f_persp \
//          [--natt 2] [--depthfmt 252] [--dualsource] [--define NAME=VAL]...
// On success: prints "OK" to stdout and writes the archive. On compile or
// pipeline-creation failure: prints "FAIL: <message>" to stdout, exit 2
// (distinct from usage-error exit 1) and writes nothing.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) {
    fprintf(stderr, "mrt_extract: %s\n", m);
    exit(1);
}

enum { O_SRC = 128, O_VTX, O_FRAG, O_NATT, O_DEPTHFMT, O_DUALSRC, O_DEFINE };
static const struct option L[] = {
    {"source",    required_argument, 0, O_SRC},
    {"vertex",    required_argument, 0, O_VTX},
    {"fragment",  required_argument, 0, O_FRAG},
    {"natt",      required_argument, 0, O_NATT},
    {"depthfmt",  required_argument, 0, O_DEPTHFMT},
    {"dualsource",no_argument,       0, O_DUALSRC},
    {"define",    required_argument, 0, O_DEFINE},
    {0, 0, 0, 0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *out = 0, *srcp = 0, *vn = 0, *fn = 0;
    unsigned natt = 1, depthfmt = 0;
    BOOL dualSource = NO;
    NSMutableDictionary *macros = [NSMutableDictionary dictionary];
    int c;
    while ((c = getopt_long(argc, argv, "o:", L, 0)) > 0) {
        switch (c) {
            case 'o': out = optarg; break;
            case O_SRC: srcp = optarg; break;
            case O_VTX: vn = optarg; break;
            case O_FRAG: fn = optarg; break;
            case O_NATT: natt = (unsigned)strtoul(optarg, NULL, 0); break;
            case O_DEPTHFMT: depthfmt = (unsigned)strtoul(optarg, NULL, 0); break;
            case O_DUALSRC: dualSource = YES; break;
            case O_DEFINE: {
                char *eq = strchr(optarg, '=');
                if (eq) {
                    NSString *k = [[NSString alloc] initWithBytes:optarg length:(eq - optarg) encoding:NSUTF8StringEncoding];
                    NSString *v = [NSString stringWithUTF8String:eq + 1];
                    macros[k] = v;
                } else {
                    macros[[NSString stringWithUTF8String:optarg]] = @"1";
                }
                break;
            }
        }
    }
    if (!out || !srcp || !vn || !fn) usageDie("need -o, --source, --vertex, --fragment");

    NSError *err = nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) usageDie("no device");
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) usageDie("read src");

    MTLCompileOptions *co = [MTLCompileOptions new];
    if ([macros count] > 0) co.preprocessorMacros = macros;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) {
        printf("FAIL: compile: %s\n", [[err localizedDescription] UTF8String]);
        return 2;
    }
    id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vn]];
    id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fn]];
    if (!vf || !ff) {
        printf("FAIL: function missing (vertex=%s present=%d, fragment=%s present=%d)\n",
               vn, vf != nil, fn, ff != nil);
        return 2;
    }

    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf;
    rd.fragmentFunction = ff;
    for (unsigned i = 0; i < natt && i < 4; i++) {
        rd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA16Float;
        if (dualSource && i == 0) {
            rd.colorAttachments[i].blendingEnabled = YES;
            rd.colorAttachments[i].sourceRGBBlendFactor = MTLBlendFactorSource1Color;
            rd.colorAttachments[i].destinationRGBBlendFactor = MTLBlendFactorSourceColor;
            rd.colorAttachments[i].sourceAlphaBlendFactor = MTLBlendFactorSource1Alpha;
            rd.colorAttachments[i].destinationAlphaBlendFactor = MTLBlendFactorSourceAlpha;
        }
    }
    if (depthfmt != 0) {
        rd.depthAttachmentPixelFormat = (MTLPixelFormat)depthfmt;
    }

    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) {
        printf("FAIL: pipeline: %s\n", [[err localizedDescription] UTF8String]);
        return 2;
    }
    fprintf(stderr, "mrt_extract: pipeline OK vertex=%s fragment=%s natt=%u depthfmt=%u dualsrc=%d\n",
            vn, fn, natt, depthfmt, dualSource);

    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (!arc) usageDie("archive creation failed");
    if (![arc addRenderPipelineFunctionsWithDescriptor:rd error:&err]) {
        printf("FAIL: addRenderPipelineFunctions: %s\n", [[err localizedDescription] UTF8String]);
        return 2;
    }
    if (![arc serializeToURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]] error:&err])
        usageDie("serialize failed");
    printf("OK\n");
    return 0;
}}
