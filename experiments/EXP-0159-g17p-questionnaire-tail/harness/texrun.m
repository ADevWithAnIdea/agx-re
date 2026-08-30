// texrun.m — EXP-0159 family FF (TEX-01). Authored by the clean-room RE team.
//
// The texture/sampler analogue of tools/agxtest/agxrun_persist: loads a
// (possibly spliced) serialized MTLBinaryArchive, forces the compute pipeline
// to instantiate from the archive's precompiled machine code
// (MTLPipelineOptionFailOnBinaryArchiveMiss, so a successful run PROVES the
// spliced bytes executed), binds an authored mipmapped texture + sampler, and
// sweeps input coordinate triples read from a case file.
//
// The bound texture is 4x4 R32Float, 3 mip levels, texel = 1000*L + 100*y + x,
// so a returned float NAMES the exact texel and mip level that was sampled.
// --array binds a 3-layer 2D array texture instead (texel = 1000*layer+100*y+x).
//
// Clean-room: PUBLIC Metal API + OWN-SHADER. No Apple binary is inspected.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void rec(NSDictionary *d) {
    NSData *j = [NSJSONSerialization dataWithJSONObject:d options:0 error:nil];
    printf("REC %.*s\n", (int)[j length], (const char *)[j bytes]);
    fflush(stdout);
}
static NSString *errstr(NSError *e) { return e ? [e localizedDescription] : @""; }

