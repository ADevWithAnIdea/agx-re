// EXP-0085 interlock_tex_probe — single-case Metal harness for the MEM-13
// texture-sample interlock kernel (kernels/interlock_tex.metal). One
// dispatch per process, one JSON record. Public Metal API only.
//
// Usage: interlock_tex_probe --source PATH --kernel NAME --w W --h H --timeout SEC
//
// Texture content is deterministic: texel(x,y).r = ((y*W+x) % 251) / 255.0,
// uploaded as r32Float so read() returns the exact stored bit pattern (no
// unorm quantization ambiguity).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void on_alarm(int sig) { (void)sig; _exit(98); }
static void hex_append(NSMutableString *s, const uint8_t *bytes, size_t n) {
    static const char *hx = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) [s appendFormat:@"%c%c", hx[(bytes[i] >> 4) & 0xf], hx[bytes[i] & 0xf]];
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        const char *source_path = NULL, *kernel = NULL;
        long w = 0, h = 0, timeout_s = 30;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--source")) source_path = argv[++i];
            else if (!strcmp(argv[i], "--kernel")) kernel = argv[++i];
            else if (!strcmp(argv[i], "--w")) w = atol(argv[++i]);
            else if (!strcmp(argv[i], "--h")) h = atol(argv[++i]);
            else if (!strcmp(argv[i], "--timeout")) timeout_s = atol(argv[++i]);
            else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
        }
        if (!source_path || !kernel || w <= 0 || h <= 0) {
            fprintf(stderr, "usage: --source --kernel --w --h --timeout\n"); return 2;
        }
        signal(SIGALRM, on_alarm);
        alarm((unsigned)timeout_s);

        NSMutableDictionary *out = [NSMutableDictionary dictionary];
        out[@"kernel"] = @(kernel); out[@"w"] = @(w); out[@"h"] = @(h);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("JSON {\"status\":\"no_device\"}\n"); return 1; }
        NSError *rerr = nil;
        NSString *src = [NSString stringWithContentsOfFile:@(source_path) encoding:NSUTF8StringEncoding error:&rerr];
        if (!src) { printf("JSON {\"status\":\"read_fail\"}\n"); return 1; }

        MTLCompileOptions *opts = [MTLCompileOptions new];
        opts.fastMathEnabled = NO;
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) {
            out[@"status"] = @"compile_fail";
            out[@"compile_err"] = err ? err.localizedDescription : @"unknown";
            NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
            printf("JSON %s\n", (const char*)j.bytes); return 0;
        }
        id<MTLFunction> fn = [lib newFunctionWithName:@(kernel)];
        if (!fn) {
            out[@"status"] = @"function_missing";
            NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
            printf("JSON %s\n", (const char*)j.bytes); return 0;
        }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) {
            out[@"status"] = @"pipeline_fail";
            out[@"compile_err"] = err ? err.localizedDescription : @"unknown";
            NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
            printf("JSON %s\n", (const char*)j.bytes); return 0;
        }

        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                                                        width:w height:h mipmapped:NO];
        td.usage = MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
        {
            float *row = malloc(sizeof(float) * w);
            for (long y = 0; y < h; y++) {
                for (long x = 0; x < w; x++) row[x] = (float)(((y * w + x) % 251)) / 255.0f;
                [tex replaceRegion:MTLRegionMake2D(0, y, w, 1) mipmapLevel:0 withBytes:row bytesPerRow:sizeof(float)*w];
            }
            free(row);
        }

        MTLResourceOptions ropt = MTLResourceStorageModeShared;
        id<MTLBuffer> b_out = [dev newBufferWithLength:w * h * sizeof(float) options:ropt];
        memset(b_out.contents, 0xEE, w * h * sizeof(float));

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setTexture:tex atIndex:0];
        [enc setBuffer:b_out offset:0 atIndex:0];
        NSUInteger tgw = MIN((NSUInteger)w, 16u), tgh = MIN((NSUInteger)h, 16u);
        [enc dispatchThreads:MTLSizeMake((NSUInteger)w, (NSUInteger)h, 1)
            threadsPerThreadgroup:MTLSizeMake(tgw, tgh, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        double gputime_ns = ([cb GPUEndTime] > 0) ? ([cb GPUEndTime] - [cb GPUStartTime]) * 1e9 : -1;
        alarm(0);

        MTLCommandBufferStatus cbs = cb.status;
        out[@"cb_status"] = @((long)cbs);
        out[@"status"] = (cbs == MTLCommandBufferStatusCompleted) ? @"ok" : @"cb_error";
        if (cb.error) out[@"err"] = cb.error.localizedDescription;
        out[@"gputime_ns"] = @(gputime_ns);
        NSMutableString *oh = [NSMutableString string];
        hex_append(oh, b_out.contents, w * h * sizeof(float));
        out[@"out_hex"] = oh;

        NSError *jerr = nil;
        NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:&jerr];
        if (!j) { fprintf(stderr, "json encode fail\n"); return 1; }
        fwrite("JSON ", 1, 5, stdout);
        fwrite(j.bytes, 1, j.length, stdout);
        fwrite("\n", 1, 1, stdout);
        int ok = (fflush(stdout) == 0) && (ferror(stdout) == 0);
        return ok ? 0 : 1;
    }
}
