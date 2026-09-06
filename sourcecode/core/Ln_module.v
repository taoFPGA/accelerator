`timescale 1ns / 1ps
// ===========================================================================
// Ln_module.v -- fixed-point natural log, ln(x) for x >= 1   (latency = 2)
//
// Softmax.v uses the identity  softmax_i = exp(x_i - max - ln(sum)); this
// block supplies ln(sum), where `sum` is the accumulated exp total
// (e_sum_U8Q8, always >= 1.0 because Softmax clamps it to >= 256 = 1.0 in
// Q8).
//
// Method: normalize x to [1,2) by finding the position `w` of the leading 1
// (priority encoder, w = 0..7), so x = 2^w * (1 + k) with k in [0,1).
//   ln(x) = w*ln(2) + ln(1+k) ~= (w + k) * (11/16)
// The single constant multiply by 4'b1011 (= 11, i.e. * 11/16 ~= ln(2) plus
// the linear ln(1+k) term folded in) covers both parts at once.
// x_U8Q8 in (unsigned, >= 1.0), y_U3Q10 out (unsigned). Registered at the
// normalize output and the product.
// ===========================================================================
module Ln_module(//latency=2
	input clk,
    input [15:0]    x_U8Q8,    // sum of exponentials, >= 1.0
    output [12:0]   y_U3Q10    // ln(x)
);

reg [2:0] w; 

reg [14:0] k_1_0Q15;



always @(*) begin
    if (x_U8Q8[15]==1'b1)begin 
        w = 7;
        k_1_0Q15 = x_U8Q8[14:0];
    end
    else if (x_U8Q8[14]==1'b1)begin
        w = 6;
        k_1_0Q15 = {x_U8Q8[13:0],1'b0};
    end
    else if (x_U8Q8[13]==1'b1)begin
        w = 5;
        k_1_0Q15 = {x_U8Q8[12:0],2'b00};
    end
    else if (x_U8Q8[12]==1'b1)begin
        w = 4;
        k_1_0Q15 = {x_U8Q8[11:0],3'b000};
    end
    else if (x_U8Q8[11]==1'b1)begin
        w = 3;
        k_1_0Q15 = {x_U8Q8[10:0],4'b0000};
    end
    else if (x_U8Q8[10]==1'b1)begin
        w = 2;
        k_1_0Q15 = {x_U8Q8[9:0],5'b00000};
    end
    else if (x_U8Q8[9]==1'b1)begin
        w = 1;
        k_1_0Q15 = {x_U8Q8[8:0],6'b000000};
    end
    else begin
        w = 0;
        k_1_0Q15 = {x_U8Q8[7:0],7'b0000000};
    end
end


wire [17:0] k_1_w_3Q15 = {w,k_1_0Q15};
reg  [17:0] k_1_w_3Q15_reg1;
always@(posedge clk)begin
	k_1_w_3Q15_reg1<=k_1_w_3Q15;
end
wire [21:0] P_3Q19;
reg  [21:0] P_3Q19_reg1;
assign P_3Q19 = k_1_w_3Q15_reg1 * 4'b1011; 
always@(posedge clk)begin
	P_3Q19_reg1<=P_3Q19;
end
assign y_U3Q10 = P_3Q19_reg1[21:9];
endmodule
