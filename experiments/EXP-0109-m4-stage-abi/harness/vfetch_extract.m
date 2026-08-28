// vfetch_extract.m — EXP-0109 structural VS-attribute-fetch extractor (OWN-SHADER).
//
// Compiles OUR OWN MSL (kernels/vfetch.metal), builds a render pipeline whose
// MTLVertexDescriptor is fully controlled by CLI args (format/offset/stride/
// step-function/step-rate), validates it on the real device, and serializes
// the compiled pipeline into an MTLBinaryArchive so agxparse.py (read-only,
// unmodified) can extract the vertex-stage AGX bytes for structural/byte-diff
// analysis. Adapted from experiments/EXP-0031-sr-abi/harness/attrdump.m (our
// own prior authored tool, A18) — extended with a step-rate/divisor parameter
// and an explicit vertex-function-name selector for the wider field-type
// matrix in kernels/vfetch.metal.
//
// CLEAN-ROOM: public Metal API only, on our own MSL source. Never disassembles
// or introspects any Apple binary. MTLVertexFormat enum values below are read
// from the public Metal.framework SDK header (MTLVertexDescriptor.h), which is
// public developer-facing API surface, not a compiled binary.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o vfetch_extract vfetch_extract.m
// Usage: vfetch_extract -o out.bin --source S.metal --vertex v_f4 --fragment f_pass \
//          --format 31 --offset 0 --stride 32 --step vertex --rate 1

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void die(const char *m, NSError *e) {
    fprintf(stderr, "vfetch_extract: %s%s%s\n", m, e ? ": " : "",
            e ? [[e localizedDescription] UTF8String] : "");
    exit(1);
}

enum { O_SRC = 128, O_VTX, O_FRAG, O_FMT, O_OFF, O_STRIDE, O_STEP, O_RATE, O_NATTR };
static const struct option L[] = {
    {"source",   required_argument, 0, O_SRC},
    {"vertex",   required_argument, 0, O_VTX},
    {"fragment", required_argument, 0, O_FRAG},
    {"format",   required_argument, 0, O_FMT},
    {"offset",   required_argument, 0, O_OFF},
    {"stride",   required_argument, 0, O_STRIDE},
    {"step",     required_argument, 0, O_STEP},   // "vertex" | "instance"
    {"rate",     required_argument, 0, O_RATE},
    {0, 0, 0, 0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *out = 0, *srcp = 0, *vn = 0, *fn = "f_pass";
    unsigned fmt = MTLVertexFormatFloat4, off = 0, stride = 32, rate = 1;
    BOOL perInstance = NO;
    int c;
    while ((c = getopt_long(argc, argv, "o:", L, 0)) > 0) {
        switch (c) {
            case 'o': out = optarg; break;
            case O_SRC: srcp = optarg; break;
            case O_VTX: vn = optarg; break;
            case O_FRAG: fn = optarg; break;
            case O_FMT: fmt = (unsigned)strtoul(optarg, NULL, 0); break;
            case O_OFF: off = (unsigned)strtoul(optarg, NULL, 0); break;
            case O_STRIDE: stride = (unsigned)strtoul(optarg, NULL, 0); break;
            case O_STEP: perInstance = (strcmp(optarg, "instance") == 0); break;
            case O_RATE: rate = (unsigned)strtoul(optarg, NULL, 0); break;
        }
    }
    if (!out || !srcp || !vn) die("need -o, --source, --vertex", 0);

    NSError *err = nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) die("no device", 0);
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) die("read src", err);
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) die("compile", err);
    id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vn]];
    id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fn]];
    if (!vf || !ff) die("function missing", 0);

    MTLVertexDescriptor *vd = [MTLVertexDescriptor new];
    vd.attributes[0].format = (MTLVertexFormat)fmt;
    vd.attributes[0].offset = off;
    vd.attributes[0].bufferIndex = 0;
    vd.layouts[0].stride = stride;
    vd.layouts[0].stepFunction = perInstance ? MTLVertexStepFunctionPerInstance
                                              : MTLVertexStepFunctionPerVertex;
    vd.layouts[0].stepRate = perInstance ? rate : 1;

    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf;
    rd.fragmentFunction = ff;
    rd.vertexDescriptor = vd;
    rd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) die("pipeline", err);
    fprintf(stderr, "vfetch_extract: pipeline OK vertex=%s fmt=%u off=%u stride=%u "
                     "step=%s rate=%u\n", vn, fmt, off, stride,
            perInstance ? "instance" : "vertex", perInstance ? rate : 1u);

    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (!arc) die("archive", err);
    if (![arc addRenderPipelineFunctionsWithDescriptor:rd error:&err]) die("addRenderPipeline", err);
    if (![arc serializeToURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]] error:&err])
        die("serialize", err);
    fprintf(stderr, "vfetch_extract: wrote %s\n", out);
    return 0;
}}
