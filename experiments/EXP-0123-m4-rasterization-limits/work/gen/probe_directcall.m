#import <Metal/Metal.h>
int main() {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = nil; // just type-check, no need to run
    if (enc) { [enc setLineWidth:5.0f]; }
    return 0;
}