int main(int argc, char **argv) {
  @autoreleasepool {
    // usage: texrun <archive> <function> <label> <casefile> [--array]
    if (argc < 5) { fprintf(stderr, "usage: texrun <archive> <function> <label> <casefile> [--array]\n"); return 2; }
    BOOL isArray = (argc >= 6 && strcmp(argv[5], "--array") == 0);
    NSString *label = [NSString stringWithUTF8String:argv[3]];
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    NSError *err = nil;
    NSURL *au = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
    id<MTLLibrary> lib = [dev newLibraryWithURL:au error:&err];
    if (!lib) { rec(@{@"family":@"ff",@"case":label,@"outcome":@"undecodable",@"note":errstr(err)}); return 3; }
    id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:argv[2]]];
    if (!fn) { rec(@{@"family":@"ff",@"case":label,@"outcome":@"undecodable",@"note":@"function missing"}); return 3; }
    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    [ad setUrl:au];
    id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (!arc) { rec(@{@"family":@"ff",@"case":label,@"outcome":@"undecodable",@"note":errstr(err)}); return 3; }
    MTLComputePipelineDescriptor *pd = [MTLComputePipelineDescriptor new];
    [pd setComputeFunction:fn];
    [pd setBinaryArchives:@[arc]];
    id<MTLComputePipelineState> pso =
        [dev newComputePipelineStateWithDescriptor:pd
                                           options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                        reflection:nil error:&err];
    if (!pso) { rec(@{@"family":@"ff",@"case":label,@"outcome":@"undecodable",
                      @"note":[@"PIPELINE_MISS " stringByAppendingString:errstr(err)]}); return 3; }

    // authored texture
    id<MTLTexture> tex;
    if (isArray) {
        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.textureType = MTLTextureType2DArray; td.pixelFormat = MTLPixelFormatR32Float;
        td.width = 4; td.height = 4; td.arrayLength = 3; td.mipmapLevelCount = 1;
        td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
        tex = [dev newTextureWithDescriptor:td];
        for (int L = 0; L < 3; L++) {
            float px[16];
            for (int y = 0; y < 4; y++) for (int x = 0; x < 4; x++) px[y*4+x] = 1000.0f*L + 100.0f*y + x;
            [tex replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 slice:L
                     withBytes:px bytesPerRow:16 bytesPerImage:64];
        }
    } else {
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                                                      width:4 height:4 mipmapped:YES];
        td.mipmapLevelCount = 3; td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
        tex = [dev newTextureWithDescriptor:td];
        for (int L = 0; L < 3; L++) {
            int w = 4 >> L; if (w < 1) w = 1;
            float *px = malloc(sizeof(float)*w*w);
            for (int y = 0; y < w; y++) for (int x = 0; x < w; x++) px[y*w+x] = 1000.0f*L + 100.0f*y + x;
            [tex replaceRegion:MTLRegionMake2D(0,0,w,w) mipmapLevel:L withBytes:px bytesPerRow:4*w];
            free(px);
        }
    }
    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
    sd.minFilter = sd.magFilter = MTLSamplerMinMagFilterNearest;
    sd.mipFilter = MTLSamplerMipFilterNearest;
    sd.sAddressMode = sd.tAddressMode = sd.rAddressMode = MTLSamplerAddressModeClampToEdge;
    id<MTLSamplerState> smp = [dev newSamplerStateWithDescriptor:sd];

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLBuffer> cin = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> out = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];

    FILE *cf = fopen(argv[4], "r");
    if (!cf) { fprintf(stderr, "cannot open case file\n"); return 2; }
    char line[512];
    while (fgets(line, sizeof(line), cf)) {
        if (line[0] == '#' || line[0] == '\n') continue;
        char cname[128] = {0};
        double u = 0, v = 0, w = 0;
        // case-name u v w  (u/v/w may be inf/-inf/nan, parsed by strtod)
        char *p = line;
        int n = 0; while (*p && !isspace((unsigned char)*p) && n < 127) cname[n++] = *p++;
        u = strtod(p, &p); v = strtod(p, &p); w = strtod(p, &p);
        float f[4] = { (float)u, (float)v, (float)w, 0.0f };
        memcpy([cin contents], f, sizeof(f));
        // majority-of-3: a lone command-buffer error is never a property of the
        // encoding (FIELD-SWEEP-PROTOCOL.md sec.7)
        int errs = 0; NSString *fc = @"";
        for (int att = 1; att <= 3; att++) {
            memset([out contents], 0xA5, 16);          // poisoned read-back buffer
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
            [ce setComputePipelineState:pso];
            [ce setBuffer:out offset:0 atIndex:0];
            [ce setBuffer:cin offset:0 atIndex:1];
            [ce setTexture:tex atIndex:0];
            [ce setSamplerState:smp atIndex:0];
            [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
            [ce endEncoding]; [cb commit]; [cb waitUntilCompleted];
            if ([cb status] == MTLCommandBufferStatusError) {
                errs++; fc = errstr([cb error]); q = [dev newCommandQueue]; continue;
            }
            // OK but the poisoned read-back buffer is untouched: retry rather
            // than record the poison as data.
            if (*(const uint32_t *)[out contents] == 0xA5A5A5A5u) {
                errs++; fc = @"dispatch reported OK but left the poisoned output unwritten";
                continue;
            }
            break;
        }
        BOOL fault = (errs >= 3);
        uint32_t raw = *(const uint32_t *)[out contents];
        float got = *(const float *)[out contents];
        // every float is emitted as a STRING: inf/nan are not representable in JSON
        rec(@{@"family":@"ff",@"case":[NSString stringWithFormat:@"%@/%s",label,cname],
              @"form_label":label, @"sub":[NSString stringWithUTF8String:cname],
              @"u":[NSString stringWithFormat:@"%.9g",u],
              @"v":[NSString stringWithFormat:@"%.9g",v],
              @"w":[NSString stringWithFormat:@"%.9g",w],
              @"observed":[NSString stringWithFormat:@"%.9g",(double)got],
              @"observed_hex":[NSString stringWithFormat:@"%08x",raw],
              @"outcome":(fault?([fc rangeOfString:@"InnocentVictim"].location!=NSNotFound?@"victim":@"fault")
                               :(raw==0xA5A5A5A5u?@"unwritten":@"ok")),
              @"fault_class":fc, @"cb_errors":@(errs),
              @"array":@(isArray), @"target":@"G17P"});
    }
    fclose(cf);
    rec(@{@"family":@"ff",@"case":[NSString stringWithFormat:@"%@/__done",label],@"outcome":@"ok",@"target":@"G17P"});
    return 0;
  }
}
