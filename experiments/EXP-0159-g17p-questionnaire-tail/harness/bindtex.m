// bindtex.m — EXP-0159 family FC (TEX-19). Authored by the clean-room RE team.
// Bindless (argument-buffer) texture ceiling probe on G17P.
//
// Declares a CAP-entry argument-buffer texture array, populates canary entries
// with 1x1 R32Uint textures whose texel is 0xC0000000|k, then selects entries
// with a genuinely runtime uint index — uniformly and per-lane — across
// boundary indices up to and PAST the published 1,000,000 ceiling.  The arm is
// run twice: CAP = 1,000,000 (the published limit) and CAP = 2,000,000, so a
// hardware indexing ceiling can be told apart from an API/validation limit.
//
// Every command-buffer error is re-run to a majority of 3 and its OS fault
// classification recorded verbatim, per FIELD-SWEEP-PROTOCOL.md sec.7 — a
// sibling agent's GPU error arrives here as ...ErrorInnocentVictim.
//
// Clean-room: PUBLIC Metal API + OWN-SHADER (kernels/bindtex.metal).
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void rec(NSDictionary *d) {
    NSData *j = [NSJSONSerialization dataWithJSONObject:d options:0 error:nil];
    printf("REC %.*s\n", (int)[j length], (const char *)[j bytes]);
    fflush(stdout);
}
static NSString *errstr(NSError *e) { return e ? [e localizedDescription] : @""; }

typedef void (^EncodeBlock)(id<MTLComputeCommandEncoder> ce);
static int runMajority(id<MTLCommandQueue> *q, id<MTLDevice> dev,
                       id<MTLComputePipelineState> pso, id<MTLBuffer> outbuf,
                       NSUInteger outLen, MTLSize grid, MTLSize tg,
                       EncodeBlock enc, NSString **outFault, int *outErrs) {
    int attempts = 0, errs = 0;
    NSString *fc = @"";
    for (attempts = 1; attempts <= 3; attempts++) {
        memset([outbuf contents], 0xA5, outLen);      // poisoned read-back buffer
        id<MTLCommandBuffer> cb = [*q commandBuffer];
        id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
        [ce setComputePipelineState:pso];
        enc(ce);
        [ce dispatchThreads:grid threadsPerThreadgroup:tg];
        [ce endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            errs++; fc = errstr([cb error]);
            *q = [dev newCommandQueue];
            continue;
        }
        // A dispatch that reports OK but leaves the poisoned read-back buffer
        // untouched has not done its job; retry it rather than record the
        // poison as data.  (Seen once on G17P under concurrent GPU load.)
        if (outLen >= 4 && *(const uint32_t *)[outbuf contents] == 0xA5A5A5A5u) {
            errs++; fc = @"dispatch reported OK but left the poisoned output unwritten";
            continue;
        }
        break;
    }
    if (outFault) *outFault = fc;
    if (outErrs) *outErrs = errs;
    return attempts;
}

