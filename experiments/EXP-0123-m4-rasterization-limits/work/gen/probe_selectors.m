#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main() {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> t = [dev newTextureWithDescriptor:td];
        rp.colorAttachments[0].texture = t;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        NSArray *sels = @[@"setLineWidth:", @"lineWidth", @"setLineRasterizationMode:",
                           @"setWideLineWidth:", @"setPolygonMode:", @"setLineWidthMTL:",
                           @"setDepthBias:slopeScale:clamp:", @"setDepthClipMode:",
                           @"setTriangleFillMode:", @"setConservativeRasterizationEnabled:"];
        for (NSString *s in sels) {
            SEL sel = NSSelectorFromString(s);
            BOOL yes = [enc respondsToSelector:sel];
            printf("%s -> %s\n", [s UTF8String], yes ? "YES" : "no");
        }
        [enc endEncoding];
        return 0;
    }
}
