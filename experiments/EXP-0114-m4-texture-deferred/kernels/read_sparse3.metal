// PILOT (not part of frozen contract) -- discriminates two hypotheses for the
// texture "read" selector field (op+4):
//   H_compact: op+4 = order-of-first-use index into a table compacted to only
//              the textures the compiled function actually references.
//   H_literal: op+4 = the literal declared [[texture(N)]] binding index.
// Declares 128 texture args (max legal), but reads only THREE of them, at
// widely separated, non-contiguous declared indices (5, 50, 100), in that
// exact source order. If op+4 sequence for the 3 read bundles comes out
// {0,1,2} -> H_compact. If it comes out {5,50,100} -> H_literal.
#include <metal_stdlib>
using namespace metal;

kernel void ksparse(
    texture2d<uint, access::read> t0 [[texture(0)]], texture2d<uint, access::read> t1 [[texture(1)]],
    texture2d<uint, access::read> t2 [[texture(2)]], texture2d<uint, access::read> t3 [[texture(3)]],
    texture2d<uint, access::read> t4 [[texture(4)]], texture2d<uint, access::read> t5 [[texture(5)]],
    texture2d<uint, access::read> t6 [[texture(6)]], texture2d<uint, access::read> t7 [[texture(7)]],
    texture2d<uint, access::read> t8 [[texture(8)]], texture2d<uint, access::read> t9 [[texture(9)]],
    texture2d<uint, access::read> t10 [[texture(10)]], texture2d<uint, access::read> t11 [[texture(11)]],
    texture2d<uint, access::read> t12 [[texture(12)]], texture2d<uint, access::read> t13 [[texture(13)]],
    texture2d<uint, access::read> t14 [[texture(14)]], texture2d<uint, access::read> t15 [[texture(15)]],
    texture2d<uint, access::read> t16 [[texture(16)]], texture2d<uint, access::read> t17 [[texture(17)]],
    texture2d<uint, access::read> t18 [[texture(18)]], texture2d<uint, access::read> t19 [[texture(19)]],
    texture2d<uint, access::read> t20 [[texture(20)]], texture2d<uint, access::read> t21 [[texture(21)]],
    texture2d<uint, access::read> t22 [[texture(22)]], texture2d<uint, access::read> t23 [[texture(23)]],
    texture2d<uint, access::read> t24 [[texture(24)]], texture2d<uint, access::read> t25 [[texture(25)]],
    texture2d<uint, access::read> t26 [[texture(26)]], texture2d<uint, access::read> t27 [[texture(27)]],
    texture2d<uint, access::read> t28 [[texture(28)]], texture2d<uint, access::read> t29 [[texture(29)]],
    texture2d<uint, access::read> t30 [[texture(30)]], texture2d<uint, access::read> t31 [[texture(31)]],
    texture2d<uint, access::read> t32 [[texture(32)]], texture2d<uint, access::read> t33 [[texture(33)]],
    texture2d<uint, access::read> t34 [[texture(34)]], texture2d<uint, access::read> t35 [[texture(35)]],
    texture2d<uint, access::read> t36 [[texture(36)]], texture2d<uint, access::read> t37 [[texture(37)]],
    texture2d<uint, access::read> t38 [[texture(38)]], texture2d<uint, access::read> t39 [[texture(39)]],
    texture2d<uint, access::read> t40 [[texture(40)]], texture2d<uint, access::read> t41 [[texture(41)]],
    texture2d<uint, access::read> t42 [[texture(42)]], texture2d<uint, access::read> t43 [[texture(43)]],
    texture2d<uint, access::read> t44 [[texture(44)]], texture2d<uint, access::read> t45 [[texture(45)]],
    texture2d<uint, access::read> t46 [[texture(46)]], texture2d<uint, access::read> t47 [[texture(47)]],
    texture2d<uint, access::read> t48 [[texture(48)]], texture2d<uint, access::read> t49 [[texture(49)]],
    texture2d<uint, access::read> t50 [[texture(50)]], texture2d<uint, access::read> t51 [[texture(51)]],
    texture2d<uint, access::read> t52 [[texture(52)]], texture2d<uint, access::read> t53 [[texture(53)]],
    texture2d<uint, access::read> t54 [[texture(54)]], texture2d<uint, access::read> t55 [[texture(55)]],
    texture2d<uint, access::read> t56 [[texture(56)]], texture2d<uint, access::read> t57 [[texture(57)]],
    texture2d<uint, access::read> t58 [[texture(58)]], texture2d<uint, access::read> t59 [[texture(59)]],
    texture2d<uint, access::read> t60 [[texture(60)]], texture2d<uint, access::read> t61 [[texture(61)]],
    texture2d<uint, access::read> t62 [[texture(62)]], texture2d<uint, access::read> t63 [[texture(63)]],
    texture2d<uint, access::read> t64 [[texture(64)]], texture2d<uint, access::read> t65 [[texture(65)]],
    texture2d<uint, access::read> t66 [[texture(66)]], texture2d<uint, access::read> t67 [[texture(67)]],
    texture2d<uint, access::read> t68 [[texture(68)]], texture2d<uint, access::read> t69 [[texture(69)]],
    texture2d<uint, access::read> t70 [[texture(70)]], texture2d<uint, access::read> t71 [[texture(71)]],
    texture2d<uint, access::read> t72 [[texture(72)]], texture2d<uint, access::read> t73 [[texture(73)]],
    texture2d<uint, access::read> t74 [[texture(74)]], texture2d<uint, access::read> t75 [[texture(75)]],
    texture2d<uint, access::read> t76 [[texture(76)]], texture2d<uint, access::read> t77 [[texture(77)]],
    texture2d<uint, access::read> t78 [[texture(78)]], texture2d<uint, access::read> t79 [[texture(79)]],
    texture2d<uint, access::read> t80 [[texture(80)]], texture2d<uint, access::read> t81 [[texture(81)]],
    texture2d<uint, access::read> t82 [[texture(82)]], texture2d<uint, access::read> t83 [[texture(83)]],
    texture2d<uint, access::read> t84 [[texture(84)]], texture2d<uint, access::read> t85 [[texture(85)]],
    texture2d<uint, access::read> t86 [[texture(86)]], texture2d<uint, access::read> t87 [[texture(87)]],
    texture2d<uint, access::read> t88 [[texture(88)]], texture2d<uint, access::read> t89 [[texture(89)]],
    texture2d<uint, access::read> t90 [[texture(90)]], texture2d<uint, access::read> t91 [[texture(91)]],
    texture2d<uint, access::read> t92 [[texture(92)]], texture2d<uint, access::read> t93 [[texture(93)]],
    texture2d<uint, access::read> t94 [[texture(94)]], texture2d<uint, access::read> t95 [[texture(95)]],
    texture2d<uint, access::read> t96 [[texture(96)]], texture2d<uint, access::read> t97 [[texture(97)]],
    texture2d<uint, access::read> t98 [[texture(98)]], texture2d<uint, access::read> t99 [[texture(99)]],
    texture2d<uint, access::read> t100 [[texture(100)]], texture2d<uint, access::read> t101 [[texture(101)]],
    texture2d<uint, access::read> t102 [[texture(102)]], texture2d<uint, access::read> t103 [[texture(103)]],
    texture2d<uint, access::read> t104 [[texture(104)]], texture2d<uint, access::read> t105 [[texture(105)]],
    texture2d<uint, access::read> t106 [[texture(106)]], texture2d<uint, access::read> t107 [[texture(107)]],
    texture2d<uint, access::read> t108 [[texture(108)]], texture2d<uint, access::read> t109 [[texture(109)]],
    texture2d<uint, access::read> t110 [[texture(110)]], texture2d<uint, access::read> t111 [[texture(111)]],
    texture2d<uint, access::read> t112 [[texture(112)]], texture2d<uint, access::read> t113 [[texture(113)]],
    texture2d<uint, access::read> t114 [[texture(114)]], texture2d<uint, access::read> t115 [[texture(115)]],
    texture2d<uint, access::read> t116 [[texture(116)]], texture2d<uint, access::read> t117 [[texture(117)]],
    texture2d<uint, access::read> t118 [[texture(118)]], texture2d<uint, access::read> t119 [[texture(119)]],
    texture2d<uint, access::read> t120 [[texture(120)]], texture2d<uint, access::read> t121 [[texture(121)]],
    texture2d<uint, access::read> t122 [[texture(122)]], texture2d<uint, access::read> t123 [[texture(123)]],
    texture2d<uint, access::read> t124 [[texture(124)]], texture2d<uint, access::read> t125 [[texture(125)]],
    texture2d<uint, access::read> t126 [[texture(126)]], texture2d<uint, access::read> t127 [[texture(127)]],
    device uint *o [[buffer(0)]], uint i [[thread_position_in_grid]])
{
    uint2 c = uint2(0,0);
    // only 3 of 128 declared textures are actually read, in this exact order,
    // at widely separated declared indices.
    o[0] = t5.read(c).x + t50.read(c).x * 2 + t100.read(c).x * 3;
}
