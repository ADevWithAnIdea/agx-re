#include <metal_stdlib>
using namespace metal;

kernel void kread_n127(
    texture2d<uint, access::read> t0 [[texture(0)]],
    texture2d<uint, access::read> t1 [[texture(1)]],
    texture2d<uint, access::read> t2 [[texture(2)]],
    texture2d<uint, access::read> t3 [[texture(3)]],
    texture2d<uint, access::read> t4 [[texture(4)]],
    texture2d<uint, access::read> t5 [[texture(5)]],
    texture2d<uint, access::read> t6 [[texture(6)]],
    texture2d<uint, access::read> t7 [[texture(7)]],
    texture2d<uint, access::read> t8 [[texture(8)]],
    texture2d<uint, access::read> t9 [[texture(9)]],
    texture2d<uint, access::read> t10 [[texture(10)]],
    texture2d<uint, access::read> t11 [[texture(11)]],
    texture2d<uint, access::read> t12 [[texture(12)]],
    texture2d<uint, access::read> t13 [[texture(13)]],
    texture2d<uint, access::read> t14 [[texture(14)]],
    texture2d<uint, access::read> t15 [[texture(15)]],
    texture2d<uint, access::read> t16 [[texture(16)]],
    texture2d<uint, access::read> t17 [[texture(17)]],
    texture2d<uint, access::read> t18 [[texture(18)]],
    texture2d<uint, access::read> t19 [[texture(19)]],
    texture2d<uint, access::read> t20 [[texture(20)]],
    texture2d<uint, access::read> t21 [[texture(21)]],
    texture2d<uint, access::read> t22 [[texture(22)]],
    texture2d<uint, access::read> t23 [[texture(23)]],
    texture2d<uint, access::read> t24 [[texture(24)]],
    texture2d<uint, access::read> t25 [[texture(25)]],
    texture2d<uint, access::read> t26 [[texture(26)]],
    texture2d<uint, access::read> t27 [[texture(27)]],
    texture2d<uint, access::read> t28 [[texture(28)]],
    texture2d<uint, access::read> t29 [[texture(29)]],
    texture2d<uint, access::read> t30 [[texture(30)]],
    texture2d<uint, access::read> t31 [[texture(31)]],
    texture2d<uint, access::read> t32 [[texture(32)]],
    texture2d<uint, access::read> t33 [[texture(33)]],
    texture2d<uint, access::read> t34 [[texture(34)]],
    texture2d<uint, access::read> t35 [[texture(35)]],
    texture2d<uint, access::read> t36 [[texture(36)]],
    texture2d<uint, access::read> t37 [[texture(37)]],
    texture2d<uint, access::read> t38 [[texture(38)]],
    texture2d<uint, access::read> t39 [[texture(39)]],
    texture2d<uint, access::read> t40 [[texture(40)]],
    texture2d<uint, access::read> t41 [[texture(41)]],
    texture2d<uint, access::read> t42 [[texture(42)]],
    texture2d<uint, access::read> t43 [[texture(43)]],
    texture2d<uint, access::read> t44 [[texture(44)]],
    texture2d<uint, access::read> t45 [[texture(45)]],
    texture2d<uint, access::read> t46 [[texture(46)]],
    texture2d<uint, access::read> t47 [[texture(47)]],
    texture2d<uint, access::read> t48 [[texture(48)]],
    texture2d<uint, access::read> t49 [[texture(49)]],
    texture2d<uint, access::read> t50 [[texture(50)]],
    texture2d<uint, access::read> t51 [[texture(51)]],
    texture2d<uint, access::read> t52 [[texture(52)]],
    texture2d<uint, access::read> t53 [[texture(53)]],
    texture2d<uint, access::read> t54 [[texture(54)]],
    texture2d<uint, access::read> t55 [[texture(55)]],
    texture2d<uint, access::read> t56 [[texture(56)]],
    texture2d<uint, access::read> t57 [[texture(57)]],
    texture2d<uint, access::read> t58 [[texture(58)]],
    texture2d<uint, access::read> t59 [[texture(59)]],
    texture2d<uint, access::read> t60 [[texture(60)]],
    texture2d<uint, access::read> t61 [[texture(61)]],
    texture2d<uint, access::read> t62 [[texture(62)]],
    texture2d<uint, access::read> t63 [[texture(63)]],
    texture2d<uint, access::read> t64 [[texture(64)]],
    texture2d<uint, access::read> t65 [[texture(65)]],
    texture2d<uint, access::read> t66 [[texture(66)]],
    texture2d<uint, access::read> t67 [[texture(67)]],
    texture2d<uint, access::read> t68 [[texture(68)]],
    texture2d<uint, access::read> t69 [[texture(69)]],
    texture2d<uint, access::read> t70 [[texture(70)]],
    texture2d<uint, access::read> t71 [[texture(71)]],
    texture2d<uint, access::read> t72 [[texture(72)]],
    texture2d<uint, access::read> t73 [[texture(73)]],
    texture2d<uint, access::read> t74 [[texture(74)]],
    texture2d<uint, access::read> t75 [[texture(75)]],
    texture2d<uint, access::read> t76 [[texture(76)]],
    texture2d<uint, access::read> t77 [[texture(77)]],
    texture2d<uint, access::read> t78 [[texture(78)]],
    texture2d<uint, access::read> t79 [[texture(79)]],
    texture2d<uint, access::read> t80 [[texture(80)]],
    texture2d<uint, access::read> t81 [[texture(81)]],
    texture2d<uint, access::read> t82 [[texture(82)]],
    texture2d<uint, access::read> t83 [[texture(83)]],
    texture2d<uint, access::read> t84 [[texture(84)]],
    texture2d<uint, access::read> t85 [[texture(85)]],
    texture2d<uint, access::read> t86 [[texture(86)]],
    texture2d<uint, access::read> t87 [[texture(87)]],
    texture2d<uint, access::read> t88 [[texture(88)]],
    texture2d<uint, access::read> t89 [[texture(89)]],
    texture2d<uint, access::read> t90 [[texture(90)]],
    texture2d<uint, access::read> t91 [[texture(91)]],
    texture2d<uint, access::read> t92 [[texture(92)]],
    texture2d<uint, access::read> t93 [[texture(93)]],
    texture2d<uint, access::read> t94 [[texture(94)]],
    texture2d<uint, access::read> t95 [[texture(95)]],
    texture2d<uint, access::read> t96 [[texture(96)]],
    texture2d<uint, access::read> t97 [[texture(97)]],
    texture2d<uint, access::read> t98 [[texture(98)]],
    texture2d<uint, access::read> t99 [[texture(99)]],
    texture2d<uint, access::read> t100 [[texture(100)]],
    texture2d<uint, access::read> t101 [[texture(101)]],
    texture2d<uint, access::read> t102 [[texture(102)]],
    texture2d<uint, access::read> t103 [[texture(103)]],
    texture2d<uint, access::read> t104 [[texture(104)]],
    texture2d<uint, access::read> t105 [[texture(105)]],
    texture2d<uint, access::read> t106 [[texture(106)]],
    texture2d<uint, access::read> t107 [[texture(107)]],
    texture2d<uint, access::read> t108 [[texture(108)]],
    texture2d<uint, access::read> t109 [[texture(109)]],
    texture2d<uint, access::read> t110 [[texture(110)]],
    texture2d<uint, access::read> t111 [[texture(111)]],
    texture2d<uint, access::read> t112 [[texture(112)]],
    texture2d<uint, access::read> t113 [[texture(113)]],
    texture2d<uint, access::read> t114 [[texture(114)]],
    texture2d<uint, access::read> t115 [[texture(115)]],
    texture2d<uint, access::read> t116 [[texture(116)]],
    texture2d<uint, access::read> t117 [[texture(117)]],
    texture2d<uint, access::read> t118 [[texture(118)]],
    texture2d<uint, access::read> t119 [[texture(119)]],
    texture2d<uint, access::read> t120 [[texture(120)]],
    texture2d<uint, access::read> t121 [[texture(121)]],
    texture2d<uint, access::read> t122 [[texture(122)]],
    texture2d<uint, access::read> t123 [[texture(123)]],
    texture2d<uint, access::read> t124 [[texture(124)]],
    texture2d<uint, access::read> t125 [[texture(125)]],
    texture2d<uint, access::read> t126 [[texture(126)]],
    device uint *o [[buffer(0)]], uint i [[thread_position_in_grid]])
{
    uint2 c = uint2(0,0);
    uint acc = 0;
    acc += t0.read(c).x * 1u;
    acc += t1.read(c).x * 2u;
    acc += t2.read(c).x * 3u;
    acc += t3.read(c).x * 4u;
    acc += t4.read(c).x * 5u;
    acc += t5.read(c).x * 6u;
    acc += t6.read(c).x * 7u;
    acc += t7.read(c).x * 8u;
    acc += t8.read(c).x * 9u;
    acc += t9.read(c).x * 10u;
    acc += t10.read(c).x * 11u;
    acc += t11.read(c).x * 12u;
    acc += t12.read(c).x * 13u;
    acc += t13.read(c).x * 14u;
    acc += t14.read(c).x * 15u;
    acc += t15.read(c).x * 16u;
    acc += t16.read(c).x * 17u;
    acc += t17.read(c).x * 18u;
    acc += t18.read(c).x * 19u;
    acc += t19.read(c).x * 20u;
    acc += t20.read(c).x * 21u;
    acc += t21.read(c).x * 22u;
    acc += t22.read(c).x * 23u;
    acc += t23.read(c).x * 24u;
    acc += t24.read(c).x * 25u;
    acc += t25.read(c).x * 26u;
    acc += t26.read(c).x * 27u;
    acc += t27.read(c).x * 28u;
    acc += t28.read(c).x * 29u;
    acc += t29.read(c).x * 30u;
    acc += t30.read(c).x * 31u;
    acc += t31.read(c).x * 32u;
    acc += t32.read(c).x * 33u;
    acc += t33.read(c).x * 34u;
    acc += t34.read(c).x * 35u;
    acc += t35.read(c).x * 36u;
    acc += t36.read(c).x * 37u;
    acc += t37.read(c).x * 38u;
    acc += t38.read(c).x * 39u;
    acc += t39.read(c).x * 40u;
    acc += t40.read(c).x * 41u;
    acc += t41.read(c).x * 42u;
    acc += t42.read(c).x * 43u;
    acc += t43.read(c).x * 44u;
    acc += t44.read(c).x * 45u;
    acc += t45.read(c).x * 46u;
    acc += t46.read(c).x * 47u;
    acc += t47.read(c).x * 48u;
    acc += t48.read(c).x * 49u;
    acc += t49.read(c).x * 50u;
    acc += t50.read(c).x * 51u;
    acc += t51.read(c).x * 52u;
    acc += t52.read(c).x * 53u;
    acc += t53.read(c).x * 54u;
    acc += t54.read(c).x * 55u;
    acc += t55.read(c).x * 56u;
    acc += t56.read(c).x * 57u;
    acc += t57.read(c).x * 58u;
    acc += t58.read(c).x * 59u;
    acc += t59.read(c).x * 60u;
    acc += t60.read(c).x * 61u;
    acc += t61.read(c).x * 62u;
    acc += t62.read(c).x * 63u;
    acc += t63.read(c).x * 64u;
    acc += t64.read(c).x * 65u;
    acc += t65.read(c).x * 66u;
    acc += t66.read(c).x * 67u;
    acc += t67.read(c).x * 68u;
    acc += t68.read(c).x * 69u;
    acc += t69.read(c).x * 70u;
    acc += t70.read(c).x * 71u;
    acc += t71.read(c).x * 72u;
    acc += t72.read(c).x * 73u;
    acc += t73.read(c).x * 74u;
    acc += t74.read(c).x * 75u;
    acc += t75.read(c).x * 76u;
    acc += t76.read(c).x * 77u;
    acc += t77.read(c).x * 78u;
    acc += t78.read(c).x * 79u;
    acc += t79.read(c).x * 80u;
    acc += t80.read(c).x * 81u;
    acc += t81.read(c).x * 82u;
    acc += t82.read(c).x * 83u;
    acc += t83.read(c).x * 84u;
    acc += t84.read(c).x * 85u;
    acc += t85.read(c).x * 86u;
    acc += t86.read(c).x * 87u;
    acc += t87.read(c).x * 88u;
    acc += t88.read(c).x * 89u;
    acc += t89.read(c).x * 90u;
    acc += t90.read(c).x * 91u;
    acc += t91.read(c).x * 92u;
    acc += t92.read(c).x * 93u;
    acc += t93.read(c).x * 94u;
    acc += t94.read(c).x * 95u;
    acc += t95.read(c).x * 96u;
    acc += t96.read(c).x * 97u;
    acc += t97.read(c).x * 98u;
    acc += t98.read(c).x * 99u;
    acc += t99.read(c).x * 100u;
    acc += t100.read(c).x * 101u;
    acc += t101.read(c).x * 102u;
    acc += t102.read(c).x * 103u;
    acc += t103.read(c).x * 104u;
    acc += t104.read(c).x * 105u;
    acc += t105.read(c).x * 106u;
    acc += t106.read(c).x * 107u;
    acc += t107.read(c).x * 108u;
    acc += t108.read(c).x * 109u;
    acc += t109.read(c).x * 110u;
    acc += t110.read(c).x * 111u;
    acc += t111.read(c).x * 112u;
    acc += t112.read(c).x * 113u;
    acc += t113.read(c).x * 114u;
    acc += t114.read(c).x * 115u;
    acc += t115.read(c).x * 116u;
    acc += t116.read(c).x * 117u;
    acc += t117.read(c).x * 118u;
    acc += t118.read(c).x * 119u;
    acc += t119.read(c).x * 120u;
    acc += t120.read(c).x * 121u;
    acc += t121.read(c).x * 122u;
    acc += t122.read(c).x * 123u;
    acc += t123.read(c).x * 124u;
    acc += t124.read(c).x * 125u;
    acc += t125.read(c).x * 126u;
    acc += t126.read(c).x * 127u;
    o[0] = acc;
}