static void arm(id<MTLDevice> dev, NSString *src, NSUInteger CAP,
                NSArray *canaries, NSArray *probes, NSArray *lanes) {
    NSString *tag = [NSString stringWithFormat:@"cap%lu", (unsigned long)CAP];
    NSString *s = [src stringByReplacingOccurrencesOfString:@"#define CAP 1000000"
                   withString:[NSString stringWithFormat:@"#define CAP %lu", (unsigned long)CAP]];
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:s options:[MTLCompileOptions new] error:&err];
    if (!lib) { rec(@{@"family":@"fc",@"case":[tag stringByAppendingString:@"/compile"],
                      @"outcome":@"reject",@"note":errstr(err)}); return; }
    id<MTLFunction> fnU = [lib newFunctionWithName:@"k_uniform"];
    id<MTLFunction> fnL = [lib newFunctionWithName:@"k_perlane"];
    NSError *e1=nil,*e2=nil;
    id<MTLComputePipelineState> psoU = [dev newComputePipelineStateWithFunction:fnU error:&e1];
    id<MTLComputePipelineState> psoL = [dev newComputePipelineStateWithFunction:fnL error:&e2];
    if (!psoU || !psoL) { rec(@{@"family":@"fc",@"case":[tag stringByAppendingString:@"/pso"],
                                @"outcome":@"reject",
                                @"note":[NSString stringWithFormat:@"%@|%@",errstr(e1),errstr(e2)]}); return; }
    id<MTLArgumentEncoder> aenc = [fnU newArgumentEncoderWithBufferIndex:0];
    NSUInteger encLen = [aenc encodedLength];
    id<MTLBuffer> argbuf = [dev newBufferWithLength:encLen options:MTLResourceStorageModeShared];
    rec(@{@"family":@"fc",@"case":[tag stringByAppendingString:@"/argbuf"],
          @"value":@(CAP),@"encoded_length":@(encLen),@"outcome":(argbuf?@"ok":@"fault"),
          @"note":[NSString stringWithFormat:@"%.3f bytes/entry", (double)encLen/(double)CAP],
          @"target":@"G17P"});
    if (!argbuf) return;
    [aenc setArgumentBuffer:argbuf offset:0];

    NSMutableArray *texs = [NSMutableArray array];
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Uint
                                                                                  width:1 height:1 mipmapped:NO];
    td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
    for (NSNumber *k in canaries) {
        id<MTLTexture> t = [dev newTextureWithDescriptor:td];
        uint32_t v = 0xC0000000u | ([k unsignedIntValue] & 0x00FFFFFFu);
        [t replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0 withBytes:&v bytesPerRow:4];
        [texs addObject:t];
        [aenc setTexture:t atIndex:[k unsignedIntegerValue]];
    }
    const uint64_t *ab = (const uint64_t *)[argbuf contents];
    for (NSUInteger i = 0; i < [canaries count]; i++)
        rec(@{@"family":@"fc",@"case":[NSString stringWithFormat:@"%@/entry_bytes_%@",tag,canaries[i]],
              @"value":canaries[i],@"outcome":@"ok",@"target":@"G17P",
              @"observed":[NSString stringWithFormat:@"%016llx",
                           (unsigned long long)ab[[canaries[i] unsignedIntegerValue]]],
              @"note":[NSString stringWithFormat:@"gpuResourceID._impl=%llu",
                       (unsigned long long)[(id<MTLTexture>)texs[i] gpuResourceID]._impl]});

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLBuffer> idxbuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    id<MTLBuffer> outbuf = [dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    NSSet *canset = [NSSet setWithArray:canaries];

    for (NSNumber *k in probes) {
        uint32_t idx = [k unsignedIntValue];
        memcpy([idxbuf contents], &idx, 4);
        NSString *fc = @""; int errs = 0;
        int attempts = runMajority(&q, dev, psoU, outbuf, 64, MTLSizeMake(1,1,1), MTLSizeMake(1,1,1),
                                   ^(id<MTLComputeCommandEncoder> ce) {
            [ce setBuffer:argbuf offset:0 atIndex:0];
            [ce setBuffer:idxbuf offset:0 atIndex:1];
            [ce setBuffer:outbuf offset:0 atIndex:2];
            for (id<MTLTexture> t in texs) [ce useResource:t usage:MTLResourceUsageRead];
        }, &fc, &errs);
        uint32_t got = *(const uint32_t *)[outbuf contents];
        BOOL isCan = [canset containsObject:k];
        uint32_t expect = isCan ? (0xC0000000u | (idx & 0x00FFFFFFu)) : 0u;
        NSString *outcome;
        if (errs >= 3) outcome = ([fc rangeOfString:@"InnocentVictim"].location != NSNotFound
                                  ? @"victim" : @"fault");
        else if (got == expect) outcome = @"ok";
        else if (got == 0) outcome = @"silent_zero";
        else if (got == 0xA5A5A5A5u) outcome = @"unwritten";
        else outcome = @"wrong_value";
        rec(@{@"family":@"fc",@"case":[NSString stringWithFormat:@"%@/uniform_%@",tag,k],@"value":k,
              @"observed":[NSString stringWithFormat:@"%08x",got],
              @"oracle":[NSString stringWithFormat:@"%08x",expect],
              @"populated":@(isCan),@"match":@(got == expect && errs < 3),@"outcome":outcome,
              @"fault_class":fc,@"attempts":@(attempts),@"cb_errors":@(errs),
              @"in_declared_array":@(idx < CAP),@"target":@"G17P"});
    }

    {
        NSUInteger nl = [lanes count];
        uint32_t *lv = calloc(nl, 4);
        for (NSUInteger i = 0; i < nl; i++) lv[i] = [lanes[i] unsignedIntValue];
        id<MTLBuffer> lb = [dev newBufferWithBytes:lv length:nl*4 options:MTLResourceStorageModeShared];
        NSString *fc = @""; int errs = 0;
        runMajority(&q, dev, psoL, outbuf, 64, MTLSizeMake(nl,1,1), MTLSizeMake(nl,1,1),
                    ^(id<MTLComputeCommandEncoder> ce) {
            [ce setBuffer:argbuf offset:0 atIndex:0];
            [ce setBuffer:lb offset:0 atIndex:1];
            [ce setBuffer:outbuf offset:0 atIndex:2];
            for (id<MTLTexture> t in texs) [ce useResource:t usage:MTLResourceUsageRead];
        }, &fc, &errs);
        const uint32_t *o = (const uint32_t *)[outbuf contents];
        NSMutableString *obs=[NSMutableString string], *exp=[NSMutableString string];
        BOOL all = YES;
        for (NSUInteger i = 0; i < nl; i++) {
            uint32_t e = [canset containsObject:lanes[i]] ? (0xC0000000u | (lv[i] & 0x00FFFFFFu)) : 0u;
            [obs appendFormat:@"%08x ", o[i]]; [exp appendFormat:@"%08x ", e];
            if (o[i] != e) all = NO;
        }
        free(lv);
        rec(@{@"family":@"fc",@"case":[tag stringByAppendingString:@"/perlane_divergent"],
              @"observed":obs,@"oracle":exp,@"match":@(all && errs < 3),
              @"outcome":(errs>=3?([fc rangeOfString:@"InnocentVictim"].location!=NSNotFound?@"victim":@"fault")
                                 :(all?@"ok":@"wrong_value")),
              @"fault_class":fc,@"cb_errors":@(errs),
              @"note":[NSString stringWithFormat:@"lanes %@",[lanes componentsJoinedByString:@","]],
              @"target":@"G17P"});
    }
}

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 2) { fprintf(stderr, "usage: bindtex <source.metal>\n"); return 2; }
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { rec(@{@"family":@"fc",@"case":@"source",@"outcome":@"fault",@"note":errstr(err)}); return 2; }
    rec(@{@"family":@"fc",@"case":@"argbuf_tier",@"observed":@([dev argumentBuffersSupport]),
          @"outcome":@"ok",@"target":@"G17P",@"note":@"MTLArgumentBuffersTier (1 == Tier2)"});

    // API-level ceiling: what declared CAP does the runtime compiler accept?
    for (NSNumber *c in @[@1000000, @1000001, @2000000, @16777216, @67108864]) {
        NSString *s = [src stringByReplacingOccurrencesOfString:@"#define CAP 1000000"
                       withString:[NSString stringWithFormat:@"#define CAP %@", c]];
        NSError *e2 = nil;
        id<MTLLibrary> l = [dev newLibraryWithSource:s options:[MTLCompileOptions new] error:&e2];
        NSMutableDictionary *r = [@{@"family":@"fc",
                                    @"case":[NSString stringWithFormat:@"declared_cap_%@",c],
                                    @"value":c,@"outcome":(l?@"ok":@"reject"),
                                    @"observed":(l?@"accept":@"reject"),@"target":@"G17P"} mutableCopy];
        if (!l) r[@"note"] = errstr(e2);
        else r[@"encoded_length"] = @([[[l newFunctionWithName:@"k_uniform"]
                                        newArgumentEncoderWithBufferIndex:0] encodedLength]);
        rec(r);
    }

    // Arm 1 — the published ceiling.
    arm(dev, src, 1000000,
        @[@0,@1,@2,@7,@255,@256,@65535,@65536,@262143,@499999,@500000,@999998,@999999],
        @[@0,@1,@2,@3,@7,@255,@256,@4096,@65535,@65536,@262143,@499998,@499999,@500000,@500001,
          @999996,@999997,@999998,@999999,@1000000,@1000001,@2000000],
        @[@0,@1,@255,@65535,@262143,@499999,@999998,@999999]);
    // Arm 2 — PAST the published ceiling: is 1,000,000 a hardware limit or an API one?
    arm(dev, src, 2000000,
        @[@0,@999999,@1000000,@1000001,@1048576,@1999998,@1999999],
        @[@0,@999999,@1000000,@1000001,@1048576,@1500000,@1999998,@1999999,@2000000],
        @[@0,@999999,@1000000,@1000001,@1048576,@1999998,@1999999,@2000000]);

    rec(@{@"family":@"fc",@"case":@"__done",@"outcome":@"ok",@"target":@"G17P"});
    return 0;
  }
}
