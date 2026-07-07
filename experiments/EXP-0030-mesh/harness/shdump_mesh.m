// shdump_mesh.m — EXP-0030 OWN-SHADER compile+serialize for a MESH pipeline.
//
// The object+mesh+fragment analogue of tools/shdump/shdump.m --render. Takes OUR
// OWN MSL (object stage + mesh stage + fragment stage), builds an
// MTLMeshRenderPipelineDescriptor, validates it compiles to a real device mesh
// pipeline, and serializes it into an MTLBinaryArchive container so our own
// parser (agxparse) can isolate the raw AGX bytes of each stage.
//
// CLEAN-ROOM: public Metal API on OUR OWN source only. Never disassembles or
// introspects any Apple binary. We inspect only the compiled form of our MSL.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o shdump_mesh shdump_mesh.m
//
// Usage:
//   ./shdump_mesh -o out.bin --object O --mesh M --fragment F [--color-format N]
//                 [--no-fast-math] src.metal
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void die(const char *msg, NSError *err) {
    if (err) fprintf(stderr, "shdump_mesh: %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else     fprintf(stderr, "shdump_mesh: %s\n", msg);
    exit(EXIT_FAILURE);
}

enum { OPT_NO_FAST_MATH = 128, OPT_OBJECT, OPT_MESH, OPT_FRAGMENT, OPT_COLOR_FORMAT };
static const struct option longOpts[] = {
    {"output",       required_argument, NULL, 'o'},
    {"object",       required_argument, NULL, OPT_OBJECT},
    {"mesh",         required_argument, NULL, OPT_MESH},
    {"fragment",     required_argument, NULL, OPT_FRAGMENT},
    {"color-format", required_argument, NULL, OPT_COLOR_FORMAT},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

static id<MTLFunction> pick(id<MTLLibrary> lib, const char *name,
                            MTLFunctionType want, const char *label) {
    if (name) {
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:name]];
        if (!fn) { fprintf(stderr, "shdump_mesh: function '%s' not found\n", name); exit(1); }
        return fn;
    }
    for (NSString *n in [lib functionNames]) {
        id<MTLFunction> c = [lib newFunctionWithName:n];
        if (c && [c functionType] == want) return c;
    }
    fprintf(stderr, "shdump_mesh: no %s function found\n", label);
    exit(1);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *output = NULL, *oName = NULL, *mName = NULL, *fName = NULL;
        BOOL fastMath = YES;
        NSUInteger colorFormat = MTLPixelFormatBGRA8Unorm;   // 80
        int c;
        while ((c = getopt_long(argc, argv, "o:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'o': output = optarg; break;
                case OPT_OBJECT:   oName = optarg; break;
                case OPT_MESH:     mName = optarg; break;
                case OPT_FRAGMENT: fName = optarg; break;
                case OPT_COLOR_FORMAT: colorFormat = (NSUInteger)strtoul(optarg, NULL, 0); break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                default:
                    fprintf(stderr, "usage: %s -o out.bin --object O --mesh M --fragment F "
                                    "[--color-format N] [--no-fast-math] src.metal\n", argv[0]);
                    return 1;
            }
        }
        if (!output || optind >= argc) {
            fprintf(stderr, "usage: %s -o out.bin --object O --mesh M --fragment F src.metal\n", argv[0]);
            return 1;
        }

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) die("read source", err);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device", nil);
        fprintf(stderr, "shdump_mesh: device = %s\n", [[dev name] UTF8String]);
        fprintf(stderr, "shdump_mesh: supportsMeshShaders(family Apple7+) assumed; probing pipeline\n");

        MTLCompileOptions *opts = [MTLCompileOptions new];
        [opts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) die("compile failed", err);
        fprintf(stderr, "shdump_mesh: functions =");
        for (NSString *n in [lib functionNames]) fprintf(stderr, " %s", [n UTF8String]);
        fprintf(stderr, "\n");

        id<MTLFunction> ofn = pick(lib, oName, MTLFunctionTypeObject,   "object");
        id<MTLFunction> mfn = pick(lib, mName, MTLFunctionTypeMesh,     "mesh");
        id<MTLFunction> ffn = pick(lib, fName, MTLFunctionTypeFragment, "fragment");
        fprintf(stderr, "shdump_mesh: object=%s mesh=%s fragment=%s\n",
                [[ofn name] UTF8String], [[mfn name] UTF8String], [[ffn name] UTF8String]);

        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        [md setObjectFunction:ofn];
        [md setMeshFunction:mfn];
        [md setFragmentFunction:ffn];
        md.colorAttachments[0].pixelFormat = (MTLPixelFormat)colorFormat;

        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithMeshDescriptor:md
                                                  options:MTLPipelineOptionNone
                                               reflection:nil
                                                    error:&err];
        if (!pso) die("mesh pipeline creation failed", err);
        fprintf(stderr, "shdump_mesh: mesh pipeline OK (colorFormat=%lu)\n", (unsigned long)colorFormat);
        fprintf(stderr, "shdump_mesh: maxTotalThreadsPerObjectTG=%lu maxTotalThreadsPerMeshTG=%lu\n",
                (unsigned long)[pso maxTotalThreadsPerObjectThreadgroup],
                (unsigned long)[pso maxTotalThreadsPerMeshThreadgroup]);

        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) die("binary archive creation failed", err);
        if (![arc addMeshRenderPipelineFunctionsWithDescriptor:md error:&err])
            die("addMeshRenderPipelineFunctions failed", err);

        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:output]];
        if (![arc serializeToURL:url error:&err]) die("serializeToURL failed", err);
        fprintf(stderr, "shdump_mesh: wrote %s\n", output);
        return 0;
    }
}
