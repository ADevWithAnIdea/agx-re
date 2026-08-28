#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main(int argc, char**argv) {
    @autoreleasepool {
        float width = argc>1 ? atof(argv[1]) : 5.0;
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSError *err=nil;
        NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\nstruct VOut{float4 position [[position]];};\nvertex VOut vs(uint vid [[vertex_id]]){float2 p[2]={float2(-0.8,0.0),float2(0.8,0.0)};VOut o;o.position=float4(p[vid],0,1);return o;}\nfragment float4 fs(){return float4(1,1,1,1);}\n";
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        id<MTLFunction> vf=[lib newFunctionWithName:@"vs"]; id<MTLFunction> ff=[lib newFunctionWithName:@"fs"];
        MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
        pd.vertexFunction=vf; pd.fragmentFunction=ff;
        pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
        pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassLine;
        id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1;}
        id<MTLTexture> tgt;
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:16 height:16 mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget; td.storageMode=MTLStorageModeShared;
        tgt=[dev newTextureWithDescriptor:td];
        id<MTLCommandQueue> queue=[dev newCommandQueue];
        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture=tgt; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
        id<MTLCommandBuffer> cb=[queue commandBuffer];
        id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        @try {
            [enc performSelector:@selector(setLineWidth:) withObject:[NSNumber numberWithFloat:width]];
        } @catch (NSException *ex) { printf("setLineWidth EXCEPTION: %s\n", [[ex reason] UTF8String]); }
        [enc drawPrimitives:MTLPrimitiveTypeLine vertexStart:0 vertexCount:2];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if ([cb status]==MTLCommandBufferStatusError) { printf("CMDBUF_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]); return 1; }
        float *px=(float*)malloc(sizeof(float)*4*16*16);
        [tgt getBytes:px bytesPerRow:16*4*sizeof(float) fromRegion:MTLRegionMake2D(0,0,16,16) mipmapLevel:0];
        int count=0;
        for(int y=0;y<16;y++){ for(int x=0;x<16;x++){ float*p=px+(y*16+x)*4; if(p[3]>0.5) count++; } }
        printf("width=%.1f litpixels=%d\n", width, count);
    }
    return 0;
}
